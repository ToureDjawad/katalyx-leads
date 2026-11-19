"""Vérifie la forme de la requête envoyée à Claude, avec un transport HTTP simulé (aucun appel réel)."""

import json

import anthropic
import httpx2

from leadgen.ia.client import ClientIA
from leadgen.ia.scoring import Evaluation

REPONSE = {
    "eligible": True, "raison_exclusion": None, "temperature": "tiède", "score": 61,
    "signal_cle": "Offre de deviseur publiée le 17/11/2026 sur France Travail", "justification": "…",
    "cas_usage": ["Agent Devis"], "decideur_cible": "Dirigeant", "accroche_appel": "…",
    "questions_decouverte": ["…"], "confiance": "moyenne",
}


def test_requete_structuree():
    requetes = []

    def repondre(requete):
        requetes.append(json.loads(requete.content))
        return httpx2.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": json.dumps(REPONSE, ensure_ascii=False)}],
            "stop_reason": "end_turn", "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 5},
        })

    ia = ClientIA("sk-test", "claude-opus-5-5")
    ia.client = anthropic.Anthropic(api_key="sk-test", http_client=httpx2.Client(transport=httpx2.MockTransport(repondre)))
    evaluation = ia.structurer("système", "message", Evaluation, effort="high")

    assert evaluation.temperature == "tiède" and evaluation.cas_usage == ["Agent Devis"]
    corps = requetes[0]
    assert corps["model"] == "claude-opus-5-5"
    assert corps["output_config"]["effort"] == "high"
    assert corps["output_config"]["format"]["type"] == "json_schema"
    assert corps["system"][0]["cache_control"] == {"type": "ephemeral"}
