import base64
import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT      = 60
_DEFAULT_MAX_RETRIES  = 3
_DEFAULT_RETRY_DELAY  = 2


class SharePointConfigError(Exception):
    """Missing or invalid .env settings."""

class SharePointAPIError(Exception):
    """HTTP or network failure on list/download."""
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code

class SharePointUpdateError(Exception):
    """SkillSet update failure (non-fatal)."""
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code

class SharePointUploadError(Exception):
    """New resume upload failure."""
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code


# ── Config readers — all from .env ───────────────────────────────────────────

def _get_base_url() -> str:
    url = getattr(settings, "SHAREPOINT_API_BASE_URL", "").strip()
    if not url:
        raise SharePointConfigError(
            "SHAREPOINT_API_BASE_URL is missing from your .env file."
        )
    return url


def _get_update_url() -> str:
    url = getattr(settings, "SHAREPOINT_UPDATE_API_URL", "").strip()
    if url:
        return url
    url = getattr(settings, "SHAREPOINT_API_BASE_URL", "").strip()
    if not url:
        raise SharePointConfigError(
            "SHAREPOINT_UPDATE_API_URL is missing from your .env file."
        )
    logger.warning(
        "[SharePoint] SHAREPOINT_UPDATE_API_URL not set — "
        "falling back to SHAREPOINT_API_BASE_URL."
    )
    return url


def _get_upload_url() -> str:
    """
    URL used to create a brand-new resume file in SharePoint.
    Falls back to SHAREPOINT_UPDATE_API_URL (same payload schema), then
    to SHAREPOINT_API_BASE_URL, since some setups use a single flow for
    everything.
    """
    url = getattr(settings, "SHAREPOINT_UPLOAD_API_URL", "").strip()
    if url:
        return url

    url = getattr(settings, "SHAREPOINT_UPDATE_API_URL", "").strip()
    if url:
        logger.warning(
            "[SharePoint] SHAREPOINT_UPLOAD_API_URL not set — "
            "falling back to SHAREPOINT_UPDATE_API_URL."
        )
        return url

    url = getattr(settings, "SHAREPOINT_API_BASE_URL", "").strip()
    if not url:
        raise SharePointConfigError(
            "Neither SHAREPOINT_UPLOAD_API_URL, SHAREPOINT_UPDATE_API_URL, "
            "nor SHAREPOINT_API_BASE_URL is set in your .env file."
        )
    logger.warning(
        "[SharePoint] SHAREPOINT_UPLOAD_API_URL not set — "
        "falling back to SHAREPOINT_API_BASE_URL."
    )
    return url


def _timeout() -> int:
    return int(getattr(settings, "SHAREPOINT_TIMEOUT", _DEFAULT_TIMEOUT))


def _max_retries() -> int:
    return int(getattr(settings, "SHAREPOINT_UPDATE_MAX_RETRIES", _DEFAULT_MAX_RETRIES))


def _retry_delay() -> float:
    return float(getattr(settings, "SHAREPOINT_UPDATE_RETRY_DELAY", _DEFAULT_RETRY_DELAY))


# ── Base64 decode helper ──────────────────────────────────────────────────────

