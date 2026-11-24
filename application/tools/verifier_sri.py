"""Vérifie que les empreintes « integrity » des scripts tiers de docs/app.js sont toujours bonnes.

Le site charge Plotly, Pyodide et html-to-image depuis un CDN avec une empreinte sha384 : si le fichier du CDN change, le
navigateur le refuse et la page ne démarre plus. Ce contrôle (lancé par la CI) télécharge chaque fichier et compare.
Usage : python application/tools/verifier_sri.py   (code de sortie 0 si tout est bon, 1 sinon)
"""

import base64
import hashlib
import re
import sys
import urllib.request
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "docs" / "app.js"


def empreintes(texte: str) -> list[tuple[str, str]]:
    """(adresse, empreinte) trouvées dans app.js : paires [« https… », « sha384-… »] et src/integrity de html-to-image."""
    paires = re.findall(r'\[\s*"(https://[^"]+)"\s*,\s*"(sha384-[A-Za-z0-9+/=]+)"\s*\]', texte)
    bloc = re.search(r'src:\s*"(https://[^"]+)",\s*integrity:\s*"(sha384-[A-Za-z0-9+/=]+)"', texte)
    return paires + ([bloc.groups()] if bloc else [])


def main() -> int:
    trouvees = empreintes(APP.read_text(encoding="utf-8"))
    if len(trouvees) < 3:
        print(f"ERREUR : {len(trouvees)} empreinte(s) trouvée(s) dans app.js, 3 attendues (plotly, pyodide, html-to-image)")
        return 1
    mauvais = 0
    for adresse, attendue in trouvees:
        with urllib.request.urlopen(adresse, timeout=60) as r:  # noqa: S310 : adresses fixes, https
            reelle = "sha384-" + base64.b64encode(hashlib.sha384(r.read()).digest()).decode()
        etat = "OK" if reelle == attendue else "DIFFÉRENTE"
        print(f"{etat:10} {adresse}")
        mauvais += reelle != attendue
    return 1 if mauvais else 0


if __name__ == "__main__":
    sys.exit(main())
