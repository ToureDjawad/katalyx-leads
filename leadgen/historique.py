"""Mémoire des leads déjà livrés, pour que chaque exécution produise des leads nouveaux."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path


class Historique:
    def __init__(self, chemin: Path):
        self.chemin = chemin
        self.donnees: dict[str, dict] = {}
        if chemin.exists():
            self.donnees = json.loads(chemin.read_text(encoding="utf-8"))

    def contient(self, siren: str) -> bool:
        return siren in self.donnees

    def ajouter(self, siren: str, nom: str, temperature: str) -> None:
        self.donnees[siren] = {"nom": nom, "temperature": temperature, "livre_le": date.today().isoformat()}

    def enregistrer(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        self.chemin.write_text(json.dumps(self.donnees, ensure_ascii=False, indent=2), encoding="utf-8")
