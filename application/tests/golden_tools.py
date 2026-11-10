"""Outils de comparaison aux références MATLAB (tests/golden/*.json), repris de tests/golden_tools.py de MecaStruct.

Un fichier golden absent fait sauter proprement les tests qui en dépendent (pas d'échec à la collecte).
Tolérance par défaut du déterministe : relative 1e-9, absolue 1e-12.
"""

import json
import math
from pathlib import Path

import numpy as np

DOSSIER_GOLDEN = Path(__file__).parent / "golden"
REL_DEFAUT = 1e-9
ABS_DEFAUT = 1e-12


def chargerGolden(nom: str) -> dict:
    """Charge un fichier golden, ou fait sauter le test s'il est absent.

    Entrée : nom du fichier (ex. « golden_exemples.json »).
    Sortie : contenu JSON (dict).
    """
    chemin = DOSSIER_GOLDEN / nom
    if not chemin.exists():
        import pytest

        pytest.skip(f"Fichier golden absent : {chemin} (lancer tools/matlab/generer_golden.m dans MATLAB)")
    return json.loads(chemin.read_text(encoding="utf-8"))


def casGolden(nom: str, liste: str = "cas") -> list:
    """Cas d'un fichier golden pour pytest.mark.parametrize ; liste vide si le fichier manque.

    Entrées : nom du fichier, liste (clé de la liste des cas dans le fichier, ex. « exemples »).
    Sortie : liste des cas (dict) ; [] sans skip à la collecte si le fichier est absent.
    """
    chemin = DOSSIER_GOLDEN / nom
    if not chemin.exists():
        return []
    return json.loads(chemin.read_text(encoding="utf-8"))[liste]


def enFlottant(v):
    """Valeur attendue en nombre(s) : None (NaN de MATLAB écrit null par jsonencode) devient nan.

    Entrée : nombre, None ou liste. Sortie : float ou np.ndarray de float.
    """
    if isinstance(v, list):
        return np.array([math.nan if x is None else x for x in v], dtype=float)
    return math.nan if v is None else float(v)


def _proche(a: float, e: float, rel: float, abs_: float) -> bool:
    if math.isnan(e):
        return math.isnan(a)
    if math.isinf(e):
        return a == e
    return math.isclose(a, e, rel_tol=rel, abs_tol=abs_)


def assertTableau(obtenu, attendu, rel: float = REL_DEFAUT, abs_: float = ABS_DEFAUT, chemin: str = "sortie") -> None:
    """Compare deux tableaux numériques élément par élément (NaN aux mêmes places).

    Entrées : obtenu, attendu (nombres, listes ou ndarray ; None attendu = nan), rel, abs_ (tolérances),
    chemin (nom affiché dans le message). Sortie : rien ; AssertionError localisée en cas d'écart.
    """
    exp = np.atleast_1d(enFlottant(attendu) if isinstance(attendu, list) else np.asarray(attendu, dtype=float))
    act = np.atleast_1d(np.asarray(obtenu, dtype=float))
    if exp.size == act.size and exp.shape != act.shape:
        act = act.reshape(exp.shape)  # vecteur ligne / colonne
    assert act.shape == exp.shape, f"{chemin} : forme {exp.shape} attendue, obtenue {act.shape}"
    assert np.array_equal(np.isnan(exp), np.isnan(act)), f"{chemin} : positions des NaN différentes"
    ok = np.isclose(act, exp, rtol=rel, atol=abs_, equal_nan=True)
    if not ok.all():
        i = tuple(np.argwhere(~ok)[0])
        raise AssertionError(f"{chemin}{list(i)} : {exp[i]!r} attendu, obtenu {act[i]!r} (rel={rel})")


def assertConforme(
    obtenu, attendu, rel: float = REL_DEFAUT, abs_: float = ABS_DEFAUT, ignore=frozenset(), chemin: str = "sortie"
) -> None:
    """Compare récursivement une sortie Python à une référence MATLAB.

    Entrées : obtenu (dict, liste, nombre, ndarray, texte), attendu (JSON golden), rel, abs_ (tolérances),
    ignore (clés à ne pas comparer), chemin (préfixe des messages).
    Règles : chaque clé attendue doit exister (clés en trop tolérées) ; listes numériques comparées comme
    tableaux ; None attendu = NaN de MATLAB pour un nombre ; booléens et textes à l'égalité.
    Sortie : rien ; AssertionError du type « sortie.CF_min : 0.95 attendu, obtenu ... ».
    """
    if isinstance(attendu, dict):
        assert isinstance(obtenu, dict), f"{chemin} : dict attendu, obtenu {type(obtenu).__name__}"
        for cle, val in attendu.items():
            if cle in ignore:
                continue
            assert cle in obtenu, f"{chemin}.{cle} : clé manquante (présentes : {sorted(obtenu)})"
            assertConforme(obtenu[cle], val, rel, abs_, ignore, f"{chemin}.{cle}")
    elif isinstance(attendu, list):
        if not attendu:
            assert obtenu is None or len(obtenu) == 0, f"{chemin} : liste vide attendue, obtenu {obtenu!r}"
        elif all(x is None or (isinstance(x, (int, float)) and not isinstance(x, bool)) for x in attendu):
            assertTableau(obtenu, attendu, rel, abs_, chemin)
        else:
            assert len(obtenu) == len(attendu), f"{chemin} : {len(attendu)} éléments attendus, obtenu {len(obtenu)}"
            for i, (a, e) in enumerate(zip(obtenu, attendu, strict=True)):
                assertConforme(a, e, rel, abs_, ignore, f"{chemin}[{i}]")
    elif isinstance(attendu, bool):
        assert bool(np.asarray(obtenu).item()) == attendu, f"{chemin} : {attendu} attendu, obtenu {obtenu!r}"
    elif isinstance(attendu, str):
        assert str(obtenu) == attendu, f"{chemin} : {attendu!r} attendu, obtenu {obtenu!r}"
    elif attendu is None or isinstance(attendu, (int, float)):
        a = float(np.asarray(obtenu, dtype=float).reshape(-1)[0]) if np.size(obtenu) == 1 else obtenu
        assert isinstance(a, float), f"{chemin} : nombre attendu, obtenu {obtenu!r}"
        e = enFlottant(attendu)
        assert _proche(a, e, rel, abs_), f"{chemin} : {e!r} attendu, obtenu {a!r} (rel={rel})"
    else:
        raise AssertionError(f"{chemin} : type attendu non géré {type(attendu).__name__}")
