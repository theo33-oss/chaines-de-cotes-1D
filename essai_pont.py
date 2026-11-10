"""Essai du pont en Python ordinaire : tous les exemples passent par les mêmes fonctions que la page web."""

import json
import sys
import time
from pathlib import Path

racine = Path(__file__).resolve().parent
sys.path[:0] = [str(racine / "application"), str(racine / "docs")]
sys.modules["pandas"] = None  # la page web n'a pas pandas au démarrage : le pont ne doit pas en dépendre
import pont  # noqa: E402

exemples = json.loads(pont.exemples())
assert exemples, "aucun exemple"
assert len(json.loads(pont.materiaux())) > 50
for e in exemples:
    p = pont.charger(e["id"])
    t = time.time()
    ap = json.loads(pont.apercu(p))
    assert ap["erreur"] is None and ap["fig"]["layout"]["annotations"], (e["id"], ap["erreur"])  # flèches : annotations
    r = json.loads(pont.calculer(p))
    assert "erreur" not in r, (e["id"], r)
    assert r["resultats"]["verdicts"]["lignes"] and r["explications"] and r["sensibilite"]["figure"]
    assert len(r["figuresStatistiques"]) == 3 and r["figuresGraphiques"]
    # aller-retour fichier : ce que la page enregistre doit se rouvrir à l'identique
    s = json.loads(pont.sauver(p))
    o = json.loads(pont.ouvrir(s["contenu"]))
    assert o["probleme"]["maillons"] == pont._nettoyer(json.loads(p))["maillons"], e["id"]  # cases vides = champ absent
    v = r["resultats"]["verdicts"]["lignes"][0]
    print(f"{e['id']:<28} {r['niveau']:<13} pire cas {v[1]} … {v[2]} mm  ({time.time() - t:.1f} s)")
vide = json.loads(pont.calculer(json.dumps({"condition": {}, "reglages": {}, "maillons": [{"sens": "+", "cote": ""}]})))
assert "erreur" in vide, vide
ap = json.loads(pont.apercu(json.dumps({"condition": {}, "reglages": {}, "maillons": [{"sens": "+", "cote": "abc"}]})))
assert ap["erreur"] and ap["fig"], ap
mauvais = json.loads(pont.sauver(json.dumps({"condition": {}, "reglages": {"kSigma": 3, "tref": 20, "modeT": "x"}, "maillons": []})))
assert "erreur" in mauvais, mauvais
# ---- phase 2 : exemples, ISO 286, ajustements, matériaux
cartes = json.loads(pont.cartes())
assert len(cartes) == len(exemples) and all(c["maillons"]["lignes"] and (c["pireCas"] or c["erreur"]) for c in cartes)
assert json.loads(pont.schemaExemple(cartes[0]["id"]))["fig"]["layout"]["annotations"]
d = json.loads(pont.iso286Donnees())
assert len(d["it"]["plages"]) == len(d["it"]["colonnes"]["IT7"]) and "h" in d["arbre"]["colonnes"] and "H" in d["alesage"]["colonnes"]
h7 = json.loads(pont.iso286Lire("50 H7"))["valeurs"][0]["valeurs"]
assert h7 == [["ES (mm)", "0,025"], ["EI (mm)", "0"], ["IT (µm)", "25"]], h7
assert len(json.loads(pont.iso286Lire("50 js7"))["valeurs"]) == 2  # IT7 impair : valeur MATLAB et valeur normalisée
assert "erreur" in json.loads(pont.iso286Lire("40 Q7"))
fonctions = json.loads(pont.ajustementFonctions())["fonctions"]
aj = json.loads(pont.ajustement(50, "tournant", "alesage"))
assert aj["noms"][0] == "H8/f7" and aj["choisi"]["jeux"] == [["Jeu mini", "0,0250 mm"], ["Jeu maxi", "0,0890 mm"]], (aj["noms"], fonctions)
assert json.loads(pont.ajustement(50, "tournant", "alesage", "H7/g6"))["choisi"]["designation"] == "H7/g6"
assert "erreur" in json.loads(pont.ajustement(5000, "tournant", "alesage")) and json.loads(pont.ajustement(5000, "tournant", "alesage"))["erreur"]
m = json.loads(pont.maillonsAjustement("H7/g6", 50, json.dumps(["Arbre"]), 20))["maillons"]
assert [x["nom"] for x in m] == ["Alésage", "Arbre (2)"] and [x["sens"] for x in m] == ["+", "-"]
t = json.loads(pont.materiauxTableau("inox", "[]"))
assert 0 < len(t["tableau"]["lignes"]) < t["total"] and t["familles"]
dil = json.loads(pont.dilatation("Acier C45", 20, 100))
assert dil["metriques"][0][1].startswith("12,4") and dil["fig"]["data"], dil["metriques"]
assert "erreur" in json.loads(pont.dilatation("Acier C45", 20, -300))
assert json.loads(pont.materiauxSources())["sources"]["lignes"]
print("saisie invalide ->", vide["erreur"])
print("fichier invalide ->", mauvais["erreur"])
