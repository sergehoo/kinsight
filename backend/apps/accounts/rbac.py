"""RBAC autoritative : rôle utilisateur → permissions de domaines + page d'atterrissage.

Le backend est la SOURCE DE VÉRITÉ des droits (le frontend n'affiche que ce que ces
permissions autorisent ; l'accès aux DONNÉES reste filtré par `User.scope()` + les
permissions DRF, quoi que fasse le client). Les chaînes de permission correspondent à
celles attendues par le frontend (`lib/permissions.ts`).
"""

from __future__ import annotations

# Permissions par domaine (miroir frontend DOMAIN_PERMISSION).
P_OVERVIEW = "view_group_overview"
P_IMMO = "view_real_estate"
P_HR = "view_hr"
P_FINANCE = "view_finance"
P_OPS = "view_operations"
P_COMMERCIAL = "view_commercial"
P_RISK = "view_risk"
P_AI = "view_ai"
P_REPORTS = "view_reports"
P_ALL = "view_all_dashboards"      # DG / CODIR : tous les domaines
P_SUPERADMIN = "SUPER_ADMIN"       # accès total (admin)

# Routes d'atterrissage (chemins frontend).
L_OVERVIEW = "/dashboard/overview-groupe"
L_FINANCE = "/dashboard/finance"
L_HR = "/dashboard/capital-humain"
L_OPS = "/dashboard/operations"
L_IMMO = "/dashboard/immobilier"
L_INTEGRATIONS = "/admin/integrations"

# Périmètre par rôle (cf. brief : RH→Capital Humain ; DAF→Finance+Rapports+Groupe ;
# Dir métier→Immo+Ops+Commercial ; DG/CODIR/SUPER_ADMIN→tout).
_BY_ROLE = {
    "ADMIN_CA": ([P_SUPERADMIN], L_OVERVIEW),
    "DG_GROUP": ([P_ALL], L_OVERVIEW),
    "CODIR": ([P_ALL], L_OVERVIEW),
    "DAF": ([P_OVERVIEW, P_FINANCE, P_REPORTS], L_FINANCE),
    "DRH": ([P_HR], L_HR),
    "DIR_OPS": ([P_OVERVIEW, P_OPS, P_IMMO, P_COMMERCIAL], L_OPS),
    "RESP_METIER": ([P_OVERVIEW, P_IMMO, P_OPS, P_COMMERCIAL, P_REPORTS], L_OVERVIEW),
    "ADMIN_INTEGRATION": ([P_OVERVIEW], L_INTEGRATIONS),
    "READER": ([P_OVERVIEW, P_REPORTS], L_OVERVIEW),
}


def permissions_for(user) -> list[str]:
    if getattr(user, "is_superuser", False):
        return [P_SUPERADMIN]
    perms, _landing = _BY_ROLE.get(getattr(user, "role", ""), ([P_OVERVIEW], L_OVERVIEW))
    return list(perms)


# Domaine (clé frontend) → permission requise pour accéder à SES données (endpoints par domaine).
DOMAIN_PERMISSION = {
    "overview": P_OVERVIEW,
    "groupe": P_OVERVIEW,
    "immobilier": P_IMMO,
    "capital-humain": P_HR,
    "hr": P_HR,
    "finance": P_FINANCE,
    "operations": P_OPS,
    "commercial-clients": P_COMMERCIAL,
    "risques-conformite": P_RISK,
    "ia": P_AI,
    "reports": P_REPORTS,
}


def can_access_domain(user, domain: str) -> bool:
    """Frontière de sécurité : l'utilisateur a-t-il le droit d'accéder aux données de ce domaine ?

    Indépendante du frontend (qui ne fait que MASQUER la navigation). Superuser / ADMIN_CA /
    DG / CODIR (accès total) → True. Domaine inconnu → refus par défaut.
    """
    if getattr(user, "is_superuser", False):
        return True
    perms = permissions_for(user)
    if P_SUPERADMIN in perms or P_ALL in perms:
        return True
    needed = DOMAIN_PERMISSION.get(domain)
    return needed is not None and needed in perms


def landing_for(user) -> str:
    if getattr(user, "is_superuser", False):
        return L_OVERVIEW
    _perms, landing = _BY_ROLE.get(getattr(user, "role", ""), ([P_OVERVIEW], L_OVERVIEW))
    return landing
