"""Régression prod (2026-10-15) : « la connexion est établie mais les données ne
remontent plus », pour un compte « Super Admin ».

Un superutilisateur créé par `createsuperuser` n'a pas la case « périmètre
groupe » cochée (défaut False) et n'a aucune filiale : `User.scope()` rendait un
périmètre VIDE. Depuis ADR-0009, un total Shield n'est servi qu'au périmètre
Groupe — l'administrateur recevait donc partout N/D et « Non rattaché », alors
que la source était connectée. L'accès total d'un administrateur vaut aussi pour
le périmètre ; un RH de filiale, lui, reste restreint.
"""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import checks
from django.core.cache import cache
from django.core.management import call_command
from rest_framework.test import APITestCase

from apps.audit.models import AccessLog
from apps.governance.tests_historique import HIER, _poser
from apps.organizations.models import Subsidiary

User = get_user_model()
CHARGE = {"status": "connected", "source": "Kaydan Shield",
          "kpis": [{"key": "effectif_total", "title": "Effectif total", "value": 640, "status": "connected"}]}


class PerimetreAdministrateurTest(APITestCase):
    def setUp(self):
        cache.clear()
        self.kre = kre = Subsidiary.objects.create(code="KRE", name="Kaydan Real Estate")
        # Exactement le compte de prod : createsuperuser, sans case « groupe ».
        self.root = User.objects.create_superuser("root", "root@k.co", "x")
        self.admin_ca = User.objects.create_user("ca", password="x", role="ADMIN_CA", is_group_scope=False)
        self.drh_kre = User.objects.create_user("drh.kre", password="x", role="DRH", is_group_scope=False)
        self.drh_kre.subsidiaries.add(kre)
        _poser("hr.presents_jour", HIER, 80)
        _poser("hr.absents_jour", HIER, 20)

    def test_un_administrateur_a_le_perimetre_groupe(self):
        self.assertFalse(self.root.is_group_scope, "le compte reproduit bien celui de la prod")
        self.assertTrue(self.root.scope().is_group)
        self.assertTrue(self.admin_ca.scope().is_group)
        self.assertFalse(self.drh_kre.scope().is_group, "un RH de filiale reste restreint")

    def test_les_chiffres_shield_remontent_pour_l_administrateur(self):
        with patch("apps.integrations.views.fetch_hr_kpis", return_value=CHARGE):
            self.client.force_authenticate(self.root)
            admin = self.client.get("/api/v1/integrations/shield/hr-kpi/").json()
            self.client.force_authenticate(self.drh_kre)
            filiale = self.client.get("/api/v1/integrations/shield/hr-kpi/").json()
        effectif = {k["key"]: k for k in admin["kpis"]}["effectif_total"]
        self.assertEqual(effectif["value"], 640)
        self.assertNotIn("restriction", admin)
        # Aucune fuite rouverte : la filiale ne reçoit toujours pas le total Groupe.
        self.assertIsNone({k["key"]: k for k in filiale["kpis"]}["effectif_total"]["value"])

    def test_l_historique_n_est_plus_non_rattache(self):
        self.client.force_authenticate(self.root)
        d = self.client.get("/api/v1/governance/hr/history/?metric=hr.taux_presence_jour&periode=7j").json()
        self.assertEqual(d["valeur"]["value"], 80.0)

    def test_le_profil_annonce_le_groupe(self):
        self.client.force_authenticate(self.root)
        self.assertEqual(self.client.get("/api/v1/auth/me/").json()["scope"], "GROUP")

    def test_la_lecture_admin_est_tracee_au_perimetre_groupe(self):
        AccessLog.objects.all().delete()
        with patch("apps.integrations.views.fetch_hr_kpis", return_value=CHARGE):
            self.client.force_authenticate(self.root)
            self.client.get("/api/v1/integrations/shield/hr-kpi/")
        self.assertEqual(AccessLog.objects.order_by("-occurred_at").first().subsidiary_scope, ["*"])

    # ── Anti-fuite : un périmètre EXPLICITE l'emporte toujours ─────────────────

    def test_un_superutilisateur_rattache_a_une_filiale_reste_restreint(self):
        rh_admin = User.objects.create_superuser("rh.admin", "rh@k.co", "x")
        rh_admin.subsidiaries.add(self.kre)
        self.assertFalse(rh_admin.scope().is_group)
        with patch("apps.integrations.views.fetch_hr_kpis", return_value=CHARGE):
            self.client.force_authenticate(rh_admin)
            charge = self.client.get("/api/v1/integrations/shield/hr-kpi/").json()
        self.assertIsNone({k["key"]: k for k in charge["kpis"]}["effectif_total"]["value"])

    def test_un_directeur_de_filiale_superutilisateur_reste_restreint(self):
        directeur = User.objects.create_superuser("dir.admin", "d@k.co", "x", role="DIR_FILIALE",
                                                  is_group_scope=True)
        directeur.subsidiaries.add(self.kre)
        self.assertEqual((directeur.scope().is_group, set(directeur.scope().subsidiaries)), (False, {"KRE"}))
        sans_filiale = User.objects.create_superuser("dir.vide", "v@k.co", "x", role="DIR_FILIALE")
        self.assertFalse(sans_filiale.scope().is_group, "un directeur sans filiale ne voit rien, jamais le Groupe")

    def test_un_admin_ca_rattache_a_une_filiale_reste_restreint(self):
        ca_kre = User.objects.create_user("ca.kre", password="x", role="ADMIN_CA")
        ca_kre.subsidiaries.add(self.kre)
        self.assertFalse(ca_kre.scope().is_group)

    def test_un_dg_sans_perimetre_n_est_pas_elargi_mais_signale(self):
        """DG / CODIR peuvent être volontairement limités : on ne les élargit pas,
        on le SIGNALE (check système, admin, commande)."""
        dg = User.objects.create_user("dg.vide", password="x", role="DG_GROUP")
        dg_kre = User.objects.create_user("dg.kre", password="x", role="DG_GROUP")
        dg_kre.subsidiaries.add(self.kre)
        self.assertFalse(dg.scope().is_group)
        alertes = [m for m in checks.run_checks() if m.id == "accounts.W001"]
        self.assertEqual([m.obj for m in alertes], ["dg.vide"])
        sortie = StringIO()
        call_command("admin_access", "dg.vide", stdout=sortie)
        self.assertIn("périmètre effectif : AUCUN", sortie.getvalue())
