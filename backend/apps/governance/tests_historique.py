"""Historique RH : collecte idempotente, lecture par période, périmètre.

Les pièges que ces tests verrouillent :
  - un jour non mesuré n'est jamais un zéro ;
  - le taux d'une période est Σ ÷ Σ, pas la moyenne des taux journaliers ;
  - rejouer une collecte ne duplique rien ;
  - un historique Shield n'est servi qu'au Groupe, Odoo par sociétés déclarées ;
  - un filtre filiale ne peut pas élargir le périmètre.
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.integrations.models import DataConnector, DataSource, SourceStatus, SourceType, SyncJob
from apps.organizations.models import Subsidiary

from . import historique as H
from .models import Dimension, KpiSnapshot, StatutMesure

User = get_user_model()
HIER = timezone.localdate() - timedelta(days=1)


def _ligne(jour, site, kind):
    return {"date": jour.isoformat(), "site": site, "holder_kind": kind}


class _FauxClient:
    def results(self, path, params=None, limit=None):
        return [{"id": 1, "name": "Chantier A"}, {"id": 2, "name": "Siège"}]


def _periode(jour, presents, absents, retards, *, tronquee=False, erreurs=None):
    return {"rows": {"present": presents, "absent": absents, "late": retards},
            "errors": erreurs or {}, "truncated": tronquee, "cutoff": None}


def _poser(metric_id, jour, valeur, *, source="shield", dimension=Dimension.GROUPE, code="",
           statut=StatutMesure.MESURE):
    KpiSnapshot.objects.update_or_create(
        jour=jour, source=source, metric_id=metric_id, dimension=dimension, code=code,
        defaults={"valeur": valeur if statut == StatutMesure.MESURE else None,
                  "statut": statut, "collecte_le": timezone.now()})


class CollectePresenceTest(TestCase):
    def setUp(self):
        cache.clear()
        self.source = DataSource.objects.create(name="Kaydan Shield", slug="kaydan-shield",
                                                source_type=SourceType.KAYDAN_SHIELD, target_module="rh",
                                                status=SourceStatus.CONNECTED)
        for cible, valeur in (("apps.integrations.shield._guard", (self.source, None)),
                              ("apps.integrations.shield.build_client", _FauxClient())):
            correctif = patch(cible, return_value=valeur)
            correctif.start()
            self.addCleanup(correctif.stop)

    def _collecter(self, periode, jour=HIER):
        with patch("apps.integrations.shield.collect_period", return_value=periode):
            return H.collecter_presence_shield(jour)

    def _jour_type(self, jour=HIER):
        return _periode(
            jour,
            [_ligne(jour, 1, "worker")] * 6 + [_ligne(jour, 2, "employee")] * 2,
            [_ligne(jour, 1, "worker")] * 2,
            [_ligne(jour, 1, "worker")],
        )

    def _valeur(self, metric_id, dimension=Dimension.GROUPE, code=""):
        return KpiSnapshot.objects.get(jour=HIER, metric_id=metric_id, dimension=dimension, code=code).valeur

    def test_une_passe_donne_groupe_sites_et_types(self):
        self._collecter(self._jour_type())
        self.assertEqual(self._valeur("hr.presents_jour"), 8)
        self.assertEqual(self._valeur("hr.absents_jour"), 2)
        self.assertEqual(self._valeur("hr.retards_jour"), 1)
        self.assertEqual(self._valeur("hr.presents_jour", Dimension.SITE, "1"), 6)
        self.assertEqual(self._valeur("hr.absents_jour", Dimension.SITE, "2"), 0)
        self.assertEqual(self._valeur("hr.presents_jour", Dimension.TYPE, "worker"), 6)
        self.assertEqual(self._valeur("hr.absents_jour", Dimension.TYPE, "employee"), 0)
        self.assertEqual(self._valeur("hr.presents_ouvriers_jour"), 6)
        site = KpiSnapshot.objects.filter(dimension=Dimension.SITE, code="1").first()
        self.assertEqual(site.libelle, "Chantier A")

    def test_rejouer_ne_duplique_rien_et_met_a_jour(self):
        self._collecter(self._jour_type())
        avant = KpiSnapshot.objects.count()
        corrige = self._jour_type()
        corrige["rows"]["present"] = corrige["rows"]["present"][:5]
        self._collecter(corrige)
        self.assertEqual(KpiSnapshot.objects.count(), avant)
        self.assertEqual(self._valeur("hr.presents_jour"), 5)

    def test_une_journee_tronquee_est_inconnue_pas_nulle(self):
        bilan = self._collecter(_periode(HIER, [], [], [], tronquee=True))
        self.assertEqual(bilan.statut, "partial")
        lignes = KpiSnapshot.objects.filter(jour=HIER, dimension=Dimension.GROUPE)
        self.assertTrue(lignes.exists())
        self.assertTrue(all(l.valeur is None and l.statut == StatutMesure.INCONNU for l in lignes))

    def test_aujourd_hui_ne_s_historise_pas(self):
        with self.assertRaises(ValueError):
            self._collecter(self._jour_type(), jour=timezone.localdate())

    def test_deux_collectes_simultanees_de_la_meme_journee(self):
        cache.add(f"historique:verrou:shield:presence:{HIER.isoformat()}", 1, 60)
        with self.assertRaises(H.CollecteEnCours):
            self._collecter(self._jour_type())

    def test_la_tache_trace_son_execution(self):
        from .tasks import executer

        with patch("apps.integrations.shield.collect_period", return_value=self._jour_type()):
            bilan = executer("shield", "test", lambda t: H.collecter_presence_shield(HIER, tache=t))
        job = SyncJob.objects.get(source=self.source)
        self.assertEqual(job.status, "success")
        self.assertEqual(job.rows_ingested, bilan.ecrites)
        self.assertTrue(KpiSnapshot.objects.filter(tache=job).exists())

    def test_une_collecte_verrouillee_est_tracee_comme_sautee(self):
        from .tasks import executer

        cache.add(f"historique:verrou:shield:presence:{HIER.isoformat()}", 1, 60)
        bilan = executer("shield", "test", lambda t: H.collecter_presence_shield(HIER, tache=t))
        self.assertEqual(bilan.statut, "skipped")
        self.assertEqual(SyncJob.objects.get(source=self.source).status, "error")


class ContraintesTest(TestCase):
    def test_une_valeur_mesuree_ne_peut_pas_etre_nulle(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            KpiSnapshot.objects.create(jour=HIER, source="shield", metric_id="hr.presents_jour",
                                       valeur=None, statut=StatutMesure.MESURE, collecte_le=timezone.now())

    def test_le_grain_est_unique(self):
        _poser("hr.presents_jour", HIER, 10)
        with self.assertRaises(IntegrityError), transaction.atomic():
            KpiSnapshot.objects.create(jour=HIER, source="shield", metric_id="hr.presents_jour",
                                       valeur=11, collecte_le=timezone.now())


class AgregationTest(TestCase):
    def setUp(self):
        self.j1, self.j2, self.j3 = HIER - timedelta(days=2), HIER - timedelta(days=1), HIER
        self.p = H.Periode(self.j1, self.j3)

    def test_le_taux_de_periode_est_un_rapport_de_sommes(self):
        """Jour 1 : 10 présents / 100 (10 %). Jour 2 : 700 / 700 (100 %). La moyenne
        des taux dirait 55 % ; la période réelle est 710 / 800 = 88,8 %."""
        for jour, p, a in ((self.j1, 10, 90), (self.j2, 700, 0)):
            _poser("hr.presents_jour", jour, p)
            _poser("hr.absents_jour", jour, a)
        r = H.agreger("hr.taux_presence_jour", H.Periode(self.j1, self.j2))
        self.assertEqual(r["value"], 88.8)

    def test_un_jour_inconnu_ne_pese_pas(self):
        _poser("hr.presents_jour", self.j1, 80)
        _poser("hr.absents_jour", self.j1, 20)
        _poser("hr.presents_jour", self.j2, None, statut=StatutMesure.INCONNU)
        _poser("hr.absents_jour", self.j2, None, statut=StatutMesure.INCONNU)
        r = H.agreger("hr.taux_presence_jour", self.p)
        self.assertEqual(r["value"], 80.0)
        self.assertEqual(r["couverture"], {"jours": 3, "jours_mesures": 1})
        points = H.serie("hr.taux_presence_jour", self.p)
        self.assertEqual([pt["status"] for pt in points], ["measured", "unknown", "unknown"])
        self.assertIsNone(points[1]["value"])

    def test_aucune_mesure_aucune_valeur(self):
        r = H.agreger("hr.taux_presence_jour", self.p)
        self.assertIsNone(r["value"])
        self.assertEqual(r["status"], "unknown")

    def test_ponctualite_est_le_complement(self):
        _poser("hr.presents_jour", self.j1, 200)
        _poser("hr.retards_jour", self.j1, 10)
        self.assertEqual(H.agreger("hr.taux_ponctualite_jour", self.p)["value"], 95.0)

    def test_stock_derniere_valeur_et_comptage_moyenne(self):
        _poser("hr.effectif_total", self.j1, 800)
        _poser("hr.effectif_total", self.j3, 812)
        self.assertEqual(H.agreger("hr.effectif_total", self.p)["value"], 812)
        _poser("hr.retards_jour", self.j1, 10)
        _poser("hr.retards_jour", self.j2, 20)
        self.assertEqual(H.agreger("hr.retards_jour", self.p)["value"], 15.0)

    def test_comparaison_en_points_pour_un_taux(self):
        actuel = {"value": 80.0, "debut": "x", "fin": "y"}
        ref = {"value": 90.0, "debut": "a", "fin": "b", "couverture": {}}
        c = H.comparer(actuel, ref, est_taux=True)
        self.assertEqual((c["ecart"], c["unite_ecart"], c["ecart_pct"]), (-10.0, "pts", None))
        c2 = H.comparer({"value": 110}, {"value": 100}, est_taux=False)
        self.assertEqual(c2["ecart_pct"], 10.0)
        self.assertIsNone(H.comparer({"value": 1}, {"value": None}, est_taux=False)["ecart"])

    def test_somme_de_societes_inconnue_si_une_manque(self):
        _poser("hr.employes_actifs_odoo", self.j1, 30, source="odoo", dimension=Dimension.SOCIETE, code="3")
        _poser("hr.employes_actifs_odoo", self.j1, 10, source="odoo", dimension=Dimension.SOCIETE, code="4")
        _poser("hr.employes_actifs_odoo", self.j2, 31, source="odoo", dimension=Dimension.SOCIETE, code="3")
        points = H.serie("hr.employes_actifs_odoo", H.Periode(self.j1, self.j2),
                         dimension=Dimension.SOCIETE, codes=["3", "4"])
        self.assertEqual(points[0]["value"], 40)
        self.assertIsNone(points[1]["value"], "une société absente ce jour-là : total inconnu")

    def test_periodes_de_reference(self):
        t3 = H.Periode(date(2026, 7, 1), date(2026, 9, 30), "trimestre")
        self.assertEqual(t3.precedente(), H.Periode(date(2026, 4, 1), date(2026, 6, 30), "trimestre"))
        self.assertEqual(t3.annee_precedente(), H.Periode(date(2025, 7, 1), date(2025, 9, 30), "trimestre"))
        t1 = H.Periode(date(2026, 1, 1), date(2026, 3, 31), "trimestre")
        self.assertEqual(t1.precedente().debut, date(2025, 10, 1), "T1 recule sur le T4 de l'an passé")

    def test_un_trimestre_en_cours_se_compare_a_date(self):
        """T4 lu au 13 octobre : 13 jours. On les compare aux 13 premiers jours de
        T3, pas au T3 entier — sinon tout trimestre en cours « chute »."""
        t4 = H.Periode(date(2026, 10, 1), date(2026, 10, 13), "trimestre")
        self.assertEqual(t4.precedente(), H.Periode(date(2026, 7, 1), date(2026, 7, 13), "trimestre"))

    def test_une_fenetre_glisse_de_sa_longueur(self):
        f = H.Periode(date(2026, 10, 7), date(2026, 10, 13))
        self.assertEqual(f.precedente(), H.Periode(date(2026, 9, 30), date(2026, 10, 6)))


class HistoriqueApiTest(APITestCase):
    def setUp(self):
        cache.clear()
        self.kre = Subsidiary.objects.create(code="KRE", name="Kaydan Real Estate")
        self.drh = User.objects.create_user("drh.h", password=None, role="DRH", is_group_scope=True)
        self.drh_kre = User.objects.create_user("drh.h.kre", password=None, role="DRH", is_group_scope=False)
        self.drh_kre.subsidiaries.add(self.kre)
        self.lecteur = User.objects.create_user("lect.h", password=None, role="READER", is_group_scope=True)
        for i in range(7):
            jour = HIER - timedelta(days=i)
            _poser("hr.presents_jour", jour, 80)
            _poser("hr.absents_jour", jour, 20)
        _poser("hr.presents_jour", HIER - timedelta(days=7), 60)
        _poser("hr.absents_jour", HIER - timedelta(days=7), 40)
        patch_live = patch("apps.governance.history_views.resoudre",
                           return_value={"value": 640, "status": "connected"})
        patch_live.start()
        self.addCleanup(patch_live.stop)

    def _get(self, user, **params):
        self.client.force_authenticate(user)
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return self.client.get(f"/api/v1/governance/hr/history/?{query}")

    def test_sept_jours_avec_comparaison_et_aujourd_hui_live(self):
        r = self._get(self.drh, metric="hr.taux_presence_jour", periode="7j")
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertEqual(d["valeur"]["value"], 80.0)
        self.assertEqual(d["periode"]["fin"], HIER.isoformat())
        self.assertEqual(len(d["points"]), 7)
        self.assertEqual(d["aujourd_hui"]["value"], 640)
        precedente = d["comparaisons"]["precedente"]
        self.assertEqual(precedente["value"], 60.0)        # seul le 8e jour est mesuré
        self.assertEqual(precedente["ecart"], 20.0)
        self.assertEqual(precedente["unite_ecart"], "pts")

    def test_le_lecteur_n_a_pas_l_historique_rh(self):
        self.assertEqual(self._get(self.lecteur, metric="hr.presents_jour").status_code, 403)

    def test_une_filiale_n_a_pas_l_historique_shield(self):
        d = self._get(self.drh_kre, metric="hr.taux_presence_jour", periode="7j").json()
        self.assertEqual(d["status"], "disconnected")
        self.assertIn("Non rattaché", d["reason"])
        self.assertEqual(d["points"], [])

    def test_un_filtre_filiale_ne_rend_pas_le_total_groupe(self):
        d = self._get(self.drh, metric="hr.presents_jour", subsidiary="KRE").json()
        self.assertEqual(d["status"], "disconnected")
        self.assertNotIn("valeur", d)

    def test_un_filtre_ne_peut_pas_elargir_le_perimetre(self):
        Subsidiary.objects.create(code="KSH", name="Kaydan Shield")
        r = self._get(self.drh_kre, metric="hr.employes_actifs_odoo", subsidiary="KSH")
        self.assertEqual(r.status_code, 403)

    def test_une_filiale_lit_la_somme_de_ses_societes_odoo(self):
        source = DataSource.objects.create(name="Odoo RH", slug="odoo-hr", source_type=SourceType.ODOO_HR,
                                           target_module="rh", status=SourceStatus.CONNECTED)
        DataConnector.objects.create(source=source, base_url="https://rh.kaydan.tech",
                                     config={"company_mapping": {"3": "KRE", "4": "KRE", "5": "KSH"}})
        for code, v in (("3", 30), ("4", 10), ("5", 999)):
            _poser("hr.employes_actifs_odoo", HIER, v, source="odoo", dimension=Dimension.SOCIETE, code=code)
        d = self._get(self.drh_kre, metric="hr.employes_actifs_odoo", periode="7j").json()
        self.assertEqual(d["valeur"]["value"], 40)

    def test_bornes_de_periode(self):
        self.assertEqual(self._get(self.drh, metric="hr.presents_jour", periode="trimestre",
                                   year=2026, quarter=5).status_code, 400)
        futur = self._get(self.drh, metric="hr.presents_jour", periode="annee", year=2099).json()
        self.assertIn("n'a pas encore commencé", futur["reason"])
        trop_long = self._get(self.drh, metric="hr.presents_jour", periode="personnalisee",
                              date_from="2024-01-01", date_to="2026-01-01")
        self.assertEqual(trop_long.status_code, 400)

    def test_ventilation_par_site_classee(self):
        for code, p, a in (("1", 50, 50), ("2", 90, 10)):
            _poser("hr.presents_jour", HIER, p, dimension=Dimension.SITE, code=code)
            _poser("hr.absents_jour", HIER, a, dimension=Dimension.SITE, code=code)
        d = self._get(self.drh, metric="hr.taux_presence_jour", periode="7j", ventilation="site").json()
        self.assertEqual([l["code"] for l in d["ventilation"]], ["2", "1"])
        self.assertEqual(d["ventilation"][0]["value"], 90.0)

    def test_metrique_sans_source(self):
        d = self._get(self.drh, metric="hr.turnover").json()
        self.assertEqual(d["status"], "disconnected")
        self.assertTrue(d["reason"])

    def test_la_lecture_est_tracee(self):
        from apps.audit.models import AccessLog

        self._get(self.drh, metric="hr.presents_jour", periode="30j")
        trace = AccessLog.objects.filter(action="query_hr_history").last()
        self.assertEqual(trace.metric_key, "hr.presents_jour")
        self.assertEqual(trace.payload["periode"], "30 derniers jours")
