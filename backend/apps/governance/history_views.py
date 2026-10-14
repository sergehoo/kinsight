"""GET /api/v1/governance/hr/history/ — une métrique RH sur une période réelle.

Paramètres :
  metric       identifiant canonique (`hr.taux_presence_jour`)            — requis
  compare      precedente | n-1 | les-deux | aucune                       — défaut les-deux
  ventilation  site | type | departement → la valeur de la période pour CHAQUE
               code de la dimension (périmètre Groupe)
  + les filtres communs du cockpit (`filtres.py`) : periode, year, quarter,
    date_from, date_to, subsidiary, site, type, departement.

Toute période s'arrête à la VEILLE : la journée en cours n'est pas close, elle
reste live (`aujourd_hui`). Une période sans mesure rend `unknown`, jamais 0.
"""

from __future__ import annotations

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.rbac import can_access_domain
from apps.audit.middleware import audit_source
from apps.audit.models import AccessLog

from . import filtres as F
from . import historique as H
from .hr_registry import ODOO, REGISTRE, SHIELD, resoudre
from .hr_sources import contexte_pour
from .lecture_rh import portee
from .models import Dimension, KpiSnapshot

DIMENSIONS_VENTILABLES = {Dimension.SITE, Dimension.TYPE, Dimension.DEPARTEMENT}


class HrHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        p = request.query_params
        metric_id = p.get("metric") or ""
        metric = REGISTRE.get(metric_id)
        if metric is None:
            return Response({"detail": f"Métrique inconnue : « {metric_id} »."},
                            status=status.HTTP_400_BAD_REQUEST)
        if not can_access_domain(request.user, metric.domaine):
            return Response({"detail": f"Accès au domaine « {metric.domaine} » non autorisé pour votre rôle."},
                            status=status.HTTP_403_FORBIDDEN)

        base = {"metric_id": metric.id, "label": metric.libelle, "definition": metric.definition,
                "unit": metric.unite, "format": metric.format, "source": metric.source,
                "regle": metric.agregat}
        if metric.source not in (SHIELD, ODOO):
            return Response({**base, "status": "disconnected", "reason": metric.motif_absence,
                             "points": []})

        try:
            filtres = F.lire(p, timezone.localdate())
            dimension_lue, codes_lus = portee(request.user, metric, filtres)
        except F.FiltreInvalide as refus:
            if refus.code_http != status.HTTP_200_OK:
                return Response({**base, "detail": refus.motif}, status=refus.code_http)
            return Response({**base, "status": "disconnected", "reason": refus.motif, "points": []})
        periode, libelle = filtres.periode, filtres.libelle

        resultat = H.agreger(metric.id, periode, dimension=dimension_lue, codes=codes_lus)
        points = H.serie(metric.id, periode, dimension=dimension_lue, codes=codes_lus)

        comparer = p.get("compare") or "les-deux"
        comparaisons = {}
        est_taux = metric.format == "pct"
        if comparer in ("precedente", "les-deux"):
            ref = H.agreger(metric.id, periode.precedente(), dimension=dimension_lue, codes=codes_lus)
            comparaisons["precedente"] = H.comparer(resultat, ref, est_taux=est_taux)
        if comparer in ("n-1", "les-deux"):
            ref = H.agreger(metric.id, periode.annee_precedente(), dimension=dimension_lue, codes=codes_lus)
            comparaisons["n_1"] = H.comparer(resultat, ref, est_taux=est_taux)

        # Ventilation : la valeur de la période pour CHAQUE code d'une dimension —
        # réservée au périmètre Groupe, comme les dimensions elles-mêmes.
        ventilation = None
        demandee = p.get("ventilation")
        if demandee in DIMENSIONS_VENTILABLES and dimension_lue == Dimension.GROUPE and codes_lus is None:
            ventilation = self._ventiler(metric.id, periode, demandee)

        premiere = H.premiere_mesure(metric)

        # La valeur du JOUR, live, à côté de la période — marquée comme telle.
        aujourd_hui = None
        if metric.instant:
            live = resoudre(metric.id, contexte_pour(request.user))
            aujourd_hui = {"value": live.get("value"), "status": live.get("status"),
                           "reason": live.get("reason"), "date": timezone.localdate().isoformat()}

        scope = request.user.scope()
        AccessLog.record(
            user=request.user, action="query_hr_history", metric_key=metric.id,
            scope_codes=(["*"] if scope.is_group else sorted(scope.subsidiaries)),
            payload=filtres.comme_trace(),
            **audit_source(request),
        )
        return Response({
            **base,
            "status": resultat["status"],
            "periode": {"debut": periode.debut.isoformat(), "fin": periode.fin.isoformat(),
                        "libelle": libelle, "jusqu_a": "veille"},
            "valeur": {k: resultat[k] for k in ("value", "status", "couverture")},
            "points": points,
            "comparaisons": comparaisons,
            "ventilation": ventilation,
            "aujourd_hui": aujourd_hui,
            "historique_depuis": premiere.isoformat() if premiere else None,
            "dimension": dimension_lue, "codes": codes_lus,
            "perimetre": "GROUP" if scope.is_group else sorted(scope.subsidiaries),
        })

    @staticmethod
    def _ventiler(metric_id: str, periode: H.Periode, dimension: str) -> list[dict]:
        metric = REGISTRE[metric_id]
        composantes = {metric_id, *metric.numerateur, *metric.denominateur}
        codes = (KpiSnapshot.objects.filter(metric_id__in=composantes, dimension=dimension,
                                            jour__gte=periode.debut, jour__lte=periode.fin)
                 .values_list("code", "libelle").distinct())
        lignes = []
        for code, libelle in sorted(set(codes)):
            agregat = H.agreger(metric_id, periode, dimension=dimension, codes=[code])
            lignes.append({"code": code, "libelle": libelle, "value": agregat["value"],
                           "couverture": agregat["couverture"]})
        # Tri par valeur décroissante, les inconnues à la fin : un classement ne
        # range pas un site sans mesure parmi les plus faibles.
        return sorted(lignes, key=lambda l: (l["value"] is None, -(l["value"] or 0)))


