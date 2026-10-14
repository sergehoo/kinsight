"""Charges de source partagées : une collecte, servie à toutes les requêtes.

POURQUOI. `fetch_hr_kpis` de Shield coûte de 32 à 65 appels. Un accueil de
domaine le déclenchait à chaque carte qui le demandait, les pages Présence et
Module à leur tour, et chaque worker gunicorn recommençait de son côté : plusieurs
centaines d'appels Shield pour afficher la même douzaine de chiffres.

CE QUI EST MIS EN CACHE, ET CE QUI NE L'EST PAS. Uniquement des charges de niveau
GROUPE, identiques pour tous les utilisateurs. La restriction de périmètre est
appliquée APRÈS, à chaque requête, par la vue : mettre en cache une réponse déjà
restreinte, ou une réponse restreinte sous une clé qui ne porte pas le périmètre,
servirait les chiffres d'un utilisateur à un autre.

SINGLE-FLIGHT. Quand la charge est périmée, UNE requête la recollecte ; les autres
attendent son résultat (borné) au lieu de lancer chacune leur collecte. Le verrou
vit dans le cache partagé, donc entre workers quand le cache est Redis.

FRAÎCHEUR DITE. La charge porte `cache` : âge et horodatage de la collecte. Une
donnée vieille de 50 s n'est pas présentée comme lue à l'instant.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Callable

from django.utils import timezone

from .odoo_session import _cache_add, _cache_delete, _cache_get, _cache_set

ATTENTE_MAX = 20.0          # une collecte Shield complète peut durer une quinzaine de secondes
DUREE_VERROU = 45


def lire(cle: str, collecter: Callable[[], dict[str, Any]], *, ttl: int = 60) -> dict[str, Any]:
    """La charge `cle`, collectée au plus une fois par `ttl` secondes pour tous.

    Une charge en ERREUR n'est gardée que 10 s : assez pour absorber une rafale de
    requêtes simultanées, pas assez pour masquer le retour de la source.
    """
    complete = f"source:{cle}"
    en_cache = _cache_get(complete)
    if isinstance(en_cache, dict):
        return _avec_age(en_cache)

    verrou = f"{complete}:verrou"
    if not _cache_add(verrou, 1, DUREE_VERROU):
        limite = time.monotonic() + ATTENTE_MAX
        while time.monotonic() < limite:
            time.sleep(0.15)
            en_cache = _cache_get(complete)
            if isinstance(en_cache, dict):
                return _avec_age(en_cache)
        # Détenteur disparu ou trop lent : on collecte nous-mêmes plutôt que de
        # laisser l'écran attendre indéfiniment.
    try:
        charge = collecter()
    finally:
        _cache_delete(verrou)

    if isinstance(charge, dict):
        horodatee = {**charge, "_collecte_le": timezone.now().isoformat()}
        duree = 10 if charge.get("status") in ("error", "disconnected") else ttl
        _cache_set(complete, horodatee, duree)
        return _avec_age(horodatee)
    return charge


def oublier(cle: str) -> None:
    _cache_delete(f"source:{cle}")


def _avec_age(charge: dict[str, Any]) -> dict[str, Any]:
    collecte = charge.get("_collecte_le")
    resultat = {k: v for k, v in charge.items() if k != "_collecte_le"}
    if collecte:
        try:
            age = (timezone.now() - datetime.fromisoformat(collecte)).total_seconds()
        except (TypeError, ValueError):
            age = None
        resultat["cache"] = {"collecte_le": collecte,
                             "age_s": int(age) if age is not None else None}
    return resultat
