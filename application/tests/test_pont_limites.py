"""Pont du site (docs/pont.py) : plafond de 10¹⁸ sur les nombres saisis et phrase française pour les erreurs arithmétiques."""

import copy
import json
import sys
from pathlib import Path

import pytest

racine = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(racine / "application"), str(racine / "docs")]
import pont
from chainecotes.core.errors import ErreurChaine

PROBLEME = {
    "condition": {"nom": "Jeu J", "jmin": 0.1, "jmax": 1.0},
    "reglages": {"kSigma": 3, "tref": 20, "modeT": "uniforme", "tservice": 20},
    "maillons": [
        {"nom": "Carter", "sens": "+", "cote": 100.0, "es": 0.05, "ei": -0.05},
        {"nom": "Arbre", "sens": "-", "cote": 99.0, "es": 0.02, "ei": -0.02},
    ],
}


def _avec(modif) -> dict:
    p = copy.deepcopy(PROBLEME)
    modif(p)
    return p


def _texte(p: dict) -> str:
    return json.dumps(p)


def _sortie(f, *args) -> dict:
    return json.loads(f(*args))


# ---------------------------------------------------------------- plafond de 10¹⁸


def test_cote_trop_grande_refusee_partout():
    t = _texte(_avec(lambda p: p["maillons"][1].update(cote=1e30)))
    for r in (_sortie(pont.calculer, t), _sortie(pont.apercu, t), _sortie(pont.sauver, t), _sortie(pont.mecaChaine, t)):
        assert "10¹⁸" in r["erreur"] and "la cote nominale" in r["erreur"] and "Maillon 2" in r["erreur"], r
        assert "mm" in r["erreur"] and "vérifiez l'unité" in r["erreur"]


def test_apercu_refuse_garde_un_schema():
    r = _sortie(pont.apercu, _texte(_avec(lambda p: p["maillons"][0].update(cote=1e30))))
    assert r["fig"] and r["pireCas"] is None and r["controles"] == []


@pytest.mark.parametrize(
    ("bloc", "champ", "libelle", "unite"),
    [
        ("condition", "jmin", "Jmin", "mm"),
        ("condition", "jmax", "Jmax", "mm"),
        ("reglages", "kSigma", "le procédé garanti k", ""),
        ("reglages", "tref", "la température de référence", "°C"),
        ("reglages", "tservice", "la température de service", "°C"),
        ("reglages", "decentrage", "le décentrage", "σ_J"),
        ("maillon", "cote", "la cote nominale", "mm"),
        ("maillon", "es", "l'écart supérieur", "mm"),
        ("maillon", "ei", "l'écart inférieur", "mm"),
        ("maillon", "derive", "la dérive", "µm"),
        ("maillon", "alpha", "le coefficient de dilatation", "µm/m/K"),
        ("maillon", "facteur", "le facteur", ""),
        ("maillon", "angle", "l'angle", "°"),
        ("maillon", "sigma_reel", "l'écart type mesuré", "mm"),
        ("maillon", "moyenne_reelle", "la moyenne mesurée", "mm"),
        ("maillon", "tservice", "la température de service", "°C"),
    ],
)
@pytest.mark.parametrize("valeur", [1e30, -1e30, "1e30"])
def test_chaque_champ_est_plafonne(bloc, champ, libelle, unite, valeur):
    def modif(p):
        (p["maillons"][1] if bloc == "maillon" else p[bloc])[champ] = valeur

    with pytest.raises(ErreurChaine) as e:
        pont._nettoyer(_avec(modif))
    assert "10¹⁸" in e.value.message and libelle in e.value.message and unite in e.value.message
    if bloc == "maillon":
        assert "Maillon 2" in e.value.message


def test_plafond_exact_accepte_et_juste_au_dessus_refuse():
    for v in (1e18, -1e18):
        pont._nettoyer(_avec(lambda p, v=v: p["maillons"][0].update(cote=abs(v), es=v, ei=-1e18)))  # ne lève pas
    r = _sortie(pont.calculer, _texte(_avec(lambda p: p["maillons"][0].update(cote=1e18))))
    assert "10¹⁸" not in r.get("erreur", "")  # le calcul (hors tables ISO) répond, pas le plafond
    with pytest.raises(ErreurChaine):
        pont._nettoyer(_avec(lambda p: p["maillons"][0].update(cote=1.0000001e18)))


