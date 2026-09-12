"""Client XML-RPC Odoo : transport, erreurs, session.

Séparé de la normalisation métier (`odoo.py`) pour la même raison que le client
Shield : la distinction entre « Odoo a dit non » et « Odoo n'a pas répondu »
détermine l'état affiché à l'écran. Un refus de droits n'est pas une panne, un
délai dépassé n'est pas une absence de donnée, et confondre les deux produit des
tableaux de bord qui mentent.

POURQUOI XML-RPC ET NON JSON-RPC. Les deux répondent sur l'instance (vérifié sur
rh.kaydan.tech, Odoo 18.0). XML-RPC est retenu parce qu'il est dans la
bibliothèque standard — `xmlrpc.client` — là où JSON-RPC demanderait de
réimplémenter l'enveloppe, la gestion des fautes et le typage des dates. Aucune
dépendance ajoutée, moins de code à se tromper.

LA SESSION ODOO N'EST PAS UN JETON. `authenticate(db, login, clé)` rend un `uid`
entier, et chaque appel ultérieur repasse la CLÉ, pas un jeton de session. Il n'y
a donc rien à rafraîchir : on met l'uid en cache pour éviter un aller-retour par
requête, et on le redemande si Odoo le refuse.
"""

from __future__ import annotations

import logging
import socket
import ssl
import threading
import time
import xmlrpc.client
from typing import Any

logger = logging.getLogger(__name__)

DELAI_DEFAUT = 10           # secondes, par appel
MAX_TENTATIVES = 2          # 1 essai + 1 reprise : Odoo est synchrone, on n'insiste pas
ATTENTE_REPRISE = 0.6
# Un uid reste valable tant que le compte existe. Le relire à chaque requête web
# ajouterait un aller-retour réseau pour une valeur qui ne change jamais.
TTL_SESSION = 15 * 60


class OdooError(Exception):
    """Échec d'appel qualifié par sa CAUSE, pas seulement par son message.

    `kind` pilote directement l'état gouverné rendu à l'écran :
      auth        → base, login ou clé refusés : `error`, et l'opérateur doit agir
      droits      → le compte est authentifié mais n'a pas accès au modèle
      absent      → le modèle n'existe pas sur cette instance (module non installé)
      timeout     → Odoo n'a pas répondu à temps
      reseau      → hôte injoignable, TLS invalide
      protocole   → réponse illisible ou inattendue
      config      → il manque une information de connexion (base, login, clé)
    """

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


