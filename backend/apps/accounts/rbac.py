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
# Permissions RENFORCÉES du Capital Humain : avoir le domaine RH ne suffit pas.
P_HR_PAYROLL = "view_hr_payroll"
P_HR_CAREER = "view_hr_career"
P_HR_PERFORMANCE = "view_hr_performance"
RH_RENFORCEES = [P_HR_PAYROLL, P_HR_CAREER, P_HR_PERFORMANCE]
# Préfixe des pages affectées à un Assistant RH (`hr_module:hr-attendance`).
P_HR_MODULE = "hr_module:"
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
    "DRH": ([P_HR], L_HR),  # + paie / carrière / performance au périmètre Groupe (voir permissions_for)
    # Directeur de filiale : tous les métiers, TOUJOURS restreint à ses filiales
    # (`User.scope`) ; la paie de sa filiale, pas carrière ni performance.
    "DIR_FILIALE": ([P_OVERVIEW, P_IMMO, P_HR, P_FINANCE, P_OPS, P_COMMERCIAL, P_RISK, P_REPORTS, P_HR_PAYROLL],
                    L_OVERVIEW),
    # Assistant RH : le domaine RH, réduit aux pages explicitement affectées.
    "ASSISTANT_RH": ([P_HR], L_HR),
    "DIR_OPS": ([P_OVERVIEW, P_OPS, P_IMMO, P_COMMERCIAL], L_OPS),
    "RESP_METIER": ([P_OVERVIEW, P_IMMO, P_OPS, P_COMMERCIAL, P_REPORTS], L_OVERVIEW),
    "ADMIN_INTEGRATION": ([P_OVERVIEW], L_INTEGRATIONS),
    "READER": ([P_OVERVIEW, P_REPORTS], L_OVERVIEW),
}


def permissions_for(user) -> list[str]:
    if getattr(user, "is_superuser", False):
        return [P_SUPERADMIN]
    role = getattr(user, "role", "")
    perms, _landing = _BY_ROLE.get(role, ([P_OVERVIEW], L_OVERVIEW))
    perms = list(perms)
    # DRH GROUPE : paie, carrière, performance. Un RH de filiale (DRH restreint)
    # garde le domaine sans ces trois volets.
    if role == "DRH" and getattr(user, "is_group_scope", False):
        perms += RH_RENFORCEES
    if role == "ASSISTANT_RH":
        perms += [f"{P_HR_MODULE}{cle}" for cle in (getattr(user, "affectations_rh", None) or [])
                  if isinstance(cle, str)]
    return perms


# Pages RH qui exigent une permission renforcée en plus du domaine.
MODULES_RENFORCES = {"hr-payroll": P_HR_PAYROLL, "hr-career": P_HR_CAREER, "hr-performance": P_HR_PERFORMANCE}


def peut_module_rh(user, cle: str) -> bool:
    """Une page (ou action) du Capital Humain est-elle ouverte à cet utilisateur ?

    Domaine RH requis ; paie / carrière / performance exigent leur permission ;
    un Assistant RH n'ouvre que les pages qui lui sont affectées. Frontière
    serveur : la navigation ne fait que masquer.
    """
    if not can_access_domain(user, "capital-humain"):
        return False
    perms = permissions_for(user)
    if P_SUPERADMIN in perms or P_ALL in perms:
        return True
    if getattr(user, "role", "") == "ASSISTANT_RH" and f"{P_HR_MODULE}{cle}" not in perms:
        return False
    requise = MODULES_RENFORCES.get(cle)
    return requise is None or requise in perms


def peut_voir_permission(user, permission: str) -> bool:
    perms = permissions_for(user)
    return P_SUPERADMIN in perms or P_ALL in perms or permission in perms


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


def peut_configurer_seuils_rh(user) -> bool:
    """Arbitrer les seuils des signaux RH : la DRH Groupe et l'administration.

    Les seuils valent pour tout le Groupe — ils jugent aussi les constats du jour.
    Un RH de filiale les lit, il ne règle pas les bornes des autres filiales.
    """
    if getattr(user, "is_superuser", False) or P_SUPERADMIN in permissions_for(user):
        return True
    return getattr(user, "role", "") == "DRH" and user.scope().is_group
