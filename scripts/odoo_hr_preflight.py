#!/usr/bin/env python3
"""Préflight Odoo RH — ce que l'instance peut RÉELLEMENT alimenter.

    # 1. Renseigner le fichier local, qui est ignoré par git :
    #      infra/airbyte/odoo-hr/.env.odoo
    # 2. Lancer, depuis la racine du dépôt :
    python3 scripts/odoo_hr_preflight.py

Le script lit `infra/airbyte/odoo-hr/.env.odoo` s'il existe, et l'environnement
sinon — ce dernier l'emporte. Ce fichier est gitignoré par trois règles ; la clé
n'a donc aucune raison de transiter par un canal de discussion ni par la ligne
de commande, où elle serait visible des autres processus.

À exécuter SUR VOTRE INFRA, là où Odoo est joignable. N'écrit rien, ne modifie
rien : uniquement des lectures.

POURQUOI CE SCRIPT EXISTE AVANT TOUTE CONFIGURATION D'AIRBYTE. Le contrat `raw`
(warehouse/ddl/raw/00_raw_odoo_hr.sql) attend des colonnes — `subsidiary_code`,
`department_code`, `date_hired`, `gross_amount` — qui ne sont PAS des champs
Odoo standard. Un Odoo nu expose `company_id`, `department_id`, `first_contract_date`.
Le mapping doit donc être établi sur l'instance réelle, jamais présumé : c'est
exactement ce que ce préflight rend visible, modèle par modèle et champ par champ.

TROIS QUESTIONS AUXQUELLES IL RÉPOND, et qu'aucune documentation ne peut trancher :

  1. QUELS MODULES RH SONT INSTALLÉS. `hr.payslip` n'existe que si la paie est
     installée — elle ne fait pas partie d'Odoo Community. Bâtir un mart de paie
     sur un modèle absent est une découverte qu'on préfère faire ici.

  2. QUE CONTIENNENT-ILS VRAIMENT. Un modèle installé mais vide ne remplira aucun
     écran. Le compte de lignes dit ce qui est réellement alimenté aujourd'hui.

  3. COMMENT LES SOCIÉTÉS ODOO SE RATTACHENT AUX FILIALES DU GROUPE. Le contrat
     `raw` veut des codes KRE / KSH / MYK ; Odoo a ses propres sociétés. Ce
     rattachement est une DÉCISION humaine — le script l'expose, il ne l'invente pas.

SÉCURITÉ : la clé API est lue depuis l'environnement, jamais passée en argument
(la ligne de commande est visible par les autres processus) et jamais affichée.
Les échantillons de données sont masqués.
"""

from __future__ import annotations

import os
import pathlib
import sys
import xmlrpc.client

FICHIER_ENV = pathlib.Path(__file__).resolve().parent.parent / "infra" / "airbyte" / "odoo-hr" / ".env.odoo"


def _charger_env() -> None:
    """Charge `.env.odoo` sans écraser l'environnement déjà posé.

    Évite l'incantation `set -a && . ./.env.odoo && set +a`, qui se recopie mal
    et qu'on oublie. L'environnement explicite reste prioritaire : on peut donc
    surcharger une valeur du fichier le temps d'un essai.
    """
    if not FICHIER_ENV.exists():
        return
    for ligne in FICHIER_ENV.read_text().splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, _, valeur = ligne.partition("=")
        cle, valeur = cle.strip(), valeur.split("#", 1)[0].strip().strip('"').strip("'")
        if cle and valeur and not os.environ.get(cle):
            os.environ[cle] = valeur

OK, ABS, WARN = "  OK  ", "ABSENT", "ALERTE"

