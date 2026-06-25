"""Passerelle d'accès au Data Warehouse (mart) — ADR-0004.

Le backend lit le mart en **lecture seule** et ne touche jamais les sources. Cette
abstraction isole l'accès SQL : implémentation PostgreSQL en prod, implémentation
mémoire pour les tests (pas de Postgres requis).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Sequence

from django.conf import settings

from k_insight.kpi.hr_mart import HrKpiRow


class MartGateway(ABC):
    @abstractmethod
    def fetch_hr_kpi(self) -> list[HrKpiRow]:
        """Lit les lignes de `mart.hr_kpi` (maille filiale × département × mois)."""


class InMemoryMartGateway(MartGateway):
    """Passerelle de test : sert des lignes fournies en mémoire."""

    def __init__(self, rows: Sequence[HrKpiRow]) -> None:
        self._rows = list(rows)

    def fetch_hr_kpi(self) -> list[HrKpiRow]:
        return list(self._rows)


class PostgresMartGateway(MartGateway):
    """Passerelle de prod : lecture seule sur `mart.hr_kpi` via psycopg (EDW_DSN)."""

    def fetch_hr_kpi(self) -> list[HrKpiRow]:
        import psycopg  # import local : pas requis pour les tests

        sql = (
            "SELECT month_start, subsidiary_code, department_code, "
            "payroll_mass_xof, entries, exits FROM mart.hr_kpi"
        )
        rows: list[HrKpiRow] = []
        with psycopg.connect(**settings.EDW_DSN) as conn, conn.cursor() as cur:
            cur.execute(sql)
            for month_start, sub, dep, payroll, entries, exits in cur.fetchall():
                rows.append(
                    HrKpiRow(
                        month_start=month_start,
                        subsidiary=sub,
                        department=dep,
                        payroll_mass_xof=int(payroll or 0),
                        entries=int(entries or 0),
                        exits=int(exits or 0),
                    )
                )
        return rows


# Fournisseur injectable (les tests substituent une passerelle mémoire).
_override: Optional[MartGateway] = None


def get_mart_gateway() -> MartGateway:
    return _override if _override is not None else PostgresMartGateway()


def set_mart_gateway(gateway: Optional[MartGateway]) -> None:
    global _override
    _override = gateway
