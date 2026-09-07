"""L'admin Django se charge-t-il vraiment ?

`manage.py check` valide les noms de champs déclarés, pas l'exécution : une méthode
d'affichage qui lève, une annotation absente du queryset ou un déchiffrement qui
échoue passent les contrôles et cassent la page. Ces tests ouvrent donc réellement
chaque liste et chaque fiche.

Ils vérifient aussi les deux garde-fous qui comptent : qu'aucun secret ne fuit dans
une page, et qu'une piste d'audit refuse l'écriture.
"""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.ai_copilot.models import (
    AIActionApproval,
    AIActionRequest,
    AIAuditLog,
    AIAutomation,
    AIConversation,
    AIMessage,
    AIProvider,
    AITool,
    AIToolExecution,
)
from apps.audit.models import AccessLog
from apps.integrations.models import (
    ConnectorCredential,
    ConnectorEndpoint,
    DataConnector,
    DataSource,
    ExternalIdentity,
    FieldMapping,
    Person,
    SourceType,
    SyncError,
    SyncJob,
    SyncLog,
    WebhookEvent,
)
from apps.organizations.models import Subsidiary

User = get_user_model()

SECRET = "jeton-tres-secret-admin-42"

# La production sert les statiques via un stockage à empreintes (whitenoise), qui
# exige un manifeste produit par `collectstatic`. Il n'en existe pas en test, et
# chaque `{% static %}` des gabarits d'admin lèverait alors — un échec de
# plomberie qui masquerait ce que ces tests cherchent réellement à vérifier.
SANS_MANIFESTE = override_settings(
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
)


@SANS_MANIFESTE
class AdminChargementTest(TestCase):
    """Chaque liste d'administration s'ouvre-t-elle, sur table vide comme peuplée ?"""

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_superuser(username="admin-test", password="x",
                                                  email="a@k.co")
        filiale = Subsidiary.objects.create(code="KSH", name="K-Shield")
        cls.staff.subsidiaries.add(filiale)

        source = DataSource.objects.create(name="Kaydan Shield", slug="kaydan-shield",
                                           source_type=SourceType.KAYDAN_SHIELD,
                                           target_module="rh", created_by=cls.staff)
        connecteur = DataConnector.objects.create(source=source,
                                                  base_url="https://api.kaydanshield.test/api/v1")
        endpoint = ConnectorEndpoint.objects.create(connector=connecteur, name="Employés",
                                                    path="/api/v1/employees/employees/")
        FieldMapping.objects.create(endpoint=endpoint, source_field="id", target_field="employee_key")
        cred = ConnectorCredential(connector=connecteur, kind="api_token", label="Jeton Shield")
        cred.set_secret(SECRET)
        cred.save()
        cls.cred = cred

        job = SyncJob.objects.create(source=source, status="success", rows_ingested=12)
        SyncLog.objects.create(source=source, job=job, level="info",
                               message="Ligne de journal\nsur deux lignes, " + "x" * 200)
        cls.erreur = SyncError.objects.create(source=source, job=job, code="E42",
                                             message="Message d'erreur " + "y" * 200)
        WebhookEvent.objects.create(source=source, payload={"a": 1}, signature_valid=True)

        personne = Person.objects.create(display_name="Aya Koné", kind="employee")
        ExternalIdentity.objects.create(person=personne, source="kaydan_shield",
                                        external_id="EMP-1", payload={"brut": True})

        AccessLog.record(user=cls.staff, action="view_dashboard", metric_key="effectif_total",
                         ip="10.0.0.1", payload={"note": "test"})

        AIProvider.objects.create(name="anthropic", kind="anthropic", model_name="claude-opus-5")
        AITool.objects.create(name="lire_kpi", description="Lecture d'un indicateur", sensitive=False)
        conv = AIConversation.objects.create(user=cls.staff, title="Analyse RH")
        AIMessage.objects.create(conversation=conv, role="user",
                                 content="Question longue " + "z" * 300)
        AIToolExecution.objects.create(tool_name="lire_kpi", user=cls.staff, status="error",
                                       error="Échec " + "w" * 200)
        demande = AIActionRequest.objects.create(user=cls.staff, tool_name="purger",
                                                summary="Purge " + "v" * 200, destructive=True,
                                                required_confirmations=2)
        AIActionApproval.objects.create(request=demande, approver=cls.staff, decision="approved")
        AIAutomation.objects.create(name="Veille quotidienne", tool_name="lire_kpi",
                                    created_by=cls.staff)
        AIAuditLog.record(user=cls.staff, action="chat", provider="anthropic",
                          latency_ms=120, ip="10.0.0.1")

    def setUp(self):
        self.client.force_login(self.staff)

    def test_tous_les_modeles_du_projet_sont_enregistres(self):
        """Le but de la mission : plus aucun modèle absent de l'admin."""
        from django.apps import apps as configs

        enregistres = set(admin.site._registry)
        manquants = [
            f"{cfg.label}.{m.__name__}"
            for cfg in configs.get_app_configs() if cfg.name.startswith("apps.")
            for m in cfg.get_models() if m not in enregistres
        ]
        self.assertEqual(manquants, [], f"modèles absents de l'admin : {manquants}")

    def test_index_de_ladmin(self):
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_chaque_liste_souvre(self):
        """Une méthode d'affichage qui lève ne se voit qu'en chargeant la page."""
        for modele in admin.site._registry:
            meta = modele._meta
            url = reverse(f"admin:{meta.app_label}_{meta.model_name}_changelist")
            with self.subTest(modele=modele.__name__):
                self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_chaque_fiche_souvre(self):
        """Les fiches exercent les inlines, les champs en lecture seule et les JSON."""
        for modele in admin.site._registry:
            instance = modele.objects.first()
            if instance is None:
                continue
            meta = modele._meta
            url = reverse(f"admin:{meta.app_label}_{meta.model_name}_change", args=[instance.pk])
            with self.subTest(modele=modele.__name__):
                self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_recherche_et_tri_ne_cassent_pas(self):
        """Les tris portant sur une annotation ne survivent pas toujours au clic."""
        for modele, options in admin.site._registry.items():
            meta = modele._meta
            url = reverse(f"admin:{meta.app_label}_{meta.model_name}_changelist")
            with self.subTest(modele=modele.__name__):
                if options.search_fields:
                    self.assertEqual(self.client.get(url, {"q": "shield"}).status_code, 200)
                self.assertEqual(self.client.get(url, {"o": "1"}).status_code, 200)


