"""Un appelant peut-il choisir ce que la piste d'audit retiendra de lui ?

Le backend partage un réseau Docker avec les autres projets de la plateforme. Un
conteneur voisin peut donc frapper gunicorn en direct et écrire les en-têtes qu'il
veut. Ces tests fixent la seule règle qui tienne : on ne croit `X-Forwarded-*` que
si le PAIR de la connexion est un proxy reconnu — la seule valeur que l'appelant ne
choisit pas.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

from apps.audit.middleware import (
    EN_TETES_DE_PROXY,
    TrustedProxyMiddleware,
    audit_source,
    client_ip,
    oublier_les_resolutions,
)
from apps.audit.models import AccessLog

User = get_user_model()

# Adresse arbitraire tenant le rôle du proxy dans les tests.
PROXY = "10.0.1.29"
PROXY_CIDR = [f"{PROXY}/32"]
VRAI_CLIENT = "160.120.33.224"
MENSONGE = "8.8.8.8"


class OrigineDeRequeteTest(TestCase):
    def setUp(self):
        oublier_les_resolutions()
        self.fabrique = RequestFactory()

    def tearDown(self):
        oublier_les_resolutions()

    def _traiter(self, *, pair, entetes=None):
        """Passe une requête dans le middleware et rend (requête, est_securisee)."""
        vu = {}

        def suite(requete):
            vu["securisee"] = requete.is_secure()
            return "réponse"

        requete = self.fabrique.get("/api/v1/governance/catalog/", **(entetes or {}))
        requete.META["REMOTE_ADDR"] = pair
        TrustedProxyMiddleware(suite)(requete)
        return requete, vu["securisee"]

    # ── Appel direct : tout ce que l'appelant prétend est écarté ──────────────
    @override_settings(TRUSTED_PROXY_CIDRS=PROXY_CIDR,
                       SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_un_appelant_inconnu_ne_choisit_pas_son_adresse(self):
        requete, _ = self._traiter(
            pair="10.0.1.77",  # un conteneur voisin, pas le proxy
            entetes={"HTTP_X_FORWARDED_FOR": MENSONGE},
        )
        self.assertEqual(requete.client_ip, "10.0.1.77", "l'adresse forgée a été retenue")
        self.assertFalse(requete.via_trusted_proxy)

    @override_settings(TRUSTED_PROXY_CIDRS=PROXY_CIDR,
                       SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_un_appelant_inconnu_ne_choisit_pas_le_protocole(self):
        """Sinon `request.is_secure()` — donc CSRF et les cookies — dépendrait de lui."""
        _, securisee = self._traiter(pair="10.0.1.77",
                                     entetes={"HTTP_X_FORWARDED_PROTO": "https"})
        self.assertFalse(securisee, "un en-tête forgé a rendu la requête « sécurisée »")

    @override_settings(TRUSTED_PROXY_CIDRS=PROXY_CIDR)
    def test_les_entetes_de_proxy_sont_retires_et_pas_seulement_ignores(self):
        """Les ignorer ne suffirait pas : la suite de la pile les relirait."""
        entetes = {entete: "valeur" for entete in EN_TETES_DE_PROXY}
        requete, _ = self._traiter(pair="10.0.1.77", entetes=entetes)
        for entete in EN_TETES_DE_PROXY:
            self.assertNotIn(entete, requete.META, entete)

    # ── Appel légitime : on remonte au vrai client ────────────────────────────
    @override_settings(TRUSTED_PROXY_CIDRS=PROXY_CIDR,
                       SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_derriere_le_proxy_on_retient_le_vrai_client(self):
        requete, securisee = self._traiter(
            pair=PROXY,
            entetes={"HTTP_X_FORWARDED_FOR": VRAI_CLIENT, "HTTP_X_FORWARDED_PROTO": "https"},
        )
        self.assertEqual(requete.client_ip, VRAI_CLIENT)
        self.assertTrue(requete.via_trusted_proxy)
        self.assertTrue(securisee)

    @override_settings(TRUSTED_PROXY_CIDRS=[f"{PROXY}/32", "10.0.2.0/24"])
    def test_la_chaine_est_remontee_par_la_droite(self):
        """« client, proxy1, proxy2 » : le plus proche de nous est à DROITE.

        Prendre le premier maillon à gauche, comme on le voit souvent, revient à
        laisser le client écrire lui-même son adresse — il suffit d'ajouter une
        valeur en tête.
        """
        requete, _ = self._traiter(
            pair=PROXY,
            entetes={"HTTP_X_FORWARDED_FOR": f"{MENSONGE}, {VRAI_CLIENT}, 10.0.2.5, {PROXY}"},
        )
        self.assertEqual(requete.client_ip, VRAI_CLIENT)

    @override_settings(TRUSTED_PROXY_CIDRS=PROXY_CIDR)
    def test_une_chaine_entierement_fiable_retombe_sur_le_pair(self):
        requete, _ = self._traiter(pair=PROXY, entetes={"HTTP_X_FORWARDED_FOR": PROXY})
        self.assertEqual(requete.client_ip, PROXY)

    @override_settings(TRUSTED_PROXY_CIDRS=PROXY_CIDR)
    def test_une_chaine_illisible_ne_fait_pas_tomber_la_requete(self):
        """`ip_address` refuserait la valeur : l'audit ne doit pas planter pour autant."""
        requete, _ = self._traiter(
            pair=PROXY, entetes={"HTTP_X_FORWARDED_FOR": "pas-une-adresse, <script>"})
        self.assertEqual(requete.client_ip, PROXY)

    @override_settings(TRUSTED_PROXY_CIDRS=PROXY_CIDR)
    def test_la_forme_adresse_port_est_acceptee(self):
        requete, _ = self._traiter(
            pair=f"{PROXY}:54321", entetes={"HTTP_X_FORWARDED_FOR": f"{VRAI_CLIENT}:443"})
        self.assertEqual(requete.client_ip, VRAI_CLIENT)

    # ── Posture par défaut : on ne fait confiance à personne ──────────────────
    @override_settings(TRUSTED_PROXY_HOSTS=[], TRUSTED_PROXY_CIDRS=[],
                       SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_sans_configuration_aucun_proxy_nest_reconnu(self):
        """Le défaut strict : une piste d'audit peu informative vaut mieux qu'une
        piste falsifiable."""
        requete, securisee = self._traiter(
            pair=PROXY,
            entetes={"HTTP_X_FORWARDED_FOR": VRAI_CLIENT, "HTTP_X_FORWARDED_PROTO": "https"},
        )
        self.assertEqual(requete.client_ip, PROXY)
        self.assertFalse(requete.via_trusted_proxy)
        self.assertFalse(securisee)

    @override_settings(TRUSTED_PROXY_HOSTS=["dokploy-traefik"], TRUSTED_PROXY_CIDRS=[])
    def test_un_hote_de_proxy_introuvable_ne_fait_confiance_a_personne(self):
        """La résolution est simulée en échec plutôt que confiée à un vrai nom
        inexistant : `getaddrinfo` met alors plusieurs secondes à renoncer, et un
        test lent finit par ne plus être lancé."""
        import socket as _socket

        with patch.object(_socket, "getaddrinfo", side_effect=_socket.gaierror("simulé")):
            requete, _ = self._traiter(pair=PROXY, entetes={"HTTP_X_FORWARDED_FOR": VRAI_CLIENT})
        self.assertEqual(requete.client_ip, PROXY)
        self.assertFalse(requete.via_trusted_proxy)

    @override_settings(TRUSTED_PROXY_HOSTS=["dokploy-traefik"], TRUSTED_PROXY_CIDRS=[])
    def test_le_proxy_est_reconnu_par_son_nom(self):
        """Sur Dokploy, le conteneur Traefik change d'adresse à chaque déploiement :
        c'est son NOM qui est déclaré, résolu à la volée."""
        import socket as _socket

        resolution = [(None, None, None, None, (PROXY, 0))]
        with patch.object(_socket, "getaddrinfo", return_value=resolution):
            requete, _ = self._traiter(pair=PROXY, entetes={"HTTP_X_FORWARDED_FOR": VRAI_CLIENT})
        self.assertEqual(requete.client_ip, VRAI_CLIENT)
        self.assertTrue(requete.via_trusted_proxy)

    @override_settings(TRUSTED_PROXY_CIDRS=["pas-un-reseau"])
    def test_un_cidr_invalide_est_ignore_sans_tout_casser(self):
        requete, _ = self._traiter(pair=PROXY, entetes={"HTTP_X_FORWARDED_FOR": VRAI_CLIENT})
        self.assertEqual(requete.client_ip, PROXY)


class TracabiliteTest(TestCase):
    """Ce que la piste d'audit retient, et comment elle signale une anomalie."""

    def setUp(self):
        oublier_les_resolutions()
        self.fabrique = RequestFactory()
        self.utilisateur = User.objects.create_user(username="tracee", password="x",
                                                    email="t@k.co", role="DG_GROUP")

    def tearDown(self):
        oublier_les_resolutions()

    def _requete(self, *, pair, entetes=None):
        requete = self.fabrique.get("/", **(entetes or {}))
        requete.META["REMOTE_ADDR"] = pair
        TrustedProxyMiddleware(lambda r: None)(requete)
        requete.user = self.utilisateur
        return requete

    @override_settings(TRUSTED_PROXY_CIDRS=PROXY_CIDR)
    def test_le_trafic_legitime_enregistre_ladresse_de_lutilisateur(self):
        """Avant, l'audit retenait REMOTE_ADDR : donc l'adresse de Traefik, la même
        pour tout le monde. La trace ne désignait personne."""
        requete = self._requete(pair=PROXY, entetes={"HTTP_X_FORWARDED_FOR": VRAI_CLIENT})
        ligne = AccessLog.record(user=requete.user, action="view_dashboard",
                                 **audit_source(requete))
        self.assertEqual(ligne.ip_address, VRAI_CLIENT)
        self.assertNotIn("appel_direct", ligne.payload)

    @override_settings(TRUSTED_PROXY_CIDRS=PROXY_CIDR)
    def test_un_appel_direct_est_marque_comme_tel(self):
        """L'adresse retenue est celle du conteneur appelant, et l'anomalie est
        lisible dans la trace au lieu de se confondre avec du trafic utilisateur."""
        requete = self._requete(pair="10.0.1.77",
                                entetes={"HTTP_X_FORWARDED_FOR": MENSONGE})
        ligne = AccessLog.record(user=requete.user, action="query_metric",
                                 payload={"metrique": "effectif"}, **audit_source(requete))
        self.assertEqual(ligne.ip_address, "10.0.1.77")
        self.assertTrue(ligne.payload["appel_direct"])
        self.assertEqual(ligne.payload["metrique"], "effectif", "la charge d'origine est conservée")

    def test_hors_requete_http_on_retombe_sur_le_pair(self):
        """Commandes de gestion et tests unitaires : jamais sur un en-tête."""
        requete = self.fabrique.get("/", HTTP_X_FORWARDED_FOR=MENSONGE)
        requete.META["REMOTE_ADDR"] = "127.0.0.1"
        self.assertEqual(client_ip(requete), "127.0.0.1")
        self.assertEqual(audit_source(requete), {"ip": "127.0.0.1", "via_proxy": None})


class MiddlewareEnPremierTest(TestCase):
    """L'ordre n'est pas cosmétique : nettoyer après la sécurité ne sert à rien."""

    def test_le_middleware_precede_la_securite_et_le_csrf(self):
        from django.conf import settings

        pile = list(settings.MIDDLEWARE)
        nettoyage = pile.index("apps.audit.middleware.TrustedProxyMiddleware")
        for apres in ("django.middleware.security.SecurityMiddleware",
                      "django.middleware.csrf.CsrfViewMiddleware"):
            self.assertLess(nettoyage, pile.index(apres),
                            f"{apres} lit is_secure() avant le nettoyage")


@override_settings(TRUSTED_PROXY_CIDRS=PROXY_CIDR, TRUSTED_PROXY_HOSTS=[])
class ProxyDoctorTest(TestCase):
    """Le verdict de `proxy_doctor` doit porter dans le bon sens.

    C'est un diagnostic : s'il classe une adresse de proxy en « client réel », il
    rassure à tort sur une piste d'audit qui ne désigne personne.
    """

    def setUp(self):
        oublier_les_resolutions()
        self.utilisateur = User.objects.create_user(username="doc", password="x",
                                                    email="d@k.co", role="DG_GROUP")

    def tearDown(self):
        oublier_les_resolutions()

    def _lancer(self):
        from io import StringIO

        from django.core.management import call_command

        sortie = StringIO()
        call_command("proxy_doctor", stdout=sortie)
        return sortie.getvalue()

    def test_une_adresse_publique_est_reconnue_comme_le_client(self):
        AccessLog.record(user=self.utilisateur, action="view_dashboard", ip=VRAI_CLIENT,
                         via_proxy=True)
        sortie = self._lancer()
        self.assertIn("client réel", sortie)
        self.assertIn("L'audit désigne bien l'utilisateur", sortie)

    def test_ladresse_du_proxy_est_signalee_comme_un_defaut(self):
        """Le cas qui rassurerait à tort : la trace existe, mais elle ne dit rien."""
        AccessLog.record(user=self.utilisateur, action="view_dashboard", ip=PROXY, via_proxy=True)
        sortie = self._lancer()
        self.assertIn("adresse du PROXY", sortie)
        self.assertIn("ne désignent personne", sortie)

    def test_un_appel_direct_est_remonte(self):
        AccessLog.record(user=self.utilisateur, action="query_metric", ip="10.0.1.77",
                         via_proxy=False)
        sortie = self._lancer()
        self.assertIn("appel DIRECT", sortie)
        self.assertIn("sans passer par le proxy", sortie)

    def test_sans_configuration_le_defaut_est_signale(self):
        with override_settings(TRUSTED_PROXY_CIDRS=[], TRUSTED_PROXY_HOSTS=[]):
            oublier_les_resolutions()
            sortie = self._lancer()
        self.assertIn("Aucun proxy reconnu", sortie)

    def test_sans_trace_la_commande_le_dit_au_lieu_de_conclure(self):
        sortie = self._lancer()
        self.assertIn("Aucune trace d'accès enregistrée", sortie)
