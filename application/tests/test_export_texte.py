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
    t = texteEtude(etude[1])
    for mot in ("DONNÉES", "RÉSULTATS", "CONCLUSION", "DÉMARCHE", "Cote_1", "Pire des cas", "Cpk", "Monte-Carlo"):
        assert mot in t
    assert "nan" not in t.lower().replace("monte-carlo", "")


def test_texte_ia_encadre_l_etude(etude):
    t = texteIA(etude[1])
    assert t.startswith(CONSIGNE_IA)
    assert "--- ÉTUDE ---" in t and t.rstrip().endswith("--- FIN DE L'ÉTUDE ---")


@pytest.mark.parametrize("i", range(len(listeExemples())))
def test_tous_les_exemples(i):
    p = chargerExemple(listeExemples()[i]["id"])
    assert "RÉSULTATS" in texteEtude(calculerChaine(p, n=500))


def test_dilatation_levier_et_absence_de_limite_sont_ecrits():
    from chainecotes.core.nombres import fr  # noqa: F401

    p = chargerExemple("thermique_par_cote")
    t = texteEtude(calculerChaine(p, n=500))
    assert "α 23,00 µm/m/K" in t and "T service 100 °C" in t and "Décalage du jeu dû à la dilatation : +0,1840 mm" in t
    assert "angle 180" not in t and "facteur" not in t  # un « − » n'est pas un levier
    p2 = chargerExemple("tableau_depart")
    p2["condition"]["jmin"] = None
    p2["condition"]["jmax"] = None
    t2 = texteEtude(calculerChaine(p2, n=500))
    assert "Aucune limite exigée" in t2 and "tient" not in t2.split("RÉSULTATS")[1].split("CONCLUSION")[0]
    assert "Cp = (Jmax − Jmin) / 6σ" in t2