@SANS_MANIFESTE
class AdminSecretTest(TestCase):
    """Aucun secret ne doit apparaître dans une page d'administration."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_superuser(username="admin-secret", password="x",
                                                  email="s@k.co")
        source = DataSource.objects.create(name="Shield", slug="kaydan-shield",
                                           source_type=SourceType.KAYDAN_SHIELD)
        connecteur = DataConnector.objects.create(source=source, base_url="https://x.test")
        cred = ConnectorCredential(connector=connecteur, kind="api_token", label="Jeton")
        cred.set_secret(SECRET)
        cred.save()
        cls.cred = cred
        cls.connecteur = connecteur

    def setUp(self):
        self.client.force_login(self.staff)

    def _pages(self):
        return [
            reverse("admin:integrations_connectorcredential_changelist"),
            reverse("admin:integrations_connectorcredential_change", args=[self.cred.pk]),
            reverse("admin:integrations_dataconnector_change", args=[self.connecteur.pk]),
        ]

    def test_ni_le_clair_ni_le_chiffre_napparaissent(self):
        for url in self._pages():
            corps = self.client.get(url).content.decode()
            with self.subTest(url=url):
                self.assertNotIn(SECRET, corps, "le secret en clair fuit")
                self.assertNotIn(self.cred.secret_ciphertext, corps, "le chiffré est exposé")

    def test_le_masque_est_sur_la_fiche_et_pas_dans_la_liste(self):
        """`masked` déchiffre, donc dérive la clé. Une colonne de liste le ferait une
        fois par ligne — une centaine de dérivations PBKDF2 par page, rechargeables
        à volonté. La liste se contente du booléen « défini »."""
        liste = self.client.get(reverse("admin:integrations_connectorcredential_changelist")).content.decode()
        self.assertNotIn(self.cred.masked, liste)
        fiche = self.client.get(
            reverse("admin:integrations_dataconnector_change", args=[self.connecteur.pk])
        ).content.decode()
        self.assertIn(self.cred.masked, fiche)

    def test_un_secret_indechiffrable_naffiche_pas_une_erreur_500(self):
        """Clé de chiffrement changée : la page doit le DIRE, pas planter.

        On vise la fiche, seul endroit où le masque est rendu : la liste ne
        déchiffre plus, précisément pour ne pas dériver la clé à chaque ligne.
        """
        ConnectorCredential.objects.filter(pk=self.cred.pk).update(secret_ciphertext="pas-du-chiffre")
        reponse = self.client.get(
            reverse("admin:integrations_connectorcredential_change", args=[self.cred.pk])
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("clé de chiffrement ne correspond plus", reponse.content.decode())

    def test_le_depot_dun_secret_est_impossible_depuis_ladmin(self):
        """Un formulaire écrirait la saisie TELLE QUELLE dans le champ chiffré."""
        self.assertEqual(self.client.get(reverse("admin:integrations_connectorcredential_add")).status_code, 403)


@SANS_MANIFESTE
class AdminPisteAuditTest(TestCase):
    """Une trace produite par le système ne se réécrit pas depuis l'admin."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_superuser(username="admin-audit", password="x",
                                                  email="au@k.co")
        cls.journal = AccessLog.record(user=cls.staff, action="view_dashboard", ip="10.0.0.9")
        source = DataSource.objects.create(name="S", slug="s", source_type=SourceType.REST)
        cls.job = SyncJob.objects.create(source=source, status="success")
        cls.erreur = SyncError.objects.create(source=source, code="E1", message="cassé")

    def setUp(self):
        self.client.force_login(self.staff)

    def test_le_journal_dacces_refuse_lajout_et_la_modification(self):
        self.assertEqual(self.client.get(reverse("admin:audit_accesslog_add")).status_code, 403)
        url = reverse("admin:audit_accesslog_change", args=[self.journal.pk])
        # Django rend la fiche en consultation (200) mais refuse l'écriture.
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {"action": "falsifie"})
        self.journal.refresh_from_db()
        self.assertEqual(self.journal.action, "view_dashboard")

    def test_les_jobs_de_synchronisation_sont_en_lecture_seule(self):
        self.assertEqual(self.client.get(reverse("admin:integrations_syncjob_add")).status_code, 403)
        self.client.post(reverse("admin:integrations_syncjob_change", args=[self.job.pk]),
                         {"status": "error", "rows_ingested": 999})
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "success")
        self.assertEqual(self.job.rows_ingested, 0)

    def test_marquer_une_erreur_traitee_reste_possible(self):
        """La seule écriture admise sur une trace : clore un constat.

        Marquer une erreur comme traitée est un acte d'administration, pas une
        falsification — le constat lui-même reste figé.
        """
        self.assertFalse(self.erreur.resolved)
        self.client.post(reverse("admin:integrations_syncerror_changelist"), {
            "action": "marquer_traitees",
            "_selected_action": [str(self.erreur.pk)],
        })
        self.erreur.refresh_from_db()
        self.assertTrue(self.erreur.resolved)
        self.assertEqual(self.erreur.message, "cassé", "le message du constat ne doit pas bouger")


