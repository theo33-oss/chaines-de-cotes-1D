"""Bibliothèque d'exemples : liste, chargement en copie indépendante, et calcul complet de chaque exemple."""

import pytest

from chainecotes.core.donnees import chargerJson
from chainecotes.core.errors import ErreurChaine
from chainecotes.services.calcul import calculerChaine
from chainecotes.services.exemples import chargerExemple, listeExemples

IDS = [e["id"] for e in chargerJson("exemples.json")["exemples"]]  # exemples MATLAB (avec golden)
IDS_ATELIER = [e["id"] for e in chargerJson("exemples_atelier.json")["exemples"]]  # exemples du site, sans golden


def test_liste_exemples():
    liste = listeExemples()
    assert [e["id"] for e in liste] == IDS + IDS_ATELIER
    for e in liste:
        assert (
            {"id", "titre", "description", "source"}
            <= set(e)
            <= {"id", "titre", "description", "source", "methodologie"}
        )
        assert all(e.values())


def test_copie_independante():
    p = chargerExemple(IDS[0])
    assert set(p) == {"condition", "reglages", "maillons"}
    p["maillons"][0]["cote"] = -999.0
    p["condition"]["jmin"] = -999.0
    q = chargerExemple(IDS[0])
    assert q["maillons"][0]["cote"] != -999.0 and q["condition"]["jmin"] != -999.0


def test_id_inconnu():
    with pytest.raises(ErreurChaine) as e:
        chargerExemple("exemple_inexistant")
    assert e.value.identifiant == "Chaine:Exemples:inconnu"


@pytest.mark.parametrize("cid", IDS + IDS_ATELIER)
def test_calcul_complet(cid):
    b = calculerChaine(chargerExemple(cid))
    assert set(b) >= {"probleme", "res", "verdicts", "contributions", "risque", "mc", "jeuT", "avertissements"}
    assert (b["mc"] is None) == (b["res"]["CF_sigma"] == 0)


def test_exemples_du_site_ont_plusieurs_pieces_et_un_dossier_de_validation_concordant():
    from chainecotes.services.validation import dossierValidation

    assert len(IDS_ATELIER) >= 3
    for cid in IDS_ATELIER:
        p = chargerExemple(cid)
        assert len(p["maillons"]) >= 5
        d = dossierValidation(p, calculerChaine(p, n=20_000))
        assert d["nOk"] == d["nTotal"], (cid, d["bilan"])


def test_un_exemple_decrit_la_methodologie_entre_les_pages():
    avec = [e for e in listeExemples() if e.get("methodologie")]
    assert len(avec) == 1 and len(avec[0]["methodologie"]) >= 6
    texte = " ".join(avec[0]["methodologie"])
    for page in ("Calcul", "Sensibilité", "Optimisation", "Assistant d'ajustement", "Mécanisme"):
        assert page in texte
    assert "methodologie" not in chargerExemple(avec[0]["id"])
