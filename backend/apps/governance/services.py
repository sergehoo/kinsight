"""Service governance : applique le périmètre RBAC puis calcule les KPI via le domaine pur.

La couche Django ne refait aucun calcul métier : elle filtre par périmètre (ADR-0005)
et délègue les agrégats à `k_insight.kpi.hr_mart` (ADR-0006).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Sequence

from k_insight.access import Scope, filter_by_scope
from k_insight.kpi.core import Period
from k_insight.kpi.hr_mart import (
    HrKpiRow,
    payroll_by_subsidiary,
    total_entries,
    total_exits,
    total_payroll_mass,
)


def period_from_quarter(year: int, quarter: int) -> Period:
    """Construit la période [start, end[ d'un trimestre civil."""
    start_month = 3 * (quarter - 1) + 1
    start = date(year, start_month, 1)
    end_month = start_month + 3
    end = date(year + 1, 1, 1) if end_month > 12 else date(year, end_month, 1)
    return Period(start, end)


def hr_kpi_summary(
    rows: Sequence[HrKpiRow], scope: Scope, period: Period
) -> dict:
    """Synthèse RH filtrée par périmètre, sur la période demandée.

    NB : le turnover n'est pas servi ici car il requiert un instantané d'effectif
    (fait `headcount` à matérialiser au mart) ; on expose la variation nette
    entrées − sorties en attendant (cf. STATUS.md).
    """
    scoped = filter_by_scope(rows, scope, key=lambda r: r.subsidiary)
    entries = total_entries(scoped, period)
    exits = total_exits(scoped, period)
    return {
        "period": {"start": period.start.isoformat(), "end": period.end.isoformat()},
        "scope": "GROUP" if scope.is_group else sorted(scope.subsidiaries),
        "metrics": {
            "hr.payroll_mass": {"value": total_payroll_mass(scoped, period), "unit": "XOF"},
            "hr.entries": {"value": entries, "unit": "personnes"},
            "hr.exits": {"value": exits, "unit": "personnes"},
            "hr.net_headcount_change": {"value": entries - exits, "unit": "personnes"},
        },
        "payroll_by_subsidiary": payroll_by_subsidiary(scoped, period),
    }


def _format_int(value: int | float) -> str:
    return f"{int(value):,}".replace(",", " ")


def _format_compact(value: int | float) -> str:
    absolute = abs(float(value))
    if absolute >= 1_000_000_000:
        out = f"{float(value) / 1_000_000_000:.1f}Md"
    elif absolute >= 1_000_000:
        out = f"{float(value) / 1_000_000:.1f}M"
    elif absolute >= 1_000:
        out = f"{float(value) / 1_000:.1f}K"
    else:
        out = str(int(value))
    return out.replace(".0", "")


def _compact_xof(value: int | float) -> str:
    return f"{_format_compact(value)} XOF"


def _clamp_gauge(value: float) -> int:
    return max(8, min(96, round(value)))


def _payroll_stats(payroll: dict[str, int]) -> dict[str, Any]:
    entries = sorted(payroll.items(), key=lambda item: item[1], reverse=True)
    total = sum(value for _, value in entries)
    top_code, top_value = entries[0] if entries else ("--", 0)
    top_share = round((top_value / total) * 100) if total else 0
    return {"count": len(entries), "top_code": top_code, "top_share": top_share}


def _availability_dashboard(
    *,
    key: str,
    title: str,
    subtitle: str,
    expected_source: str,
    image_hint: str,
    chart_title: str,
    chart_unit: str,
    card_labels: Sequence[tuple[str, str, str]],
    period_label: str,
) -> dict[str, Any]:
    """Dashboard alimenté par le backend mais sans mart matérialisé disponible."""
    cards = [
        {
            "label": label,
            "context": context,
            "value": "--",
            "delta": "mart absent",
            "up": False,
            "gauge": 8,
            "color": color,
            "highlighted": index == 0,
        }
        for index, (label, context, color) in enumerate(card_labels)
    ]
    return {
        "key": key,
        "title": title,
        "subtitle": subtitle,
        "status": f"Source backend attendue : {expected_source}",
        "available": False,
        "source": expected_source,
        "imageHint": image_hint,
        "overlayTitle": "Mart a connecter",
        "overlaySubtitle": expected_source,
        "overlayValue": "--",
        "overlayBadges": ["EDW", "MART"],
        "periodLabel": period_label,
        "chartTitle": chart_title,
        "chartValue": "--",
        "chartDelta": "Aucune donnee servie",
        "chartDeltaUp": False,
        "chartUnit": chart_unit,
        "chartData": {},
        "chartEmptyLabel": f"Aucune donnee disponible dans {expected_source}",
        "cards": cards,
        "controlTitle": "Controle donnees",
        "controlSubtitle": f"Materialiser {expected_source} pour activer ce dashboard",
        "alertTop": [
            ["Source", expected_source],
            ["Etat", "Absent"],
            ["API", "OK"],
            ["RBAC", "OK"],
            ["Mode", "read"],
        ],
        "alertBottom": [
            ["Action", "dbt"],
            ["Grain", "a definir"],
            ["Scope", "filiale"],
            ["Audit", "OK"],
            ["Prod", "pret"],
        ],
    }


def _hr_dashboard(summary: dict[str, Any] | None, *, year: int, quarter: int, error: str = "") -> dict[str, Any]:
    if summary is None:
        return {
            **_availability_dashboard(
                key="hr",
                title="Pilotage RH",
                subtitle="Synthese RH issue du mart backend : masse salariale, entrees, sorties et repartition par filiale.",
                expected_source="mart.hr_kpi",
                image_hint="hr",
                chart_title="Masse salariale par filiale",
                chart_unit="XOF",
                period_label=f"T{quarter} {year}",
                card_labels=(
                    ("Masse salariale", "Cumul de la periode", "#416FF4"),
                    ("Entrees RH", "Embauches periode", "#42BFA0"),
                    ("Sorties RH", "Departs periode", "#D92B55"),
                ),
            ),
            "status": "mart.hr_kpi indisponible" if error else "Chargement mart.hr_kpi",
            "controlSubtitle": "Source backend : mart.hr_kpi",
        }

    metrics = summary["metrics"]
    payroll_mass = int(metrics["hr.payroll_mass"]["value"])
    entries = int(metrics["hr.entries"]["value"])
    exits = int(metrics["hr.exits"]["value"])
    net_change = int(metrics["hr.net_headcount_change"]["value"])
    payroll = {str(key): int(value) for key, value in summary["payroll_by_subsidiary"].items()}
    stats = _payroll_stats(payroll)
    movement_total = entries + exits
    entries_share = (entries / movement_total) * 100 if movement_total else 0
    exits_share = (exits / movement_total) * 100 if movement_total else 0
    badges = list(payroll.keys()) or ["EDW", "MART"]

    return {
        "key": "hr",
        "title": "Pilotage RH",
        "subtitle": "Synthese RH issue du backend : masse salariale, entrees, sorties et repartition par filiale.",
        "status": "Donnees backend chargees",
        "available": True,
        "source": "mart.hr_kpi",
        "imageHint": "hr",
        "overlayTitle": f"Perimetre {'Groupe' if summary['scope'] == 'GROUP' else ', '.join(summary['scope'])}",
        "overlaySubtitle": f"{summary['period']['start']} -> {summary['period']['end']}",
        "overlayValue": str(stats["count"]),
        "overlayBadges": badges,
        "periodLabel": f"T{quarter} {year}",
        "chartTitle": "Masse salariale par filiale",
        "chartValue": _compact_xof(payroll_mass),
        "chartDelta": "mart.hr_kpi",
        "chartDeltaUp": True,
        "chartUnit": "XOF",
        "chartData": payroll,
        "chartEmptyLabel": "Aucune masse salariale sur la periode",
        "cards": [
            {
                "label": "Masse salariale",
                "context": "Cumul de la periode",
                "value": _compact_xof(payroll_mass),
                "delta": f"{stats['top_code']} {stats['top_share']}%",
                "up": True,
                "gauge": _clamp_gauge(stats["top_share"]),
                "color": "#416FF4",
                "highlighted": True,
            },
            {
                "label": "Entrees RH",
                "context": "Embauches periode",
                "value": _format_int(entries),
                "delta": f"{_format_int(abs(net_change))} net",
                "up": net_change >= 0,
                "gauge": _clamp_gauge(entries_share),
                "color": "#42BFA0",
            },
            {
                "label": "Sorties RH",
                "context": "Departs periode",
                "value": _format_int(exits),
                "delta": f"{_format_int(exits)} departs",
                "up": False,
                "gauge": _clamp_gauge(exits_share),
                "color": "#D92B55",
            },
        ],
        "controlTitle": "Controle donnees RH",
        "controlSubtitle": "Source backend : mart.hr_kpi",
        "alertTop": [
            ["Entrees", _format_int(entries)],
            ["Sorties", _format_int(exits)],
            ["Net", f"{'+' if net_change >= 0 else '-'}{_format_int(abs(net_change))}"],
            ["Audit", "OK"],
            ["RBAC", "OK"],
        ],
        "alertBottom": [
            ["Mart", "hr_kpi"],
            ["Grain", "mois"],
            ["Scope", "filiale"],
            ["Unite", "XOF"],
            ["Mode", "read"],
        ],
    }


def governance_overview(
    *,
    year: int,
    quarter: int,
    scope: Scope,
    hr_summary: dict[str, Any] | None,
    hr_error: str = "",
) -> dict[str, Any]:
    """Contrat unique consommé par le dashboard React."""
    period = period_from_quarter(year, quarter)
    scope_payload: str | list[str] = "GROUP" if scope.is_group else sorted(scope.subsidiaries)
    real_estate = _availability_dashboard(
        key="realEstate",
        title="Pilotage Real Estate",
        subtitle="Suivi consolide des programmes, chantiers, ventes et reserves foncieres du groupe.",
        expected_source="mart.real_estate_kpi",
        image_hint="real_estate",
        chart_title="Avancement par programme",
        chart_unit="%",
        period_label="Real Estate",
        card_labels=(
            ("Programmes", "En cours", "#416FF4"),
            ("Chantiers", "Suivi planning", "#D92B55"),
            ("Taux de vente", "Unites commercialisees", "#42BFA0"),
        ),
    )
    finance = _availability_dashboard(
        key="finance",
        title="Pilotage Finance",
        subtitle="Lecture consolidee du resultat, des engagements, de la tresorerie et des depenses groupe.",
        expected_source="mart.finance_kpi",
        image_hint="finance",
        chart_title="Repartition des charges",
        chart_unit="XOF",
        period_label="Finance",
        card_labels=(
            ("Resultat net", "YTD vs N-1", "#D92B55"),
            ("Tresorerie", "Disponible", "#42BFA0"),
            ("Charges", "YTD", "#416FF4"),
        ),
    )
    return {
        "period": {"start": period.start.isoformat(), "end": period.end.isoformat()},
        "scope": scope_payload,
        "dashboards": {
            "realEstate": real_estate,
            "hr": _hr_dashboard(hr_summary, year=year, quarter=quarter, error=hr_error),
            "finance": finance,
        },
    }
