"""Couche sémantique : catalogue déclaratif des métriques de gouvernance.

Ce catalogue est la *source de vérité* sur « quelles métriques existent, comment
elles s'appellent, dans quelle unité, à quelle maille ». Il sert à trois usages :
1. L'API governance (catalogue exposé au frontend BI).
2. Le moteur IA décisionnel, qui ne raisonne QUE sur des métriques déclarées ici
   (ancrage strict — il n'invente jamais d'indicateur, cf. ADR-0007).
3. Le moteur d'alertes (seuils, direction « bon sens »).
"""

from .registry import Metric, MetricCatalog, CATALOG

__all__ = ["Metric", "MetricCatalog", "CATALOG"]
