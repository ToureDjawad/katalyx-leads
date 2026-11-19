"""Export des leads : CSV (ouvrable dans Excel ou Google Sheets), JSON et fiches d'appel en Markdown."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from .ia.scoring import LIBELLES_TRANCHES, type_effectif
from .modeles import Candidat

COLONNES = [
    "rang", "temperature", "score", "confiance", "entreprise", "siren", "code_naf", "effectif",
    "chiffre_affaires", "ville", "departement", "decideur", "fonction_registre", "fonction_a_appeler",
    "email", "telephone", "linkedin", "source_contact", "signal_cle", "date_signal", "source_signal",
    "url_signal", "nb_signaux", "cas_usage", "accroche_appel", "questions_decouverte", "justification",
    "site_web", "fiche_annuaire", "mode_scoring",
]


def _signal_principal(c: Candidat):
    return max(c.signaux, key=lambda s: (s.date.toordinal() if s.date else 0))


def ligne(rang: int, c: Candidat) -> dict:
    e, ev, ct, s = c.entreprise, c.evaluation, c.contact, _signal_principal(c)
    return {
        "rang": rang,
        "temperature": ev["temperature"],
        "score": ev["score"],
        "confiance": ev["confiance"],
        "entreprise": e.nom,
        "siren": e.siren,
        "code_naf": e.naf,
        "effectif": LIBELLES_TRANCHES.get(e.tranche_effectif or "", "non diffusé"),
        "chiffre_affaires": f"{e.chiffre_affaires:.0f}" if e.chiffre_affaires else "",
        "ville": e.ville,
        "departement": e.departement,
        "decideur": ct.nom_complet if ct else "",
        "fonction_registre": ct.fonction if ct else "",
        "fonction_a_appeler": ev["decideur_cible"],
        "email": (ct.email if ct else "") or "",
        "telephone": (ct.telephone if ct else "") or "",
        "linkedin": (ct.linkedin if ct else "") or "",
        "source_contact": ct.source if ct else "",
        "signal_cle": ev["signal_cle"],
        "date_signal": s.date.isoformat() if s.date else "",
        "source_signal": s.source,
        "url_signal": s.url,
        "nb_signaux": len(c.signaux),
        "cas_usage": ", ".join(ev["cas_usage"]),
        "accroche_appel": ev["accroche_appel"],
        "questions_decouverte": " | ".join(ev["questions_decouverte"]),
        "justification": ev["justification"],
        "site_web": e.site_web or "",
        "fiche_annuaire": e.lien_annuaire,
        "mode_scoring": ev.get("mode", ""),
    }


def fiche_markdown(rang: int, c: Candidat) -> str:
    d = ligne(rang, c)
    emoji = {"chaud": "🔥", "tiède": "🌤️", "froid": "❄️"}.get(d["temperature"], "")
    signaux = "\n".join(
        f"  - {x.date.isoformat() if x.date else '?'} · {x.source} · [{x.titre}]({x.url})"
        for x in sorted(c.signaux, key=lambda x: x.date.toordinal() if x.date else 0, reverse=True)
    )
    questions = "\n".join(f"  {i}. {q}" for i, q in enumerate(c.evaluation["questions_decouverte"], 1))
    contact = " · ".join(v for v in [d["email"], d["telephone"]] if v) or "à compléter (voir LinkedIn ou le standard)"
    return f"""## {rang}. {d['entreprise']} : {emoji} {d['temperature']} ({d['score']}/100, confiance {d['confiance']})

- **Entreprise** : SIREN {d['siren']}, NAF {d['code_naf']}, {d['effectif']} salariés, {d['ville']} ({d['departement']}). [Fiche officielle]({d['fiche_annuaire']})
- **Qui appeler** : {d['decideur'] or 'non identifié'} ({d['fonction_registre']}). Fonction visée : {d['fonction_a_appeler']}
- **Coordonnées** : {contact}{f". [Recherche LinkedIn]({d['linkedin']})" if d['linkedin'] else ""}
- **Signal clé** : {d['signal_cle']}
- **Offre à proposer** : {d['cas_usage']}
- **Pourquoi** : {d['justification']}
- **Accroche** : « {d['accroche_appel']} »
- **Questions de découverte** :
{questions}
- **Tous les signaux** :
{signaux}
"""


def exporter(leads: list[Candidat], dossier: Path, statistiques: dict) -> dict[str, Path]:
    dossier.mkdir(parents=True, exist_ok=True)
    horodatage = datetime.now().strftime("%Y-%m-%d_%Hh%M")
    chemins = {
        "csv": dossier / f"leads_{horodatage}.csv",
        "json": dossier / f"leads_{horodatage}.json",
        "md": dossier / f"leads_{horodatage}.md",
    }
    lignes = [ligne(i, c) for i, c in enumerate(leads, 1)]
    # Point-virgule et BOM UTF-8 : le CSV s'ouvre directement dans Excel en français.
    with open(chemins["csv"], "w", newline="", encoding="utf-8-sig") as f:
        ecrivain = csv.DictWriter(f, fieldnames=COLONNES, delimiter=";")
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    chemins["json"].write_text(
        json.dumps({"statistiques": statistiques, "leads": lignes}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    entete = (
        f"# Leads Katalyx : Agents IA et Audit IA ({datetime.now().strftime('%d/%m/%Y')})\n\n"
        + " · ".join(f"{k} : {v}" for k, v in statistiques.items())
        + "\n\n"
    )
    chemins["md"].write_text(entete + "\n".join(fiche_markdown(i, c) for i, c in enumerate(leads, 1)), encoding="utf-8")
    return chemins
