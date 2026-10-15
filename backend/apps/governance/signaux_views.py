"""Signaux RH et réglage de leurs seuils.

GET  /api/v1/governance/hr/signaux/  — les neuf signaux sur la période filtrée
GET  /api/v1/governance/hr/seuils/   — les seuils appliqués, avec leur provenance
PUT  /api/v1/governance/hr/seuils/   — arbitrer un seuil (DRH Groupe, administration)
     {"signal", "surveillance", "critique"} ou {"signal", "reinitialiser": true}
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.rbac import can_access_domain, peut_configurer_seuils_rh
from apps.audit.middleware import audit_source
from apps.audit.models import AccessLog

from . import filtres as F
from . import seuils_rh as S
from .hr_sources import oublier_charge_shield
from .models import SeuilRh
from .signaux_rh import SIGNAUX, evaluer

LIBELLES = {s.cle: s.libelle for s in SIGNAUX}


def _refus_domaine():
    return Response({"detail": "Accès au domaine « capital-humain » non autorisé pour votre rôle."},
                    status=status.HTTP_403_FORBIDDEN)


def _perimetre(user):
    scope = user.scope()
    return ["*"] if scope.is_group else sorted(scope.subsidiaries)


class HrSignalsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not can_access_domain(request.user, "capital-humain"):
            return _refus_domaine()
        try:
            filtres = F.lire(request.query_params, timezone.localdate())
            resultat = evaluer(request.user, filtres)
        except F.FiltreInvalide as refus:
            return Response({"detail": refus.motif}, status=refus.code_http)

        AccessLog.record(user=request.user, action="query_hr_signals", metric_key="hr.signaux",
                         scope_codes=_perimetre(request.user),
                         payload={**filtres.comme_trace(), "compteurs": resultat["compteurs"]},
                         **audit_source(request))
        periode = filtres.periode
        return Response({
            **resultat,
            "periode": {"debut": periode.debut.isoformat(), "fin": periode.fin.isoformat(),
                        "libelle": filtres.libelle, "jusqu_a": "veille"},
            "seuils_modifiables": peut_configurer_seuils_rh(request.user),
        })


class HrThresholdsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not can_access_domain(request.user, "capital-humain"):
            return _refus_domaine()
        return Response(self._etat(request.user))

    def put(self, request):
        if not can_access_domain(request.user, "capital-humain"):
            return _refus_domaine()
        if not peut_configurer_seuils_rh(request.user):
            return Response({"detail": "Seule la DRH Groupe ou l'administration arbitre les seuils RH."},
                            status=status.HTTP_403_FORBIDDEN)
        donnees = request.data if isinstance(request.data, dict) else {}
        signal = str(donnees.get("signal") or "")
        if signal not in S.DEFAUTS:
            return Response({"detail": f"Signal inconnu ou sans seuil : « {signal} »."},
                            status=status.HTTP_400_BAD_REQUEST)
        avant = S.effectifs()[signal]

        with transaction.atomic():
            if donnees.get("reinitialiser") is True:
                SeuilRh.objects.filter(signal=signal).delete()
            else:
                try:
                    surveillance, critique = S.valider(signal, donnees.get("surveillance"), donnees.get("critique"))
                except S.SeuilInvalide as erreur:
                    return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
                SeuilRh.objects.update_or_create(
                    signal=signal, defaults={"surveillance": surveillance, "critique": critique,
                                             "modifie_par": request.user})
            transaction.on_commit(S.oublier)
            transaction.on_commit(oublier_charge_shield)
        S.oublier()
        apres = S.effectifs()[signal]

        AccessLog.record(user=request.user, action="update_hr_threshold", metric_key=f"seuil.{signal}",
                         scope_codes=_perimetre(request.user),
                         payload={"signal": signal,
                                  "avant": {k: avant[k] for k in ("surveillance", "critique", "par_defaut")},
                                  "apres": {k: apres[k] for k in ("surveillance", "critique", "par_defaut")}},
                         **audit_source(request))
        return Response(self._etat(request.user))

    @staticmethod
    def _etat(user) -> dict:
        lignes = {s.signal: s for s in SeuilRh.objects.select_related("modifie_par")}
        seuils = []
        for cle, valeurs in S.effectifs().items():
            ligne = lignes.get(cle)
            seuils.append({"signal": cle, "libelle": LIBELLES.get(cle, cle), **valeurs,
                           "modifie_le": ligne.modifie_le.isoformat() if ligne else None,
                           "modifie_par": ((ligne.modifie_par.get_full_name() or ligne.modifie_par.username)
                                           if ligne and ligne.modifie_par else None)})
        return {"seuils": seuils, "modifiable": peut_configurer_seuils_rh(user)}
