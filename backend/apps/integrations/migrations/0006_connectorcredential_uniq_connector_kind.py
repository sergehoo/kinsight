"""Un connecteur n'a qu'un secret par type — et le ménage avant la règle.

La contrainte seule échouerait sur toute base déjà en service : chaque
enregistrement de secret créait une ligne au lieu de remplacer la précédente, et
une source de production en portait huit. `AddConstraint` planterait donc pendant
`migrate`, laissant le conteneur backend sans rien à l'écoute.

On dédoublonne d'abord, en gardant le PLUS RÉCENT de chaque couple
(connecteur, type) : c'est le dernier secret déposé, donc celui qu'on voulait
utiliser. Les versions antérieures n'ont aucune valeur — elles ne servaient qu'à
faire douter de ce que le connecteur envoyait vraiment.
"""

from django.db import migrations, models


def degrouper(apps, schema_editor):
    Credential = apps.get_model("integrations", "ConnectorCredential")
    # Tri descendant sur la date : la première ligne vue pour un couple est la plus
    # récente, on la garde ; les suivantes sont des versions périmées.
    vus = set()
    perimes = []
    for cred in Credential.objects.order_by("connector_id", "kind", "-created_at").only(
        "id", "connector_id", "kind"
    ):
        cle = (cred.connector_id, cred.kind)
        if cle in vus:
            perimes.append(cred.pk)
        else:
            vus.add(cle)
    if perimes:
        Credential.objects.filter(pk__in=perimes).delete()


def ne_rien_defaire(apps, schema_editor):
    """Rien à restaurer : les secrets supprimés étaient périmés, et leur clair n'a
    jamais quitté la base chiffrée. Une migration inverse ne peut pas les recréer."""


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0005_alter_connectorcredential_options_and_more"),
    ]

    operations = [
        migrations.RunPython(degrouper, ne_rien_defaire),
        migrations.AddConstraint(
            model_name="connectorcredential",
            constraint=models.UniqueConstraint(
                fields=("connector", "kind"), name="uniq_connector_kind"
            ),
        ),
    ]
