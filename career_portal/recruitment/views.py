import logging
import os
import re
import json
import tempfile
import requests
from datetime import datetime as _dt

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Count

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.generics import DestroyAPIView

from .models import ScreeningResult, Shortlist, InterviewSchedule
from .candidate_model import Candidate
from .serializers import (
    ScreeningResultSerializer,
    ShortlistSerializer,
    InterviewScheduleSerializer,
)
from .rag_pipeline import process_resume_upload, run_rag_screening
from accounts.models import Employee
from jobs.models import JobOpening

logger = logging.getLogger(__name__)


# ── Shared text extraction helpers ───────────────────────────────────────────

def extract_email_from_text(text):
    if not text:
        return None
    match = re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
    return match.group(0) if match else None


def extract_text_from_resume(file_path):
    text = ""
    ext  = os.path.splitext(file_path)[1].lower()
    try:
        if ext == ".pdf":
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text += t + "\n"
            if not text.strip():
                text = extract_text_with_ocr(file_path)
        elif ext in (".docx", ".doc"):
            import docx
            doc  = docx.Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        logger.error("[extract_text] %s", e)
    return text


def extract_text_with_ocr(file_path):
    text = ""
    try:
        import pytesseract
        from pdf2image import convert_from_path
        pytesseract.pytesseract.tesseract_cmd = getattr(
            settings, "TESSERACT_CMD",
            r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        )
        pages = convert_from_path(
            file_path, dpi=300,
            poppler_path=getattr(
                settings, "POPPLER_PATH",
                r"C:\poppler\poppler-26.02.0\Library\bin"
            ),
        )
        for page_image in pages:
            page_text = pytesseract.image_to_string(page_image, lang='eng')
            if page_text:
                text += page_text + "\n"
    except Exception as e:
        logger.error("[OCR error] %s", e)
    return text


# ── Helper: clean newlines from any string ────────────────────────────────────
def clean_name(value):
    """
    Strip embedded newlines and collapse whitespace.
    PII extractor can embed \\n in candidate names (e.g. 'Arjun Mehta\\nSenior')
    which breaks JSON serialization and onclick attributes.
    """
    if not value:
        return value
    return ' '.join(str(value).split())


