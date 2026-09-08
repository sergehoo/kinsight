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


class SubsidiariesView(APIView):
    """GET /api/v1/auth/subsidiaries/ — les filiales que CET utilisateur peut filtrer.

    Pourquoi cet endpoint existe alors que `/auth/me/` porte déjà le périmètre :
    `Scope.group()` a un ensemble de filiales VIDE (`perimeter.py:32`). Un DG Groupe
    reçoit donc `scope: "GROUP"` et `subsidiaries: []`, ce qui ne permet pas de
    peupler une liste de choix. Et `/auth/me/` ne rend que des codes, pas les noms
    affichés à l'écran.

    Le frontend codait la liste en dur — quatre entrées, sans référentiel
    (`store/filters.ts`). Un filtre bâti sur une constante ne peut ni suivre
    l'organisation réelle, ni respecter un périmètre : il proposait les mêmes
    filiales à tout le monde, y compris à un directeur qui n'a droit qu'à la sienne.

    La borne est ici, côté serveur, et non dans l'appel : proposer une filiale
    qu'on n'a pas le droit de voir est déjà une fuite, même si la requête suivante
    la refuse.
    """

    def get(self, request):
        from apps.organizations.models import Subsidiary

        scope = request.user.scope()
        filiales = Subsidiary.objects.filter(is_active=True)
        if not scope.is_group:
            # `Scope.allows()` est la règle de référence ; on l'applique en base
            # plutôt qu'en mémoire pour ne pas charger le Groupe entier au passage.
            filiales = filiales.filter(code__in=sorted(scope.subsidiaries))
        return Response({
            "scope": "GROUP" if scope.is_group else sorted(scope.subsidiaries),
            "results": [
                {"code": f.code, "name": f.name, "country": f.country, "currency": f.currency}
                for f in filiales
            ],
        })