@SANS_MANIFESTE
class AdminUtilisateurTest(TestCase):
    """Le mot de passe doit être HACHÉ, et le rôle attribuable sans passer par un shell."""

    def setUp(self):
        self.staff = User.objects.create_superuser(username="admin-user", password="x",
                                                   email="u@k.co")
        self.client.force_login(self.staff)

    def test_creation_dun_compte_hache_le_mot_de_passe(self):
        reponse = self.client.post(reverse("admin:accounts_user_add"), {
            "username": "nouveau", "password1": "MotDePasse!2026", "password2": "MotDePasse!2026",
            "role": "ADMIN_INTEGRATION", "is_group_scope": "on",
        }, follow=True)
        self.assertEqual(reponse.status_code, 200)
        cree = User.objects.get(username="nouveau")
        self.assertNotEqual(cree.password, "MotDePasse!2026", "mot de passe stocké en clair")
        self.assertTrue(cree.check_password("MotDePasse!2026"))
        self.assertEqual(cree.role, "ADMIN_INTEGRATION")

    def test_le_perimetre_est_lisible_en_liste(self):
        filiale = Subsidiary.objects.create(code="KRE", name="K-Express")
        self.staff.is_group_scope = False
        self.staff.save(update_fields=["is_group_scope"])
        self.staff.subsidiaries.add(filiale)
        corps = self.client.get(reverse("admin:accounts_user_changelist")).content.decode()
        self.assertIn("KRE", corps)


