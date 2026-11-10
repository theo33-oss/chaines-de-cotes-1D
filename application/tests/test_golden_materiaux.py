"""α moyen et domaine d'emploi : alphaMateriau redonne alphaMateriau.m (tests/golden/golden_materiaux.json)."""

import numpy as np
import pytest

from chainecotes.core.materiaux import PERSONNALISE, alphaMateriau, nomsMateriaux
from tests.golden_tools import assertTableau, casGolden, chargerGolden

GOLDEN = "golden_materiaux.json"
CAS = casGolden(GOLDEN)


@pytest.mark.parametrize("c", CAS, ids=lambda c: f"{c['nom']}_Tref{c['tref']:g}")
def test_alpha_comme_matlab(c):
    r = alphaMateriau(c["nom"], c["T"], c["tref"])
    assertTableau(r["alpha"], c["alpha"], rel=1e-12, abs_=0.0, chemin=f"{c['nom']}.alpha")
    assert np.asarray(r["horsDomaine"]).tolist() == c["horsDomaine"]


def test_tous_les_materiaux_et_deux_tref():
    cas = chargerGolden(GOLDEN)["cas"]
    noms = set(nomsMateriaux()) - {PERSONNALISE}
    for tref in (20, 100):
        assert {c["nom"] for c in cas if c["tref"] == tref} == noms
