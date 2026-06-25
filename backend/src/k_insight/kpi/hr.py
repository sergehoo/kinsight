"""KPI de Gouvernance RH (domaine pur, testé).

Indicateurs couverts par le 1er incrément :
- Effectif (headcount) à une date
- Entrées / sorties sur une période
- Taux de turnover (rotation du personnel)
- Taux d'absentéisme
- Masse salariale (brut) sur une période, ventilable par filiale / département

Modèle de données minimal (ce que le mart RH matérialisera, cf. warehouse/ddl/marts/hr_mart.sql).
Les dates de fin de contrat suivent la convention : `terminated_on` = **premier jour
non travaillé** (jour de départ effectif). Un salarié est donc actif si
`hired_on <= d < terminated_on`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence

from .core import MetricResult, Period, aggregate_by, safe_ratio


@dataclass(frozen=True)
class Employee:
    """Salarié (grain du mart `dim_employee`)."""

    employee_id: str
    subsidiary: str          # filiale (KRE, KSH, MYK…)
    department: str
    hired_on: date
    terminated_on: Optional[date] = None  # premier jour NON travaillé, ou None si en poste


@dataclass(frozen=True)
class Payslip:
    """Ligne de bulletin de paie (grain du mart `fact_payroll`).

    `gross_xof` : salaire brut en francs CFA (entier, 0 décimale).
    `pay_date` : date de rattachement du bulletin (1er du mois de paie en général).
    """

    employee_id: str
    subsidiary: str
    department: str
    pay_date: date
    gross_xof: int


def is_active(emp: Employee, d: date) -> bool:
    """Vrai si `emp` est en poste à la date `d` (convention hired <= d < terminated)."""
    if emp.hired_on > d:
        return False
    return emp.terminated_on is None or d < emp.terminated_on


def headcount(employees: Sequence[Employee], as_of: date) -> int:
    """Effectif (stock) à la date `as_of`."""
    return sum(1 for e in employees if is_active(e, as_of))


def entries(employees: Sequence[Employee], period: Period) -> int:
    """Nombre d'embauches dont la date tombe dans [start, end[."""
    return sum(1 for e in employees if period.contains(e.hired_on))


def exits(employees: Sequence[Employee], period: Period) -> int:
    """Nombre de départs dont la date tombe dans [start, end[."""
    return sum(
        1
        for e in employees
        if e.terminated_on is not None and period.contains(e.terminated_on)
    )


def average_headcount(employees: Sequence[Employee], period: Period) -> float:
    """Effectif moyen = (effectif au début + effectif à la fin) / 2.

    L'effectif de fin est évalué au dernier instant de la période. Comme les bornes
    sont demi-ouvertes, on prend `end` exclu : un salarié parti le jour `end` n'est
    plus compté à la fin, ce qui est cohérent avec `contains`.
    """
    start_hc = headcount(employees, period.start)
    end_hc = headcount(employees, period.end)
    return (start_hc + end_hc) / 2


def turnover_rate(employees: Sequence[Employee], period: Period) -> float:
    """Taux de turnover = départs sur la période / effectif moyen.

    Retourne une fraction (0.20 = 20 %). 0.0 si l'effectif moyen est nul.
    """
    return safe_ratio(exits(employees, period), average_headcount(employees, period))


def absenteeism_rate(absent_days: float, theoretical_days: float) -> float:
    """Taux d'absentéisme = jours d'absence / jours théoriques travaillés.

    Fonction-ratio pure : les agrégats (somme des absences, jours théoriques =
    effectif × jours ouvrés) sont calculés en amont dans le mart. 0.0 si dénominateur nul.
    """
    return safe_ratio(absent_days, theoretical_days)


def payroll_mass(payslips: Sequence[Payslip], period: Period) -> int:
    """Masse salariale brute (XOF) sur la période. Entier — pas de float sur l'argent."""
    return sum(p.gross_xof for p in payslips if period.contains(p.pay_date))


def payroll_mass_by_subsidiary(
    payslips: Sequence[Payslip], period: Period
) -> dict[str, int]:
    """Masse salariale brute ventilée par filiale (XOF entiers)."""
    in_period = [p for p in payslips if period.contains(p.pay_date)]
    return {
        k: int(v)
        for k, v in aggregate_by(
            in_period, key_fn=lambda p: p.subsidiary, value_fn=lambda p: p.gross_xof
        ).items()
    }


def payroll_mass_by_department(
    payslips: Sequence[Payslip], period: Period
) -> dict[str, int]:
    """Masse salariale brute ventilée par département (XOF entiers)."""
    in_period = [p for p in payslips if period.contains(p.pay_date)]
    return {
        k: int(v)
        for k, v in aggregate_by(
            in_period, key_fn=lambda p: p.department, value_fn=lambda p: p.gross_xof
        ).items()
    }


# --- Façade « résultats sémantiques » : enveloppe les calculs dans MetricResult ----
# Utilisée par l'API governance et le moteur IA pour servir des résultats typés et
# rattachés à une métrique du catalogue (cf. semantic/hr.py, ADR-0006/0007).


def headcount_result(employees: Sequence[Employee], period: Period) -> MetricResult:
    return MetricResult(
        key="hr.headcount",
        value=headcount(employees, period.end),
        unit="personnes",
        period=period,
    )


def turnover_result(employees: Sequence[Employee], period: Period) -> MetricResult:
    return MetricResult(
        key="hr.turnover_rate",
        value=turnover_rate(employees, period),
        unit="ratio",
        period=period,
    )


def payroll_mass_result(payslips: Sequence[Payslip], period: Period) -> MetricResult:
    return MetricResult(
        key="hr.payroll_mass",
        value=payroll_mass(payslips, period),
        unit="XOF",
        period=period,
    )
