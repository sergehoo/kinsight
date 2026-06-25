"""Réconciliation domaine pur ↔ grain du mart (ADR-0006).

On reconstruit les lignes du mart (`build_hr_kpi_rows`, miroir du SQL dbt) puis on
vérifie que les agrégats issus du mart égalent les calculs directs de `kpi/hr.py`
sur le même jeu de données. Si le SQL dérive, ce test (et celui à brancher côté dbt)
doit échouer.
"""

import unittest
from datetime import date

from k_insight.kpi.core import Period
from k_insight.kpi.hr import (
    entries,
    exits,
    payroll_mass,
    payroll_mass_by_subsidiary,
)
from k_insight.kpi.hr_mart import (
    build_hr_kpi_rows,
    total_payroll_mass,
    total_entries,
    total_exits,
    payroll_by_subsidiary,
)
# Réutilise le jeu de données déjà validé.
from tests.test_hr_kpis import EMPLOYEES, PAYSLIPS, Q1


class ReconciliationTest(unittest.TestCase):
    def setUp(self):
        self.rows = build_hr_kpi_rows(EMPLOYEES, PAYSLIPS)

    def test_masse_salariale_reconcilie(self):
        self.assertEqual(
            total_payroll_mass(self.rows, Q1), payroll_mass(PAYSLIPS, Q1)
        )
        self.assertEqual(total_payroll_mass(self.rows, Q1), 3_110_000)

    def test_entrees_sorties_reconcilient(self):
        self.assertEqual(total_entries(self.rows, Q1), entries(EMPLOYEES, Q1))
        self.assertEqual(total_exits(self.rows, Q1), exits(EMPLOYEES, Q1))
        self.assertEqual(total_entries(self.rows, Q1), 1)
        self.assertEqual(total_exits(self.rows, Q1), 2)

    def test_ventilation_filiale_reconcilie(self):
        self.assertEqual(
            payroll_by_subsidiary(self.rows, Q1),
            payroll_mass_by_subsidiary(PAYSLIPS, Q1),
        )

    def test_hors_periode_exclu(self):
        # Les embauches anciennes (E1 2025, E3 2024…) existent dans les lignes
        # mais ne doivent pas compter dans Q1 2026.
        all_entries = total_entries(self.rows, None)
        self.assertEqual(all_entries, len(EMPLOYEES))  # 1 embauche par employé
        self.assertGreater(all_entries, total_entries(self.rows, Q1))


if __name__ == "__main__":
    unittest.main()
