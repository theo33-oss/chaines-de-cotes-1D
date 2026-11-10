"""Essai du pont en Python ordinaire : tous les exemples passent par les mêmes fonctions que la page web."""

import json
import sys
from pathlib import Path

racine = Path(__file__).resolve().parent
sys.path[:0] = [str(racine / "application"), str(racine / "docs")]
import pont  # noqa: E402

exemples = json.loads(pont.exemples())
assert exemples, "aucun exemple"
for e in exemples:
    r = json.loads(pont.calculer(pont.charger(e["id"])))
    assert "erreur" not in r, (e["id"], r)
    assert len(r["figures"]) == 5 and len(r["metriques"]) == 4
    print(f"{e['id']:<28} {r['niveau']:<13} {r['metriques'][0][1]} … {r['metriques'][1][1]}  Cpk {r['metriques'][2][1]}")
vide = json.loads(pont.calculer(json.dumps({"condition": {}, "reglages": {}, "maillons": [{"sens": "+", "cote": ""}]})))
assert "erreur" in vide, vide
print("saisie invalide ->", vide["erreur"])
