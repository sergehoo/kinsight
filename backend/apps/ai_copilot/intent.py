"""Routage d'intention → outil (déterministe, hors-ligne).

Permet au Copilot d'AGIR sans LLM : une formulation explicite déclenche un outil contrôlé.
Conservateur par construction (uniquement des intentions non ambiguës) ; tout passe ensuite
par `PermissionAwareToolExecutor` (RBAC + approbation). Quand un LLM est branché, il peut
émettre les mêmes appels d'outils (tool-calling natif) via le même exécuteur gouverné.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def _first_int(text: str) -> Optional[int]:
    m = re.search(r"\b(\d{1,9})\b", text)
    return int(m.group(1)) if m else None


def detect_tool_intent(message: str) -> Optional[tuple[str, dict]]:
    """(tool_name, args) si une intention d'action claire est détectée, sinon None."""
    t = _norm(message)

    # Génération de rapport (lecture) — intention forte, sans paramètre requis.
    if re.search(r"\b(genere|generer|produis|produire|prepare|preparer|fais|etablis)\b", t) and re.search(
        r"\b(rapport|synthese|reporting|tableau de bord|bilan)\b", t
    ):
        return "generate_report", {}

    # Synchronisation d'un connecteur (écriture sensible) — exige un identifiant.
    if re.search(r"\b(synchronis|sync)\w*\b", t) and re.search(r"\b(connecteur|source|integration)\b", t):
        sid = _first_int(t)
        if sid is not None:
            return "run_connector_sync", {"source_id": sid}

    # Suppression d'un connecteur (destructif) — exige un identifiant explicite.
    if re.search(r"\b(supprime|supprimer|efface|effacer|detruis|detruire)\b", t) and re.search(
        r"\b(connecteur|source|integration)\b", t
    ):
        sid = _first_int(t)
        if sid is not None:
            return "delete_connector", {"source_id": sid}

    return None
