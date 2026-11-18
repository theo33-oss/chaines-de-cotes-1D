"""Fabrique docs/chainecotes.zip : le calcul de l'application (sans Qt) que la page web charge dans le navigateur.

À relancer après toute modification de application/chainecotes/core, plots ou services, ou de application/data, ou de
la page (docs/*.js, style.css, pont.py). Il versionne aussi les adresses des scripts dans docs/index.html (?v=empreinte) :
GitHub Pages fait garder chaque fichier 10 minutes par le navigateur, et sans cela un visiteur récent recevrait de
nouveaux scripts avec d'anciens. Il pose enfin le numéro de build (affiché dans le pied de page, comparé à celui en
ligne) et le nom du cache du service worker (docs/sw.js, usage hors ligne).
Usage : python construire_web.py
"""

import hashlib
import re
import shutil
import zipfile
from pathlib import Path

racine = Path(__file__).resolve().parent
appli = racine / "application"
docs = racine / "docs"
sortie = docs / "chainecotes.zip"
EXCLUS = {"bureau", "__pycache__", "polices"}  # l'interface Qt, les caches et les polices du PDF
EXTENSIONS = {".py", ".json", ".j2"}  # .j2 : gabarit du dossier de validation
# le dossier de validation relit les valeurs MATLAB de référence des exemples (chemin relatif à application/)
SUPPLEMENTS = ("tests/golden/golden_exemples.json",)
DATE_FIXE = (2026, 1, 1, 0, 0, 0)  # même contenu → même zip, octet pour octet (pas de faux changement dans git)


def fichiers():
    for dossier in ("chainecotes", "data"):
        for f in sorted((appli / dossier).rglob("*")):
            if f.is_file() and not EXCLUS & set(f.relative_to(appli).parts) and f.suffix in EXTENSIONS:
                yield f
    for chemin in SUPPLEMENTS:
        yield appli / chemin


def contenu_actuel() -> list[tuple[str, bytes]] | None:
    """(nom, octets décompressés) du zip déjà là, ou None s'il manque ou est abîmé."""
    try:
        with zipfile.ZipFile(sortie) as z:
            return [(i.filename, z.read(i)) for i in z.infolist()]
    except (OSError, zipfile.BadZipFile):
        return None


entrees = [(f.relative_to(appli).as_posix(), f.read_bytes().replace(b"\r\n", b"\n")) for f in fichiers()]
# même contenu → on garde le zip tel quel : une autre version de zlib (Python 3.14+ sous Windows, autre image Linux
# de la CI) compresse autrement et changerait les octets, donc les empreintes, sans que rien n'ait changé
if contenu_actuel() != entrees:
    with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for nom, octets in entrees:
            info = zipfile.ZipInfo(nom, DATE_FIXE)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, octets)
print(f"{sortie.relative_to(racine)} : {sortie.stat().st_size / 1024:.0f} Ko")

shutil.copyfile(appli / "data" / "icone.svg", docs / "icone.svg")  # l'icône vient de l'application de bureau : une seule source


def octets(chemin: str) -> bytes:
    """Contenu d'un fichier de docs/, fins de ligne normalisées (Windows : CRLF, git et CI Linux : LF) pour des empreintes identiques."""
    brut = (docs / chemin).read_bytes()
    return brut if chemin.endswith(".zip") else brut.replace(b"\r\n", b"\n")


def empreinte(chemin: str) -> str:
    return hashlib.sha1(octets(chemin)).hexdigest()[:8]


def ecrire_si_change(chemin: Path, ancien: str, nouveau: str) -> None:
    if nouveau != ancien:
        chemin.write_text(nouveau, encoding="utf-8", newline="")


# numéro de version : une seule source, chainecotes/__init__.py, recopiée dans le pied de page
version = re.search(r'__version__ = "([^"]+)"', (appli / "chainecotes" / "__init__.py").read_text(encoding="utf-8")).group(1)
print(f"version {version}")

# service worker : un nom de cache par version du site, les anciennes copies sont effacées
sw = docs / "sw.js"
texte_sw = open(sw, encoding="utf-8", newline="").read()
cle = hashlib.sha1(b"".join(octets(f) for f in ("chainecotes.zip", "app.js", "style.css"))).hexdigest()[:8]
ecrire_si_change(sw, texte_sw, re.sub(r'const VERSION = "[^"]*";', f'const VERSION = "chainecotes-{version}-{cle}";', texte_sw))

# numéro de build : change dès qu'un fichier du site change (le site affiche le sien et le compare à celui en ligne)
build = hashlib.sha1(
    b"".join(octets(f) for f in sorted(["chainecotes.zip", "app.js", "style.css", "pont.py", *[f"js/{p.name}" for p in (docs / "js").glob("*.js")]]))
).hexdigest()[:8]

index = docs / "index.html"
page = open(index, encoding="utf-8", newline="").read()


def versionner(m: re.Match) -> str:
    return f'{m.group(1)}="{m.group(2)}?v={empreinte(m.group(2))}"'


nouvelle = re.sub(r'(src|href)="((?:app\.js|style\.css|js/[a-z0-9]+\.js))(?:\?v=[0-9a-f]+)?"', versionner, page)
# le zip est lu par app.js : son empreinte est posée dans une balise <meta> que le script relit
nouvelle = re.sub(r'(<meta name="zip" content=")[^"]*(")', rf"\g<1>{empreinte('chainecotes.zip')}\g<2>", nouvelle)
nouvelle = re.sub(r'(<meta name="build" content=")[^"]*(")', rf"\g<1>{build}\g<2>", nouvelle)
nouvelle = re.sub(r'(<span id="version">)[^<]*(</span>)', rf"\g<1>{version}\g<2>", nouvelle)
ecrire_si_change(index, page, nouvelle)
print(f"index.html : {len(re.findall(r'[?]v=[0-9a-f]+', nouvelle))} adresses versionnées, build {build}")
