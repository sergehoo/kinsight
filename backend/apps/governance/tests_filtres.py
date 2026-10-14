"""Filtres du cockpit RH : un filtre agit, ou il dit pourquoi il ne peut pas.

Aucun filtre décoratif : chaque test vérifie que le filtre CHANGE la valeur
servie — ou qu'il rend la carte N/D avec un motif, jamais le total Groupe sous
l'étiquette du filtre.
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.organizations.models import Subsidiary

from . import filtres as F
from .models import Dimension, KpiSnapshot, StatutMesure

User = get_user_model()
AUJ = timezone.localdate()
HIER = AUJ - timedelta(days=1)


def _poser(metric_id, jour, valeur, dimension=Dimension.GROUPE, code="", libelle=""):
    KpiSnapshot.objects.update_or_create(
        jour=jour, source="shield", metric_id=metric_id, dimension=dimension, code=code,
        defaults={"valeur": valeur, "statut": StatutMesure.MESURE, "libelle": libelle,
                  "collecte_le": timezone.now()})


CHARGE = {
    "status": "connected", "source": "Kaydan Shield",
    "kpis": [{"key": "presents", "value": 640, "status": "connected"},
             {"key": "absents", "value": 160, "status": "connected"},
             {"key": "retards", "value": 32, "status": "connected"},
             {"key": "taux_presence", "value": 80.0, "status": "connected"},
             {"key": "effectif_total", "value": 812, "status": "connected"}],
    "by_kind": {"status": "connected", "employees": 240, "workers": 400},
    "by_site": {"status": "connected", "sites": [
        {"site": {"id": 1, "name": "Chantier A"}, "present": 50, "absent": 50, "late": 5}]},
}


class LectureDesFiltresTest(SimpleTestCase):
    def test_defaut_trimestre_courant_et_pas_t1_2026(self):
        f = F.lire({}, date(2026, 10, 14))
        self.assertEqual(f.libelle, "T4 2026 à date")
        self.assertEqual((f.periode.debut, f.periode.fin), (date(2026, 10, 1), date(2026, 10, 13)))

    def test_fenetres_et_annee(self):
        self.assertEqual(F.lire({"periode": "90j"}, date(2026, 10, 14)).periode.jours, 90)
        a = F.lire({"periode": "annee", "year": "2025"}, date(2026, 10, 14))
        self.assertEqual((a.periode.debut, a.periode.fin, a.libelle),
                         (date(2025, 1, 1), date(2025, 12, 31), "Année 2025"))

    def test_entrees_invalides(self):
        for params in ({"quarter": "5"}, {"periode": "x"}, {"periode": "personnalisee", "date_from": "2026-02-01",
                                                              "date_to": "2026-01-01"}, {"type": "cadre"}):
            with self.subTest(params=params), self.assertRaises(F.FiltreInvalide):
                F.lire(params, date(2026, 10, 14))

    def test_toutes_filiales_n_est_pas_un_filtre(self):
        self.assertIsNone(F.lire({"subsidiary": "all"}, date(2026, 10, 14)).subsidiary)


class ModuleSousFiltresTest(APITestCase):
    def setUp(self):
        cache.clear()
        self.kre = Subsidiary.objects.create(code="KRE", name="Kaydan Real Estate")
        self.drh = User.objects.create_user("drh.f", password=None, role="DRH", is_group_scope=True)
        self.drh_kre = User.objects.create_user("drh.f.kre", password=None, role="DRH", is_group_scope=False)
        self.drh_kre.subsidiaries.add(self.kre)
        correctif = patch("apps.integrations.shield.fetch_hr_kpis", side_effect=lambda: dict(CHARGE))
        correctif.start()
        self.addCleanup(correctif.stop)
        # 7 jours de présence : Groupe, le site 1 et les deux types.
        for i in range(1, 15):
            jour = AUJ - timedelta(days=i)
            g = (80, 20) if i <= 7 else (60, 40)
            _poser("hr.presents_jour", jour, g[0])
            _poser("hr.absents_jour", jour, g[1])
            _poser("hr.presents_jour", jour, 30, Dimension.SITE, "1", "Chantier A")
            _poser("hr.absents_jour", jour, 70, Dimension.SITE, "1", "Chantier A")
            _poser("hr.presents_jour", jour, 50, Dimension.TYPE, "worker", "Ouvriers")
            _poser("hr.absents_jour", jour, 5, Dimension.TYPE, "worker", "Ouvriers")

    def _carte(self, user, libelle, **params):
        self.client.force_authenticate(user)
        query = "&".join(f"{k}={v}" for k, v in params.items())
        r = self.client.get(f"/api/v1/governance/module/hr-attendance/?{query}")
        return r if libelle is None else r.json()["values"][libelle]

    def test_la_periode_change_la_valeur_et_le_live_reste_marque(self):
        c = self._carte(self.drh, "Taux de présence", periode="7j")
        self.assertEqual(c["value"], 80.0)
        self.assertEqual(c["precedente"]["value"], 60.0)
        self.assertEqual(c["precedente"]["ecart"], 20.0)
        self.assertEqual(c["aujourd_hui"]["value"], 80.0)
        self.assertEqual(c["periode"]["libelle"], "7 derniers jours")
        c14 = self._carte(self.drh, "Taux de présence", periode="personnalisee",
                          date_from=(AUJ - timedelta(days=14)).isoformat(), date_to=HIER.isoformat())
        self.assertEqual(c14["value"], 70.0, "la période change bien la valeur")

    def test_le_filtre_site_agit_sur_la_periode_et_le_live(self):
        c = self._carte(self.drh, "Taux de présence", periode="7j", site="1")
        self.assertEqual(c["value"], 30.0)
        self.assertEqual(c["aujourd_hui"]["value"], 50.0)   # 50 / (50 + 50), répartition du jour

    def test_un_filtre_inapplicable_rend_n_d_et_pas_le_total(self):
        self.client.force_authenticate(self.drh)
        r = self.client.get("/api/v1/governance/module/hr-executive/?periode=7j&site=1").json()
        effectif = r["values"]["Effectif total"]
        self.assertIsNone(effectif["value"])
        self.assertIn("Non ventilé par site", effectif["reason"])
        self.assertIsNone(effectif["aujourd_hui"]["value"], "le live non plus ne rend pas le total")

    def test_le_filtre_type_agit(self):
        c = self._carte(self.drh, "Présents", periode="7j", type="worker")
        self.assertEqual(c["value"], 50.0)
        self.assertEqual(c["aujourd_hui"]["value"], 400)
        absents = self._carte(self.drh, "Absents", periode="7j", type="worker")
        self.assertEqual(absents["value"], 5.0)
        self.assertIsNone(absents["aujourd_hui"]["value"], "Shield ne sert pas les absents par type en direct")

    def test_site_et_type_ne_se_croisent_pas(self):
        self.assertEqual(self._carte(self.drh, None, site="1", type="worker").status_code, 400)

    def test_une_filiale_hors_perimetre_est_refusee(self):
        Subsidiary.objects.create(code="KSH", name="K-Shield")
        self.assertEqual(self._carte(self.drh_kre, None, subsidiary="KSH").status_code, 403)

    def test_une_periode_future_rend_n_d_motive(self):
        c = self._carte(self.drh, "Présents", periode="annee", year=2099)
        self.assertIsNone(c["value"])
        self.assertIn("pas encore commencé", c["reason"])

    def test_les_options_de_filtres_viennent_de_l_historique(self):
        self.client.force_authenticate(self.drh)
        d = self.client.get("/api/v1/governance/hr/dimensions/").json()
        self.assertEqual(d["site"], [{"code": "1", "libelle": "Chantier A"}])
        self.assertEqual([t["code"] for t in d["type"]], ["worker"])
        self.client.force_authenticate(self.drh_kre)
        restreint = self.client.get("/api/v1/governance/hr/dimensions/").json()
        self.assertEqual(restreint["site"], [])
        self.assertIn("Groupe", restreint["restriction"])