# Les modèles qui intéressent les écrans RH de K-Insight, et le domaine qu'ils
# alimenteraient. On les SONDE tous : c'est l'instance qui dit lesquels existent.
MODELES = [
    ("hr.employee", "effectifs, organigramme, ancienneté"),
    ("hr.department", "répartition par département"),
    ("hr.job", "répartition par métier / poste"),
    ("hr.contract", "types de contrat, échéances"),
    ("hr.leave", "congés et absences"),
    ("hr.leave.type", "natures de congé"),
    ("hr.applicant", "recrutement"),
    ("hr.payslip", "paie (module non inclus dans Odoo Community)"),
    ("hr.attendance", "pointages"),
    ("res.company", "sociétés → rattachement aux filiales du Groupe"),
]

# Le contrat `raw` en vigueur. Ces noms ne sont PAS ceux d'Odoo : c'est
# précisément ce que le préflight doit rendre évident.
CONTRAT_RAW = {
    "hr.employee": ["id", "name", "subsidiary_code", "department_code", "date_hired", "date_departure"],
    "hr.payslip": ["id", "employee_id", "subsidiary_code", "department_code", "date_from",
                   "gross_amount", "net_amount", "employer_charges"],
}


def _masquer(valeur) -> str:
    """Un échantillon doit confirmer un mapping, pas divulguer un dossier RH."""
    s = str(valeur)
    return s if len(s) <= 6 else s[:3] + "···" + s[-2:]


def _cause(exc: Exception) -> str:
    """La première ligne utile d'une faute Odoo, pas ses 40 lignes de traceback."""
    texte = str(exc)
    for marqueur in ("psycopg2.OperationalError:", "odoo.exceptions.AccessDenied",
                     "does not exist", "AccessError", "KeyError:"):
        if marqueur in texte:
            fragment = texte.split(marqueur, 1)[1].strip().splitlines()[0]
            return f"{marqueur.rstrip(':')} {fragment}".strip()[:180]
    return texte.splitlines()[0][:180]


