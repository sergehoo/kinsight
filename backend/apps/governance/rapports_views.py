"""Rapports Capital Humain programmés — l'action « Programmer un rapport ».

GET    /api/v1/governance/hr/rapports-programmes/            mes programmations (+ journal)
POST   /api/v1/governance/hr/rapports-programmes/            programmer
PATCH  /api/v1/governance/hr/rapports-programmes/<id>/       modifier, suspendre
DELETE /api/v1/governance/hr/rapports-programmes/<id>/       supprimer
POST   /api/v1/governance/hr/rapports-programmes/<id>/envoyer/  envoyer maintenant

Destinataires : soi-même ; la DRH Groupe et l'administration peuvent ajouter
d'autres utilisateurs ayant accès au Capital Humain — jamais une adresse libre.
Chacun reçoit le rapport sous SES droits.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.rbac import peut_configurer_seuils_rh, peut_module_rh
from apps.audit.middleware import audit_source
from apps.audit.models import AccessLog

from . import filtres as F
from . import rapports_programmes as P
from .hr_registry import REGISTRE
from .lecture_rh import portee
from .models import RapportProgramme

User = get_user_model()


def _refus():
    return Response({"detail": "Rapports RH non autorisés pour votre profil."},
                    status=status.HTTP_403_FORBIDDEN)


def _nom(u) -> str:
    return u.get_full_name() or u.username


def _possibles(user) -> list:
    if not peut_configurer_seuils_rh(user):
        return [user]
    return [u for u in User.objects.filter(is_active=True).exclude(email="").order_by("username")
            if peut_module_rh(u, "hr-reports")]


def _serialiser(r: RapportProgramme) -> dict:
    return {
        "id": r.pk, "nom": r.nom, "frequence": r.frequence, "frequence_libelle": r.get_frequence_display(),
        "format": r.format, "filtres": r.filtres,
        "periode_libelle": P.PERIODES.get(r.filtres.get("periode", ""), r.filtres.get("periode", "")),
        "actif": r.actif, "auteur": _nom(r.auteur),
        "destinataires": [{"id": u.pk, "nom": _nom(u)} for u in r.destinataires.all()],
        "prochain_envoi": r.prochain_envoi.isoformat() if r.prochain_envoi else None,
        "dernier_envoi": r.dernier_envoi.isoformat() if r.dernier_envoi else None,
        "envois": [{"destinataire": _nom(e.destinataire) if e.destinataire else "—", "statut": e.statut,
                    "statut_libelle": e.get_statut_display(), "detail": e.detail, "le": e.envoye_le.isoformat()}
                   for e in r.envois.select_related("destinataire")[:6]],
    }


class _Base(APIView):
    permission_classes = [IsAuthenticated]

    def _visibles(self, user):
        qs = RapportProgramme.objects.select_related("auteur").prefetch_related("destinataires")
        return qs if peut_configurer_seuils_rh(user) else qs.filter(auteur=user)

    def _valider(self, user, donnees: dict, partiel: bool = False) -> tuple[dict, list | None]:
        """Champs validés, destinataires validés. Lève F.FiltreInvalide (400/403)."""
        champs = {}
        if not partiel or "nom" in donnees:
            nom = str(donnees.get("nom") or "").strip()
            if not nom:
                raise F.FiltreInvalide("Donnez un nom au rapport.", 400)
            champs["nom"] = nom[:120]
        if not partiel or "frequence" in donnees:
            if donnees.get("frequence") not in RapportProgramme.Frequence.values:
                raise F.FiltreInvalide("Fréquence inconnue (quotidien, hebdomadaire, mensuel).", 400)
            champs["frequence"] = donnees["frequence"]
        if not partiel or "format" in donnees:
            if donnees.get("format") not in RapportProgramme.Format.values:
                raise F.FiltreInvalide("Format inconnu (xlsx, pdf, pptx).", 400)
            champs["format"] = donnees["format"]
        if not partiel or "filtres" in donnees:
            filtres = P.filtres_propres(donnees.get("filtres") or {})
            # Les filtres doivent être lisibles par l'AUTEUR : une filiale hors de
            # son périmètre est refusée dès la programmation (403), un filtre
            # incohérent aussi (400). « Rien à lire aujourd'hui » (début de
            # trimestre) n'empêche pas de programmer : la période est relative.
            try:
                portee(user, REGISTRE["hr.employes_actifs_odoo"], F.lire(filtres, timezone.localdate()))
            except F.FiltreInvalide as refus:
                if refus.code_http != 200:
                    raise
            champs["filtres"] = filtres
        if "actif" in donnees:
            champs["actif"] = bool(donnees["actif"])

        destinataires = None
        if not partiel or "destinataires" in donnees:
            ids = {int(i) for i in donnees.get("destinataires") or [user.pk] if str(i).isdigit()}
            permis = {u.pk: u for u in _possibles(user)}
            refuses = ids - set(permis)
            if refuses:
                raise F.FiltreInvalide("Destinataire non autorisé : seuls des utilisateurs ayant accès au "
                                       "Capital Humain peuvent recevoir ce rapport"
                                       + ("." if peut_configurer_seuils_rh(user) else
                                          ", et vous ne pouvez programmer que pour vous-même."), 400)
            if not ids:
                raise F.FiltreInvalide("Au moins un destinataire.", 400)
            destinataires = [permis[i] for i in ids]
        return champs, destinataires

    def _tracer(self, request, action: str, rapport: RapportProgramme, **extra):
        scope = request.user.scope()
        AccessLog.record(user=request.user, action=action, metric_key="hr.rapport",
                         scope_codes=["*"] if scope.is_group else sorted(scope.subsidiaries),
                         payload={"rapport": rapport.pk, "nom": rapport.nom, "format": rapport.format,
                                  "frequence": rapport.frequence, "filtres": rapport.filtres,
                                  "destinataires": [u.pk for u in rapport.destinataires.all()], **extra},
                         **audit_source(request))


class RapportsProgrammesView(_Base):
    def get(self, request):
        if not peut_module_rh(request.user, "hr-reports"):
            return _refus()
        return Response({
            "rapports": [_serialiser(r) for r in self._visibles(request.user)],
            "smtp_configure": P.smtp_configure(),
            "peut_programmer_pour_autrui": peut_configurer_seuils_rh(request.user),
            "destinataires_possibles": [{"id": u.pk, "nom": _nom(u)} for u in _possibles(request.user)],
            "periodes": P.PERIODES,
        })

    def post(self, request):
        if not peut_module_rh(request.user, "hr-reports"):
            return _refus()
        donnees = request.data if isinstance(request.data, dict) else {}
        try:
            champs, destinataires = self._valider(request.user, donnees)
        except F.FiltreInvalide as refus:
            return Response({"detail": refus.motif}, status=refus.code_http)
        rapport = RapportProgramme.objects.create(
            auteur=request.user, prochain_envoi=P.prochaine_echeance(champs["frequence"], timezone.now()), **champs)
        rapport.destinataires.set(destinataires)
        self._tracer(request, "schedule_hr_report", rapport)
        return Response(_serialiser(rapport), status=status.HTTP_201_CREATED)


class RapportProgrammeView(_Base):
    def _trouver(self, request, pk):
        if not peut_module_rh(request.user, "hr-reports"):
            return None, _refus()
        rapport = self._visibles(request.user).filter(pk=pk).first()
        if rapport is None:
            return None, Response({"detail": "Rapport programmé introuvable."}, status=status.HTTP_404_NOT_FOUND)
        return rapport, None

    def patch(self, request, pk: int):
        rapport, refus = self._trouver(request, pk)
        if refus:
            return refus
        donnees = request.data if isinstance(request.data, dict) else {}
        try:
            champs, destinataires = self._valider(request.user, donnees, partiel=True)
        except F.FiltreInvalide as erreur:
            return Response({"detail": erreur.motif}, status=erreur.code_http)
        for cle, valeur in champs.items():
            setattr(rapport, cle, valeur)
        if "frequence" in champs or champs.get("actif"):
            rapport.prochain_envoi = P.prochaine_echeance(rapport.frequence, timezone.now())
        rapport.save()
        if destinataires is not None:
            rapport.destinataires.set(destinataires)
        self._tracer(request, "update_scheduled_hr_report", rapport, champs=sorted(champs))
        return Response(_serialiser(rapport))

    def delete(self, request, pk: int):
        rapport, refus = self._trouver(request, pk)
        if refus:
            return refus
        self._tracer(request, "delete_scheduled_hr_report", rapport)
        rapport.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EnvoyerRapportView(RapportProgrammeView):
    def post(self, request, pk: int):
        rapport, refus = self._trouver(request, pk)
        if refus:
            return refus
        traces = P.envoyer(rapport)
        self._tracer(request, "send_now_hr_report", rapport, statuts=[t.statut for t in traces])
        rapport.refresh_from_db()
        return Response(_serialiser(rapport))