def test_entier_demesure_refuse():
    with pytest.raises(ErreurChaine) as e:
        pont._nettoyer(_avec(lambda p: p["maillons"][0].update(cote=10**400)))
    assert "10¹⁸" in e.value.message


def test_limite_sans_borne_et_infinis_gardent_leur_comportement():
    pont._nettoyer(_avec(lambda p: p["condition"].update(jmax=float("inf"), jmin=float("-inf"))))  # pas un cas de plafond
    pont._nettoyer(_avec(lambda p: p["condition"].update(jmax=None)))
    pont._nettoyer(_avec(lambda p: p["condition"].update(jmax="")))
    r = _sortie(pont.calculer, _texte(_avec(lambda p: p["condition"].update(jmax=None))))
    assert "erreur" not in r
    r = _sortie(pont.calculer, _texte(_avec(lambda p: p["condition"].update(jmax=float("inf")))))  # refus existant du calcul
    assert "10¹⁸" not in r["erreur"]


def test_texte_non_numerique_laisse_au_calcul():
    r = _sortie(pont.calculer, _texte(_avec(lambda p: p["maillons"][0].update(cote="abc"))))
    assert "doit être un nombre" in r["erreur"] and "10¹⁸" not in r["erreur"]


def test_empreinte_ne_refuse_pas():
    assert pont.empreinteProbleme(_texte(_avec(lambda p: p["maillons"][0].update(cote=1e30))))


def test_fichier_refuse_a_l_ouverture():
    contenu = pont.sauver(_texte(PROBLEME))
    assert "erreur" not in json.loads(contenu)
    fichier = json.loads(contenu)["contenu"]
    assert "erreur" not in _sortie(pont.ouvrir, fichier)
    d = json.loads(fichier)
    d["probleme"]["maillons"][0]["es"] = 5e20
    r = _sortie(pont.ouvrir, json.dumps(d))
    assert "10¹⁸" in r["erreur"] and "l'écart supérieur" in r["erreur"]
    d["probleme"]["maillons"][0]["es"] = 0.05
    d["revisions"] = [{"indice": "A", "date": "", "auteur": "", "objet": "", "probleme": _avec(lambda p: p["maillons"][1].update(cote=1e19))}]
    r = _sortie(pont.ouvrir, json.dumps(d))
    assert "Révision 1" in r["erreur"] and "10¹⁸" in r["erreur"]


def test_mecanisme_import_refuse_et_calcul_par_chaine():
    bonne, mauvaise = copy.deepcopy(PROBLEME), _avec(lambda p: p["maillons"][0].update(cote=1e30))
    mauvaise["condition"]["nom"] = "Chaîne trop grande"
    mec = json.dumps({"format": "mecanisme", "version": 1, "nom": "m", "chaines": [bonne, mauvaise]})
    r = _sortie(pont.mecaImporter, mec)
    assert "Chaîne 2" in r["erreur"] and "10¹⁸" in r["erreur"]
    # au calcul, la chaîne refusée est en erreur sans empêcher l'autre
    r = _sortie(pont.mecaCalculer, mec, 2000)
    assert [x["nom"] for x in r["enErreur"]] == ["Chaîne trop grande"]
    assert "10¹⁸" in r["enErreur"][0]["message"]


def test_comparerN_colonne_refusee_sans_bloquer_les_autres():
    mauvaise = _avec(lambda p: p["maillons"][0].update(cote=1e30))
    d = {"colonnes": [{"nom": "A", "probleme": PROBLEME}, {"nom": "B", "probleme": mauvaise}], "n": 2000}
    r = _sortie(pont.comparerN, json.dumps(d))
    assert [c["erreur"] is None for c in r["colonnes"]] == [True, False]
    assert "10¹⁸" in r["colonnes"][1]["erreur"] and "Maillon 1" in r["colonnes"][1]["erreur"]


def test_comparer_refuse_la_variante():
    r = _sortie(pont.comparer, _texte(PROBLEME), _texte(_avec(lambda p: p["maillons"][0].update(cote=1e30))), "B")
    assert "10¹⁸" in r["erreur"]


