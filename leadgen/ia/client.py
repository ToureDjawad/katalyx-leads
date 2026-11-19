"""Client Claude commun : sortie JSON validée par Pydantic, mise en cache du prompt système,
et repli automatique côté serveur si le modèle principal décline une requête."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from ..config import RACINE

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)
DOSSIER_PROMPTS = RACINE / "prompts"


def lire_prompt(nom: str) -> str:
    return (DOSSIER_PROMPTS / nom).read_text(encoding="utf-8")


class ClientIA:
    def __init__(self, cle: str, modele: str):
        self.client = anthropic.Anthropic(api_key=cle, max_retries=4)
        self.modele = modele
        self.jetons_entree = 0
        self.jetons_sortie = 0

    def structurer(self, systeme: str, message: str, schema: type[T], effort: str = "medium",
                   max_tokens: int = 16000) -> T | None:
        """Envoie une requête et renvoie un objet Pydantic validé, ou None en cas d'échec."""
        try:
            reponse = self.client.beta.messages.parse(
                model=self.modele,
                max_tokens=max_tokens,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                system=[{"type": "text", "text": systeme, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": message}],
                output_format=schema,
                output_config={"effort": effort},
            )
        except anthropic.RateLimitError as erreur:
            log.error("Limite de débit Claude atteinte : %s", erreur)
            return None
        except anthropic.APIStatusError as erreur:
            log.error("Erreur API Claude (%s) : %s", erreur.status_code, erreur.message)
            return None
        except anthropic.APIConnectionError as erreur:
            log.error("Connexion à Claude impossible : %s", erreur)
            return None

        if reponse.usage:
            self.jetons_entree += (reponse.usage.input_tokens or 0) + (reponse.usage.cache_read_input_tokens or 0)
            self.jetons_sortie += reponse.usage.output_tokens or 0
        if reponse.stop_reason == "refusal":
            log.warning("Claude a décliné la requête.")
            return None
        if reponse.stop_reason == "max_tokens":
            log.warning("Réponse tronquée (max_tokens atteint).")
            return None
        return reponse.parsed_output
