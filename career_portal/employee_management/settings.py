from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-_df0vvhvn3q+#83%*ox88&&gtmy+7!k9g8&)41zcr!dvw6zczu'

DEBUG = True

ALLOWED_HOSTS = []

AUTH_USER_MODEL = 'accounts.Employee'

from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

AUTHENTICATION_BACKENDS = [
    'accounts.backends.EmailBackend',
]

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.Argon2PasswordHasher',
]

INSTALLED_APPS = [
     'corsheaders',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'drf_yasg',
     'recruitment',
    'accounts',
    'masters',
    'jobs',
]

SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header'
        }
    }
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

MIDDLEWARE = [
     'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'employee_management.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'employee_management.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

          
import  os      
from dotenv import load_dotenv
load_dotenv()

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')

import os
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'

CORS_ALLOW_ALL_ORIGINS = True







import os
from dotenv import load_dotenv

load_dotenv()

EMAIL_BACKEND = os.getenv('EMAIL_BACKEND')
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'False') == 'True'
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL')









import os
from dotenv import load_dotenv
 
load_dotenv()  # already called in your original — skip duplicate if present
 
# Base URL of your SharePoint REST API wrapper
# e.g. "https://your-sharepoint-api.example.com/api"
SHAREPOINT_API_BASE_URL = os.environ.get("SHAREPOINT_API_BASE_URL", "")
 
# Optional Bearer token / API key for SharePoint API authentication
SHAREPOINT_API_KEY = os.environ.get("SHAREPOINT_API_KEY", "")
 
# The specific folder inside SharePoint to process.
# All other folders are ignored automatically.
SHAREPOINT_TARGET_FOLDER = os.environ.get("SHAREPOINT_TARGET_FOLDER", "Resumes")
 


# Ask your manager for this URL — it may be the same or a different flow
SHAREPOINT_UPDATE_API_URL = os.environ.get("SHAREPOINT_UPDATE_API_URL", "")
 
# HTTP timeout in seconds for all SharePoint API calls
SHAREPOINT_TIMEOUT = int(os.environ.get("SHAREPOINT_TIMEOUT", "60"))
 
# Retry settings for SkillSet update (non-fatal operation)
SHAREPOINT_UPDATE_MAX_RETRIES = int(os.environ.get("SHAREPOINT_UPDATE_MAX_RETRIES", "3"))
SHAREPOINT_UPDATE_RETRY_DELAY = float(os.environ.get("SHAREPOINT_UPDATE_RETRY_DELAY", "2"))
 
# ════════════════════════════════════════════════════════════════════════════
# OCR PATHS  ← UPDATE if your paths differ (already in your original settings)
# ════════════════════════════════════════════════════════════════════════════
 
# Path to Tesseract executable (used for scanned PDF fallback)
TESSERACT_CMD = os.environ.get(
    "TESSERACT_CMD",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
)
 
# Path to Poppler bin directory (used by pdf2image)
POPPLER_PATH = os.environ.get(
    "POPPLER_PATH",
    r"C:\poppler\poppler-26.02.0\Library\bin",
)


# ════════════════════════════════════════════════════════════════════════════
# CHROMA DB — Vector Database for RAG Resume Screening
# ════════════════════════════════════════════════════════════════════════════
CHROMA_DB_PATH = os.path.join(BASE_DIR, "chroma_db")
CHROMA_COLLECTION_NAME = "resume_chunks"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

import logging.handlers

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '[{asctime}] [{levelname}] [{name}] {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'detailed',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'recruitment.log'),
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'detailed',
        },
    },
    'loggers': {
        'recruitment': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'console': {
    'class': 'logging.StreamHandler',
    'formatter': 'detailed',
    'stream': 'ext://sys.stdout',
},
}