def test_repartir_refuse():
    r = _sortie(pont.repartir, _texte(_avec(lambda p: p["maillons"][0].update(cote=1e30))), "proportionnelle", "pire_cas")
    assert "10¹⁸" in r["erreur"]


def test_assistant_refuse_cote_et_limites():
    cotes = [{"piece": "Carter", "de": "A", "vers": "B", "cote": 1e30}, {"piece": "Arbre", "de": "A", "vers": "C", "cote": 50}]
    r = _sortie(pont.assistant, json.dumps(cotes), "[]")
    assert "10¹⁸" in r["erreur"] and "Carter" in r["erreur"] and "surfaces" in r
    cotes[0]["cote"] = 80
    r = _sortie(pont.assistant, json.dumps(cotes), "[]", "", "", "Jeu J", 0.0, 1e30)
    assert "10¹⁸" in r.get("erreur", "") and "Jmax" in r["erreur"]


def test_dilatation_refuse_temperature_demesuree():
    r = _sortie(pont.dilatation, json.loads(pont.materiaux())[0], 20.0, 1e30)
    assert "10¹⁸" in r["erreur"]


def test_tous_les_exemples_sans_erreur():
    for e in json.loads(pont.exemples()):
        p = pont.charger(e["id"])
        assert _sortie(pont.apercu, p)["erreur"] is None, e["id"]
        assert "erreur" not in _sortie(pont.calculer, p), e["id"]
        assert "erreur" not in _sortie(pont.sauver, p), e["id"]


# ---------------------------------------------------------------- erreurs arithmétiques


@pytest.mark.parametrize(
    "erreur",
    [
        ZeroDivisionError("float division by zero"),
        OverflowError("int too large to convert to float"),
        FloatingPointError("overflow encountered"),
        ArithmeticError("x"),
        ValueError("math domain error"),
        OverflowError("cannot convert float infinity to integer"),
        ValueError("cannot convert float infinity to integer"),
        ValueError("Out of range float values are not JSON compliant"),
    ],
)
def test_phrase_arithmetique(erreur):
    phrase = pont._phraseArithmetique(erreur)
    assert phrase and phrase.startswith("Le calcul sort du domaine des nombres")
    assert "division by zero" not in phrase and "vérifiez" in phrase


@pytest.mark.parametrize("erreur", [ValueError("loi inconnue"), KeyError("cote"), TypeError("x"), RuntimeError("bug"), IndexError("i")])
def test_phrase_arithmetique_ne_masque_pas_les_autres_erreurs(erreur):
    assert pont._phraseArithmetique(erreur) is None


def _lever(erreur):
    def f(*args, **kwargs):
        raise erreur

    return f


FONCTIONS_CALCUL = [
    ("calculer", lambda: pont.calculer(_texte(PROBLEME)), "calculerChaine"),
    ("apercu", lambda: pont.apercu(_texte(PROBLEME)), "apercuChaine"),
    ("comparer", lambda: pont.comparer(_texte(PROBLEME), _texte(PROBLEME)), "calculerChaine"),
    ("dossier", lambda: pont.dossier(_texte(PROBLEME)), "calculerChaine"),
    ("texteEtude", lambda: pont.texteEtude(_texte(PROBLEME)), "calculerChaine"),
    ("texteIA", lambda: pont.texteIA(_texte(PROBLEME)), "calculerChaine"),
    ("repartir", lambda: pont.repartir(_texte(PROBLEME), "proportionnelle", "pire_cas"), "apercuChaine"),
]


@pytest.mark.parametrize("erreur", [ZeroDivisionError("float division by zero"), OverflowError("math range error"), FloatingPointError("x")])
@pytest.mark.parametrize(("nom", "appel", "cible"), FONCTIONS_CALCUL, ids=[f[0] for f in FONCTIONS_CALCUL])
def test_erreur_arithmetique_devient_une_phrase(monkeypatch, nom, appel, cible, erreur):
    monkeypatch.setitem(pont._dernier, "cle", None)
    monkeypatch.setitem(pont._dernier, "bundle", None)
    monkeypatch.setattr(pont, cible, _lever(erreur))
    r = json.loads(appel())
    assert r["erreur"] == pont.PHRASE_ARITHMETIQUE, nom
    assert "division by zero" not in json.dumps(r)


