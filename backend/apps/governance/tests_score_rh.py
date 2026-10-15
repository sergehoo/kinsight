"""Score de gouvernance RH sur données réelles.

Remplace les tests du calcul depuis `mart.hr_score` (ADR-0009 : le mart n'est
plus une source des écrans RH, et seul un jeu de démonstration l'alimentait).
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.organizations.models import Subsidiary

from . import score_rh
from .models import Dimension, KpiSnapshot

User = get_user_model()
HIER = timezone.localdate() - timedelta(days=1)


def _jour(jour, presents, absents, retards):
    for m, v in (("hr.presents_jour", presents), ("hr.absents_jour", absents), ("hr.retards_jour", retards)):
        KpiSnapshot.objects.update_or_create(
            jour=jour, source="shield", metric_id=m, dimension=Dimension.GROUPE, code="",
            defaults={"valeur": v, "statut": "measured", "collecte_le": timezone.now()})


class RegleDeConversionTest(SimpleTestCase):
    def test_lineaire_et_bornee(self):
        self.assertEqual(score_rh._lineaire(70, 70, 95), 0.0)
        self.assertEqual(score_rh._lineaire(95, 70, 95), 100.0)
        self.assertEqual(score_rh._lineaire(82.5, 70, 95), 50.0)
        self.assertEqual(score_rh._lineaire(40, 70, 95), 0.0)
        self.assertEqual(score_rh._lineaire(100, 70, 95), 100.0)

    def test_le_plancher_de_presence_est_le_seuil_critique(self):
        from apps.integrations import shield_rules as R

        self.assertEqual(score_rh.PRESENCE_PLANCHER, R.PRESENCE_CRITIQUE)


class ScoreApiTest(APITestCase):
    def setUp(self):
        self.kre = Subsidiary.objects.create(code="KRE", name="Kaydan Real Estate")
        self.drh = User.objects.create_user("drh.s", password=None, role="DRH", is_group_scope=True)
        self.drh_kre = User.objects.create_user("drh.s.kre", password=None, role="DRH", is_group_scope=False)
        self.drh_kre.subsidiaries.add(self.kre)
        self.lecteur = User.objects.create_user("lect.s", password=None, role="READER", is_group_scope=True)
        # 7 jours : 85 % de présence (170/200), 95 % de ponctualité (retards 8,5 sur 170).
        for i in range(1, 8):
            _jour(HIER - timedelta(days=i - 1), 170, 30, 8.5)

    def _score(self, user, **params):
        self.client.force_authenticate(user)
        q = "&".join(f"{k}={v}" for k, v in params.items())
        return self.client.get(f"/api/v1/governance/hr/score/?{q}")

    def test_la_dimension_presence_est_calculee_et_detaillee(self):
        d = self._score(self.drh, periode="7j").json()
        presence = next(x for x in d["dimensions"] if x["key"] == "presence_ponctualite")
        # présence 85 % → (85−70)/25 = 60 ; ponctualité 95 % → (95−85)/14 = 71,4 ; moyenne 65,7
        self.assertEqual(presence["sous_scores"], {"presence": 60.0, "ponctualite": 71.4})
        self.assertEqual(presence["score"], 65.7)
        self.assertEqual(presence["entrees"]["taux_presence"], 85.0)
        self.assertIn("linéaires", presence["formule"])

    def test_les_dimensions_sans_source_sont_n_d_motivees_jamais_zero(self):
        d = self._score(self.drh, periode="7j").json()
        autres = [x for x in d["dimensions"] if x["key"] != "presence_ponctualite"]
        self.assertEqual(len(autres), 8)
        for x in autres:
            self.assertIsNone(x["score"], x["key"])
            self.assertTrue(x["motif"], x["key"])

    def test_pas_de_global_sur_dix_pour_cent_du_poids(self):
        """La renormalisation ferait un « score global » de la seule présence (10 %)."""
        d = self._score(self.drh, periode="7j").json()
        self.assertIsNone(d["global"])
        self.assertFalse(d["available"])
        self.assertEqual(d["couverture"]["poids_couvert"], 10)
        self.assertIn("Couverture insuffisante", d["motif_global"])

    def test_une_periode_trop_peu_couverte_n_est_pas_scoree(self):
        d = self._score(self.drh, periode="30j").json()
        presence = next(x for x in d["dimensions"] if x["key"] == "presence_ponctualite")
        self.assertIsNone(presence["score"])
        self.assertIn("Couverture insuffisante", presence["motif"])

    def test_une_filiale_n_a_pas_la_presence_shield(self):
        d = self._score(self.drh_kre, periode="7j").json()
        presence = next(x for x in d["dimensions"] if x["key"] == "presence_ponctualite")
        self.assertIsNone(presence["score"])
        self.assertIn("Non rattaché", presence["motif"])
        self.assertEqual(d["by_subsidiary"], [])

    def test_droits_et_bornes(self):
        self.assertEqual(self._score(self.lecteur).status_code, 403)
        self.assertEqual(self._score(self.drh, quarter=5).status_code, 400)

    def test_un_filtre_filiale_hors_perimetre_est_refuse(self):
        """Une requête interdite n'est pas un « non mesuré » : 403, sans rien servir."""
        Subsidiary.objects.create(code="KSH", name="K-Shield")
        r = self._score(self.drh_kre, periode="7j", subsidiary="KSH")
        self.assertEqual(r.status_code, 403)
        self.assertNotIn("dimensions", r.json())

    def test_tendance_mensuelle_sans_valeur_inventee(self):
        d = self._score(self.drh, periode="7j").json()
        self.assertEqual(len(d["trend"]), 12)
        self.assertTrue(all(p["score"] is None or 0 <= p["score"] <= 100 for p in d["trend"]))

    def test_lecture_tracee(self):
        from apps.audit.models import AccessLog

        self._score(self.drh, periode="7j")
        self.assertTrue(AccessLog.objects.filter(action="query_hr_score").exists())
