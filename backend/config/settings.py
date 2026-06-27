"""Réglages Django de k-insight (backend Governance).

Deux bases logiques (ADR-0004) :
- `default` : base applicative (utilisateurs, rôles, périmètres, audit). SQLite en dev,
  PostgreSQL (schéma `app`) en prod.
- L'EDW (mart en lecture seule) n'est PAS un alias ORM : il est accédé via une connexion
  psycopg dédiée dans `apps.governance.gateway` (jamais de modèles Django sur le mart).
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Domaine pur importable (src/k_insight).
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-key-change-me")
INTEGRATIONS_SECRET_KEY = os.environ.get("INTEGRATIONS_SECRET_KEY", SECRET_KEY)
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Tiers
    "rest_framework",
    "corsheaders",
    # Apps k-insight
    "apps.accounts",
    "apps.organizations",
    "apps.governance",
    "apps.audit",
    "apps.integrations",
    "apps.ai_copilot",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Base applicative. SQLite par défaut (dev/tests) ; PostgreSQL si APP_DB_* est fourni.
if os.environ.get("APP_DB_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["APP_DB_NAME"],
            "USER": os.environ["APP_DB_USER"],
            "PASSWORD": os.environ["APP_DB_PASSWORD"],
            "HOST": os.environ["APP_DB_HOST"],
            "PORT": os.environ.get("APP_DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Connexion EDW (mart, lecture seule) — utilisée par le gateway, pas par l'ORM.
EDW_DSN = {
    "host": os.environ.get("EDW_DB_HOST", "localhost"),
    "port": os.environ.get("EDW_DB_PORT", "5432"),
    "dbname": os.environ.get("EDW_DB_NAME", "k_insight_edw"),
    "user": os.environ.get("EDW_DB_USER", "k_insight_app"),
    "password": os.environ.get("EDW_DB_PASSWORD", ""),
}

# --- Celery (orchestration : syncs, alertes, automatisations Copilot) ---
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", os.environ.get("REDIS_URL", "redis://localhost:6379/1"))
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "")
CELERY_BEAT_SCHEDULE = {
    "ai-copilot-run-due-automations": {
        "task": "ai_copilot.run_due_automations",
        "schedule": float(os.environ.get("AI_AUTOMATIONS_TICK_SECONDS", "300")),  # vérifie les automatisations dues
    },
}

# --- K-Insight AI Copilot : moteurs LLM (multi-provider, fallback) ---
# DeepSeek = principal, Claude = fallback. Sans clé, le router bascule sur le repli
# déterministe ancré (catalogue/mart) — aucune donnée inventée.
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
AI_MODEL_SYNTHESIS = os.environ.get("AI_MODEL_SYNTHESIS", "claude-opus-4-8")

AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

# Derrière un reverse proxy TLS (Traefik/Nginx en prod, ex. déploiement Dokploy).
# Tout est piloté par variables d'env et désactivé par défaut → dev/tests inchangés.
CSRF_TRUSTED_ORIGINS = [
    origin for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if origin
]
# Le proxy termine le TLS et transmet X-Forwarded-Proto=https : Django doit le reconnaître.
if os.environ.get("SECURE_SSL_PROXY", "0") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Cookies de session/CSRF en HTTPS uniquement (à activer en prod).
if os.environ.get("DJANGO_SECURE_COOKIES", "0") == "1":
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# JWT (simplejwt). Durée de vie d'accès allongée en dev pour le confort ;
# à resserrer en prod (15 min + refresh).
SIMPLE_JWT = {"ACCESS_TOKEN_LIFETIME": timedelta(hours=12)}

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