class HrDimensionsView(APIView):
    """GET /api/v1/governance/hr/dimensions/ — les options RÉELLES des filtres RH.

    Les sites, types et départements proposés sont ceux que l'historique a
    effectivement mesurés : un filtre ne propose jamais une valeur qu'aucune
    donnée ne porte. Sites et types sont des dimensions Shield, départements une
    dimension Odoo ; les trois ne sont historisés qu'au niveau Groupe — un
    périmètre restreint reçoit donc des listes vides et le motif, pas des sites
    qu'il ne pourrait pas filtrer.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not can_access_domain(request.user, "capital-humain"):
            return Response({"detail": "Accès au domaine « capital-humain » non autorisé pour votre rôle."},
                            status=status.HTTP_403_FORBIDDEN)
        if not request.user.scope().is_group:
            motif = ("Sites, types et départements ne sont historisés qu'au niveau Groupe : Shield ne "
                     "rattache pas ses sites aux filiales.")
            return Response({"site": [], "type": [], "departement": [], "restriction": motif})

        def options(dimension: str, metric_ids: set[str]) -> list[dict]:
            lignes = (KpiSnapshot.objects.filter(dimension=dimension, metric_id__in=metric_ids,
                                                 statut="measured")
                      .values_list("code", "libelle").distinct())
            vus: dict[str, str] = {}
            for code, libelle in lignes:
                vus[code] = libelle or vus.get(code) or code
            return [{"code": c, "libelle": l} for c, l in sorted(vus.items(), key=lambda kv: kv[1])]

        return Response({
            "site": options(Dimension.SITE, {"hr.presents_jour"}),
            "type": options(Dimension.TYPE, {"hr.presents_jour"}),
            "departement": options(Dimension.DEPARTEMENT, {"hr.employes_actifs_odoo"}),
        })