@SANS_MANIFESTE
class AdminSourceGardeFousTest(TestCase):
    """Ce que l'admin doit refuser sur une source, et pourquoi."""

    def setUp(self):
        self.staff = User.objects.create_superuser(username="admin-src", password="x",
                                                   email="src@k.co")
        self.client.force_login(self.staff)
        self.vierge = DataSource.objects.create(name="Créée par erreur", slug="erreur",
                                                source_type=SourceType.REST)
        self.exploitee = DataSource.objects.create(name="En service", slug="en-service",
                                                   source_type=SourceType.REST)
        SyncJob.objects.create(source=self.exploitee, status="success")

    def _admin(self):
        return admin.site._registry[DataSource]

    def test_une_source_sans_trace_reste_supprimable(self):
        """Retirer une source créée par erreur doit rester possible."""
        self.assertTrue(self._admin().has_delete_permission(self._requete(), self.vierge))

    def test_une_source_qui_a_produit_des_traces_nest_pas_supprimable(self):
        """La supprimer emporterait en CASCADE jobs, journaux, erreurs et webhooks —
        exactement l'historique que cet admin protège partout ailleurs."""
        self.assertFalse(self._admin().has_delete_permission(self._requete(), self.exploitee))

    def test_la_suppression_en_masse_est_retiree(self):
        """L'action de masse ne consulte pas le contrôle par objet : elle effacerait
        l'historique sans le moindre avertissement."""
        self.assertNotIn("delete_selected", self._admin().get_actions(self._requete()))

    def test_le_code_nest_pas_regenere_a_la_modification(self):
        """`prepopulated_fields` s'applique aussi au formulaire de modification :
        renommer une source réécrirait son code, qui sert de clé de corrélation aux
        traces d'audit et par lequel le connecteur Shield retrouve sa source."""
        options = self._admin()
        self.assertEqual(options.get_prepopulated_fields(self._requete(), self.vierge), {})
        self.assertEqual(options.get_prepopulated_fields(self._requete(), None),
                         {"slug": ("name",)})

    def test_lauteur_est_renseigne_et_non_saisi(self):
        reponse = self.client.post(reverse("admin:integrations_datasource_add"), {
            "name": "Nouvelle", "slug": "nouvelle", "source_type": "rest",
            "target_module": "autre", "environment": "production", "is_active": "on",
            "sync_frequency": "manual", "description": "",
            "connector-TOTAL_FORMS": "0", "connector-INITIAL_FORMS": "0",
            "connector-MIN_NUM_FORMS": "0", "connector-MAX_NUM_FORMS": "1",
        }, follow=True)
        self.assertEqual(reponse.status_code, 200)
        creee = DataSource.objects.get(slug="nouvelle")
        self.assertEqual(creee.created_by, self.staff, "l'auteur doit être posé, pas saisi")
        self.assertIn("created_by", self._admin().readonly_fields)

    def test_le_connecteur_nest_pas_supprimable(self):
        """Le supprimer laisserait une source impossible à configurer."""
        connecteur = DataConnector.objects.create(source=self.vierge)
        self.assertFalse(
            admin.site._registry[DataConnector].has_delete_permission(self._requete(), connecteur)
        )

    def _requete(self):
        from django.test import RequestFactory

        requete = RequestFactory().get("/")
        requete.user = self.staff
        return requete


class DerivationCleTest(TestCase):
    """La clé de chiffrement ne doit être dérivée qu'une fois par processus.

    120 000 itérations PBKDF2 sont le prix voulu contre la force brute — mais à la
    dérivation, pas à chaque usage. Sans mémoïsation, ce prix était acquitté à
    chaque déchiffrement : donc à chaque appel Shield, qui déchiffre le jeton pour
    construire son en-tête d'authentification.
    """

    def test_la_cle_nest_derivee_quune_seule_fois(self):
        from unittest.mock import patch as _patch

        from apps.integrations import encryption

        encryption._key.cache_clear()
        vraie = encryption.hashlib.pbkdf2_hmac
        with _patch.object(encryption.hashlib, "pbkdf2_hmac", side_effect=vraie) as derivation:
            chiffre = encryption.encrypt("valeur")
            for _ in range(20):
                self.assertEqual(encryption.decrypt(chiffre), "valeur")
        self.assertEqual(derivation.call_count, 1,
                         f"{derivation.call_count} dérivations pour 21 opérations")

    def test_un_changement_de_reglage_invalide_le_cache(self):
        """Sinon un `override_settings` sur la clé déchiffrerait avec l'ancienne."""
        from django.test import override_settings as _override

        from apps.integrations import encryption

        encryption._key.cache_clear()
        premiere = encryption._key()
        with _override(INTEGRATIONS_SECRET_KEY="une-tout-autre-cle-de-test"):
            self.assertNotEqual(encryption._key(), premiere)
        self.assertEqual(encryption._key(), premiere)
