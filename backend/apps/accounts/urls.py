from django.urls import path

from .views import MeView, SubsidiariesView

urlpatterns = [
    path("me/", MeView.as_view(), name="auth-me"),
    # Les filiales que l'utilisateur peut filtrer, bornées côté serveur. Voir la
    # vue : `/auth/me/` ne suffit pas, un périmètre Groupe y a une liste vide.
    path("subsidiaries/", SubsidiariesView.as_view(), name="auth-subsidiaries"),
]