# ── UPLOAD & SCREEN (RAG version) ────────────────────────────────────────────
class ScreenUploadView(APIView):
    """
    POST /api/recruitment/upload/
    Single resume upload → extract → PII → Candidate DB → Chunk → Embed → ChromaDB
    Save file to disk. NO SharePoint yet.
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]
    ALLOWED_EXT        = {'.pdf', '.docx'}

    def post(self, request):
        file_obj = request.FILES.get('resume')
        if not file_obj:
            return Response(
                {'error': 'No file provided. Send it under the "resume" field.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        original_name = file_obj.name
        raw_name, ext = os.path.splitext(original_name)
        ext           = ext.lower()

        if ext not in self.ALLOWED_EXT:
            return Response(
                {'error': f'Unsupported file type "{ext}". Only .pdf and .docx allowed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        timestamp   = _dt.now().strftime('%Y%m%d_%H%M%S')
        safe_name   = re.sub(r'[^A-Za-z0-9_\-]+', '_', raw_name).strip('_') or 'resume'
        sp_filename = f"{safe_name}_{timestamp}{ext}"

        file_bytes = file_obj.read()
        if not file_bytes:
            return Response(
                {'error': 'Uploaded file is empty.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            text = extract_text_from_resume(tmp_path)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        if not text.strip():
            return Response(
                {'error': 'Could not extract text from resume.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            candidate = process_resume_upload(
                text                = text,
                source_filename     = original_name,
                sharepoint_filename = sp_filename,
                file_bytes          = file_bytes,
            )
        except Exception as exc:
            logger.exception("[ScreenUploadView] Pipeline error: %s", exc)
            return Response(
                {'error': f'Processing error: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.info(
            "[ScreenUploadView] ✅ %s → candidate_id=%d",
            original_name, candidate.id
        )

        return Response({
            'message'            : 'Resume uploaded and processed successfully.',
            'candidate_id'       : candidate.id,
            'candidate_name'     : clean_name(candidate.full_name),
            'email'              : candidate.email,
            'phone'              : candidate.phone,
            'source_filename'    : candidate.source_filename,
            'sharepoint_filename': sp_filename,
            'is_embedded'        : candidate.is_embedded,
        }, status=status.HTTP_201_CREATED)


# ── BULK UPLOAD ───────────────────────────────────────────────────────────────
class BulkUploadView(APIView):
    """
    POST /api/recruitment/bulk-upload/
    Multiple resumes → each through full RAG pipeline.
    Save files to disk. NO SharePoint yet.
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]
    ALLOWED_EXT        = {'.pdf', '.docx'}

    def post(self, request):
        files = request.FILES.getlist('resumes')
        if not files:
            return Response(
                {'error': 'No files provided. Send files under the "resumes" field.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = []
        success = 0
        failed  = 0

        for file_obj in files:
            original_name = file_obj.name
            raw_name, ext = os.path.splitext(original_name)
            ext           = ext.lower()

            if ext not in self.ALLOWED_EXT:
                results.append({
                    'filename': original_name,
                    'status'  : 'failed',
                    'error'   : f'Unsupported file type "{ext}"',
                })
                failed += 1
                continue

            timestamp   = _dt.now().strftime('%Y%m%d_%H%M%S')
            safe_name   = re.sub(r'[^A-Za-z0-9_\-]+', '_', raw_name).strip('_') or 'resume'
            sp_filename = f"{safe_name}_{timestamp}{ext}"

            file_bytes = file_obj.read()
            if not file_bytes:
                results.append({
                    'filename': original_name,
                    'status'  : 'failed',
                    'error'   : 'File is empty',
                })
                failed += 1
                continue

            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                    tmp.write(file_bytes)
                    tmp_path = tmp.name
                text = extract_text_from_resume(tmp_path)
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

            if not text.strip():
                results.append({
                    'filename': original_name,
                    'status'  : 'failed',
                    'error'   : 'Could not extract text',
                })
                failed += 1
                continue

            try:
                candidate = process_resume_upload(
                    text                = text,
                    source_filename     = original_name,
                    sharepoint_filename = sp_filename,
                    file_bytes          = file_bytes,
                )
                results.append({
                    'filename'      : original_name,
                    'status'        : 'success',
                    'candidate_id'  : candidate.id,
                    'candidate_name': clean_name(candidate.full_name),
                    'email'         : candidate.email,
                    'is_embedded'   : candidate.is_embedded,
                })
                success += 1
                logger.info(
                    "[BulkUpload] ✅ %s → candidate_id=%d",
                    original_name, candidate.id
                )
            except Exception as exc:
                logger.error("[BulkUpload] Failed %s: %s", original_name, exc)
                results.append({
                    'filename': original_name,
                    'status'  : 'failed',
                    'error'   : str(exc),
                })
                failed += 1

        return Response({
            'total'  : len(files),
            'success': success,
            'failed' : failed,
            'results': results,
        }, status=status.HTTP_201_CREATED)


# ── RAG SCREENING ─────────────────────────────────────────────────────────────
class RAGScreeningView(APIView):
    """
    POST /api/recruitment/rag-screen/
    Full RAG screening pipeline.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        job_id          = request.data.get('job_id')
        top_k           = int(request.data.get('top_k', 20))
        score_threshold = int(request.data.get('score_threshold', 80))

        if not job_id:
            return Response(
                {'error': 'job_id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            job = JobOpening.objects.get(pk=job_id)
        except JobOpening.DoesNotExist:
            return Response(
                {'error': 'Job not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            rag_result = run_rag_screening(
                job             = job,
                request_user    = request.user,
                top_k           = top_k,
                score_threshold = score_threshold,
            )
        except Exception as exc:
            logger.exception("[RAGScreeningView] Error: %s", exc)
            return Response(
                {'error': f'Screening error: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        from .rag_pipeline import _post_to_sharepoint

        enriched = []

        for r in rag_result.get('results', []):

            # ── Save ScreeningResult to DB ─────────────────────────────────────
            sr, created = ScreeningResult.objects.get_or_create(
                job_opening     = job,
                source_filename = r['source_filename'],
                resume_source   = 'LOCAL',
                defaults        = {
                    'candidate_name' : clean_name(r['candidate_name']),
                    'candidate_email': r.get('candidate_email'),
                    'match_score'    : r['match_score'],
                    'reason'         : r['reason'],
                    'screened_by'    : request.user,
                }
            )
            if not created:
                sr.candidate_name = clean_name(r['candidate_name'])
                sr.match_score    = r['match_score']
                sr.reason         = r['reason']
                sr.save(update_fields=['candidate_name', 'match_score', 'reason'])

            is_shortlisted = False
            sp_posted      = False
            shortlist_id   = None

            # ── Auto-shortlist if above threshold ──────────────────────────────
            if r['match_score'] >= score_threshold:
                shortlist, sl_created = Shortlist.objects.get_or_create(
                    job_opening      = job,
                    screening_result = sr,
                    defaults         = {
                        'shortlisted_by': request.user,
                        'notes'         : (
                            f'Auto-shortlisted — score: {r["match_score"]}% '
                            f'(threshold: {score_threshold}%)'
                        ),
                    }
                )
                is_shortlisted = True
                shortlist_id   = shortlist.id

                # ── POST to SharePoint only for newly shortlisted ──────────────
                if sl_created:
                    try:
                        candidate = Candidate.objects.get(id=r['candidate_id'])
                        if not candidate.is_posted_to_sharepoint:
                            sp_posted = _post_to_sharepoint(
                                candidate = candidate,
                                skills    = r.get('skills', ''),
                            )
                    except Candidate.DoesNotExist:
                        logger.warning(
                            "[RAGScreeningView] Candidate id=%s not found",
                            r['candidate_id']
                        )
                else:
                    try:
                        candidate = Candidate.objects.get(id=r['candidate_id'])
                        sp_posted = candidate.is_posted_to_sharepoint
                    except Candidate.DoesNotExist:
                        pass

            # ── Always get fresh sharepoint_filename from Candidate ────────────
            try:
                fresh_candidate   = Candidate.objects.get(id=r['candidate_id'])
                fresh_sp_filename = fresh_candidate.sharepoint_filename or r.get('sharepoint_filename', '')
            except Candidate.DoesNotExist:
                fresh_sp_filename = r.get('sharepoint_filename', '')

            enriched.append({
                **r,
                'candidate_name'     : clean_name(r['candidate_name']),
                'sharepoint_filename': fresh_sp_filename,
                'screening_result_id': sr.id,
                'is_shortlisted'     : is_shortlisted,
                'shortlist_id'       : shortlist_id,
                'sp_posted'          : sp_posted,
            })

        rag_result['results'] = enriched
        return Response(rag_result, status=status.HTTP_200_OK)


# ── SCREENING RESULTS ─────────────────────────────────────────────────────────

class ScreeningResultsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        results = ScreeningResult.objects.filter(
            job_opening_id=job_id
        ).select_related('job_opening', 'screened_by')

        data = ScreeningResultSerializer(results, many=True).data

        shortlisted_filenames = set(
            Shortlist.objects.filter(
                job_opening_id=job_id
            ).values_list('screening_result__source_filename', flat=True)
        )

        for item in data:
            src = item.get('source_filename', '')

            candidate = Candidate.objects.filter(source_filename=src).first()
            if candidate:
                item['sharepoint_filename']     = candidate.sharepoint_filename or ''
                item['is_posted_to_sharepoint'] = getattr(candidate, 'is_posted_to_sharepoint', False)
            else:
                item['sharepoint_filename']     = ''
                item['is_posted_to_sharepoint'] = False

            item['is_shortlisted'] = src in shortlisted_filenames

            # FIX: clean newlines from candidate_name
            if item.get('candidate_name'):
                item['candidate_name'] = clean_name(item['candidate_name'])

        return Response(data)


class AllScreeningJobsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        jobs = JobOpening.objects.filter(
            screening_results__isnull=False
        ).annotate(
            result_count=Count('screening_results')
        ).distinct().order_by('-result_count')
        return Response([{
            'id'          : j.id,
            'title'       : j.title,
            'department'  : str(getattr(j, 'department', '') or ''),
            'result_count': j.result_count,
        } for j in jobs])


# ── SHORTLIST ─────────────────────────────────────────────────────────────────

class ShortlistCandidateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, sr_id):
        try:
            sr = ScreeningResult.objects.get(pk=sr_id)
        except ScreeningResult.DoesNotExist:
            return Response(
                {'error': 'Screening result not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        if hasattr(sr, 'shortlist'):
            return Response(
                {'error': 'Already shortlisted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        shortlist = Shortlist.objects.create(
            job_opening      = sr.job_opening,
            screening_result = sr,
            shortlisted_by   = request.user,
            notes            = request.data.get('notes', ''),
        )
        return Response({
            'shortlist_id'  : shortlist.id,
            'candidate_name': clean_name(sr.candidate_name),
        }, status=status.HTTP_201_CREATED)

    def patch(self, request, sr_id):
        try:
            sr = ScreeningResult.objects.get(pk=sr_id)
        except ScreeningResult.DoesNotExist:
            return Response(
                {'error': 'Screening result not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        if not hasattr(sr, 'shortlist'):
            return Response(
                {'error': 'Candidate is not shortlisted yet'},
                status=status.HTTP_400_BAD_REQUEST
            )
        shortlist = sr.shortlist
        if 'notes' in request.data:
            shortlist.notes = request.data['notes']
        if 'status' in request.data:
            allowed = ['SHORTLISTED', 'SCHEDULED', 'HIRED', 'REJECTED']
            if request.data['status'] not in allowed:
                return Response(
                    {'error': f'Invalid status. Allowed: {allowed}'},
                    status=400
                )
            shortlist.status = request.data['status']
        shortlist.save()
        return Response({
            'shortlist_id'  : shortlist.id,
            'candidate_name': clean_name(sr.candidate_name),
            'status'        : shortlist.status,
        })

    def delete(self, request, sr_id):
        try:
            sr = ScreeningResult.objects.get(pk=sr_id)
            sr.shortlist.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except (ScreeningResult.DoesNotExist, Shortlist.DoesNotExist):
            return Response(
                {'error': 'Not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class ShortlistByJobView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        shortlists = Shortlist.objects.filter(
            job_opening_id=job_id
        ).select_related(
            'screening_result', 'screening_result__job_opening',
            'shortlisted_by', 'job_opening'
        ).prefetch_related('interviews')

        data = ShortlistSerializer(shortlists, many=True).data

        for item in data:
            sr_filename = item.get('source_filename', '')
            candidate   = Candidate.objects.filter(source_filename=sr_filename).first()

            if candidate:
                item['sharepoint_filename']     = candidate.sharepoint_filename or ''
                item['is_posted_to_sharepoint'] = getattr(candidate, 'is_posted_to_sharepoint', False)
            else:
                item['sharepoint_filename']     = ''
                item['is_posted_to_sharepoint'] = False

            # FIX: clean newlines from all name/text fields —
            # embedded \n in candidate_name breaks JSON serialization
            # causing the entire API response to return empty strings
            item['candidate_name']  = clean_name(item.get('candidate_name', ''))
            item['candidate_email'] = (item.get('candidate_email') or '').strip()
            item['candidate_phone'] = (item.get('candidate_phone') or '').strip()
            item['reason']          = (item.get('reason') or '').strip()

        return Response({'shortlisted': data})


class AllShortlistJobsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        jobs = JobOpening.objects.filter(
            shortlisted_candidates__isnull=False
        ).annotate(
            shortlist_count=Count('shortlisted_candidates')
        ).distinct().order_by('-shortlist_count')
        return Response([{
            'job_id'         : j.id,
            'job_title'      : j.title,
            'department'     : str(getattr(j, 'department', '') or ''),
            'shortlist_count': j.shortlist_count,
        } for j in jobs])


# ── EMAIL HELPERS ─────────────────────────────────────────────────────────────

DEFAULT_CANDIDATE_EMAIL_TEMPLATE = """Dear {candidate_name},

We are pleased to inform you that you have been shortlisted for the position of {job_title} at {company}.

INTERVIEW DETAILS:
━━━━━━━━━━━━━━━━━━━━━━━━
Date        : {interview_date}
Time        : {interview_time}
Mode        : {mode}
Location    : {location}
━━━━━━━━━━━━━━━━━━━━━━━━

Please confirm your availability by replying to this email.

Best regards,
SynergyCom HR Team"""


def fill_template(template, interview, round_name="Round 1"):
    shortlist = interview.shortlist
    sr        = shortlist.screening_result

    location = (
        interview.meeting_link
        if interview.mode == "ONLINE"
        else (interview.venue or "To be communicated")
    )

    raw_date = interview.interview_date
    if isinstance(raw_date, str):
        try:
            raw_date = _dt.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            raw_date = None
    date_str = raw_date.strftime("%d %B %Y") if raw_date else str(interview.interview_date)

    raw_time = interview.interview_time
    if isinstance(raw_time, str):
        try:
            raw_time = _dt.strptime(raw_time[:5], "%H:%M").time()
        except ValueError:
            raw_time = None
    time_str = raw_time.strftime("%I:%M %p") if raw_time else str(interview.interview_time)

    values = {
        "candidate_name": clean_name(sr.candidate_name),
        "job_title"     : shortlist.job_opening.title,
        "interview_date": date_str,
        "interview_time": time_str,
        "mode"          : interview.get_mode_display(),
        "location"      : location,
        "round"         : round_name,
        "company"       : "SynergyCom",
        "date"          : date_str,
        "time"          : time_str,
        "link_or_venue" : location,
    }

    class SafeDict(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    return template.format_map(SafeDict(values))


def send_candidate_email(interview, round_name="Round 1", subject=None, body=None):
    candidate_email = interview.shortlist.screening_result.candidate_email
    if not candidate_email:
        return False, "No candidate email on record"

    if not subject:
        subject = f"Interview Invitation – {interview.shortlist.job_opening.title} ({round_name})"
    if not body:
        body = fill_template(DEFAULT_CANDIDATE_EMAIL_TEMPLATE, interview, round_name)
    else:
        body = fill_template(body, interview, round_name)

    subject = fill_template(subject, interview, round_name)

    try:
        send_mail(
            subject       = subject,
            message       = body,
            from_email    = settings.DEFAULT_FROM_EMAIL,
            recipient_list= [candidate_email],
            fail_silently = False,
        )
        return True, "Email sent"
    except Exception as e:
        return False, str(e)


# ── INTERVIEW ─────────────────────────────────────────────────────────────────

class ScheduleInterviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, shortlist_id):
        try:
            shortlist = Shortlist.objects.get(pk=shortlist_id)
        except Shortlist.DoesNotExist:
            return Response(
                {'error': 'Shortlist entry not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        try:
            interviewer = Employee.objects.get(
                pk=request.data.get('assigned_interviewer')
            )
        except Employee.DoesNotExist:
            return Response(
                {'error': 'Interviewer not found'},
                status=status.HTTP_400_BAD_REQUEST
            )

        interview = InterviewSchedule.objects.create(
            shortlist            = shortlist,
            interview_date       = request.data.get('interview_date'),
            interview_time       = request.data.get('interview_time'),
            mode                 = request.data.get('mode', 'ONLINE'),
            meeting_link         = request.data.get('meeting_link', ''),
            venue                = request.data.get('venue', ''),
            assigned_interviewer = interviewer,
            notes                = request.data.get('notes', ''),
            scheduled_by         = request.user,
        )

        sent, msg = send_candidate_email(
            interview,
            round_name = 'Round 1',
            subject    = request.data.get('email_subject') or None,
            body       = request.data.get('email_body') or None,
        )
        interview.email_sent = sent
        interview.save(update_fields=['email_sent'])

        return Response({
            **InterviewScheduleSerializer(interview).data,
            'emails_sent'  : {'candidate': sent},
            'email_message': msg,
        }, status=status.HTTP_201_CREATED)

class ResendInterviewEmailView(APIView):
    permission_classes = [IsAuthenticated]
 
    def post(self, request):
        shortlist_id = request.data.get('shortlist_id')
        if not shortlist_id:
            return Response(
                {'error': 'shortlist_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            shortlist = Shortlist.objects.get(pk=shortlist_id)
        except Shortlist.DoesNotExist:
            return Response(
                {'error': 'Shortlist entry not found'},
                status=status.HTTP_404_NOT_FOUND
            )
 
        round_name     = request.data.get('round_name', 'Notification')
        custom_subject = request.data.get('email_subject') or None
        custom_body    = request.data.get('email_body') or None
 
        # Try to get the latest interview for template filling
        interview = shortlist.interviews.order_by('-scheduled_at').first()
 
        if interview:
            # ── Normal path: interview exists, use existing helper ─────────────
            success, msg = send_candidate_email(
                interview,
                round_name=round_name,
                subject=custom_subject,
                body=custom_body,
            )
        else:
            # ── No interview yet (rejected/hired directly from Shortlisted) ────
            # Send directly using candidate data from ScreeningResult
            sr              = shortlist.screening_result
            candidate_email = sr.candidate_email
            candidate_name  = clean_name(sr.candidate_name)
            job_title       = shortlist.job_opening.title
 
            if not candidate_email:
                return Response(
                    {'sent': False, 'message': 'No candidate email on record'},
                    status=status.HTTP_400_BAD_REQUEST
                )
 
            subject = custom_subject or f"{round_name} — {job_title}"
            body    = custom_body or (
                f"Dear {candidate_name},\n\n"
                f"This is regarding your application for {job_title} at SynergyCom.\n\n"
                f"Best regards,\nSynergyCom HR Team"
            )
 
            # Replace basic placeholders (no interview data available)
            for template_str in [subject, body]:
                pass  # do replacements below
 
            replacements = {
                '{candidate_name}': candidate_name,
                '{job_title}'     : job_title,
                '{company}'       : 'SynergyCom',
                '{round}'         : round_name,
            }
            for placeholder, value in replacements.items():
                subject = subject.replace(placeholder, value)
                body    = body.replace(placeholder, value)
 
            try:
                send_mail(
                    subject       = subject,
                    message       = body,
                    from_email    = settings.DEFAULT_FROM_EMAIL,
                    recipient_list= [candidate_email],
                    fail_silently = False,
                )
                success, msg = True, "Email sent"
            except Exception as e:
                logger.error("[ResendInterviewEmailView] Direct send failed: %s", e)
                success, msg = False, str(e)
 
        if success:
            return Response({
                'sent'     : True,
                'round'    : round_name,
                'candidate': clean_name(shortlist.screening_result.candidate_name),
                'message'  : f'Email sent for {round_name}',
            })
        return Response(
            {'sent': False, 'message': msg},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
 
class InterviewsByJobView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        interviews = InterviewSchedule.objects.filter(
            shortlist__job_opening_id=job_id
        ).select_related(
            'shortlist__screening_result',
            'shortlist__job_opening',
            'assigned_interviewer',
            'scheduled_by',
        )
        return Response({
            'interviews': InterviewScheduleSerializer(interviews, many=True).data
        })


class AllInterviewJobsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        jobs = JobOpening.objects.filter(
            shortlisted_candidates__interviews__isnull=False
        ).annotate(
            interview_count=Count('shortlisted_candidates__interviews')
        ).distinct()
        return Response([{
            'job_id'         : j.id,
            'job_title'      : j.title,
            'department'     : str(getattr(j, 'department', '') or ''),
            'interview_count': j.interview_count,
        } for j in jobs])


class AllInterviewsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        interviews = InterviewSchedule.objects.all().select_related(
            'shortlist__screening_result',
            'shortlist__job_opening',
            'assigned_interviewer',
            'scheduled_by',
        ).order_by('-scheduled_at')
        return Response(InterviewScheduleSerializer(interviews, many=True).data)


class UpdateShortlistStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            shortlist = Shortlist.objects.get(pk=pk)
        except Shortlist.DoesNotExist:
            return Response(
                {'error': 'Shortlist entry not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        new_status = request.data.get('status')
        allowed    = ['SHORTLISTED', 'SCHEDULED', 'HIRED', 'REJECTED']

        if new_status not in allowed:
            return Response(
                {'error': f'Invalid status. Allowed: {allowed}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shortlist.status = new_status
        shortlist.save(update_fields=['status'])

        messages_map = {
            'SHORTLISTED': 'Candidate returned to Shortlist.',
            'SCHEDULED'  : 'Candidate status updated to Scheduled.',
            'HIRED'      : 'Candidate marked as Selected / Hired.',
            'REJECTED'   : 'Candidate rejected and archived.',
        }
        return Response({
            'status' : new_status,
            'message': messages_map[new_status]
        })


# ── CANDIDATE POOL ────────────────────────────────────────────────────────────

class CandidateListView(APIView):
    """GET /api/recruitment/candidates/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        candidates = Candidate.objects.all().order_by('-created_at')

        shortlisted_filenames = set(
            Shortlist.objects.values_list(
                'screening_result__source_filename', flat=True
            )
        )

        data = []
        for c in candidates:
            data.append({
                'id'                     : c.id,
                'full_name'              : clean_name(c.full_name),
                'email'                  : c.email,
                'phone'                  : c.phone,
                'source_filename'        : c.source_filename,
                'sharepoint_filename'    : c.sharepoint_filename,
                'is_embedded'            : c.is_embedded,
                'is_shortlisted'         : c.source_filename in shortlisted_filenames,
                'is_posted_to_sharepoint': getattr(c, 'is_posted_to_sharepoint', False),
                'created_at'             : c.created_at.isoformat(),
            })
        return Response(data)


class CandidateCountView(APIView):
    """GET /api/recruitment/candidate-count/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Candidate.objects.filter(is_embedded=True).count()
        return Response({'count': count})


# ── RESUME PREVIEW ────────────────────────────────────────────────────────────

class ResumePreviewView(APIView):
    """
    GET /api/recruitment/resume-preview/?filename=<filename>
    Priority order:
      1. Disk  — FileField on Candidate
      2. Disk  — media/resumes/<sharepoint_filename>
      3. Disk  — media/resumes/<source_filename>
      4. SharePoint — using the REAL sharepoint_filename from Candidate record
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        filename = request.query_params.get('filename', '').strip()
        if not filename:
            return Response(
                {'error': 'filename query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.http import HttpResponse

        ext = filename.rsplit('.', 1)[-1].lower()
        content_type = (
            'application/pdf' if ext == 'pdf'
            else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )

        file_bytes = self._read_from_disk(filename)

        if file_bytes:
            logger.info("[ResumePreviewView] Serving from disk: %s", filename)
            response = HttpResponse(file_bytes, content_type=content_type)
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            response['Access-Control-Allow-Origin'] = '*'
            return response

        real_sp_filename = self._resolve_sharepoint_filename(filename)

        logger.info(
            "[ResumePreviewView] Not on disk. SP lookup: requested=%s resolved=%s",
            filename, real_sp_filename
        )

        try:
            from .sharepoint_client import download_file, SharePointAPIError, SharePointConfigError
            file_bytes = download_file(real_sp_filename)
            logger.info("[ResumePreviewView] Serving from SharePoint: %s", real_sp_filename)

            sp_ext = real_sp_filename.rsplit('.', 1)[-1].lower()
            sp_content_type = (
                'application/pdf' if sp_ext == 'pdf'
                else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )

            response = HttpResponse(file_bytes, content_type=sp_content_type)
            response['Content-Disposition'] = f'inline; filename="{real_sp_filename}"'
            response['Access-Control-Allow-Origin'] = '*'
            return response

        except Exception as sp_exc:
            logger.warning(
                "[ResumePreviewView] SharePoint also failed for %s: %s",
                real_sp_filename, sp_exc
            )
            return Response(
                {
                    'error': (
                        f'Resume not found on disk or SharePoint. '
                        f'Looked for: "{real_sp_filename}" on SharePoint. '
                        f'Error: {sp_exc}'
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

    def _resolve_sharepoint_filename(self, filename: str) -> str:
        try:
            candidate = (
                Candidate.objects.filter(sharepoint_filename=filename).first()
                or Candidate.objects.filter(source_filename=filename).first()
            )
            if candidate and candidate.sharepoint_filename:
                return candidate.sharepoint_filename
        except Exception as e:
            logger.debug("[ResumePreviewView] _resolve_sharepoint_filename error: %s", e)
        return filename

    def _read_from_disk(self, filename: str) -> bytes:
        resumes_dir = os.path.join(settings.MEDIA_ROOT, 'resumes')

        try:
            candidate = (
                Candidate.objects.filter(sharepoint_filename=filename).first()
                or Candidate.objects.filter(source_filename=filename).first()
            )

            if candidate:
                if candidate.resume_file:
                    try:
                        with candidate.resume_file.open('rb') as f:
                            data = f.read()
                        if data:
                            return data
                    except Exception as e:
                        logger.debug("[ResumePreviewView] FileField read failed: %s", e)

                if candidate.sharepoint_filename:
                    path = os.path.join(resumes_dir, candidate.sharepoint_filename)
                    if os.path.exists(path):
                        with open(path, 'rb') as f:
                            return f.read()

                if candidate.source_filename:
                    path = os.path.join(resumes_dir, candidate.source_filename)
                    if os.path.exists(path):
                        with open(path, 'rb') as f:
                            return f.read()

        except Exception as e:
            logger.debug("[ResumePreviewView] Candidate lookup error: %s", e)

        path = os.path.join(resumes_dir, filename)
        if os.path.exists(path):
            with open(path, 'rb') as f:
                return f.read()

        return b""


# ── CANDIDATE DELETE ──────────────────────────────────────────────────────────

class CandidateDeleteView(DestroyAPIView):
    queryset           = Candidate.objects.all()
    permission_classes = [IsAuthenticated]

    def destroy(self, request, *args, **kwargs):
        candidate = self.get_object()

        # 1. Delete from ChromaDB
        try:
            import chromadb
            chroma_client = chromadb.PersistentClient(path=str(settings.CHROMA_DB_PATH))
            collection = chroma_client.get_collection(name=settings.CHROMA_COLLECTION_NAME)
            collection.delete(where={"candidate_id": str(candidate.id)})
        except Exception as e:
            logger.warning("[CandidateDelete] ChromaDB delete failed: %s", e)

        # 2. Delete file from disk (try both filenames)
        resumes_dir = os.path.join(settings.MEDIA_ROOT, 'resumes')
        for fname in [candidate.sharepoint_filename, candidate.source_filename]:
            if fname:
                path = os.path.join(resumes_dir, fname)
                if os.path.exists(path):
                    try:
                        os.remove(path)
                        logger.info("[CandidateDelete] Deleted from disk: %s", path)
                    except OSError as e:
                        logger.warning("[CandidateDelete] File remove failed: %s", e)

        candidate.delete()
        return Response(
            {'message': f'Candidate "{clean_name(candidate.full_name)}" deleted successfully.'},
            status=status.HTTP_204_NO_CONTENT
        )