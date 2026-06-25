"""Tests du moteur de KPI RH (domaine pur).

Exécution : PYTHONPATH=src python3 -m unittest discover -s tests
Aucune base de données requise.

Jeu de données (5 salariés, 2 filiales) — valeurs attendues calculées à la main,
voir commentaires. Période d'analyse : 1er trimestre 2026 = [2026-01-01, 2026-04-01[.
"""

import unittest
from datetime import date

from k_insight.kpi.core import Period, safe_ratio, pct_change, aggregate_by, KpiError
from k_insight.kpi.hr import (
    Employee,
    Payslip,
    is_active,
    headcount,
    entries,
    exits,
    average_headcount,
    turnover_rate,
    absenteeism_rate,
    payroll_mass,
    payroll_mass_by_subsidiary,
    payroll_mass_by_department,
)
from k_insight.semantic import CATALOG


Q1 = Period(date(2026, 1, 1), date(2026, 4, 1))

EMPLOYEES = [
    # actif tout le trimestre
    Employee("E1", "KRE", "OPS", date(2025, 1, 1)),
    # parti le 15/03/2026
    Employee("E2", "KRE", "OPS", date(2025, 6, 1), date(2026, 3, 15)),
    # actif tout le trimestre
    Employee("E3", "KSH", "SEC", date(2024, 3, 1)),
    # embauché le 01/02/2026
    Employee("E4", "KSH", "SEC", date(2026, 2, 1)),
    # parti le 10/01/2026
    Employee("E5", "KRE", "FIN", date(2023, 1, 1), date(2026, 1, 10)),
]

# Bulletins du trimestre. E5 perçoit janvier (parti le 10/01), E4 à partir de février.
PAYSLIPS = [
    Payslip("E1", "KRE", "OPS", date(2026, 1, 1), 300_000),
    Payslip("E2", "KRE", "OPS", date(2026, 1, 1), 250_000),
    Payslip("E3", "KSH", "SEC", date(2026, 1, 1), 200_000),
    Payslip("E5", "KRE", "FIN", date(2026, 1, 1), 500_000),
    Payslip("E1", "KRE", "OPS", date(2026, 2, 1), 300_000),
    Payslip("E2", "KRE", "OPS", date(2026, 2, 1), 250_000),
    Payslip("E3", "KSH", "SEC", date(2026, 2, 1), 200_000),
    Payslip("E4", "KSH", "SEC", date(2026, 2, 1), 180_000),
    Payslip("E1", "KRE", "OPS", date(2026, 3, 1), 300_000),
    Payslip("E2", "KRE", "OPS", date(2026, 3, 1), 250_000),
    Payslip("E3", "KSH", "SEC", date(2026, 3, 1), 200_000),
    Payslip("E4", "KSH", "SEC", date(2026, 3, 1), 180_000),
]


class PeriodTest(unittest.TestCase):
    def test_demi_ouverte(self):
        self.assertTrue(Q1.contains(date(2026, 1, 1)))    # start inclus
        self.assertFalse(Q1.contains(date(2026, 4, 1)))   # end exclu
        self.assertTrue(Q1.contains(date(2026, 3, 31)))

    def test_periode_invalide(self):
        with self.assertRaises(KpiError):
            Period(date(2026, 4, 1), date(2026, 1, 1))


