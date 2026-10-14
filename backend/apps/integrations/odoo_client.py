"""Client JSON-RPC Odoo : transport et erreurs qualifiées.

Séparé de la normalisation métier (`odoo.py`) pour la même raison que le client
Shield : la distinction entre « Odoo a dit non » et « Odoo n'a pas répondu »
détermine l'état affiché à l'écran. Un refus de droits n'est pas une panne, un
délai dépassé n'est pas une absence de donnée, et confondre les deux produit des
tableaux de bord qui mentent.

POURQUOI JSON-RPC, APRÈS UNE PREMIÈRE VERSION EN XML-RPC. Les deux répondent sur
rh.kaydan.tech (Odoo 18.0), et XML-RPC avait été retenu pour sa présence dans la
bibliothèque standard. Mais une faute XML-RPC n'est qu'une chaîne : refus
d'identifiants, droits manquants et base inexistante ne s'y distinguaient qu'en
cherchant des mots dans un traceback. JSON-RPC rend la CLASSE de l'exception —
`data.name = "odoo.exceptions.AccessDenied"` — et c'est exactement ce qui sépare
« réauthentifier » de « ne surtout pas réauthentifier ». Le transport reste en
bibliothèque standard (`urllib` + `json`) : aucune dépendance ajoutée.

LA SESSION ODOO N'EST PAS UN JETON. `common.authenticate(db, login, clé, {})`
rend un `uid` entier, et chaque `object.execute_kw` repasse la CLÉ, pas un jeton.
Il n'y a rien à rafraîchir : la permanence vient du compte technique et de sa clé
stockée chiffrée. La gestion de l'uid — cache, réauthentification, single-flight
— vit dans `odoo_session`.
"""

from __future__ import annotations

