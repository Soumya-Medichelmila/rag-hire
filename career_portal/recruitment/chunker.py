import re
from typing import List, Dict


SECTION_HEADINGS: Dict[str, str] = {
    # Summary / Objective
    "summary"                   : "summary",
    "professional summary"      : "summary",
    "career summary"            : "summary",
    "objective"                 : "summary",
    "career objective"          : "summary",
    "profile"                   : "summary",
    "about me"                  : "summary",

    # Skills
    "skills"                    : "skills",
    "technical skills"          : "skills",
    "core competencies"         : "skills",
    "competencies"              : "skills",
    "key skills"                : "skills",
    "technologies"              : "skills",
    "tech stack"                : "skills",
    "tools"                     : "skills",
    "tools & technologies"      : "skills",
    "skills & technologies"     : "skills",
    "technical expertise"       : "skills",

    # Experience
    "experience"                : "experience",
    "work experience"           : "experience",
    "professional experience"   : "experience",
    "employment history"        : "experience",
    "work history"              : "experience",
    "career history"            : "experience",
    "internship"                : "experience",
    "internships"               : "experience",

    # Education
    "education"                 : "education",
    "educational background"    : "education",
    "academic background"       : "education",
    "qualifications"            : "education",
    "academic qualifications"   : "education",

    # Projects
    "projects"                  : "projects",
    "personal projects"         : "projects",
    "academic projects"         : "projects",
    "project experience"        : "projects",
    "key projects"              : "projects",
    "notable projects"          : "projects",

    # Certifications
    "certifications"            : "certifications",
    "certification"             : "certifications",
    "licenses"                  : "certifications",
    "licenses & certifications" : "certifications",
    "achievements"              : "certifications",
    "awards"                    : "certifications",
    "awards & achievements"     : "certifications",
}


# ── Heading Detection ─────────────────────────────────────────────────────────

def _detect_section(line: str) -> str | None:
  
    cleaned = line.strip().rstrip(":").strip()
    if not cleaned or len(cleaned) > 60:
        return None

    lower = cleaned.lower()

    # Known heading match
    if lower in SECTION_HEADINGS:
        return SECTION_HEADINGS[lower]

    # ALL CAPS short line — likely an unknown section heading
    if cleaned.isupper() and 2 <= len(cleaned.split()) <= 6:
        return "other"

    return None


# ── Main Chunker ──────────────────────────────────────────────────────────────

def chunk_resume(
    text: str,
    candidate_id: int,
    source_filename: str,
) -> List[Dict]:
    
    lines = text.splitlines()

    # ── Pass 1: identify heading positions ───────────────────────────────────
    sections = []   # list of (line_index, section_name)
    for i, line in enumerate(lines):
        section = _detect_section(line)
        if section:
            sections.append((i, section))

    # ── If no headings found — treat entire resume as one chunk ──────────────
    if not sections:
        clean = text.strip()
        if clean:
            return [{
                "text"            : clean,
                "section"         : "full_resume",
                "candidate_id"    : candidate_id,
                "source_filename" : source_filename,
                "chunk_index"     : 0,
            }]
        return []

    # ── Pass 2: slice text between headings ───────────────────────────────────
    chunks = []
    chunk_index = 0

    # Text before first heading → treat as summary if substantial
    pre_text = "\n".join(lines[:sections[0][0]]).strip()
    if pre_text and len(pre_text) > 30:
        chunks.append({
            "text"            : pre_text,
            "section"         : "summary",
            "candidate_id"    : candidate_id,
            "source_filename" : source_filename,
            "chunk_index"     : chunk_index,
        })
        chunk_index += 1

    # Text between headings
    for idx, (line_i, section_name) in enumerate(sections):

        if idx + 1 < len(sections):
            end_line = sections[idx + 1][0]
        else:
            end_line = len(lines)

        section_lines = lines[line_i + 1 : end_line] 
        section_text  = "\n".join(section_lines).strip()

        # Skip empty sections
        if not section_text or len(section_text) < 10:
            continue

        chunks.append({
            "text"            : section_text,
            "section"         : section_name,
            "candidate_id"    : candidate_id,
            "source_filename" : source_filename,
            "chunk_index"     : chunk_index,
        })
        chunk_index += 1

    return chunks