"""Erreurs bloquantes de saisie : chaque défaut lève ErreurChaine avec son identifiant stable."""

import math

import pytest

from chainecotes.core.chaine import normaliserMaillon, preparerProbleme
from chainecotes.core.errors import ErreurChaine
from chainecotes.services.exemples import chargerExemple

REGLAGES = {"kSigma": 3.0, "tref": 20.0, "modeT": "uniforme", "tservice": 20.0}


def _maillon(**champs) -> dict:
    m = {"nom": "M", "sens": "+", "cote": 50.0, "iso": None, "es": 0.1, "ei": -0.1, "loi": "normale",
         "materiau": None, "alpha": None, "tservice": 20.0}  # fmt: skip
    m.update(champs)
    return m


def _identifiant(fonction, *args) -> str:
    with pytest.raises(ErreurChaine) as e:
        fonction(*args)
    assert e.value.message
    return e.value.identifiant


@pytest.mark.parametrize(
    "champs, identifiant",
    [
        ({"es": -0.1, "ei": 0.1}, "Chaine:Saisie:ecarts"),
        ({"cote": -1.0}, "Chaine:Saisie:cote"),
        ({"sens": "x"}, "Chaine:Saisie:sens"),
        ({"loi": "gaussienne"}, "Chaine:Saisie:loi"),
        ({"iso": "40 xx"}, "Chaine:Iso286:saisie"),
        ({"iso": "40 h7", "cote": 50.0}, "Chaine:Saisie:iso"),
        ({"materiau": "Matériau imaginaire"}, "Chaine:Saisie:materiau"),
        ({"cote": math.inf}, "Chaine:Saisie:nombre"),
        ({"es": math.nan}, "Chaine:Saisie:nombre"),
        ({"cote": "abc"}, "Chaine:Saisie:nombre"),
    ],
    ids=["ES<EI", "cote negative", "sens", "loi", "iso illisible", "iso autre cote", "materiau", "inf", "nan", "texte"],
)
def test_maillon_invalide(champs, identifiant):
    assert _identifiant(normaliserMaillon, _maillon(**champs), 1, REGLAGES) == identifiant


@pytest.mark.parametrize("maillons", [[_maillon()], [_maillon(), _maillon(nom="N")]], ids=["un maillon", "un sens"])
def test_chaine_non_fermee(maillons):
    p = chargerExemple("validation_100_40_59")
    p["maillons"] = maillons
    assert _identifiant(preparerProbleme, p) == "Chaine:Saisie:nonFermee"


@pytest.mark.parametrize(
    "partie, champs, identifiant",
    [
        ("condition", {"jmin": 1.2, "jmax": 0.8}, "Chaine:Saisie:condition"),
        ("reglages", {"kSigma": -1}, "Chaine:Saisie:kSigma"),
        ("reglages", {"modeT": "gradient"}, "Chaine:Saisie:modeT"),
    ],
    ids=["Jmin>Jmax", "k<0", "modeT"],
)
def test_probleme_invalide(partie, champs, identifiant):
    p = chargerExemple("validation_100_40_59")
    p[partie].update(champs)
    assert _identifiant(preparerProbleme, p) == identifiant


def test_k_nul_refuse():
    p = chargerExemple("validation_100_40_59")
    p["reglages"]["kSigma"] = 0
    assert _identifiant(preparerProbleme, p) == "Chaine:Saisie:kSigma"


@pytest.mark.parametrize(
    ("partie", "champs"),
    [
        ("reglages", {"kSigma": float("inf")}),
        ("reglages", {"tref": float("nan")}),
        ("reglages", {"tref": "abc"}),
        ("condition", {"jmin": "abc"}),
        ("condition", {"jmax": float("nan")}),
    ],
    ids=["k infini", "tref nan", "tref texte", "jmin texte", "jmax nan"],
)
def test_reglage_ou_condition_non_fini_refuse(partie, champs):
    p = chargerExemple("validation_100_40_59")
    p[partie].update(champs)
    assert _identifiant(preparerProbleme, p) == "Chaine:Saisie:nombre"


def test_exemple_valide_passe():
    p = preparerProbleme(chargerExemple("validation_100_40_59"))
    assert len(p["maillons"]) == 3


def test_editeur_colonne_derive_et_loi():
    from chainecotes.core.chaine import solveurChaine
    from chainecotes.bureau import editeur

    assert editeur._versProbleme("derive", None) is None and editeur._versProbleme("derive", 12) == 12.0
    assert editeur._versProbleme("loi", None) == "normale" and editeur._versProbleme("loi", "uniforme") == "uniforme"
    p = chargerExemple("validation_100_40_59")
    lignes, _ = editeur.lignesTableau(p["maillons"])
    assert all(x["derive"] is None for x in lignes) and [x["loi"] for x in lignes] == ["normale"] * 3  # valeurs par défaut
    p["maillons"][0]["derive"] = 15.0
    lignes, _ = editeur.lignesTableau(p["maillons"])
    assert lignes[0]["derive"] == 15.0
    # une case vide (None) vaut 0 pour le cœur : le résultat est celui d'un problème sans dérive
    p["maillons"][0]["derive"] = None
    sans = chargerExemple("validation_100_40_59")
    assert solveurChaine(p)["CF_sigma"] == solveurChaine(sans)["CF_sigma"]
    assert [m["derive"] for m in solveurChaine(p)["maillons"]] == [0.0, 0.0, 0.0]


def test_decentrage_negatif_refuse():
    p = chargerExemple("validation_100_40_59")
    p["reglages"]["decentrage"] = -0.5
    assert _identifiant(preparerProbleme, p) == "Chaine:Saisie:decentrage"


def test_options_iso_contiennent_h7_g6_et_les_saisies_existantes():
    from chainecotes.bureau.editeur import optionsIso

    opts = optionsIso([{"iso": "40 h7"}, {"iso": None}])
    assert "H7" in opts and "g6" in opts and "IT18" not in opts and "h18" in opts
    assert "40 h7" in opts  # une désignation déjà saisie reste visible dans la liste
    assert len(opts) == len(set(opts))