import itertools
import json
import logging
import socket
import ssl
import threading
import time
import urllib.error
import urllib.request
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
      base        → la base nommée n'existe pas sur le serveur
    """

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


_identifiants_rpc = itertools.count(1)


class ClientOdoo:
    """Lecture seule sur une instance Odoo. N'écrit jamais, n'appelle que `search_read`,
    `search_count`, `fields_get`, `read` et `search`.

    La clé API est gardée en mémoire le temps de l'appel et ne sort jamais d'ici :
    ni journal, ni message d'erreur, ni réponse d'API.

    `session` : un `odoo_session.SessionOdoo` partagé. Sans lui, le client garde
    un uid local — c'était le seul mode de la première version, et il ne servait
    à rien : `build_client` créant un client par requête, l'uid mourait avec lui
    et chaque requête web se réauthentifiait.
    """

    def __init__(self, url: str, base: str, login: str, cle: str,
                 delai: int = DELAI_DEFAUT, max_tentatives: int = MAX_TENTATIVES,
                 session=None):
        self.url = (url or "").rstrip("/")
        self.base = base or ""
        self.login = login or ""
        self._cle = cle or ""
        self.delai = delai
        self.max_tentatives = max_tentatives
        self.appels = 0
        self.session = session
        self._uid: int | None = None
        self._uid_expire = 0.0
        self._verrou = threading.Lock()

    # ── Transport ───────────────────────────────────────────────────────────

    def _rpc(self, service: str, methode: str, *args):
        """Un appel `POST /jsonrpc`. Rend `result`, ou lève une `OdooError` qualifiée."""
        corps = json.dumps({
            "jsonrpc": "2.0", "method": "call", "id": next(_identifiants_rpc),
            "params": {"service": service, "method": methode, "args": list(args)},
        }).encode()
        requete = urllib.request.Request(
            f"{self.url}/jsonrpc", data=corps, method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json",
                     "User-Agent": "k-insight"},
        )
        with urllib.request.urlopen(requete, timeout=self.delai) as reponse:  # noqa: S310
            try:
                charge = json.loads(reponse.read().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise OdooError("protocole", "Réponse Odoo illisible (JSON attendu).") from exc
        if not isinstance(charge, dict):
            raise OdooError("protocole", "Réponse Odoo inattendue (objet JSON attendu).")
        if charge.get("error"):
            raise self._traduire_erreur(charge["error"])
        return charge.get("result")

    def _appeler_brut(self, fonction):
        """Exécute un appel en traduisant toute panne de TRANSPORT en `OdooError`.

        Une erreur rendue PAR Odoo est une réponse : on ne la réessaie pas. Seules
        les pannes de transport ont droit à une reprise, et une seule.
        """
        derniere: OdooError | None = None
        for tentative in range(self.max_tentatives):
            self.appels += 1
            try:
                return fonction()
            except OdooError:
                raise
            except (socket.timeout, TimeoutError) as exc:
                derniere = OdooError("timeout", f"Odoo n'a pas répondu en {self.delai} s.")
                derniere.__cause__ = exc
            except urllib.error.HTTPError as exc:
                # /jsonrpc répond 200 même pour une erreur applicative : un code
                # HTTP d'erreur vient donc du serveur frontal (proxy, maintenance).
                if exc.code in (502, 503, 504):
                    derniere = OdooError("reseau", f"Odoo indisponible (HTTP {exc.code}).")
                    derniere.__cause__ = exc
                else:
                    raise OdooError("protocole", f"Odoo a répondu HTTP {exc.code} sur /jsonrpc : "
                                                 "point d'accès désactivé ou URL erronée.") from exc
            except urllib.error.URLError as exc:
                raison = getattr(exc, "reason", exc)
                if isinstance(raison, ssl.SSLCertVerificationError):
                    # Symptôme cryptique, cause banale — même diagnostic que pour
                    # Shield : c'est le magasin de certificats de NOTRE environnement.
                    raise OdooError("reseau", "Certificat TLS d'Odoo non vérifiable : le magasin "
                                              "de certificats de l'environnement est absent ou "
                                              "incomplet.") from exc
                if isinstance(raison, (socket.timeout, TimeoutError)):
                    derniere = OdooError("timeout", f"Odoo n'a pas répondu en {self.delai} s.")
                else:
                    derniere = OdooError("reseau", f"Odoo injoignable ({type(raison).__name__}).")
                derniere.__cause__ = exc
            except (OSError, ConnectionError) as exc:
                derniere = OdooError("reseau", f"Odoo injoignable ({type(exc).__name__}).")
                derniere.__cause__ = exc
            if tentative + 1 < self.max_tentatives:
                time.sleep(ATTENTE_REPRISE)
        raise derniere or OdooError("reseau", "Odoo injoignable.")

    @staticmethod
    def _traduire_erreur(erreur: dict) -> OdooError:
        """Qualifie une erreur Odoo par la CLASSE de son exception.

        JSON-RPC rend `data.name` (« odoo.exceptions.AccessDenied ») : on décide sur
        ce nom, et on ne retombe sur le texte que pour les exceptions Python
        génériques. Le message et le traceback d'Odoo ne sont JAMAIS recopiés vers
        l'écran : ils contiennent l'arborescence du serveur et l'adresse de sa base.
        """
        data = erreur.get("data") if isinstance(erreur, dict) else None
        data = data if isinstance(data, dict) else {}
        nom = str(data.get("name") or "")
        texte = f"{data.get('message') or ''} {erreur.get('message') or ''}"
        if nom.endswith("AccessDenied"):
            return OdooError("auth", "Odoo refuse ces identifiants pour cette base.")
        if nom.endswith("AccessError"):
            return OdooError("droits", "Le compte Odoo n'a pas accès à cette donnée.")
        if "does not exist" in texte and "database" in texte.lower():
            return OdooError("base", "Cette base Odoo n'existe pas sur le serveur.")
        if nom.endswith("KeyError") or ("Object" in texte and "doesn't exist" in texte):
            return OdooError("absent", "Modèle absent de cette instance : le module "
                                       "correspondant n'est pas installé.")
        logger.warning("Erreur Odoo non qualifiée : %s", nom or "(sans nom)")
        return OdooError("protocole", "Odoo a répondu par une erreur inattendue.")

    # ── Connexion ───────────────────────────────────────────────────────────

    def version(self) -> dict:
        """`common.version` : joignabilité et version, SANS authentification."""
        resultat = self._appeler_brut(lambda: self._rpc("common", "version"))
        return resultat if isinstance(resultat, dict) else {}

    def authentifier(self) -> int:
        """`common.authenticate` brut, sans cache. Rend l'uid ou lève `OdooError`."""
        manquants = [n for n, v in (("base", self.base), ("login", self.login),
                                    ("clé API", self._cle), ("URL", self.url)) if not v]
        if manquants:
            raise OdooError("config", f"Connexion Odoo incomplète : {', '.join(manquants)}.")
        uid = self._appeler_brut(lambda: self._rpc(
            "common", "authenticate", self.base, self.login, self._cle, {}))
        # Odoo rend `False` pour un mauvais login, une mauvaise clé ou un compte
        # désactivé — sans dire lequel, et c'est tant mieux : le message ne doit
        # pas aider à deviner.
        if not isinstance(uid, int) or isinstance(uid, bool) or uid <= 0:
            raise OdooError("auth", "Odoo refuse ces identifiants pour cette base.")
        return uid

    def uid(self) -> int:
        """L'identifiant de session, mis en cache. Lève `OdooError` si refusé."""
        if self.session is not None:
            return self.session.uid(self)
        with self._verrou:
            if self._uid and time.monotonic() < self._uid_expire:
                return self._uid
            self._uid = self.authentifier()
            self._uid_expire = time.monotonic() + TTL_SESSION
            return self._uid

    def oublier_la_session(self, uid: int | None = None) -> None:
        if self.session is not None:
            self.session.invalider(uid)
            return
        with self._verrou:
            self._uid = None
            self._uid_expire = 0.0

    # ── Appels ──────────────────────────────────────────────────────────────

    def executer(self, modele: str, methode: str, args: list, options: dict | None = None):
        """`execute_kw` en lecture seule. Toute autre méthode est refusée ici.

        Sur un refus d'AUTHENTIFICATION — et seulement celui-là — l'uid est
        jeté, une session neuve est ouverte avec le compte de service, et
        l'appel est rejoué UNE fois. Pas de boucle : un second refus remonte tel
        quel. Une panne réseau ne déclenche jamais de réauthentification, qui ne
        la réparerait pas et consommerait une tentative de connexion pour rien.
        """
        if methode not in ("search_read", "search_count", "fields_get", "read", "search"):
            raise OdooError("config", f"Méthode « {methode} » interdite : ce client est en lecture seule.")

        def appel(uid: int):
            return self._appeler_brut(lambda: self._rpc(
                "object", "execute_kw", self.base, uid, self._cle, modele, methode,
                args, options or {}))

        uid = self.uid()
        try:
            return appel(uid)
        except OdooError as exc:
            if exc.kind != "auth":
                raise
            self.oublier_la_session(uid)
        return appel(self.uid())

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
