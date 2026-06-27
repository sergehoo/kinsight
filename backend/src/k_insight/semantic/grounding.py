"""Ancrage IA : résolution question → métrique du catalogue (domaine pur, testé).

Garantie de gouvernance (ADR-0007) : l'IA ne répond QUE sur une métrique réellement
définie dans le catalogue, et sur une valeur réellement issue du mart. Si aucune métrique
ne correspond, elle REFUSE — elle n'invente jamais une métrique ni un chiffre. Si la
métrique existe mais que sa source n'est pas branchée, la valeur est « N/D ».

Ce module est purement déterministe (résolution + phrase factuelle). Un LLM peut, en aval
et de façon optionnelle, reformuler la réponse — mais la SOURCE (quelle métrique, quelle
valeur) reste fixée ici.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Callable, Optional

from .registry import MetricCatalog

# Mots vides ignorés lors du rapprochement.
_STOP = {
    "le", "la", "les", "un", "une", "des", "de", "du", "d", "l", "quel", "quelle", "est",
    "le", "sur", "pour", "par", "en", "et", "a", "au", "aux", "ce", "cette", "quel", "moyen",
    "moyenne", "taux", "nombre", "combien", "donne", "moi", "the", "of", "what", "is",
}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", _norm(text)) if t and t not in _STOP and len(t) > 1}


def resolve_metric(catalog: MetricCatalog, query: str):
    """Métrique du catalogue la plus proche de `query`, ou None si rien de pertinent.

    1) clé explicite citée (ex. « finance.dso ») → match exact.
    2) sinon, recouvrement de mots-clés avec libellé + clé + description ; seuil minimal
       pour éviter de « deviner ». Aucune correspondance → None (l'API refusera).
    """
    qn = _norm(query)
    for m in catalog.all():
        if m.key.lower() in qn:
            return m

    qtokens = _tokens(query)
    if not qtokens:
        return None
    best = None
    best_key = (0, 0.0)  # (recouvrement, spécificité = recouvrement / taille des termes)
    for m in catalog.all():
        # Rapprochement sur le LIBELLÉ + la CLÉ seulement (pas la description : ses mots
        # génériques — « cours », « total », « date » — provoqueraient de faux positifs).
        # Précision avant rappel : mieux vaut refuser que répondre sur la mauvaise métrique.
        terms = _tokens(m.label) | _tokens(m.key.split(".")[-1])
        if not terms:
            continue
        overlap = len(qtokens & terms)
        if overlap == 0:
            continue
        rank = (overlap, overlap / len(terms))  # + de mots communs, puis le plus spécifique
        if rank > best_key:
            best, best_key = m, rank
    # Refus si AUCUN mot-clé du catalogue ne recoupe la question (best reste None).
    return best


def answer(catalog: MetricCatalog, query: str, value_lookup: Callable[[str], Optional[float]]) -> dict:
    """Réponse ANCRÉE à une question, ou refus motivé. Jamais d'invention."""
    metric = resolve_metric(catalog, query)
    if metric is None:
        return {
            "grounded": False,
            "answer": (
                "Aucun indicateur du catalogue de gouvernance ne correspond à cette demande. "
                "Je ne réponds que sur des métriques définies et sourcées par le Data Warehouse "
                "(je n'invente ni indicateur ni chiffre)."
            ),
            "metric": None,
            "value": None,
            "source": None,
        }

    value = value_lookup(metric.key)
    meta = {
        "key": metric.key,
        "label": metric.label,
        "domain": metric.domain,
        "unit": metric.unit,
        "direction": metric.direction.value,
        "mart": metric.mart,
        "description": metric.description,
    }
    if value is None:
        phrase = (
            f"« {metric.label} » ({metric.key}) est défini dans le catalogue "
            f"(unité : {metric.unit}, source : {metric.mart}), mais sa valeur n'est pas encore "
            f"disponible — source non branchée (N/D, aucune donnée inventée)."
        )
    else:
        phrase = f"{metric.label} ({metric.key}) : {value} {metric.unit} — source {metric.mart}."
    return {"grounded": True, "answer": phrase, "metric": meta, "value": value, "source": metric.mart}
