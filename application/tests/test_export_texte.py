"""Texte de l'étude (bloc-notes et IA) : tout y est, rien n'est recalculé."""

import pytest

from chainecotes.services.calcul import calculerChaine
from chainecotes.services.exemples import chargerExemple, listeExemples
from chainecotes.services.export_texte import CONSIGNE_IA, texteEtude, texteIA


@pytest.fixture(scope="module")
def etude():
    p = chargerExemple(listeExemples()[0]["id"])
    return p, calculerChaine(p, n=2000)


def test_texte_contient_donnees_resultats_demarche(etude):
    t = texteEtude(*etude)
    for mot in ("DONNÉES", "RÉSULTATS", "CONCLUSION", "DÉMARCHE", "Cote_1", "Pire des cas", "Cpk", "Monte-Carlo"):
        assert mot in t
    assert "nan" not in t.lower().replace("monte-carlo", "")


def test_texte_ia_encadre_l_etude(etude):
    t = texteIA(*etude)
    assert t.startswith(CONSIGNE_IA)
    assert "--- ÉTUDE ---" in t and t.rstrip().endswith("--- FIN DE L'ÉTUDE ---")


@pytest.mark.parametrize("i", range(len(listeExemples())))
def test_tous_les_exemples(i):
    p = chargerExemple(listeExemples()[i]["id"])
    assert "RÉSULTATS" in texteEtude(p, calculerChaine(p, n=500))