class HeadcountTest(unittest.TestCase):
    def test_is_active(self):
        self.assertTrue(is_active(EMPLOYEES[0], date(2026, 1, 1)))
        # E5 parti le 10/01 : actif le 09, plus le 10 (jour de départ = non travaillé)
        self.assertTrue(is_active(EMPLOYEES[4], date(2026, 1, 9)))
        self.assertFalse(is_active(EMPLOYEES[4], date(2026, 1, 10)))
        # E4 embauché le 01/02 : pas actif avant
        self.assertFalse(is_active(EMPLOYEES[3], date(2026, 1, 31)))
        self.assertTrue(is_active(EMPLOYEES[3], date(2026, 2, 1)))

    def test_headcount_debut(self):
        # E1, E2, E3, E5 actifs au 01/01 ; E4 pas encore => 4
        self.assertEqual(headcount(EMPLOYEES, date(2026, 1, 1)), 4)

    def test_headcount_fin(self):
        # au 01/04 (end) : E1, E3, E4 ; E2 (parti 15/03) et E5 (parti 10/01) sortis => 3
        self.assertEqual(headcount(EMPLOYEES, Q1.end), 3)

    def test_entrees_sorties(self):
        self.assertEqual(entries(EMPLOYEES, Q1), 1)  # E4
        self.assertEqual(exits(EMPLOYEES, Q1), 2)    # E2, E5

    def test_average_headcount(self):
        self.assertEqual(average_headcount(EMPLOYEES, Q1), 3.5)  # (4+3)/2


class TurnoverTest(unittest.TestCase):
    def test_turnover_rate(self):
        # 2 départs / 3.5 effectif moyen
        self.assertAlmostEqual(turnover_rate(EMPLOYEES, Q1), 2 / 3.5, places=10)

    def test_turnover_effectif_nul(self):
        self.assertEqual(turnover_rate([], Q1), 0.0)


class AbsenteeismTest(unittest.TestCase):
    def test_ratio(self):
        self.assertAlmostEqual(absenteeism_rate(12, 240), 0.05)

    def test_denominateur_nul(self):
        self.assertEqual(absenteeism_rate(5, 0), 0.0)


class PayrollTest(unittest.TestCase):
    def test_masse_totale(self):
        # Jan 1 250 000 + Fev 930 000 + Mar 930 000 = 3 110 000
        self.assertEqual(payroll_mass(PAYSLIPS, Q1), 3_110_000)

    def test_resultat_entier(self):
        self.assertIsInstance(payroll_mass(PAYSLIPS, Q1), int)

    def test_par_filiale(self):
        self.assertEqual(
            payroll_mass_by_subsidiary(PAYSLIPS, Q1),
            {"KRE": 2_150_000, "KSH": 960_000},
        )

    def test_par_departement(self):
        self.assertEqual(
            payroll_mass_by_department(PAYSLIPS, Q1),
            {"OPS": 1_650_000, "SEC": 960_000, "FIN": 500_000},
        )

    def test_somme_ventilations_egale_total(self):
        total = payroll_mass(PAYSLIPS, Q1)
        self.assertEqual(sum(payroll_mass_by_subsidiary(PAYSLIPS, Q1).values()), total)
        self.assertEqual(sum(payroll_mass_by_department(PAYSLIPS, Q1).values()), total)


class CoreHelpersTest(unittest.TestCase):
    def test_safe_ratio(self):
        self.assertEqual(safe_ratio(10, 0), 0.0)
        self.assertEqual(safe_ratio(10, 4), 2.5)

    def test_pct_change(self):
        self.assertEqual(pct_change(0, 5), 0.0)
        self.assertAlmostEqual(pct_change(100, 120), 0.20)
        self.assertAlmostEqual(pct_change(100, 80), -0.20)

    def test_aggregate_by(self):
        out = aggregate_by([("a", 1), ("b", 2), ("a", 3)], lambda x: x[0], lambda x: x[1])
        self.assertEqual(out, {"a": 4, "b": 2})


class SemanticCatalogTest(unittest.TestCase):
    """Ancrage IA : toute métrique calculée doit être déclarée au catalogue (ADR-0007)."""

    def test_metriques_rh_presentes(self):
        for key in ("hr.headcount", "hr.turnover_rate", "hr.payroll_mass"):
            self.assertTrue(CATALOG.has(key), f"{key} absente du catalogue")

    def test_metrique_inconnue_leve(self):
        with self.assertRaises(KeyError):
            CATALOG.get("hr.metrique_inventee")

    def test_unite_coherente(self):
        self.assertEqual(CATALOG.get("hr.payroll_mass").unit, "XOF")
        self.assertEqual(CATALOG.get("hr.turnover_rate").unit, "ratio")


if __name__ == "__main__":
    unittest.main()
