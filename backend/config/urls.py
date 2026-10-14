"""Routage racine. API versionnée sous /api/v1/."""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts.jwt_views import VueRenouvellement


def healthz(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("manage/app/back/", admin.site.urls),
    # Auth JWT (brief : JWT)
    path("api/v1/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    # Vue maison : celle de simplejwt rend un 500 quand le compte porté par le
    # jeton n'existe plus. Voir apps/accounts/jwt_views.py.
    path("api/v1/auth/token/refresh/", VueRenouvellement.as_view(), name="token_refresh"),
    path("api/v1/auth/", include("apps.accounts.urls")),
    # Modules
    path("api/v1/governance/", include("apps.governance.urls")),
    path("api/v1/integrations/", include("apps.integrations.urls")),
    path("api/v1/ai/", include("apps.ai_copilot.urls")),
]
