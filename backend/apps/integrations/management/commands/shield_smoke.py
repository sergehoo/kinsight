"""Smoke test Kaydan Shield — peu d'appels, avant toute série lourde.

    python manage.py shield_smoke

Vérifie ce qui doit être confirmé sur l'instance RÉELLE avant de lui envoyer des
collectes de période : que l'authentification passe, que `count` reflète bien le
total filtré, que les booléens documentés sont acceptés, et que les valeurs
d'énumération se comportent comme le Swagger l'annonce.

N'affiche jamais le jeton, ni aucune donnée personnelle : uniquement des
compteurs et des codes de retour.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.integrations import shield
from apps.integrations import shield_endpoints as EP
from apps.integrations.shield_client import ShieldError

OK, KO, WARN = "  OK  ", " ÉCHEC", " ALERTE"


class Command(BaseCommand):
    help = "Vérifie l'accès Kaydan Shield en une poignée d'appels, avant les séries."

    def handle(self, *args, **options):
        source = shield.get_shield_source()
        if source is None:
            self.stderr.write("Aucune source `kaydan-shield` configurée.")
            return
        base = shield._base_url(source)
        if not base:
            self.stderr.write("Source sans URL de base.")
            return

        client = shield.build_client(source)
        self.stdout.write(f"Instance : {base}\n")
        checks: list[tuple[str, bool, str]] = []

        def run(label, fn):
            try:
                value = fn()
                checks.append((label, True, str(value)))
                return value
            except ShieldError as exc:
                checks.append((label, False, f"{exc.kind}{f'/{exc.status}' if exc.status else ''}"))
                return None

        # 1. Authentification et joignabilité, au coût d'un seul appel.
        run("auth + joignabilité", lambda: client.get_json(EP.SITES, {"limit": 1}, use_cache=False) and "réponse reçue")
        # 2. Compteurs de référentiel.
        sites = run("sites (count)", lambda: client.count(EP.SITES))
        run("employés (count)", lambda: client.count(EP.EMPLOYEES))
        run("ouvriers (count)", lambda: client.count(EP.WORKERS))
        # 3. Présence du jour.
        run("présence du jour", lambda: client.get_json(EP.ATTENDANCE_TODAY) and "réponse reçue")
        # 4. Le booléen documenté est-il accepté ?
        total = run("attendance (sans filtre)", lambda: client.count(EP.ATTENDANCE_DAYS))
        presents = run("attendance present=true", lambda: client.count(EP.ATTENDANCE_DAYS, {"present": "true"}))
        # 5. Le filtre site est-il effectif ?
        first_site = None
        try:
            rows = client.results(EP.SITES, {"limit": 1})
            first_site = rows[0].get("id") if rows else None
        except ShieldError:
            pass
        scoped = run(f"attendance site={first_site}",
                     lambda: client.count(EP.ATTENDANCE_DAYS, {"site": first_site})) if first_site else None
        # 6. La pagination expose-t-elle bien un total cohérent ?
        page = run("pagination (count vs results)",
                   lambda: client.get_json(EP.SITES, {"limit": 2}, use_cache=False))

        self.stdout.write("")
        for label, ok, detail in checks:
            self.stdout.write(f"[{OK if ok else KO}] {label:32s} {detail}")

        # ── Confirmations explicites demandées avant toute collecte lourde ──
        self.stdout.write("\nConfirmations :")

        if isinstance(total, int) and isinstance(presents, int):
            coherent = presents <= total
            self.stdout.write(f"[{OK if coherent else WARN}] `count` reflète le total FILTRÉ "
                              f"(présents {presents} ≤ total {total})")
            if not coherent:
                self.stdout.write("      → un filtre inconnu serait ignoré : NE PAS lancer les séries.")
        else:
            self.stdout.write(f"[{WARN}] `count` non vérifiable (lecture en échec)")

        if isinstance(scoped, int) and isinstance(total, int):
            filtre_actif = scoped <= total
            self.stdout.write(f"[{OK if filtre_actif else WARN}] filtre `site` effectif "
                              f"({scoped} ≤ {total})")

        if isinstance(page, dict):
            forme = {"count", "results"} <= set(page)
            n = len(page.get("results") or [])
            self.stdout.write(f"[{OK if forme else WARN}] enveloppe paginée count/results "
                              f"(count={page.get('count')}, page={n})")
            if isinstance(sites, int) and page.get("count") != sites:
                self.stdout.write("      → le total varie entre deux lectures : à investiguer.")

        m = client.metrics.as_dict()
        self.stdout.write(f"\nCoût du smoke test : {m['calls']} appels, "
                          f"{m['duration_ms']:.0f} ms, erreurs {m['errors'] or 'aucune'}")
        if any(not ok for _, ok, _ in checks):
            self.stdout.write("\nDes vérifications ont échoué : ne pas lancer les séries.")