def test_erreur_arithmetique_mecanisme_et_comparaison(monkeypatch):
    monkeypatch.setattr(pont.meca, "calculerMecanisme", _lever(ZeroDivisionError("float division by zero")))
    mec = json.dumps({"format": "mecanisme", "version": 1, "nom": "m", "chaines": [PROBLEME]})
    assert _sortie(pont.mecaCalculer, mec)["erreur"] == pont.PHRASE_ARITHMETIQUE
    monkeypatch.setattr(pont.comparatif, "comparerColonnes", _lever(ZeroDivisionError("float division by zero")))
    d = json.dumps({"colonnes": [{"nom": "A", "probleme": PROBLEME}]})
    assert _sortie(pont.comparerN, d)["erreur"] == pont.PHRASE_ARITHMETIQUE


def test_erreur_arithmetique_mecaChaine_et_sauver(monkeypatch):
    monkeypatch.setattr(pont.projet_io, "exporterProbleme", _lever(OverflowError("x")))
    assert _sortie(pont.mecaChaine, _texte(PROBLEME))["erreur"] == pont.PHRASE_ARITHMETIQUE
    monkeypatch.setattr(pont.projet_io, "exporterProjet", _lever(ZeroDivisionError("x")))
    assert _sortie(pont.sauver, _texte(PROBLEME))["erreur"] == pont.PHRASE_ARITHMETIQUE


def test_erreur_arithmetique_exporterExcel(monkeypatch):
    pytest.importorskip("openpyxl")
    monkeypatch.setattr(pont, "calculerChaine", _lever(ZeroDivisionError("float division by zero")))
    assert _sortie(pont.exporterExcel, _texte(PROBLEME))["erreur"] == pont.PHRASE_ARITHMETIQUE


def test_erreur_arithmetique_assistant_garde_les_surfaces(monkeypatch):
    monkeypatch.setattr(pont, "construireChaines", _lever(ZeroDivisionError("float division by zero")))
    cotes = [{"piece": "Carter", "de": "A", "vers": "B", "cote": 80}, {"piece": "Arbre", "de": "A", "vers": "C", "cote": 50}]
    r = _sortie(pont.assistant, json.dumps(cotes), "[]")
    assert r["erreur"] == pont.PHRASE_ARITHMETIQUE and r["surfaces"]


def test_nan_ou_infini_produit_devient_une_phrase(monkeypatch):
    """Un résultat nan ou infini fait échouer json.dumps(allow_nan=False) : la page reçoit la phrase, pas l'erreur Python."""
    vrai = pont.calculerChaine

    def avec_nan(*args, **kwargs):
        b = vrai(*args, **kwargs)
        b["res"]["jeu_nominal"] = float("nan")
        return b

    monkeypatch.setattr(pont, "_resultats", lambda bundle: {"x": float("nan")})
    monkeypatch.setattr(pont, "calculerChaine", avec_nan)
    r = _sortie(pont.calculer, _texte(PROBLEME))
    assert r["erreur"] == pont.PHRASE_ARITHMETIQUE


def test_les_messages_specifiques_ne_changent_pas():
    r = _sortie(pont.calculer, json.dumps({"condition": {}, "reglages": {}, "maillons": [{"sens": "+", "cote": ""}]}))
    assert "doit être un nombre" in r["erreur"] and "domaine des nombres" not in r["erreur"]
    r = _sortie(pont.calculer, _texte(_avec(lambda p: p["reglages"].update(kSigma=0))))
    assert r["erreur"] == "Le procédé garanti k doit être strictement positif."


def test_un_vrai_bug_n_est_pas_masque(monkeypatch):
    monkeypatch.setattr(pont, "calculerChaine", _lever(RuntimeError("bug")))
    with pytest.raises(RuntimeError):
        pont.calculer(_texte(PROBLEME))
    monkeypatch.setattr(pont, "calculerChaine", _lever(KeyError("cote")))
    assert "Saisie incomplète" in _sortie(pont.calculer, _texte(PROBLEME))["erreur"]