def _decode_if_base64(content: bytes, file_name: str) -> bytes:
    """
    SharePoint Power Automate flows often return file content as a
    base64-encoded string — either:
      - Plain base64:       b'JVBERi0xLjM...'
      - JSON-quoted base64: b'"JVBERi0xLjM..."'

    This function detects all cases and returns raw file bytes.

    Cases handled:
      1. Already raw PDF:   starts with b'%PDF-'  → return as-is
      2. Already raw DOCX:  starts with b'PK'     → return as-is
      3. JSON-quoted b64:   strip quotes, decode   → return decoded
      4. Plain b64:         decode directly        → return decoded
    """
    ext = ("." + file_name.rsplit(".", 1)[-1].lower()) if "." in file_name else ""

    # Case 1 & 2 — already raw bytes
    if ext == ".pdf" and content.startswith(b"%PDF-"):
        logger.debug("[SharePoint] '%s' is raw PDF ✅", file_name)
        return content
    if ext == ".docx" and content.startswith(b"PK"):
        logger.debug("[SharePoint] '%s' is raw DOCX ✅", file_name)
        return content

    # Strip JSON string quotes if present: b'"abc..."' → b'abc...'
    stripped = content.strip()
    if stripped.startswith(b'"') and stripped.endswith(b'"'):
        stripped = stripped[1:-1]
        logger.debug("[SharePoint] '%s' — stripped JSON quotes", file_name)

    # Try base64 decode
    try:
        decoded = base64.b64decode(stripped)

        if ext == ".pdf" and decoded.startswith(b"%PDF-"):
            logger.info(
                "[SharePoint] '%s' was base64-encoded → decoded %d bytes ✅",
                file_name, len(decoded)
            )
            return decoded

        if ext == ".docx" and decoded.startswith(b"PK"):
            logger.info(
                "[SharePoint] '%s' was base64-encoded → decoded %d bytes ✅",
                file_name, len(decoded)
            )
            return decoded

        logger.warning(
            "[SharePoint] '%s' base64-decoded but still not valid "
            "(first bytes after decode: %r)",
            file_name, decoded[:20]
        )

    except Exception as exc:
        logger.warning(
            "[SharePoint] '%s' base64 decode failed: %s",
            file_name, exc
        )

    # Return original — _validate_content will raise a clear error
    return content


def _validate_content(content: bytes, file_name: str) -> None:
    """Raise SharePointAPIError if content doesn't match expected file type."""
    ext = ("." + file_name.rsplit(".", 1)[-1].lower()) if "." in file_name else ""

    if ext == ".pdf" and not content.startswith(b"%PDF-"):
        raise SharePointAPIError(
            f"'{file_name}' is not a valid PDF after download/decode "
            f"(first bytes: {content[:20]!r}). "
            "SharePoint may be returning base64 in an unexpected format."
        )
    if ext == ".docx" and not content.startswith(b"PK"):
        raise SharePointAPIError(
            f"'{file_name}' is not a valid DOCX after download/decode "
            f"(first bytes: {content[:20]!r})."
        )


# ── API 1: List all files ─────────────────────────────────────────────────────

