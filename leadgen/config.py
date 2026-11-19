"""Chargement de la configuration (config.toml) et des secrets (.env)."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def _charger_env(chemin: Path) -> None:
    """Charge un fichier .env sans écraser les variables déjà définies."""
    try:
        from dotenv import load_dotenv

        load_dotenv(chemin, override=False)
    except ImportError:  # python-dotenv absent : lecture minimale
        if chemin.exists():
            for ligne in chemin.read_text(encoding="utf-8").splitlines():
                ligne = ligne.strip()
                if ligne and not ligne.startswith("#") and "=" in ligne:
                    cle, valeur = ligne.split("=", 1)
                    os.environ.setdefault(cle.strip(), valeur.strip())


@dataclass
class Secrets:
    anthropic: str | None
    france_travail_id: str | None
    france_travail_secret: str | None
    dropcontact: str | None
    lusha: str | None

    @classmethod
    def depuis_env(cls) -> "Secrets":
        lire = lambda nom: (os.environ.get(nom) or "").strip() or None  # noqa: E731
        return cls(
            anthropic=lire("ANTHROPIC_API_KEY"),
            france_travail_id=lire("FRANCE_TRAVAIL_CLIENT_ID"),
            france_travail_secret=lire("FRANCE_TRAVAIL_CLIENT_SECRET"),
            dropcontact=lire("DROPCONTACT_API_KEY"),
            lusha=lire("LUSHA_API_KEY"),
        )

    def etat(self) -> dict[str, bool]:
        return {
            "Claude (ANTHROPIC_API_KEY)": bool(self.anthropic),
            "France Travail (FRANCE_TRAVAIL_CLIENT_ID/SECRET)": bool(
                self.france_travail_id and self.france_travail_secret
            ),
            "Dropcontact (DROPCONTACT_API_KEY)": bool(self.dropcontact),
            "Lusha (LUSHA_API_KEY)": bool(self.lusha),
        }


def charger_config(chemin: str | Path | None = None) -> dict:
    chemin = Path(chemin) if chemin else RACINE / "config.toml"
    with open(chemin, "rb") as f:
        config = tomllib.load(f)
    _charger_env(RACINE / ".env")
    return config
