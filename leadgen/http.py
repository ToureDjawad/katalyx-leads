"""Session HTTP partagée : délais d'attente, reprises automatiques et identification polie."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "katalyx-leads/1.0 (+https://katalyx.fr)"
DELAI = (10, 60)  # connexion, lecture (secondes)


def nouvelle_session() -> requests.Session:
    session = requests.Session()
    reprises = Retry(
        total=5,
        connect=5,
        read=3,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
        respect_retry_after_header=True,
    )
    adaptateur = HTTPAdapter(max_retries=reprises)
    session.mount("https://", adaptateur)
    session.mount("http://", adaptateur)
    session.headers["User-Agent"] = USER_AGENT
    return session
