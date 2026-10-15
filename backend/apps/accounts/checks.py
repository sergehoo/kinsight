"""Garde-fou d'exploitation : un compte de direction sans périmètre ne voit rien.

DG Groupe et CODIR ont tous les DOMAINES, mais leur PÉRIMÈTRE suit la case
« groupe » et les filiales cochées. Sans l'une ni l'autre, leurs écrans RH sont
entièrement N/D — « connecté mais rien ne remonte » (incident du 2026-10-15).
On ne l'élargit pas en silence (un DG peut être volontairement limité à une
filiale) : on le SIGNALE, à chaque `manage.py check`, au démarrage et dans l'admin.
"""

from __future__ import annotations

from django.core import checks
from django.db import DatabaseError

ROLES_A_ACCES_TOTAL = ("DG_GROUP", "CODIR")


def comptes_sans_perimetre():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    candidats = (User.objects.filter(is_active=True, role__in=ROLES_A_ACCES_TOTAL, is_group_scope=False)
                 .prefetch_related("subsidiaries"))
    return [u for u in candidats if not u.scope().is_group and not u.scope().subsidiaries]


@checks.register(checks.Tags.security)
def verifier_les_perimetres(app_configs=None, **kwargs):
    try:
        orphelins = comptes_sans_perimetre()
    except DatabaseError:
        return []  # base pas encore migrée : rien à vérifier
    return [
        checks.Warning(
            f"Le compte « {u.username} » ({u.role}) a tous les domaines mais AUCUN périmètre : "
            "ses écrans afficheront N/D partout.",
            hint="Admin → Utilisateurs → Gouvernance K-Insight : cocher « périmètre groupe » ou ses filiales.",
            obj=u.username, id="accounts.W001",
        )
        for u in orphelins
    ]
