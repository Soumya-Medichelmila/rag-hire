# 🎯 RAG-Hire — AI-Powered Internal Recruitment System

A full-stack internal HR and recruitment management system that uses a **RAG (Retrieval-Augmented Generation) pipeline** with **ChromaDB vector search** and **Groq LLM (Llama 3.1)** for intelligent resume screening — with zero PII sent to the LLM.

---

## 🔄 Full Recruitment Flow

```
Employee raises vacancy request
        ↓
HR / Admin reviews & approves → Job Opening created
        ↓
Recruitment team uploads resumes (PDF / DOCX)
        ↓
  ┌─────────────────────────────────────────────┐
  │         TEXT EXTRACTION PIPELINE            │
  │                                             │
  │  DOCX → python-docx                        │
  │  Text PDF → pdfplumber                     │
  │  Scanned PDF → pdf2image + pytesseract OCR │
  └─────────────────────────────────────────────┘
        ↓
  ┌─────────────────────────────────────────────┐
  │         PII EXTRACTION (spaCy / Regex)      │
  │                                             │
  │  Name, Email, Phone extracted               │
  │  Saved to Candidate DB (PostgreSQL)         │
  │  PII is NEVER sent to the LLM              │
  └─────────────────────────────────────────────┘
        ↓
  ┌─────────────────────────────────────────────┐
  │      SECTION-BASED CHUNKING                 │
  │                                             │
  │  Resume split into semantic sections:       │
  │  Education / Experience / Skills /          │
  │  Projects / Certifications / Summary        │
  └─────────────────────────────────────────────┘
        ↓
  ┌─────────────────────────────────────────────┐
  │      EMBEDDING → CHROMADB                   │
  │                                             │
  │  Each chunk embedded via                   │
  │  Sentence Transformers (all-MiniLM-L6-v2)  │
  │  Stored in ChromaDB vector store           │
  └─────────────────────────────────────────────┘
        ↓
  When HR runs AI Screening for a Job:
        ↓
  ┌─────────────────────────────────────────────┐
  │      JD VECTOR SEARCH (RAG Retrieval)       │
  │                                             │
  │  Job Description → embedded to vector       │
  │  Semantic similarity search in ChromaDB     │
  │  Top matching resume chunks retrieved       │
  └─────────────────────────────────────────────┘
        ↓
  ┌─────────────────────────────────────────────┐
  │      LLM SCORING (Groq — Llama 3.1)         │
  │                                             │
  │  Only relevant chunks sent (NO PII)         │
  │  LLM scores each candidate 0–100           │
  │  Returns match score + detailed reason      │
  └─────────────────────────────────────────────┘
        ↓
  Candidates above threshold (default: 80%)
  → Auto-shortlisted
        ↓
HR views results → Shortlisted candidates on Kanban board
        ↓
JRHR / HR drags candidates through pipeline:
  Shortlisted → Interview Scheduled → Selected / Rejected
        ↓
Interview Scheduled → Candidate receives email (Mailtrap)
        ↓
Selected → Employee added to system
Rejected → Candidate receives rejection email
```

---

## 📌 Features

### 👥 Employee & Vacancy Management
- Employees raise internal vacancy requests
- HR / Admin reviews and approves requests
- Approved requests automatically create job openings

### 🤖 RAG-Powered Resume Screening
- Resumes chunked into **section-based chunks** (Education, Experience, Skills, Projects etc.)
- Each chunk embedded using **Sentence Transformers (`all-MiniLM-L6-v2`)**
- Chunks stored in **ChromaDB** persistent vector store
- At screening time, the **Job Description is vectorized** and semantically matched against stored chunks
- Only the **top matching chunks** (no PII) are sent to **Groq LLM (Llama 3.1)** for scoring
- Candidates scoring above the **threshold (default 80%)** are **auto-shortlisted**

### 🔒 Privacy-First Design
- PII (name, email, phone) is extracted separately and stored in the database
- **PII is never sent to the LLM** — only anonymized resume content chunks
- PII extraction uses spaCy NER + Regex patterns

### 📄 Smart Resume Parsing Pipeline

| File Type | Parsing Method |
|-----------|---------------|
| DOCX | python-docx |
| Text-based PDF | pdfplumber |
| Scanned / Image PDF | pdf2image + pytesseract OCR |

### 📊 Auto-Shortlisting
- Candidates above the score threshold are automatically shortlisted
- HR can also manually review all scores and adjust shortlisting
- Match score + LLM reasoning shown for every candidate

### 🗂️ Kanban Interview Pipeline (JRHR / HR)
Drag-and-drop Kanban board to manage candidate stages:
- **Shortlisted → Interview Scheduled → Selected / Rejected**
- Moving to Interview Scheduled → sends interview invitation email
- Moving to Rejected → sends rejection email
- Moving to Selected → triggers employee onboarding

