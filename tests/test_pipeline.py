"""Tests hors ligne : aucune requête réseau, aucune clé nécessaire."""

from datetime import date, timedelta

from leadgen.config import charger_config
from leadgen.enrichissement.contacts import choisir_dirigeant
from leadgen.export import exporter
from leadgen.filtres import raison_exclusion
from leadgen.ia.extraction import extraire_par_regles
from leadgen.ia.scoring import evaluer_heuristique, pre_score
from leadgen.modeles import Candidat, Dirigeant, Entreprise, Signal
from leadgen.pipeline import regrouper, selectionner
from leadgen.sources.actualites import lire_flux
from leadgen.sources.boamp import _extraire
from leadgen.sources.france_travail import _vers_signal
from leadgen.texte import normaliser_nom, similarite

CONFIG = charger_config()
AUJOURDHUI = date(2026, 11, 19)


class HistoriqueVide:
    def contient(self, siren):
        return False


def entreprise(**kw):
    base = dict(siren="123456789", nom="DURAND INDUSTRIES", naf="25.62B", libelle_naf=None, tranche_effectif="12",
                categorie="PME", nature_juridique="5710", adresse="1 rue X 13100 AIX", code_postal="13100",
                ville="AIX-EN-PROVENCE", departement="13", date_creation="1998-01-01",
                dirigeants=[Dirigeant("JEAN PIERRE", "DURAND", "Président")])
    base.update(kw)
    return Entreprise(**base)


def signal(type_="offre_emploi_ia", jours=2, source="france_travail", entreprise_nom="Durand Industries", **kw):
    return Signal(source=source, type=type_, titre="Offre d'emploi : Chef de projet IA", url="https://x",
                  date=AUJOURDHUI - timedelta(days=jours), entreprise_nom=entreprise_nom, **kw)


def test_normalisation_des_noms():
    assert normaliser_nom("Groupe Durand Industries SAS") == "durand industries"
    assert similarite("Durand Industries", "DURAND INDUSTRIES (DI)") == 1.0
    assert similarite("Durand", "Martin Logistique") < 0.5


def test_offre_france_travail_convertie():
    offre = {"id": "1", "intitule": "Deviseur H/F", "dateCreation": "2026-11-17T10:00:00.000Z",
             "description": "<p>Chiffrage</p>", "entreprise": {"nom": "ACME", "url": "https://acme.fr"},
             "lieuTravail": {"libelle": "13 - Aix", "codePostal": "13100"}, "codeNAF": "25.62B"}
    s = _vers_signal(offre, "offre_emploi_douleur", "deviseur")
    assert s.entreprise_nom == "ACME" and s.date == date(2026, 11, 17) and s.meta["site_web"] == "https://acme.fr"
    assert _vers_signal({**offre, "entreprise": {}}, "x", "y") is None  # offre anonyme écartée


def test_flux_rss():
    rss = b"""<rss><channel><item><title>Acme l\xc3\xa8ve 3 millions - Les Echos</title><link>https://a</link>
    <pubDate>Tue, 17 Nov 2026 08:00:00 GMT</pubDate><description>&lt;b&gt;Acme&lt;/b&gt; industrie</description></item></channel></rss>"""
    [s] = lire_flux(rss, "test")
    assert s.date == date(2026, 11, 17) and s.texte == "Acme industrie"
    assert extraire_par_regles(s).entreprise_nom == "Acme"


def test_boamp_ignore_les_plateformes():
    infos = _extraire('{"siret": "24310051800014", "mail": "publications-joue@aws-france.com", "email": "achats@ville.fr", "cp": "31000"}')
    assert infos == {"siret": "24310051800014", "email_acheteur": "achats@ville.fr", "code_postal": "31000", "ville": None}


def test_filtres():
    c = Candidat(cle="x", nom_signal="x", signaux=[signal()], entreprise=entreprise())
    assert raison_exclusion(c, CONFIG, HistoriqueVide()) is None
    c.entreprise = entreprise(naf="78.20Z")
    assert "activité exclue" in raison_exclusion(c, CONFIG, HistoriqueVide())
    c.entreprise = entreprise(tranche_effectif="02")
    assert "trop petite" in raison_exclusion(c, CONFIG, HistoriqueVide())
    c.signaux = [signal(type_="actualite", source="actualites")]
    c.entreprise = entreprise(tranche_effectif=None, chiffre_affaires=None)
    assert "non diffusé" in raison_exclusion(c, CONFIG, HistoriqueVide())


def test_pre_score_et_heuristique():
    chaud = Candidat(cle="a", nom_signal="a", signaux=[signal()], entreprise=entreprise())
    froid = Candidat(cle="b", nom_signal="b", signaux=[signal(type_="actualite", source="actualites", jours=28)],
                     entreprise=entreprise(departement="59", naf="47.11A"))
    chaud.pre_score, froid.pre_score = pre_score(chaud, CONFIG, AUJOURDHUI), pre_score(froid, CONFIG, AUJOURDHUI)
    assert chaud.pre_score > 70 > froid.pre_score
    assert evaluer_heuristique(chaud, AUJOURDHUI)["temperature"] == "chaud"
    assert evaluer_heuristique(froid, AUJOURDHUI)["temperature"] == "froid"


def test_regroupement_et_selection():
    groupes = regrouper([signal(), signal(type_="offre_emploi_douleur"), signal(entreprise_nom="Autre SA")])
    assert sorted(len(g.signaux) for g in groupes) == [1, 2]
    candidats = []
    for i, (temp, score, source) in enumerate([("tiède", 90, "france_travail"), ("chaud", 70, "boamp"),
                                               ("chaud", 80, "boamp"), ("chaud", 75, "france_travail")]):
        c = Candidat(cle=str(i), nom_signal="", signaux=[signal(source=source)])
        c.evaluation = {"temperature": temp, "score": score}
        candidats.append(c)
    choisis = selectionner(candidats, 3, max_boamp=1)
    assert [(c.evaluation["temperature"], c.evaluation["score"]) for c in choisis] == [("chaud", 80), ("chaud", 75), ("tiède", 90)]


def test_choix_du_dirigeant():
    d = choisir_dirigeant([Dirigeant("A", "X", "Commissaire aux comptes titulaire"), Dirigeant("B", "Y", "Directeur général"),
                           Dirigeant("C", "Z", "Président")])
    assert d.nom == "Z"


def test_export(tmp_path):
    c = Candidat(cle="a", nom_signal="a", signaux=[signal()], entreprise=entreprise(), pre_score=80)
    c.evaluation = evaluer_heuristique(c, AUJOURDHUI)
    chemins = exporter([c], tmp_path, {"leads livrés": 1})
    contenu = chemins["csv"].read_text(encoding="utf-8-sig")
    assert contenu.startswith("rang;temperature;score") and "DURAND INDUSTRIES" in contenu
    assert "## 1. DURAND INDUSTRIES" in chemins["md"].read_text(encoding="utf-8")
