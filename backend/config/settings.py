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

from celery.schedules import crontab

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
    # EN PREMIER, impérativement : il neutralise les en-têtes de proxy venant d'un
    # appelant inconnu, et `SecurityMiddleware` comme la protection CSRF lisent
    # `request.is_secure()`, qui dépend de `X-Forwarded-Proto`.
    "apps.audit.middleware.TrustedProxyMiddleware",
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
# Cache partagé. Sans lui, Django retombe sur un cache EN MÉMOIRE PAR PROCESSUS :
# chaque worker gunicorn gardait son propre uid Odoo et s'authentifiait de son
# côté, et le verrou « une seule authentification à la fois » ne valait que dans
# un processus. Redis est déjà en production (`REDIS_URL`) pour Celery.
#
# Délais d'une seconde : une panne Redis ne doit coûter qu'une seconde, jamais
# bloquer une requête — le code qui s'en sert (`odoo_session`) retombe alors sur
# son cache de processus. La base 0 est libre : Celery occupe la 1.
_REDIS_CACHE = os.environ.get("REDIS_URL", "")
CACHES = {
    "default": (
        {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _REDIS_CACHE,
            "KEY_PREFIX": "kinsight",
            "OPTIONS": {"socket_connect_timeout": 1, "socket_timeout": 1},
        }
        if _REDIS_CACHE
        else {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    )
}

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", os.environ.get("REDIS_URL", "redis://localhost:6379/1"))
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "")
# Le « jour » d'un instantané est celui de K-Insight (timezone.localdate) : les
# tâches planifiées doivent tourner dans le même fuseau, sinon « la veille » de
# Celery et celle de Django ne sont pas la même journée.
CELERY_TIMEZONE = "UTC"  # = TIME_ZONE, déclaré plus bas ; Abidjan est en UTC+0
CELERY_BEAT_SCHEDULE = {
    # Historique RH (ADR-0009). Idempotent : rejouer une exécution met ses lignes
    # à jour sans en ajouter.
    "historique-presence-veille": {
        "task": "historique.presence_veille",
        "schedule": crontab(hour=1, minute=15),
    },
    "historique-stocks-shield": {
        "task": "historique.stocks_shield",
        "schedule": crontab(minute=5),
    },
    "historique-odoo-quotidien": {
        "task": "historique.odoo_quotidien",
        "schedule": crontab(hour=2, minute=0),
    },
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

# --- Kaydan Shield (lecture RH) ---
# Repli d'environnement : la configuration primaire reste le connecteur de la
# DataSource 'kaydan-shield' (secrets chiffrés en base, jamais en clair ici).
SHIELD_BASE_URL = os.environ.get("SHIELD_BASE_URL", "")
SHIELD_API_TOKEN = os.environ.get("SHIELD_API_TOKEN", "")
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
# Le proxy termine le TLS et transmet X-Forwarded-Proto=https : Django doit le
# reconnaître — mais seulement lorsque l'en-tête vient VRAIMENT du proxy. Le
# backend partageant un réseau Docker avec d'autres projets, tout conteneur pourrait
# sinon écrire cet en-tête et décider de ce que `request.is_secure()` renvoie.
# `TrustedProxyMiddleware` retire l'en-tête si le pair n'est pas un proxy reconnu :
# le réglage ci-dessous ne s'applique donc qu'au trafic proxy légitime.
if os.environ.get("SECURE_SSL_PROXY", "0") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Qui a le droit de dire d'où vient une requête. Vide par défaut : on ne fait
# confiance à personne, et l'audit retient alors le pair de la connexion — une
# valeur peut-être peu informative, mais que l'appelant ne choisit pas.
# Sur Dokploy, il s'agit du conteneur Traefik ; son adresse change à chaque
# déploiement, d'où la résolution par NOM plutôt qu'une IP figée.
TRUSTED_PROXY_HOSTS = [
    h for h in os.environ.get("TRUSTED_PROXY_HOSTS", "").split(",") if h.strip()
]
TRUSTED_PROXY_CIDRS = [
    c for c in os.environ.get("TRUSTED_PROXY_CIDRS", "").split(",") if c.strip()
]
# Cookies de session/CSRF en HTTPS uniquement (à activer en prod).
if os.environ.get("DJANGO_SECURE_COOKIES", "0") == "1":
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# JWT (simplejwt).
#
# Jusqu'ici : un accès de 12 h, un renouvellement d'un jour (le défaut), et un
# front qui n'appelait JAMAIS /auth/token/refresh/. Conséquence vécue en
# production : au bout de douze heures, le premier appel prenait un 401 et
# l'utilisateur retombait sur l'écran de connexion. « Il faut à chaque fois
# s'authentifier » ne décrivait pas une panne, mais ce réglage.
#
# Désormais l'accès est court — il est renouvelé en silence, donc sa longueur
# n'achète plus de confort, seulement de l'exposition : un jeton volé reste
# utilisable jusqu'à son terme et rien ne permet de le révoquer. Le jeton de
# renouvellement, lui, est long ET tournant : chaque renouvellement en rend un
# neuf, si bien qu'un poste utilisé au moins une fois par semaine ne redemande
# jamais le mot de passe.
#
# BLACKLIST_AFTER_ROTATION reste à False, ce qui est un ARBITRAGE et non un
# oubli. L'activer tuerait l'ancien jeton à l'instant de la rotation ; mais si
# la réponse se perd en route — réseau coupé juste après l'écriture — le
# navigateur garde un jeton désormais mort et l'utilisateur est déconnecté sans
# recours. C'est précisément le symptôme qu'on corrige ici. Le prix de ce choix :
# un jeton de renouvellement dérobé reste valide jusqu'à son expiration. Le jour
# où la révocation immédiate devient nécessaire, il faudra installer
# `rest_framework_simplejwt.token_blacklist`, migrer, et purger
# périodiquement (`manage.py flushexpiredtokens`).
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
}

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
