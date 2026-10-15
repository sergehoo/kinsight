"""Branchement du registre RH sur les sources réelles, pour UNE requête.

Le registre (`hr_registry`) ne sait rien des connecteurs ; ce module lui donne les
charges Shield et Odoo — partagées et mises en cache au niveau GROUPE par
`integrations.partage` — et le périmètre de l'utilisateur. La restriction est
toujours appliquée après le cache, jamais avant : une charge en cache est la même
pour tous.
"""

from __future__ import annotations

from apps.accounts.rbac import can_access_domain

from .hr_registry import Contexte

TTL_SHIELD = 60
TTL_ODOO = 120


def _cle(prefixe: str, source) -> str:
    """Clé de cache liée à la source ET à sa configuration : une source recréée,
    ou un connecteur modifié, ne relit pas la charge de l'ancien."""
    connecteur = getattr(source, "connector", None)
    version = getattr(connecteur, "updated_at", None) or getattr(source, "updated_at", None)
    return f"{prefixe}:{source.pk}:{version.timestamp() if version else 0}"


def charge_shield_groupe(collecteur=None) -> dict:
    """`collecteur` : la fonction de collecte à employer, par défaut celle du
    connecteur. L'injecter permet à une vue de garder SON point d'appel — c'est ce
    qu'interceptent ses tests."""
    from apps.integrations import partage
    from apps.integrations.shield import fetch_hr_kpis, get_shield_source

    collecter = collecteur or fetch_hr_kpis
    source = get_shield_source()
    if source is None:
        return collecter()  # renvoie l'état « non déclarée », sans appel réseau
    return partage.lire(_cle("shield.hr_kpi", source), collecter, ttl=TTL_SHIELD)


def oublier_charge_shield() -> None:
    """Après un arbitrage de seuils : les constats du jour en cache ont été jugés
    avec l'ancienne borne, ils sont recalculés à la lecture suivante."""
    from apps.integrations import partage
    from apps.integrations.shield import get_shield_source

    source = get_shield_source()
    if source is not None:
        partage.oublier(_cle("shield.hr_kpi", source))


def charge_odoo(societes: list[int] | None) -> dict:
    from apps.integrations import partage
    from apps.integrations.odoo import fetch_hr_kpis, get_odoo_source

    source = get_odoo_source()
    if source is None:
        return fetch_hr_kpis(societes)
    # Le périmètre SOCIÉTÉS fait partie de la clé : la charge d'une filiale ne
    # doit jamais être resservie à une autre, ni la charge Groupe à une filiale.
    portee = "*" if societes is None else ",".join(str(i) for i in sorted(societes))
    return partage.lire(f"{_cle('odoo.hr_kpi', source)}:{portee}",
                        lambda: fetch_hr_kpis(societes), ttl=TTL_ODOO)


def societes_des_filiales(filiales: frozenset[str]) -> list[int]:
    """Sociétés Odoo DÉCLARÉES comme appartenant à ces filiales. Rien de deviné."""
    from apps.integrations.odoo import get_odoo_source
    from apps.integrations.odoo_session import correspondance_societes

    source = get_odoo_source()
    if source is None or getattr(source, "connector", None) is None:
        return []
    return sorted(int(cid) for cid, code in correspondance_societes(source.connector).items()
                  if code in filiales)


def contexte_pour(user) -> Contexte:
    scope = user.scope()
    return Contexte(
        peut_voir=lambda domaine: can_access_domain(user, domaine),
        perimetre_groupe=scope.is_group,
        filiales=frozenset(scope.subsidiaries) if not scope.is_group else frozenset(),
        charge_shield=charge_shield_groupe,
        charge_odoo=charge_odoo,
        societes_des_filiales=societes_des_filiales,
    )
