"""Fabrique docs/chainecotes.zip : le calcul de l'application (sans Qt) que la page web charge dans le navigateur.

À relancer après toute modification de application/chainecotes/core, plots ou services, ou de application/data.
Usage : python construire_web.py
"""

import zipfile
from pathlib import Path

racine = Path(__file__).resolve().parent
appli = racine / "application"
sortie = racine / "docs" / "chainecotes.zip"
EXCLUS = {"bureau", "__pycache__", "polices"}  # l'interface Qt, les caches et les polices du PDF
EXTENSIONS = {".py", ".json", ".j2"}  # .j2 : gabarit du dossier de validation
# le dossier de validation relit les valeurs MATLAB de référence des exemples (chemin relatif à application/)
SUPPLEMENTS = ("tests/golden/golden_exemples.json",)


def fichiers():
    for dossier in ("chainecotes", "data"):
        for f in sorted((appli / dossier).rglob("*")):
            if f.is_file() and not EXCLUS & set(f.relative_to(appli).parts) and f.suffix in EXTENSIONS:
                yield f
    for chemin in SUPPLEMENTS:
        yield appli / chemin


with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as z:
    for f in fichiers():
        z.write(f, f.relative_to(appli).as_posix())
print(f"{sortie.relative_to(racine)} : {sortie.stat().st_size / 1024:.0f} Ko")
