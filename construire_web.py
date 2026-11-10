"""Fabrique docs/chainecotes.zip : le calcul de l'application (sans Qt) que la page web charge dans le navigateur.

À relancer après toute modification de application/chainecotes/core, plots ou services, ou de application/data.
Usage : python construire_web.py
"""

import zipfile
from pathlib import Path

racine = Path(__file__).resolve().parent
appli = racine / "application"
sortie = racine / "docs" / "chainecotes.zip"
EXCLUS = {"bureau", "__pycache__", "polices", "templates"}  # l'interface Qt, les caches, les polices et gabarits PDF/HTML


def fichiers():
    for dossier in ("chainecotes", "data"):
        for f in sorted((appli / dossier).rglob("*")):
            if f.is_file() and not EXCLUS & set(f.relative_to(appli).parts) and f.suffix in {".py", ".json"}:
                yield f


with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as z:
    for f in fichiers():
        z.write(f, f.relative_to(appli).as_posix())
print(f"{sortie.relative_to(racine)} : {sortie.stat().st_size / 1024:.0f} Ko")
