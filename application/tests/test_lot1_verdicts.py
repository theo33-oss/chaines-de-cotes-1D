"""Corrections de l'audit : marge numérique des verdicts, risque selon Cp, Bender plafonné."""

import math

from chainecotes.core.chaine import risqueSelonCp, solveurChaine, verdicts
from chainecotes.core.inertiel import verdictBender


def _chaine(maillons, jmin, jmax, loi="normale"):
    return {
        "condition": {"nom": "J", "jmin": jmin, "jmax": jmax},
        "reglages": {"kSigma": 3, "tref": 20.0, "modeT": "uniforme", "tservice": 20.0},
        "maillons": [
            {"nom": f"C{i}", "sens": s, "cote": c, "es": t, "ei": -t, "loi": loi} for i, (s, c, t) in enumerate(maillons)
        ],
    }


def test_jeu_pile_sur_la_limite_reste_conforme():
    res = solveurChaine(_chaine([("+", 40.3, 0.05), ("-", 20.1, 0.025), ("-", 20.1, 0.025)], 0.0, 0.2))
    assert verdicts(res)["pireCas"]["ok"]


def test_risque_selon_cp_ne_depend_pas_de_la_loi():
    m = [("+", 1.0, 0.1), ("-", 0.0001, 0.1)]
    normale = risqueSelonCp(solveurChaine(_chaine(m, 0.7, 1.3)))
    uniforme = risqueSelonCp(solveurChaine(_chaine(m, 0.7, 1.3, loi="uniforme")))
    assert all(math.isclose(a, b, rel_tol=1e-9) for a, b in zip(normale["ppm"], uniforme["ppm"], strict=True))


def test_bender_jamais_plus_large_que_le_pire_cas():
    res = solveurChaine(_chaine([("+", 10.0, 0.1), ("-", 5.0, 0.1)], 4.0, 6.0))
    assert verdictBender(res)["demi"] <= (res["CF_max"] - res["CF_min"]) / 2 + 1e-12


def _decentree(decentrage):
    """J = 100 − 40 − 59 = 1 mm, σ_J ≈ 0,0408 : ± 3σ tient dans [0,87 ; 1,13] tant que la moyenne reste centrée."""
    p = _chaine([("+", 100.0, 0.1), ("-", 40.0, 0.05), ("-", 59.0, 0.05)], 0.87, 1.13)
    p["reglages"]["decentrage"] = decentrage
    return p


def test_sans_decentrage_rssProc_egale_rssK():
    v = verdicts(solveurChaine(_decentree(0)))
    assert v["rssProc"] == v["rssK"] and v["rssK"]["ok"]


def test_decentrage_fort_plus_de_verdict_conforme_en_statistique():
    from chainecotes.services.calcul import calculerChaine
    from chainecotes.services.conclusion import conclusionEtude
    from chainecotes.services.mecanisme import _verdict

    b = calculerChaine(_decentree(1.5), monteCarlo=False)
    v = b["verdicts"]
    assert not v["pireCas"]["ok"] and v["rssK"]["ok"] and not v["rssProc"]["ok"]
    assert _verdict(v) == "non conforme"
    assert conclusionEtude(b)["niveau"] == "erreur"


def test_inverse_maillon_de_reglage_a_90_degres_sans_decalage_absurde():
    from chainecotes.core.inverse import repartirTolerances

    p = _chaine([("+", 100.0, 0.1), ("-", 40.0, 0.05), ("-", 59.0, 0.05), ("+", 5.0, 0.05)], 0.8, 1.2)
    p["maillons"][3]["angle"] = 90.0
    sortie = repartirTolerances(p, "egale", "pire_cas", [], 3)
    assert sortie["decalage"] == 0.0


def test_alpha_c45_du_calcul_differe_du_tableau():
    """Garde le déclencheur de l'avertissement de la page Matériaux (courbe générique non recalée)."""
    from chainecotes.core.materiaux import alphaMateriau, listeMateriaux

    m = next(x for x in listeMateriaux() if x["nom"] == "Acier C45")
    assert abs(alphaMateriau("Acier C45", 100.0, 20.0)["alpha"] / m["alpha"] - 1) > 0.05
