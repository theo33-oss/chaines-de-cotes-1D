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
print("saisie invalide ->", vide["erreur"])
print("fichier invalide ->", mauvais["erreur"])
