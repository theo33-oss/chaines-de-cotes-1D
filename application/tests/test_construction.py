"""Assistant de construction de chaîne : chemins les plus courts, signes, contrôles et page."""

import copy

import pytest

from chainecotes.core.chaine import solveurChaine
from chainecotes.core.construction import construireChaines, lireSaisie, positions
from chainecotes.core.donnees import chargerJson
from chainecotes.core.errors import ErreurChaine
from chainecotes.plots.assistant import figureConstruction


@pytest.fixture
def ex():
    return copy.deepcopy(chargerJson("assistant_exemple.json"))


def _chaines(ex, **maj):
    d = {**ex, **maj}
    return construireChaines(d["cotes"], d["contacts"], d["depart"], d["arrivee"])


def test_chaine_minimale_de_l_exemple(ex):
    (c,) = _chaines(ex)
    assert [m["sens"] for m in c["maillons"]] == ["-", "-", "+", "-"]  # arbre, cale, carter, couvercle
    assert [m["cote"] for m in c["maillons"]] == [54.2, 2.0, 60.0, 3.0]
    assert c["nominal"] == pytest.approx(0.8)
    assert c["pieces"] == ["Arbre", "Cale", "Carter", "Couvercle"] and c["avertissements"] == []
    assert c["surfaces"][0] == "Arbre.bout" and c["surfaces"][-1] == "Couvercle.interieur"


def test_la_chaine_se_calcule_avec_le_nominal_du_jeu(ex):
    (c,) = _chaines(ex)
    p = {"condition": {"nom": "J", "jmin": 0.3, "jmax": 1.3}, "reglages": {}, "maillons": c["maillons"]}
    assert solveurChaine(p)["CF_nom"] == pytest.approx(c["nominal"])


def test_sens_inverse_si_on_inverse_les_surfaces(ex):
    (c,) = _chaines(ex, depart="Couvercle.interieur", arrivee="Arbre.bout")
    assert c["nominal"] == pytest.approx(-0.8)
    assert [m["sens"] for m in c["maillons"]] == ["+", "-", "+", "+"]


def test_plusieurs_chaines_de_meme_longueur(ex):
    ex["cotes"].append({"piece": "Cale2", "de": "a", "vers": "b", "cote": 2.0, "es": 0.05, "ei": -0.05})
    ex["contacts"] += [{"a": "Cale2.a", "b": "Carter.fond"}, {"a": "Arbre.epaulement", "b": "Cale2.b"}]
    chaines = _chaines(ex)
    assert len(chaines) == 2 and {c["pieces"][1] for c in chaines} == {"Cale", "Cale2"}


def test_cotes_en_cascade_signalees(ex):
    """Deux cotes de la même pièce sur le chemin : avertissement « une cote par pièce »."""
    ex["cotes"] = [c for c in ex["cotes"] if not (c["piece"] == "Arbre" and c["vers"] == "bout")]
    ex["cotes"] += [
        {"piece": "Arbre", "de": "epaulement", "vers": "milieu", "cote": 30.0, "es": 0.1, "ei": -0.1},
        {"piece": "Arbre", "de": "milieu", "vers": "bout", "cote": 24.2, "es": 0.1, "ei": -0.1},
    ]
    (c,) = _chaines(ex)
    assert c["pieces"].count("Arbre") == 2
    assert any("Arbre" in a and "une cote par pièce" in a for a in c["avertissements"])


def test_non_relie_nomme_les_groupes(ex):
    ex["contacts"] = ex["contacts"][:1]
    with pytest.raises(ErreurChaine, match="Aucun chemin") as e:
        _chaines(ex)
    assert "Couvercle" in e.value.message and "Arbre" in e.value.message


@pytest.mark.parametrize(
    "maj,attendu",
    [
        ({"depart": "Arbre.nulle_part"}, "n'existe"),
        ({"arrivee": "Arbre.bout"}, "différentes"),
        ({"depart": "Cale.a", "arrivee": "Carter.fond"}, "contact direct"),
    ],
)
def test_extremites_invalides(ex, maj, attendu):
    with pytest.raises(ErreurChaine, match=attendu):
        _chaines(ex, **maj)


@pytest.mark.parametrize(
    "ligne",
    [{"piece": "", "de": "a", "vers": "b", "cote": 1}, {"piece": "P", "de": "a", "vers": "a", "cote": 1},
     {"piece": "P", "de": "a", "vers": "b", "cote": -1}, {"piece": "P", "de": "a", "vers": "b", "cote": "x"}],
)  # fmt: skip
def test_cotes_invalides(ex, ligne):
    ex["cotes"].append(ligne)
    with pytest.raises(ErreurChaine):
        _chaines(ex)


def test_contact_invalide(ex):
    ex["contacts"].append({"a": "Cale.a", "b": "Cale.b"})
    with pytest.raises(ErreurChaine, match="même pièce"):
        _chaines(ex)


def test_positions_et_figure(ex):
    lues, liens = lireSaisie(ex["cotes"], ex["contacts"])
    pos, incoh = positions(lues, liens, ex["depart"])
    assert incoh == []
    assert pos["Couvercle.interieur"] - pos["Arbre.bout"] == pytest.approx(0.8)
    (c,) = _chaines(ex)
    fig, legende = figureConstruction(lues, liens, ex["depart"], ex["arrivee"], c)
    assert len(fig.data) > 6 and "J = 0,8 mm" in str(fig.data[-1].text)
    ex["cotes"][0]["cote"] = 61.0  # redondance incompatible : carter d'un côté, cales et arbre de l'autre
    ex["contacts"].append({"a": "Carter.bride", "b": "Arbre.portee"})
    lues, liens = lireSaisie(ex["cotes"], ex["contacts"])
    assert positions(lues, liens, ex["depart"])[1]


