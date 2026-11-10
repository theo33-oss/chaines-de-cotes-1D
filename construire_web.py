"""Fabrique docs/chainecotes.zip : le calcul de l'application (sans Qt) que la page web charge dans le navigateur.

À relancer après toute modification de application/chainecotes/core, plots ou services, ou de application/data, ou de
la page (docs/*.js, style.css, pont.py). Il versionne aussi les adresses des scripts dans docs/index.html (?v=empreinte) :
GitHub Pages fait garder chaque fichier 10 minutes par le navigateur, et sans cela un visiteur récent recevrait de
nouveaux scripts avec d'anciens.
Usage : python construire_web.py
"""

import hashlib
import re
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

# versions des scripts et de la feuille de style : une empreinte de leur contenu, qui change avec lui
docs = racine / "docs"
index = docs / "index.html"
page = index.read_text(encoding="utf-8")


def empreinte(chemin: str) -> str:
    return hashlib.sha1((docs / chemin).read_bytes()).hexdigest()[:8]


def versionner(m: re.Match) -> str:
    return f'{m.group(1)}="{m.group(2)}?v={empreinte(m.group(2))}"'


nouvelle = re.sub(r'(src|href)="((?:app\.js|style\.css|js/[a-z0-9]+\.js))(?:\?v=[0-9a-f]+)?"', versionner, page)
if nouvelle != page:
    index.write_text(nouvelle, encoding="utf-8")
print(f"index.html : {len(re.findall(r'[?]v=[0-9a-f]+', nouvelle))} adresses versionnées")
