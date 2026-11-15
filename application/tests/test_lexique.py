"""Les bulles d'aide du bureau disent la même chose que celles du site (LEXIQUE de docs/app.js)."""

import re
from pathlib import Path

from chainecotes.core.lexique import LEXIQUE, aideTerme

APP_JS = Path(__file__).resolve().parents[2] / "docs" / "app.js"


def test_memes_motifs_et_textes_que_le_site():
    js = APP_JS.read_text(encoding="utf-8")
    bloc = js[js.index("const LEXIQUE = ["):]
    bloc = bloc[: bloc.index("\n  ];")]
    site = re.findall(r'^\s*\[/(.+?)/(i?), "(.*)"\],?$', bloc, flags=re.M)
    assert [(m.pattern, bool(m.flags & re.I), t) for m, t in LEXIQUE] == [(m, bool(d), t) for m, d, t in site]


def test_termes_connus():
    assert "Capabilité réelle" in aideTerme("Cpk")
    assert "Écart supérieur" in aideTerme("ES (mm)")
    assert aideTerme("Maillon") == ""


def test_palette_sombre_des_figures_identique_au_site():
    """Les figures du bureau passent en sombre avec les mêmes couleurs que celles du site (COULEURS_SOMBRES)."""
    import json

    from chainecotes.bureau.widgets import FIGURE_SOMBRE

    js = APP_JS.read_text(encoding="utf-8")
    site = json.loads(re.search(r"const COULEURS_SOMBRES = (\{.*?\});", js)[1])
    assert site == FIGURE_SOMBRE
