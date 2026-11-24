"""« Mes études » du site : contrôles d'import (docs/js/etudes.js), exécutés sous Node sans navigateur."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
SCRIPT = RACINE / "docs" / "js" / "etudes.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node absent")

PROBLEME = {"condition": {"nom": "Jeu J", "jmin": 0.2, "jmax": 1}, "reglages": {"kSigma": 3}, "maillons": [{"nom": "A", "sens": "+", "cote": 10, "es": 0.1, "ei": 0}]}


def node(code: str):
    sortie = subprocess.run(
        ["node", "-e", f"const e = require({json.dumps(str(SCRIPT))}); const sortie = (() => {{ {code} }})(); console.log(JSON.stringify(sortie));"],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert sortie.returncode == 0, sortie.stderr
    return json.loads(sortie.stdout)


def export(**changements):
    d = {"format": "chaines-de-cotes-etudes", "version": 1, "schema_version": 1, "copies": [{"id": "e1", "nom": "Mon étude", "cree": 1, "modif": 2, "favori": True, "probleme": PROBLEME}]}
    d.update(changements)
    return json.dumps(d)


def lire(texte: str):
    return node(f"return e.lireImport({json.dumps(texte)});")


def test_export_valide_est_relu():
    r = lire(export())
    assert r["ignorees"] == 0 and r["copies"][0]["nom"] == "Mon étude" and r["copies"][0]["favori"] is True
    assert r["copies"][0]["probleme"]["maillons"][0]["cote"] == 10


def test_fichier_sans_schema_version_est_la_version_1():
    d = json.loads(export())
    del d["schema_version"]
    assert "copies" in lire(json.dumps(d))


def test_version_plus_recente_refusee():
    assert "plus récente" in lire(export(schema_version=2))["erreur"]
    assert "plus récente" in lire(export(version=2))["erreur"]


def test_cle_inconnue_ignoree_et_autres_formats_refuses():
    d = json.loads(export())
    d["copies"][0]["inconnue"] = {"x": 1}
    d["copies"][0]["probleme"]["autre"] = 5  # clé hors liste : retirée du problème
    r = lire(json.dumps(d))
    assert "autre" not in r["copies"][0]["probleme"] and "inconnue" not in r["copies"][0]
    assert "erreur" in lire(json.dumps({"format": "autre"}))
    assert "erreur" in lire("pas du json")


def test_copies_abimees_comptees_et_proto_rejete():
    d = json.loads(export())
    bonne = d["copies"][0]
    vide = {**bonne, "id": "e2", "probleme": {**PROBLEME, "maillons": []}}
    sans_nom = {**bonne, "id": "e3", "nom": "  "}
    mauvais_id = {**bonne, "id": "../x"}
    d["copies"] = [bonne, vide, sans_nom, mauvais_id, 5]
    r = lire(json.dumps(d))
    assert len(r["copies"]) == 1 and r["ignorees"] == 4
    texte = export().replace('"probleme": {', '"probleme": {"__proto__": {"x": 1}, ')
    assert lire(texte)["ignorees"] == 1  # clé « __proto__ » : étude refusée


def test_fusion_et_plafond():
    r = node("""
      const a = (i, modif) => ({ id: 'e' + i, nom: 'N' + i, cree: 1, modif, favori: false, probleme: %s });
      const existantes = [a(1, 10), a(2, 20)];
      const f = e.fusionner(existantes, [a(2, 15), a(1, 99), a(3, 5)]);
      const beaucoup = Array.from({ length: 40 }, (_, i) => a(100 + i, i + 1));
      const g = e.fusionner([], beaucoup);
      return { ids: f.copies.map((c) => c.id), ajoutees: f.ajoutees, remplacees: f.remplacees, total: g.copies.length, coupees: g.coupees, premier: g.copies[0].id };
    """ % json.dumps(PROBLEME))
    assert r["ids"] == ["e1", "e2", "e3"] and r["ajoutees"] == 1 and r["remplacees"] == 1  # e1 plus récente remplacée, e2 gardée
    assert r["total"] == 30 and r["coupees"] == 10 and r["premier"] == "e139"


def test_fichier_trop_gros_refuse():
    assert "trop gros" in node("return e.lireImport('x'.repeat(3100000));")["erreur"]
