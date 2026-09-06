"""Chemins Kaydan Shield RÉELLEMENT documentés (Swagger `/api/docs/`).

Un seul endroit déclare les chemins et les filtres réellement acceptés. Toute
lecture passe par ici : c'est ce qui garantit qu'aucun endpoint ni paramètre
n'est inventé ailleurs dans le code.

Constat important, vérifié dans le Swagger et non contourné :
`/api/v1/employees/employees/` n'expose AUCUN filtre `site` (seulement company,
contract_type, department, status, tenant). L'effectif employés par site n'est
donc pas dérivable — il est rendu `unknown`, jamais réparti au prorata.
"""

# ── Référentiel ──────────────────────────────────────────────────────────────
EMPLOYEES = "/api/v1/employees/employees/"          # filtres : company, contract_type, department, status, tenant
WORKERS = "/api/v1/ouvriers/workers/"               # filtres : site, status, trade, subcontractor, tenant
SITES = "/api/v1/sites/sites/"                      # filtres : company, status, type, tenant
DEPARTMENTS = "/api/v1/employees/departments/"

# ── Présence ─────────────────────────────────────────────────────────────────
ATTENDANCE_TODAY = "/api/v1/attendance/summary/today/"   # aucun filtre ; compteurs du jour
ATTENDANCE_DAYS = "/api/v1/attendance/days/"             # filtres : site, date, date_from/to, present, absent, late, person_kind…

# ── Sécurité ─────────────────────────────────────────────────────────────────
ALERTS = "/api/v1/antifraud/alerts/"                # filtres : site, severity(critical|warning|info), status(open|acknowledged|confirmed|dismissed|escalated)
ACCESS_EVENTS = "/api/v1/access/events/"            # filtres : site, decision, date_from/to, direction, device
DEVICES = "/api/v1/devices/devices/"                # filtres : site, status(active|inactive|maintenance|lost), zone, battery_lt
VISITOR_REQUESTS = "/api/v1/visitors/requests/"     # filtres : site, status, category

# Valeurs d'énumération confirmées par le Swagger.
ALERT_SEVERITIES = ("critical", "warning", "info")
# Vérifié sur le schéma LIVE : la valeur est « denied », pas « deny ».
# Un filtre inconnu est ignoré silencieusement par DRF et aurait renvoyé
# TOUS les événements d'accès en les présentant comme des refus.
ACCESS_DECISIONS = ("granted", "denied", "review")
VISITOR_STATUSES = ("pending", "approved", "checked_in", "completed", "rejected", "cancelled", "expired")
ALERT_OPEN_STATUSES = ("open", "acknowledged", "escalated")
DEVICE_STATUSES = ("active", "inactive", "maintenance", "lost")
SITE_STATUSES = ("active", "inactive", "archived")