def list_all_items() -> list[str]:
    """POST fileName=All → flat JSON array of all names at root."""
    url = _get_base_url()
    logger.info("[SharePoint] Listing root files...")

    try:
        resp = requests.post(
            url,
            headers={"Accept": "application/json"},
            params={"fileName": "All"},
            timeout=_timeout(),
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info("[SharePoint] Root contains %d items", len(data))
        return data

    except requests.exceptions.Timeout:
        raise SharePointAPIError("SharePoint list API timed out.")
    except requests.exceptions.ConnectionError as exc:
        raise SharePointAPIError(f"Cannot connect to SharePoint API: {exc}")
    except requests.exceptions.HTTPError as exc:
        raise SharePointAPIError(
            f"SharePoint list API HTTP error: {exc}",
            status_code=resp.status_code,
        )
    except ValueError:
        raise SharePointAPIError("SharePoint list API returned non-JSON.")


# ── API 2: Download a single file ─────────────────────────────────────────────

def download_file(file_name: str) -> bytes:
    """
    POST fileName=<name> → raw PDF/DOCX bytes.

    SharePoint Power Automate flows return file content in different formats:
      - Raw binary  (Content-Type: application/pdf / application/octet-stream)
      - Base64 string inside JSON  (Content-Type: application/json)
      - JSON-quoted base64 string

    This function handles ALL cases and always returns raw validated bytes.
    """
    url = _get_base_url()
    logger.info("[SharePoint] Downloading: %s", file_name)

    try:
        resp = requests.post(
            url,
            headers={"Accept": "application/octet-stream"},
            params={"fileName": file_name},
            timeout=_timeout(),
        )
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        raise SharePointAPIError(f"Timed out downloading '{file_name}'.")
    except requests.exceptions.ConnectionError as exc:
        raise SharePointAPIError(f"Cannot connect to SharePoint API: {exc}")
    except requests.exceptions.HTTPError as exc:
        raise SharePointAPIError(
            f"SharePoint download HTTP error for '{file_name}': {exc}",
            status_code=resp.status_code,
        )

    content = resp.content
    content_type = resp.headers.get("Content-Type", "")

    logger.debug(
        "[SharePoint] '%s' — Content-Type: %s, raw size: %d bytes, first bytes: %r",
        file_name, content_type, len(content), content[:30]
    )

    # Auto-detect and decode base64 if needed
    content = _decode_if_base64(content, file_name)

    # Validate final content
    _validate_content(content, file_name)

    logger.info(
        "[SharePoint] Downloaded '%s' — %d bytes ✅",
        file_name, len(content)
    )
    return content


# ── API 3: Update SkillSet column in SharePoint ───────────────────────────────

def update_skillset(file_name: str, file_bytes: bytes, skill_set: str) -> bool:
   
    url         = _get_update_url()
    max_retries = _max_retries()
    delay       = _retry_delay()

    encoded_content = base64.b64encode(file_bytes).decode("utf-8")

    payload = {
        "fileName":    file_name,
        "fileContent": encoded_content,
        "SkillSet":    skill_set,
    }

    logger.info(
        "[SharePoint/Update] Pushing SkillSet for '%s' → '%s…'",
        file_name, skill_set[:80]
    )

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                url,
                headers={
                    "Content-Type": "application/json",
                    "Accept":       "application/json",
                },
                json=payload,
                timeout=_timeout(),
            )
            resp.raise_for_status()
            logger.info(
                "[SharePoint/Update] ✅ SkillSet updated for '%s' (attempt %d/%d)",
                file_name, attempt, max_retries
            )
            return True

        except requests.exceptions.Timeout:
            logger.warning(
                "[SharePoint/Update] Timeout — attempt %d/%d for '%s'",
                attempt, max_retries, file_name
            )
        except requests.exceptions.ConnectionError as exc:
            logger.warning(
                "[SharePoint/Update] Connection error — attempt %d/%d for '%s': %s",
                attempt, max_retries, file_name, exc
            )
        except requests.exceptions.HTTPError as exc:
            sc = exc.response.status_code if exc.response else None
            logger.warning(
                "[SharePoint/Update] HTTP %s — attempt %d/%d for '%s': %s",
                sc, attempt, max_retries, file_name, exc
            )
            if sc and 400 <= sc < 500:
                logger.error(
                    "[SharePoint/Update] ❌ Client error %s for '%s'. "
                    "Check SHAREPOINT_UPDATE_API_URL in .env",
                    sc, file_name
                )
                return False
        except Exception as exc:
            logger.warning(
                "[SharePoint/Update] Unexpected error — attempt %d/%d for '%s': %s",
                attempt, max_retries, file_name, exc
            )

        if attempt < max_retries:
            wait = delay * (2 ** (attempt - 1))
            logger.info(
                "[SharePoint/Update] Retrying in %.0fs… (%d/%d)",
                wait, attempt, max_retries
            )
            time.sleep(wait)

    logger.error(
        "[SharePoint/Update] ❌ All %d attempts failed for '%s'.",
        max_retries, file_name
    )
    return False


# ── API 4: Upload a brand-new resume file (NEW) ───────────────────────────────