def main() -> int:
    _charger_env()
    url = os.environ.get("ODOO_URL", "").rstrip("/")
    db = os.environ.get("ODOO_DB", "")
    login = os.environ.get("ODOO_LOGIN", "")
    api_key = os.environ.get("ODOO_API_KEY", "")
    manquantes = [k for k, v in {"ODOO_URL": url, "ODOO_DB": db,
                                 "ODOO_LOGIN": login, "ODOO_API_KEY": api_key}.items() if not v]
    if manquantes:
        print(f"✗ Paramètres manquants : {', '.join(manquantes)}")
        print(f"  Renseignez-les dans {FICHIER_ENV}")
        print("  (fichier ignoré par git ; modèle à côté : env.odoo.example)")
        return 2

    try:
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        version = common.version()
        uid = common.authenticate(db, login, api_key, {})
    except Exception as exc:  # noqa: BLE001
        print(f"✗ Connexion Odoo impossible : {_cause(exc)}")
        return 1
    if not uid:
        print("✗ Authentification refusée : login ou clé invalide pour cette base.")
        return 1

    serie = version.get("server_serie", version.get("server_version", "?"))
    print(f"✓ Odoo {serie} — base « {db} », uid {uid}\n")

    objets = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    def lire(modele: str, methode: str, args, kwargs=None):
        return objets.execute_kw(db, uid, api_key, modele, methode, args, kwargs or {})

    # ── 1. Modules RH installés ─────────────────────────────────────────────
    print("MODULES RH INSTALLÉS")
    try:
        modules = lire("ir.module.module", "search_read",
                       [[["state", "=", "installed"], ["name", "like", "hr%"]]],
                       {"fields": ["name", "shortdesc"], "limit": 60})
        for m in sorted(modules, key=lambda m: m["name"]):
            print(f"  [{OK}] {m['name']:<28} {m.get('shortdesc') or ''}")
        if not modules:
            print("  [ALERTE] aucun module « hr* » installé : rien à alimenter côté RH.")
    except Exception as exc:  # noqa: BLE001
        print(f"  [{WARN}] liste des modules illisible ({_cause(exc)})")
        print("           → le compte API n'a probablement pas accès à `ir.module.module` ;")
        print("             ce n'est pas bloquant, la suite reste valable.")

    # ── 2. Modèles présents et RÉELLEMENT alimentés ─────────────────────────
    print("\nMODÈLES — présence et volume")
    disponibles: dict[str, int] = {}
    for modele, usage in MODELES:
        try:
            n = lire(modele, "search_count", [[]])
        except Exception as exc:  # noqa: BLE001
            print(f"  [{ABS}] {modele:<18} — {usage}")
            print(f"           ({_cause(exc)})")
            continue
        disponibles[modele] = n
        etat = OK if n else WARN
        suffixe = "" if n else "   ← installé mais VIDE : n'alimentera aucun écran"
        print(f"  [{etat}] {modele:<18} {n:>7} ligne(s)  — {usage}{suffixe}")

    # ── 3. Sociétés → filiales du Groupe ────────────────────────────────────
    print("\nSOCIÉTÉS ODOO → FILIALES DU GROUPE")
    if "res.company" in disponibles:
        try:
            societes = lire("res.company", "search_read", [[]], {"fields": ["id", "name"], "limit": 50})
            for c in societes:
                print(f"  id={c['id']:<4} « {c['name']} »   → code filiale K-Insight : À DÉCIDER")
            print("\n  Le contrat `raw` attend un `subsidiary_code` (KRE / KSH / MYK).")
            print("  Ce rattachement est une décision d'organisation : il ne peut pas être")
            print("  déduit d'un nom de société, et l'inventer produirait des chiffres")
            print("  attribués à la mauvaise entité.")
        except Exception as exc:  # noqa: BLE001
            print(f"  [{WARN}] sociétés illisibles ({_cause(exc)})")

    # ── 4. Contrat `raw` : champ par champ ──────────────────────────────────
    print("\nCONTRAT `raw` — champs attendus vs champs réels")
    conforme = True
    for modele, attendus in CONTRAT_RAW.items():
        if modele not in disponibles:
            print(f"\n  {modele} : MODÈLE ABSENT — le contrat ne peut pas être honoré.")
            conforme = False
            continue
        try:
            champs = lire(modele, "fields_get", [], {"attributes": ["type", "string"]})
        except Exception as exc:  # noqa: BLE001
            print(f"\n  {modele} : schéma illisible ({_cause(exc)})")
            conforme = False
            continue

        presents = [f for f in attendus if f in champs]
        absents = [f for f in attendus if f not in champs]
        print(f"\n  {modele} — {len(champs)} champs exposés")
        print(f"    présents : {presents or 'aucun'}")
        if absents:
            conforme = False
            print(f"    ABSENTS  : {absents}")
            for f in absents:
                racine = f.split("_")[0]
                candidats = [a for a in champs if racine in a or a in f][:6]
                if candidats:
                    print(f"      candidats pour « {f} » : {candidats}")
        if presents:
            try:
                echantillon = lire(modele, "search_read", [[]], {"fields": presents, "limit": 2})
                for ligne in echantillon:
                    print("      exemple :", {k: _masquer(v) for k, v in ligne.items()})
            except Exception as exc:  # noqa: BLE001
                print(f"      (échantillon indisponible : {_cause(exc)})")

    # ── Verdict ─────────────────────────────────────────────────────────────
    print("\n" + "─" * 72)
    alimentes = [m for m, n in disponibles.items() if n]
    print(f"Modèles réellement alimentés : {len(alimentes)} sur {len(MODELES)} sondés")
    if conforme:
        print("✓ Le contrat `raw` est honoré tel quel : Airbyte peut être configuré.")
        return 0
    print("⚠ Le contrat `raw` n'est PAS honoré tel quel — c'est le cas attendu sur un")
    print("  Odoo standard, dont les champs ne portent pas ces noms. Deux décisions")
    print("  à prendre avant Airbyte, à partir des candidats listés ci-dessus :")
    print("    1. le mapping champ Odoo → colonne du contrat `raw` ;")
    print("    2. le rattachement société Odoo → code filiale du Groupe.")
    return 3


if __name__ == "__main__":
    sys.exit(main())
