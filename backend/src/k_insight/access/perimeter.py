"""Périmètre de visibilité multi-filiales (ADR-0005).

Un `Scope` exprime ce qu'un utilisateur a le droit de voir :
- périmètre **groupe** (toutes les filiales), ou
- un **ensemble de codes filiales** explicite.

Toute requête au mart DOIT être filtrée par le scope de l'appelant. C'est la
première barrière (la seconde étant les droits PostgreSQL / RLS).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Scope:
    """Périmètre d'accès. `is_group=True` => accès à toutes les filiales.

    Sinon, accès limité aux codes présents dans `subsidiaries`. Un scope ni groupe
    ni doté de filiales = aucun accès (utile pour un compte non habilité).
    """

    subsidiaries: frozenset[str]
    is_group: bool = False

    @classmethod
    def group(cls) -> "Scope":
        return cls(frozenset(), True)

    @classmethod
    def of(cls, *codes: str) -> "Scope":
        return cls(frozenset(codes), False)

    @classmethod
    def none(cls) -> "Scope":
        return cls(frozenset(), False)

    def allows(self, subsidiary_code: str) -> bool:
        """Vrai si la filiale `subsidiary_code` est visible dans ce périmètre."""
        return self.is_group or subsidiary_code in self.subsidiaries


def filter_by_scope(
    rows: Iterable[T],
    scope: Scope,
    key: Callable[[T], str],
) -> list[T]:
    """Ne conserve que les lignes dont la filiale (via `key`) est autorisée par `scope`."""
    if scope.is_group:
        return list(rows)
    return [r for r in rows if scope.allows(key(r))]