### 🔐 Role-Based Access Control

| Role | Access |
|------|--------|
| Admin | Full access to everything |
| HR | Approve vacancies, view results, shortlist, Kanban |
| JRHR | Kanban pipeline, manage interview stages |
| Recruitment | Upload resumes, run AI screening, resume pool |
| Employee | Raise vacancy requests only |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django, Django REST Framework |
| Frontend | HTML, CSS, JavaScript |
| AI / LLM | Groq API (Llama 3.1) |
| Vector Store | ChromaDB (persistent) |
| Embeddings | Sentence Transformers (`all-MiniLM-L6-v2`) |
| PII Extraction | spaCy NER + Regex |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Auth | JWT (SimpleJWT) |
| Email | Mailtrap (sandbox SMTP) |
| PDF Extraction | pdfplumber (text PDFs) |
| OCR (Scanned PDFs) | pytesseract + pdf2image + Poppler |
| DOCX Parsing | python-docx |
| Environment | python-dotenv |

---

## 📁 Project Structure

```
rag-hire/
├── employee-frontend/               # HTML/CSS/JS frontend
│   ├── css/
│   │   └── style.css
│   ├── index.html                   # Login page
│   ├── admin-dashboard.html
│   ├── employee-dashboard.html
│   ├── hr-screening-results.html
│   ├── jrhr-dashboard.html
│   ├── jrhr-kanban.html             # Kanban drag-and-drop board
│   ├── recruitment-screen.html      # Upload & AI screening
│   ├── recruitment-resumes.html     # Resume pool
│   └── ...
│
└── career_portal/                   # Django REST API backend
    ├── accounts/                    # Auth, users, roles
    ├── employee_management/         # Django project settings
    │   ├── settings.py
    │   ├── urls.py
    │   └── wsgi.py
    ├── jobs/                        # Job openings & vacancy requests
    ├── masters/                     # Departments & master data
    ├── recruitment/                 # Core RAG pipeline
    │   ├── migrations/
    │   ├── models.py                # ScreeningResult, Shortlist, Interview
    │   ├── candidate_model.py       # Candidate + PII storage
    │   ├── views.py                 # API views
    │   ├── serializers.py
    │   ├── urls.py
    │   ├── rag_pipeline.py          # RAG: chunk → embed → ChromaDB → LLM
    │   └── sharepoint_client.py     # SharePoint integration
    ├── media/
    │   └── resumes/                 # Uploaded resume files
    ├── chroma_db/                   # ChromaDB persistent vector store
    ├── .gitignore
    ├── manage.py
    └── requirements.txt
```

---

## ⚙️ Setup & Installation

### 1. Clone the repository
```bash
git clone https://github.com/Soumya-Medichelmila/rag-hire.git
cd rag-hire
```

### 2. Set up virtual environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r career_portal/requirements.txt
```

### 4. Install Tesseract OCR (for scanned PDFs)

**Windows:**
- Download from https://github.com/UB-Mannheim/tesseract/wiki
- Install and add to PATH, or set in settings:
```python
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

**Ubuntu/Debian:**
```bash
sudo apt install tesseract-ocr
```

**Mac:**
```bash
brew install tesseract
```

### 5. Install Poppler (for pdf2image / scanned PDFs)

**Windows:**
- Download from https://github.com/oschwartz10612/poppler-windows/releases
- Extract and add `bin/` to PATH

**Ubuntu/Debian:**
```bash
sudo apt install poppler-utils
```

**Mac:**
```bash
brew install poppler
```

### 6. Create `.env` file inside `career_portal/`
```env
GROQ_API_KEY=your_groq_api_key_here
SECRET_KEY=your_django_secret_key_here
DEBUG=True
DATABASE_URL=your_database_url_here

# Mailtrap email config
EMAIL_HOST=sandbox.smtp.mailtrap.io
EMAIL_PORT=2525
EMAIL_HOST_USER=your_mailtrap_user
EMAIL_HOST_PASSWORD=your_mailtrap_password
EMAIL_USE_TLS=True

# ChromaDB
CHROMA_DB_PATH=./chroma_db
CHROMA_COLLECTION_NAME=resumes

# Tesseract & Poppler paths (Windows only)
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
POPPLER_PATH=C:\poppler\Library\bin
```

### 7. Run migrations
```bash
cd career_portal
python manage.py migrate
```

### 8. Create superuser
```bash
python manage.py createsuperuser
```

### 9. Start the server
```bash
python manage.py runserver
```

