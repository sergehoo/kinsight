"""Rapports Capital Humain programmés : échéances, génération, envoi.

Trois règles, chacune contre une fuite ou un mensonge :

1. Chaque destinataire reçoit le rapport assemblé sous SES droits (`assembler`
   avec son utilisateur) : un rapport programmé ne montre jamais plus que ce
   que son destinataire verrait à l'écran. Un destinataire qui a perdu l'accès
   au Capital Humain n'est plus servi — l'envoi est journalisé « non envoyé ».
2. Sans SMTP configuré, rien ne part, et le journal le dit. Un échec d'envoi
   est un échec, avec son motif.
3. L'échéance avance AVANT l'envoi (sous verrou) : une tâche relancée ou deux
   workers simultanés n'envoient pas deux fois le même rapport.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone

from apps.accounts.rbac import can_access_domain
from apps.audit.models import AccessLog

from . import filtres as F
from .models import EnvoiRapport, RapportProgramme

journal = logging.getLogger(__name__)

HEURE_ENVOI = time(7, 0)
# Périodes RELATIVES : elles se résolvent au moment de l'envoi.
PERIODES = {"7j": "7 derniers jours", "30j": "30 derniers jours", "90j": "90 derniers jours",
            "trimestre": "Trimestre en cours", "annee": "Année en cours"}
CLES_FILTRES = ("periode", "subsidiary", "site", "type", "departement")


def smtp_configure() -> bool:
    return bool(getattr(settings, "EMAIL_HOST", ""))


def prochaine_echeance(frequence: str, apres: datetime) -> datetime:
    """La prochaine occurrence STRICTEMENT après `apres`, à 07:00 (heure locale)."""
    local = timezone.localtime(apres)
    jour = local.date()
    if frequence == RapportProgramme.Frequence.QUOTIDIEN:
        candidat = jour if local.time() < HEURE_ENVOI else jour + timedelta(days=1)
    elif frequence == RapportProgramme.Frequence.HEBDOMADAIRE:
        decalage = (7 - jour.weekday()) % 7          # lundi
        candidat = jour + timedelta(days=decalage)
        if decalage == 0 and local.time() >= HEURE_ENVOI:
            candidat += timedelta(days=7)
    else:
        candidat = jour.replace(day=1)
        if not (jour.day == 1 and local.time() < HEURE_ENVOI):
            mois = jour.month % 12 + 1
            annee = jour.year + (jour.month == 12)
            candidat = candidat.replace(year=annee, month=mois)
    return timezone.make_aware(datetime.combine(candidat, HEURE_ENVOI), timezone.get_current_timezone())


def filtres_propres(brut: dict) -> dict:
    """Seules les clés de filtre connues ; une période relative obligatoire."""
    propre = {k: str(v) for k, v in (brut or {}).items() if k in CLES_FILTRES and v not in (None, "", "all")}
    propre.setdefault("periode", "30j")
    if propre["periode"] not in PERIODES:
        raise F.FiltreInvalide(f"Période programmable inconnue : « {propre['periode']} » "
                               f"(attendu : {', '.join(PERIODES)}).", 400)
    return propre


def envoyer(rapport: RapportProgramme, *, maintenant=None) -> list[EnvoiRapport]:
    """Génère et envoie le rapport à chacun de ses destinataires, sous SES droits."""
    from .rapport_formats import RENDUS
    from .rapport_rh import assembler

    maintenant = maintenant or timezone.now()
    traces = []
    rendu, type_contenu = RENDUS[rapport.format]
    for destinataire in rapport.destinataires.all():
        def tracer(statut, detail=""):
            traces.append(EnvoiRapport.objects.create(rapport=rapport, destinataire=destinataire,
                                                      statut=statut, detail=detail[:300]))

        if not destinataire.is_active or not can_access_domain(destinataire, "capital-humain"):
            tracer(EnvoiRapport.Statut.IGNORE, "Destinataire sans accès au Capital Humain.")
            continue
        if not destinataire.email:
            tracer(EnvoiRapport.Statut.IGNORE, "Destinataire sans adresse e-mail.")
            continue
        if not smtp_configure():
            tracer(EnvoiRapport.Statut.IGNORE, "SMTP non configuré sur le serveur (EMAIL_HOST).")
            continue
        try:
            filtres = F.lire(rapport.filtres, timezone.localdate(maintenant))
            contenu_rapport = assembler(destinataire, filtres)
        except F.FiltreInvalide as refus:
            tracer(EnvoiRapport.Statut.IGNORE, f"Filtres non applicables pour ce destinataire : {refus.motif}")
            continue
        piece = rendu(contenu_rapport)
        nom = f"k-insight-capital-humain-{filtres.periode.debut.isoformat()}-{filtres.periode.fin.isoformat()}.{rapport.format}"
        message = EmailMessage(
            subject=f"[K-Insight] {rapport.nom} — {filtres.libelle}",
            body=(f"Bonjour,\n\nVeuillez trouver le rapport Capital Humain « {rapport.nom} » "
                  f"({filtres.libelle}, périmètre : {contenu_rapport['perimetre']}).\n\n"
                  "Il est établi sous vos droits d'accès K-Insight. N/D signifie « non mesuré », jamais zéro.\n\n"
                  "— K-Insight, plateforme de gouvernance du Groupe Kaydan"),
            to=[destinataire.email],
        )
        message.attach(nom, piece, type_contenu)
        try:
            message.send(fail_silently=False)
        except Exception as erreur:  # noqa: BLE001 — l'échec SMTP est journalisé, pas avalé
            journal.warning("Envoi du rapport %s à %s en échec : %s", rapport.pk, destinataire.pk, erreur)
            tracer(EnvoiRapport.Statut.ECHEC, f"Échec SMTP : {type(erreur).__name__}")
            continue
        tracer(EnvoiRapport.Statut.ENVOYE, f"{len(piece)} octets")
        AccessLog.record(user=destinataire, action="send_hr_report", metric_key="hr.rapport",
                         scope_codes=(["*"] if destinataire.scope().is_group else sorted(destinataire.scope().subsidiaries)),
                         payload={"rapport": rapport.pk, "format": rapport.format, **filtres.comme_trace()})
    return traces


def envoyer_les_dus(maintenant=None) -> dict:
    """Pour chaque rapport dû : avancer l'échéance sous verrou, PUIS envoyer."""
    maintenant = maintenant or timezone.now()
    bilan = {"rapports": 0, "envoyes": 0, "non_envoyes": 0}
    dus = list(RapportProgramme.objects.filter(actif=True, prochain_envoi__lte=maintenant)
               .values_list("pk", flat=True))
    for pk in dus:
        with transaction.atomic():
            rapport = (RapportProgramme.objects.select_for_update(skip_locked=True)
                       .filter(pk=pk, actif=True, prochain_envoi__lte=maintenant).first())
            if rapport is None:
                continue  # pris par un autre worker, ou déjà avancé
            rapport.prochain_envoi = prochaine_echeance(rapport.frequence, maintenant)
            rapport.dernier_envoi = maintenant
            rapport.save(update_fields=["prochain_envoi", "dernier_envoi"])
        traces = envoyer(rapport, maintenant=maintenant)
        bilan["rapports"] += 1
        bilan["envoyes"] += sum(1 for t in traces if t.statut == EnvoiRapport.Statut.ENVOYE)
        bilan["non_envoyes"] += sum(1 for t in traces if t.statut != EnvoiRapport.Statut.ENVOYE)
    return bilan
