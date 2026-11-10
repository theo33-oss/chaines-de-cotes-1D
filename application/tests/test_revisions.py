"""Révisions de l'étude : service, fichier projet et page Calcul."""

import copy
import json

import pytest

from chainecotes.core.errors import ErreurChaine
from chainecotes.services.exemples import chargerExemple
from chainecotes.services.projet_io import (
    MAX_REVISIONS_ETUDE,
    exporterProbleme,
    exporterProjet,
    importerProbleme,
    importerProjet,
)
from chainecotes.services.revisions import (
    ajouterRevision,
    comparerRevisions,
    diffProblemes,
    indiceSuivant,
    libelleRevision,
    nouvelleRevision,
)


def _variante():
    p = chargerExemple("ajustements_h7_h6_n7")
    q = copy.deepcopy(p)
    q["maillons"][0].update(iso=None, es=0.05, ei=-0.05)
    q["maillons"].append({"nom": "Cale", "sens": "-", "cote": 0.5, "es": 0.01, "ei": -0.01})
    q["condition"]["jmax"] = 2.0
    return p, q


def test_indices():
    assert [indiceSuivant([0] * n) for n in (0, 1, 25, 26, 27)] == ["A", "B", "Z", "A2", "B2"]


def test_diff_saisie():
    p, q = _variante()
    phrases = diffProblemes(p, q)
    texte = "\n".join(phrases)
    assert "Maillon ajouté : Cale" in texte
    assert "Cote condition : Jmax" in texte and "désignation ISO" in texte and "ES" in texte
    assert diffProblemes(p, copy.deepcopy(p)) == []


def test_comparaison_des_resultats():
    p, q = _variante()
    c = comparerRevisions(p, q)
    assert c["saisie"] and not c["resultats"]["identiques"]
    assert any("Maillon ajouté" in x for x in c["resultats"]["phrases"])
    assert comparerRevisions(p, copy.deepcopy(p))["resultats"]["identiques"]


def test_comparaison_d_un_etat_invalide_nomme_le_probleme():
    p, q = _variante()
    q["maillons"][0]["sens"] = "x"
    with pytest.raises(ErreurChaine, match="Problème B"):
        comparerRevisions(p, q)


def test_nouvelle_revision_et_limites():
    p, _ = _variante()
    r = nouvelleRevision(p, " A ", "2026-11-03", "TB", "Création")
    assert (r["indice"], libelleRevision(r)) == ("A", "A — 2026-11-03 — Création")
    r["probleme"]["condition"]["nom"] = "autre"
    assert p["condition"]["nom"] != "autre"  # copie profonde
    with pytest.raises(ErreurChaine):
        nouvelleRevision(p, "", "2026-11-03")
    with pytest.raises(ErreurChaine):
        nouvelleRevision(p, "A", "2026-11-03", objet="x" * 201)
    revs = []
    for _ in range(MAX_REVISIONS_ETUDE):
        revs = ajouterRevision(revs, r)
    with pytest.raises(ErreurChaine, match="Trop de révisions"):
        ajouterRevision(revs, r)


def test_fichier_aller_retour_et_compatibilite():
    p, q = _variante()
    revs = [nouvelleRevision(p, "A", "2026-10-01", "TB", "Création")]
    lu = importerProjet(exporterProjet(q, revs))
    assert lu["probleme"]["condition"]["jmax"] == 2.0 and lu["revisions"][0]["probleme"]["condition"]["jmax"] != 2.0
    assert exporterProjet(p) == exporterProbleme(p)  # sans révision, le fichier est celui d'avant
    assert importerProjet(exporterProbleme(p))["revisions"] == []
    assert importerProbleme(exporterProjet(q, revs)) == q  # l'ancienne lecture ignore les révisions


@pytest.mark.parametrize(
    "abime",
    [
        lambda d: d.update(revisions="A"),
        lambda d: d.update(revisions=[3]),
        lambda d: d.update(revisions=[{"indice": "A", "inconnu": 1, "probleme": d["probleme"]}]),
        lambda d: d.update(revisions=[{"indice": "A"}]),
        lambda d: d.update(revisions=[{"indice": "A", "probleme": {"condition": {}}}]),
        lambda d: d.update(revisions=[{"indice": "A", "probleme": d["probleme"]}] * (MAX_REVISIONS_ETUDE + 1)),
    ],
)
def test_fichier_refuse_revisions_invalides(abime):
    p, _ = _variante()
    d = json.loads(exporterProbleme(p))
    abime(d)
    with pytest.raises(ErreurChaine):
        importerProjet(json.dumps(d))