### 10. Open the frontend
Open `employee-frontend/index.html` in your browser or serve via Live Server.

---

## 🔑 Get Free API Keys

### Groq API (LLM Scoring)
- Go to https://console.groq.com
- Sign up for a free account
- Generate an API key → paste in `.env`

### Mailtrap (Email Testing)
- Go to https://mailtrap.io
- Sign up free → Email Testing → Inboxes → SMTP Settings
- Copy credentials → paste in `.env`

---

## 🤖 RAG Pipeline — Technical Details

### Chunking Strategy
Resumes are split into **section-based chunks** by detecting common section headings:
- Summary / Objective
- Education
- Work Experience
- Skills
- Projects
- Certifications
- Achievements

Each section becomes an independent chunk, preserving semantic meaning.

### Embedding
Each chunk is embedded using **`sentence-transformers/all-MiniLM-L6-v2`** — a lightweight, fast model optimized for semantic similarity.

### Vector Store
Embeddings are stored in **ChromaDB** (persistent local vector store). Each chunk is stored with metadata: `candidate_id`, `source_filename`, `section`.

### Retrieval
When HR runs screening for a job:
1. The **Job Description** is embedded using the same model
2. ChromaDB performs **cosine similarity search** across all stored chunks
3. Top-K most relevant chunks are retrieved (across all candidates)

### LLM Scoring
Retrieved chunks (anonymized, no PII) are sent to **Groq LLM (Llama 3.1)** with the JD. The LLM returns:
- **Match score** (0–100)
- **Reason** explaining the score

### Auto-Shortlisting
Candidates scoring **≥ threshold (default: 80%)** are automatically added to the shortlist and appear on the Kanban board.

### Scoring Guide

| Score | Match Level |
|-------|-------------|
| 80–100 | Excellent match — auto-shortlisted |
| 60–79 | Good match |
| 40–59 | Partial match |
| 0–39 | Poor match |

---

## 📡 API Endpoints

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/accounts/login/` | Login & get JWT token |
| POST | `/api/accounts/token/refresh/` | Refresh JWT token |

### Vacancy & Jobs
| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| POST | `/api/jobs/vacancy-request/` | Employee | Raise vacancy request |
| GET | `/api/jobs/vacancy-requests/` | HR / Admin | View all requests |
| GET | `/api/jobs/openings/` | All | List job openings |

### Recruitment & RAG Screening
| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| POST | `/api/recruitment/upload/` | Recruitment | Upload single resume |
| POST | `/api/recruitment/bulk-upload/` | Recruitment | Bulk upload resumes |
| GET | `/api/recruitment/candidates/` | Recruitment | Resume pool |
| DELETE | `/api/recruitment/candidates/<id>/` | Recruitment | Delete candidate |
| POST | `/api/recruitment/screen/` | Recruitment | Run RAG screening |
| GET | `/api/recruitment/results/` | HR / Admin | All screened jobs |
| GET | `/api/recruitment/results/<job_id>/` | HR / Admin | Results for a job |
| GET | `/api/recruitment/resume-preview/` | HR / Recruitment | Preview resume file |

### Shortlisting & Kanban
| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| GET | `/api/recruitment/shortlist/job/<job_id>/` | HR / JRHR | Shortlisted candidates |
| PATCH | `/api/recruitment/shortlist/status/<id>/` | HR / JRHR | Update Kanban status |
| POST | `/api/recruitment/interview/<shortlist_id>/` | HR / JRHR | Schedule interview |
| POST | `/api/recruitment/interview/resend/` | HR / JRHR | Resend email |

---

## 📦 Key Dependencies

```
django
djangorestframework
djangorestframework-simplejwt
groq
chromadb
sentence-transformers
spacy
pdfplumber
pytesseract
pdf2image
python-docx
python-dotenv
Pillow
```

Full list in `career_portal/requirements.txt`

---

## 📧 Email Notifications (via Mailtrap)

All emails go to Mailtrap sandbox — no real emails sent during development.

| Trigger | Email Sent To |
|---------|--------------|
| Interview Scheduled | Candidate — interview invitation with date/time/mode |
| Candidate Rejected | Candidate — rejection notification |
| Candidate Selected | Internal HR — onboarding trigger |

---

## 🚫 .gitignore

The following are never committed:
```
venv/
__pycache__/
*.pyc
.env
db.sqlite3
media/
chroma_db/
staticfiles/
.vscode/
```

---

## 👩‍💻 Author

**Soumya Medichelmila**
Built with Django REST Framework · Groq LLM (Llama 3.1) · ChromaDB · Sentence Transformers · pdfplumber · pytesseract OCR · Mailtrap

---

## 📄 License

MIT License — free to use and modify.
