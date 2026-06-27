"""API comptes : profil de l'utilisateur connecté (rôle, périmètre, permissions, atterrissage)."""

from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import APIView

from . import rbac


class MeView(APIView):
    """GET /api/v1/auth/me/ — identité + droits de l'utilisateur authentifié (source de vérité RBAC)."""

    def get(self, request):
        user = request.user
        scope = user.scope()
        return Response(
            {
                "username": user.username,
                "full_name": user.get_full_name() or user.username,
                "role": user.role,
                "is_superuser": user.is_superuser,
                "is_group_scope": user.is_group_scope,
                "subsidiaries": sorted(user.subsidiaries.values_list("code", flat=True)),
                "scope": "GROUP" if scope.is_group else sorted(scope.subsidiaries),
                "can_see_nominative": user.can_see_nominative,
                "permissions": rbac.permissions_for(user),
                "landing": rbac.landing_for(user),
            }
        )
