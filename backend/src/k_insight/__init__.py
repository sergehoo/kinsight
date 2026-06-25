"""Domaine pur k-insight — logique métier sans dépendance (ni Django, ni DB).

Ce paquet contient les *définitions sémantiques* et les *fonctions de calcul* des
KPI de gouvernance. Il est volontairement dépourvu de toute dépendance externe :
il se teste avec `unittest` sans base de données, exactement comme le domaine
financier d'AUGUSTINE.

Règle d'or : le calcul des indicateurs vit ICI (Python pur, testé), tandis que la
*matérialisation* à grande échelle se fait dans le Data Warehouse (SQL/dbt). Les
deux doivent rester cohérents — le domaine pur fait foi sur la sémantique.
"""

__all__ = ["kpi", "semantic"]
