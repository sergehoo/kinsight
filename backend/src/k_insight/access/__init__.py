"""Contrôle d'accès multi-filiales (domaine pur) — cf. ADR-0005.

Le filtrage par périmètre est une règle de sécurité : on l'implémente et on la teste
ici, sans Django, pour qu'elle soit indépendante du transport (API, IA, rapports).
"""

from .perimeter import Scope, filter_by_scope

__all__ = ["Scope", "filter_by_scope"]
