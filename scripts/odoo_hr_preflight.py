#!/usr/bin/env python3
"""Préflight Odoo RH — à exécuter SUR VOTRE INFRA (là où Odoo est joignable).

Vérifie, AVANT de configurer Airbyte :
  1. la connectivité + l'authentification à Odoo (XML-RPC) ;
  2. la présence des champs attendus par le contrat `raw` (warehouse/ddl/raw/00_raw_odoo_hr.sql) ;
  3. un échantillon (masqué) pour confirmer le mapping filiale/département.

SÉCURITÉ : la clé API est lue depuis l'ENVIRONNEMENT, jamais en argument ni affichée.
  export ODOO_URL="https://odoo.kaydan.tech"
  export ODOO_DB="kaydan_rh"
  export ODOO_LOGIN="api@kaydan.tech"
  export ODOO_API_KEY="***"        # depuis votre coffre / secret manager
  python3 scripts/odoo_hr_preflight.py

Aucune dépendance externe (xmlrpc.client est dans la stdlib). N'écrit rien, ne modifie rien.
"""

from __future__ import annotations

import os
import sys
import xmlrpc.client

# Champs attendus par le contrat raw (côté staging dbt). Adaptez si vos noms diffèrent.
EXPECTED = {
    "hr.employee": ["id", "name", "subsidiary_code", "department_code", "date_hired", "date_departure"],
    "hr.payslip": ["id", "employee_id", "subsidiary_code", "department_code", "date_from",
                   "gross_amount", "net_amount", "employer_charges"],
}


def _mask(value):
    s = str(value)
    return s if len(s) <= 6 else s[:3] + "···" + s[-2:]


def main() -> int:
    url = os.environ.get("ODOO_URL", "").rstrip("/")
    db = os.environ.get("ODOO_DB", "")
    login = os.environ.get("ODOO_LOGIN", "")
    api_key = os.environ.get("ODOO_API_KEY", "")
    missing = [k for k, v in {"ODOO_URL": url, "ODOO_DB": db, "ODOO_LOGIN": login, "ODOO_API_KEY": api_key}.items() if not v]
    if missing:
        print(f"✗ Variables d'environnement manquantes : {', '.join(missing)}")
        return 2

    try:
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        version = common.version()
        uid = common.authenticate(db, login, api_key, {})
    except Exception as exc:  # noqa: BLE001
        print(f"✗ Connexion/authentification Odoo échouée : {exc}")
        return 1
    if not uid:
        print("✗ Authentification refusée (login/clé invalides pour cette base).")
        return 1
    print(f"✓ Connecté à Odoo {version.get('server_version', '?')} — uid={uid}, base={db}")

    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    ok = True
    for model, expected_fields in EXPECTED.items():
        try:
            available = models.execute_kw(db, uid, api_key, model, "fields_get", [], {"attributes": ["type"]})
        except Exception as exc:  # noqa: BLE001
            print(f"✗ {model} : lecture du schéma impossible ({exc})")
            ok = False
            continue
        present = [f for f in expected_fields if f in available]
        absent = [f for f in expected_fields if f not in available]
        print(f"\n{model} : {len(available)} champs exposés")
        print(f"  ✓ présents : {present}")
        if absent:
            ok = False
            print(f"  ⚠ ABSENTS (mapping à ajuster) : {absent}")
            # propose des candidats proches pour les champs absents
            for f in absent:
                cand = [a for a in available if f.split('_')[0] in a or a in f][:5]
                if cand:
                    print(f"      candidats pour « {f} » : {cand}")
        try:
            sample = models.execute_kw(db, uid, api_key, model, "search_read", [[]],
                                       {"fields": present, "limit": 2})
            for row in sample:
                print("  exemple :", {k: _mask(v) for k, v in row.items()})
        except Exception as exc:  # noqa: BLE001
            print(f"  (échantillon indisponible : {exc})")

    print("\n" + ("✓ Préflight OK — schéma compatible, prêt pour Airbyte." if ok
                  else "⚠ Préflight partiel — ajustez le mapping des champs ABSENTS avant Airbyte."))
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
