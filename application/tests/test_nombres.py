"""Écriture des nombres : virgule, exposants lisibles, bruit d'arrondi."""

from chainecotes.core.nombres import exposants, fr, versTableur


def test_exposant_positif():
    assert fr(2.487e7, ".3e") == "2,487·10⁷"


def test_exposant_negatif():
    assert fr(1.5e-5, ".2e") == "1,50·10⁻⁵"
    assert exposants("3e-05") == "3·10⁻⁵"


def test_exposant_a_deux_chiffres():
    assert fr(1e15, ".1e") == "1,0·10¹⁵"


def test_sans_exposant_inchange():
    assert fr(1234.5, ".1f") == "1234,5"
    assert fr(0.25, ".4g") == "0,25"


def test_bruit_arrondi_et_cas_speciaux():
    assert fr(1e-14) == "0,0000"
    assert fr(None) == "—"
    assert fr(float("inf")) == "+∞"


def test_versTableur_rend_un_nombre_lisible_par_excel():
    assert versTableur(fr(1.2e5, ".3g")) == "1,2e5"
    assert versTableur(fr(1.5e-5, ".2e")) == "1,50e-5"
    assert versTableur("Cote_1\t2,487·10⁷\t0,25") == "Cote_1\t2,487e7\t0,25"
    assert versTableur("sans exposant 10 mm") == "sans exposant 10 mm"
