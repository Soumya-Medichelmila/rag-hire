"""
recruitment/urls.py  — complete, with CandidateDeleteView added
"""
from django.urls import path
from .views import (
    ScreenUploadView,
    BulkUploadView,
    RAGScreeningView,
    ScreeningResultsView,
    AllScreeningJobsView,
    ShortlistCandidateView,
    ShortlistByJobView,
    AllShortlistJobsView,
    ScheduleInterviewView,
    ResendInterviewEmailView,
    InterviewsByJobView,
    AllInterviewJobsView,
    AllInterviewsView,
    UpdateShortlistStatusView,
    CandidateListView,
    CandidateCountView,
    CandidateDeleteView,       # ← new
    ResumePreviewView,
)

urlpatterns = [
    # ── Upload
    path('upload/',           ScreenUploadView.as_view(),   name='resume-upload'),
    path('bulk-upload/',      BulkUploadView.as_view(),     name='bulk-upload'),

    # ── Screening
    path('screen/',           RAGScreeningView.as_view(),   name='rag-screen'),
    path('results/',          AllScreeningJobsView.as_view(), name='screening-jobs'),
    path('results/<int:job_id>/', ScreeningResultsView.as_view(), name='screening-results'),

    # ── Shortlist
    path('shortlist/<int:sr_id>/',   ShortlistCandidateView.as_view(),  name='shortlist-candidate'),
    path('shortlist/job/<int:job_id>/', ShortlistByJobView.as_view(),   name='shortlist-by-job'),
    path('shortlist/jobs/',          AllShortlistJobsView.as_view(),    name='shortlist-jobs'),
    path('shortlist/status/<int:pk>/', UpdateShortlistStatusView.as_view(), name='shortlist-status'),

    # ── Interviews
    path('interview/<int:shortlist_id>/',  ScheduleInterviewView.as_view(),  name='schedule-interview'),
    path('interview/resend/',              ResendInterviewEmailView.as_view(), name='resend-email'),
    path('interviews/',                    AllInterviewsView.as_view(),       name='all-interviews'),
    path('interviews/job/<int:job_id>/',   InterviewsByJobView.as_view(),     name='interviews-by-job'),
    path('interviews/jobs/',               AllInterviewJobsView.as_view(),    name='interview-jobs'),

    # ── Candidates
    path('candidates/',              CandidateListView.as_view(),   name='candidate-list'),
    path('candidates/<int:pk>/',     CandidateDeleteView.as_view(), name='candidate-delete'),  # ← new
    path('candidate-count/',         CandidateCountView.as_view(),  name='candidate-count'),

    # ── Resume preview (SharePoint)
    path('resume-preview/',          ResumePreviewView.as_view(),   name='resume-preview'),
]

# from django.urls import path
# from .views import (
#     # ── RAG Screening ──────────────────────────────────────────────────────────
#     ScreenUploadView,
#     BulkUploadView,
#     RAGScreeningView,
#     ScreeningResultsView,
#     AllScreeningJobsView,

#     # ── Shortlist ──────────────────────────────────────────────────────────────
#     ShortlistCandidateView,
#     ShortlistByJobView,
#     AllShortlistJobsView,
#     UpdateShortlistStatusView,

#     # ── Interview ──────────────────────────────────────────────────────────────
#     ScheduleInterviewView,
#     ResendInterviewEmailView,
#     InterviewsByJobView,
#     AllInterviewJobsView,
#     AllInterviewsView,

#     # ── Candidate + Preview ────────────────────────────────────────────────────
#     CandidateListView,
#     CandidateCountView,
#     ResumePreviewView,
# )

# urlpatterns = [

#     # ── UPLOAD ─────────────────────────────────────────────────────────────────
#     path('upload/',                 ScreenUploadView.as_view(),        name='screen-upload'),
#     path('bulk-upload/',            BulkUploadView.as_view(),          name='bulk-upload'),

#     # ── RAG SCREENING ──────────────────────────────────────────────────────────
#     path('rag-screen/',             RAGScreeningView.as_view(),        name='rag-screen'),

#     # ── RESUME PREVIEW ─────────────────────────────────────────────────────────
#     path('resume-preview/',         ResumePreviewView.as_view(),       name='resume-preview'),

#     # ── SCREENING RESULTS ──────────────────────────────────────────────────────
#     path('results/',                AllScreeningJobsView.as_view(),    name='all-screening-jobs'),
#     path('results/<int:job_id>/',   ScreeningResultsView.as_view(),    name='screening-results'),

#     # ── SHORTLIST ──────────────────────────────────────────────────────────────
#     path('shortlist/jobs/',              AllShortlistJobsView.as_view(),      name='all-shortlist-jobs'),
#     path('shortlist/all/',               AllShortlistJobsView.as_view(),      name='all-shortlist-jobs-alias'),
#     path('shortlist/job/<int:job_id>/',  ShortlistByJobView.as_view(),        name='shortlist-by-job'),
#     path('shortlist/<int:sr_id>/',       ShortlistCandidateView.as_view(),    name='shortlist-candidate'),
#     path('shortlist/<int:pk>/status/',   UpdateShortlistStatusView.as_view(), name='update-shortlist-status'),

#     # ── INTERVIEW ──────────────────────────────────────────────────────────────
#     path('interview/all/',                         AllInterviewsView.as_view(),        name='all-interviews'),
#     path('interview/jobs/',                        AllInterviewJobsView.as_view(),     name='all-interview-jobs'),
#     path('interview/resend-email/',                ResendInterviewEmailView.as_view(), name='resend-interview-email'),
#     path('interview/schedule/<int:shortlist_id>/', ScheduleInterviewView.as_view(),   name='schedule-interview'),
#     path('interview/job/<int:job_id>/',            InterviewsByJobView.as_view(),      name='interviews-by-job'),

#     # ── CANDIDATE POOL ──────────────────────────────────────────────────────────
#     path('candidates/',      CandidateListView.as_view(),  name='candidate-list'),
#     path('candidate-count/', CandidateCountView.as_view(), name='candidate-count'),
# ]