def upload_resume(file_name: str, file_bytes: bytes) -> bool:
    """
    POST a newly-uploaded (frontend) resume to SharePoint so it can later
    be picked up by the normal SharePoint screening pipeline
    (list_all_items → download_file → score → update_skillset).

    URL read from SHAREPOINT_UPLOAD_API_URL in .env (falls back to
    SHAREPOINT_UPDATE_API_URL, then SHAREPOINT_API_BASE_URL — see
    _get_upload_url docstring above for why).

    Request body (same schema as update_skillset):
    {
        "fileName":    "John_Resume_20260616_143022.pdf",
        "fileContent": "<base64 encoded bytes>",
        "SkillSet":    ""   ← empty at upload time; filled in later by
                              the screening run via update_skillset()
    }

    Raises SharePointConfigError / SharePointAPIError / SharePointUploadError
    on failure — uploading is NOT optional like update_skillset, so the
    caller (the view) needs to know if it failed.

    Retries with the same exponential backoff as update_skillset
    (2s → 4s → 8s) since transient network/Flow errors are common.
    """
    url         = _get_upload_url()
    max_retries = _max_retries()
    delay       = _retry_delay()

    encoded_content = base64.b64encode(file_bytes).decode("utf-8")

    payload = {
        "fileName":    file_name,
        "fileContent": encoded_content,
        "SkillSet":    "",
    }

    logger.info(
        "[SharePoint/Upload] Uploading new resume '%s' (%d bytes)",
        file_name, len(file_bytes)
    )

    last_exc = None

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                url,
                headers={
                    "Content-Type": "application/json",
                    "Accept":       "application/json",
                },
                json=payload,
                timeout=_timeout(),
            )
            resp.raise_for_status()
            logger.info(
                "[SharePoint/Upload] ✅ Uploaded '%s' (attempt %d/%d)",
                file_name, attempt, max_retries
            )
            return True

        except requests.exceptions.Timeout as exc:
            last_exc = exc
            logger.warning(
                "[SharePoint/Upload] Timeout — attempt %d/%d for '%s'",
                attempt, max_retries, file_name
            )
        except requests.exceptions.ConnectionError as exc:
            last_exc = exc
            logger.warning(
                "[SharePoint/Upload] Connection error — attempt %d/%d for '%s': %s",
                attempt, max_retries, file_name, exc
            )
        except requests.exceptions.HTTPError as exc:
            last_exc = exc
            sc = exc.response.status_code if exc.response else None
            logger.warning(
                "[SharePoint/Upload] HTTP %s — attempt %d/%d for '%s': %s",
                sc, attempt, max_retries, file_name, exc
            )
            if sc and 400 <= sc < 500:
                # Client errors (bad payload, auth, etc.) won't fix
                # themselves on retry — fail immediately.
                raise SharePointUploadError(
                    f"SharePoint rejected upload of '{file_name}' "
                    f"(HTTP {sc}): {exc}",
                    status_code=sc,
                )
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "[SharePoint/Upload] Unexpected error — attempt %d/%d for '%s': %s",
                attempt, max_retries, file_name, exc
            )

        if attempt < max_retries:
            wait = delay * (2 ** (attempt - 1))
            logger.info(
                "[SharePoint/Upload] Retrying in %.0fs… (%d/%d)",
                wait, attempt, max_retries
            )
            time.sleep(wait)

    logger.error(
        "[SharePoint/Upload] ❌ All %d attempts failed for '%s': %s",
        max_retries, file_name, last_exc
    )
    raise SharePointUploadError(
        f"Failed to upload '{file_name}' to SharePoint after "
        f"{max_retries} attempts: {last_exc}"
    )


# ── Main entry: get resume files only ────────────────────────────────────────

def get_resume_files() -> list[str]:
    """
    1. Fetch full root list
    2. Deduplicate
    3. Keep only .pdf and .docx
    4. Skip everything else
    """
    all_items = list_all_items()

    supported = {".pdf", ".docx"}
    seen      = set()
    resumes   = []
    skipped   = []

    for item in all_items:
        if not isinstance(item, str) or not item.strip():
            continue
        item = item.strip()

        if item in seen:
            logger.debug("[SharePoint] Duplicate skipped: %s", item)
            continue
        seen.add(item)

        if "." not in item:
            skipped.append(item)
            continue

        ext = "." + item.rsplit(".", 1)[-1].lower()
        if ext in supported:
            resumes.append(item)
        else:
            skipped.append(item)

    if skipped:
        logger.info(
            "[SharePoint] Skipped %d non-resume item(s): %s",
            len(skipped), skipped
        )
    logger.info(
        "[SharePoint] %d resume file(s) ready: %s",
        len(resumes), resumes
    )
    return resumes