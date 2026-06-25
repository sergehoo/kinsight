"""Grain du mart RH + agrégations servies à l'API (domaine pur).

`HrKpiRow` reproduit exactement la maille de `mart.hr_kpi`
(filiale × département × mois). `build_hr_kpi_rows` reconstruit ces lignes à partir
des données brutes (employés, bulletins) **en miroir de la logique dbt/SQL** :
c'est ce qui permet le **test de réconciliation** (ADR-0006) — les agrégats calculés
depuis le mart doivent égaler les calculs directs de `kpi/hr.py`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence

from .core import Period
from .hr import Employee, Payslip


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


@dataclass(frozen=True)
class HrKpiRow:
    """Une ligne du mart RH (maille filiale × département × mois)."""

    month_start: date
    subsidiary: str
    department: str
    payroll_mass_xof: int
    entries: int
    exits: int


def build_hr_kpi_rows(
    employees: Sequence[Employee], payslips: Sequence[Payslip]
) -> list[HrKpiRow]:
    """Reconstruit les lignes du mart RH (miroir de `models/marts/hr/hr_kpi.sql`)."""
    payroll: dict[tuple[date, str, str], int] = defaultdict(int)
    entries: dict[tuple[date, str, str], int] = defaultdict(int)
    exits: dict[tuple[date, str, str], int] = defaultdict(int)

    for p in payslips:
        payroll[(_month_start(p.pay_date), p.subsidiary, p.department)] += p.gross_xof
    for e in employees:
        entries[(_month_start(e.hired_on), e.subsidiary, e.department)] += 1
        if e.terminated_on is not None:
            exits[(_month_start(e.terminated_on), e.subsidiary, e.department)] += 1

    keys = set(payroll) | set(entries) | set(exits)
    rows = [
        HrKpiRow(
            month_start=k[0],
            subsidiary=k[1],
            department=k[2],
            payroll_mass_xof=payroll.get(k, 0),
            entries=entries.get(k, 0),
            exits=exits.get(k, 0),
        )
        for k in keys
    ]
    rows.sort(key=lambda r: (r.month_start, r.subsidiary, r.department))
    return rows


def _in_period(rows: Sequence[HrKpiRow], period: Optional[Period]) -> list[HrKpiRow]:
    if period is None:
        return list(rows)
    return [r for r in rows if period.contains(r.month_start)]


def total_payroll_mass(rows: Sequence[HrKpiRow], period: Optional[Period] = None) -> int:
    return sum(r.payroll_mass_xof for r in _in_period(rows, period))


def total_entries(rows: Sequence[HrKpiRow], period: Optional[Period] = None) -> int:
    return sum(r.entries for r in _in_period(rows, period))


def total_exits(rows: Sequence[HrKpiRow], period: Optional[Period] = None) -> int:
    return sum(r.exits for r in _in_period(rows, period))


def payroll_by_subsidiary(
    rows: Sequence[HrKpiRow], period: Optional[Period] = None
) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for r in _in_period(rows, period):
        out[r.subsidiary] += r.payroll_mass_xof
    return dict(out)