class ClientOdoo:
    """Lecture seule sur une instance Odoo. N'écrit jamais, n'appelle que `search_read`,
    `search_count` et `fields_get`.

    La clé API est gardée en mémoire le temps de l'appel et ne sort jamais d'ici :
    ni journal, ni message d'erreur, ni réponse d'API.
    """

    def __init__(self, url: str, base: str, login: str, cle: str,
                 delai: int = DELAI_DEFAUT, max_tentatives: int = MAX_TENTATIVES):
        self.url = (url or "").rstrip("/")
        self.base = base or ""
        self.login = login or ""
        self._cle = cle or ""
        self.delai = delai
        self.max_tentatives = max_tentatives
        self.appels = 0
        self._uid: int | None = None
        self._uid_expire = 0.0
        self._verrou = threading.Lock()

    # ── Connexion ───────────────────────────────────────────────────────────

    def _proxy(self, service: str) -> xmlrpc.client.ServerProxy:
        # `allow_none` : Odoo renvoie `False` là où d'autres renvoient null, mais
        # certains champs vides remontent bien en None et casseraient le marshalling.
        return xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/{service}",
                                         allow_none=True)

    def uid(self) -> int:
        """L'identifiant de session, mis en cache. Lève `OdooError` si refusé."""
        with self._verrou:
            if self._uid and time.monotonic() < self._uid_expire:
                return self._uid
            manquants = [n for n, v in (("base", self.base), ("login", self.login),
                                        ("clé API", self._cle), ("URL", self.url)) if not v]
            if manquants:
                raise OdooError("config", f"Connexion Odoo incomplète : {', '.join(manquants)}.")
            uid = self._appeler_brut(lambda: self._proxy("common").authenticate(
                self.base, self.login, self._cle, {}))
            if not uid:
                # Odoo ne distingue pas un mauvais login d'une mauvaise clé, et
                # c'est tant mieux : le message ne doit pas aider à deviner lequel.
                raise OdooError("auth", "Odoo refuse ces identifiants pour cette base.")
            self._uid = int(uid)
            self._uid_expire = time.monotonic() + TTL_SESSION
            return self._uid

    def oublier_la_session(self) -> None:
        with self._verrou:
            self._uid = None
            self._uid_expire = 0.0

    # ── Appels ──────────────────────────────────────────────────────────────

    def _appeler_brut(self, fonction):
        """Exécute un appel XML-RPC en traduisant toute panne en `OdooError`."""
        derniere: OdooError | None = None
        for tentative in range(self.max_tentatives):
            self.appels += 1
            try:
                return fonction()
            except xmlrpc.client.Fault as exc:
                # Une faute Odoo est une réponse, pas une panne : on ne réessaie pas.
                raise self._traduire_faute(exc) from exc
            except socket.timeout as exc:
                derniere = OdooError("timeout", f"Odoo n'a pas répondu en {self.delai} s.")
                derniere.__cause__ = exc
            except ssl.SSLCertVerificationError as exc:
                # Symptôme cryptique, cause banale — même diagnostic que pour Shield :
                # c'est le magasin de certificats de NOTRE environnement qui manque.
                raise OdooError("reseau", "Certificat TLS d'Odoo non vérifiable : le magasin "
                                          "de certificats de l'environnement est absent ou "
                                          "incomplet.") from exc
            except (xmlrpc.client.ProtocolError, xmlrpc.client.ResponseError) as exc:
                derniere = OdooError("protocole", f"Réponse Odoo inattendue : {exc}")
                derniere.__cause__ = exc
            except (OSError, ConnectionError) as exc:
                derniere = OdooError("reseau", f"Odoo injoignable : {exc}")
                derniere.__cause__ = exc
            if tentative + 1 < self.max_tentatives:
                time.sleep(ATTENTE_REPRISE)
        raise derniere or OdooError("reseau", "Odoo injoignable.")

    @staticmethod
    def _traduire_faute(exc: xmlrpc.client.Fault) -> OdooError:
        """Qualifie une faute Odoo à partir de son texte.

        Odoo renvoie toutes ses erreurs applicatives dans un `Fault` unique dont
        seul le message distingue un refus de droits d'un modèle absent. On lit
        donc le texte — à défaut de code — mais on ne le RECOPIE pas vers l'écran :
        il contient l'arborescence du serveur et l'adresse de sa base.
        """
        texte = str(exc.faultString or "")
        if "AccessDenied" in texte or "Access denied" in texte:
            return OdooError("auth", "Odoo refuse ces identifiants pour cette base.")
        if "AccessError" in texte or "not allowed" in texte:
            return OdooError("droits", "Le compte Odoo n'a pas accès à cette donnée.")
        if "Object" in texte and "doesn't exist" in texte:
            return OdooError("absent", "Modèle absent de cette instance : le module "
                                       "correspondant n'est pas installé.")
        if "does not exist" in texte and "database" in texte:
            return OdooError("config", "Cette base Odoo n'existe pas sur le serveur.")
        # Message générique : on ne renvoie PAS le traceback d'Odoo à l'écran.
        logger.warning("Faute Odoo non qualifiée : %s", texte[:400])
        return OdooError("protocole", "Odoo a répondu par une erreur inattendue.")

    def executer(self, modele: str, methode: str, args: list, options: dict | None = None):
        """`execute_kw` en lecture seule. Toute autre méthode est refusée ici."""
        if methode not in ("search_read", "search_count", "fields_get", "read", "search"):
            raise OdooError("config", f"Méthode « {methode} » interdite : ce client est en lecture seule.")
        uid = self.uid()
        try:
            return self._appeler_brut(lambda: self._proxy("object").execute_kw(
                self.base, uid, self._cle, modele, methode, args, options or {}))
        except OdooError as exc:
            if exc.kind == "auth":
                # L'uid en cache a pu être invalidé (compte désactivé, clé révoquée) :
                # on le jette pour que la tentative suivante reparte d'une session neuve.
                self.oublier_la_session()
            raise

    # ── Raccourcis de lecture ───────────────────────────────────────────────

    def compter(self, modele: str, domaine: list | None = None) -> int:
        return int(self.executer(modele, "search_count", [domaine or []]))

    def lire(self, modele: str, champs: list[str], domaine: list | None = None,
             limite: int = 200, ordre: str | None = None) -> list[dict[str, Any]]:
        options: dict[str, Any] = {"fields": champs, "limit": limite}
        if ordre:
            options["order"] = ordre
        lignes = self.executer(modele, "search_read", [domaine or []], options)
        return [l for l in lignes if isinstance(l, dict)]

    def champs_de(self, modele: str) -> dict[str, Any]:
        """Le schéma réel du modèle. Sert à vérifier qu'un champ existe AVANT de
        le demander : un champ inconnu fait échouer tout l'appel, donc tout l'écran."""
        return self.executer(modele, "fields_get", [], {"attributes": ["type", "string"]})

    def modele_present(self, modele: str) -> bool:
        """Vrai si le modèle existe ET est lisible par ce compte."""
        try:
            self.compter(modele)
            return True
        except OdooError as exc:
            if exc.kind in ("absent", "droits"):
                return False
            raise
