#!/usr/bin/env python3
"""Utilitaire d'administration Django de k-insight."""
import os
import sys
from pathlib import Path

# Le domaine pur vit sous src/ (paquet `k_insight`). On l'ajoute au chemin pour que
# la couche Django puisse l'importer (cf. ADR-0006).
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "src"))


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
