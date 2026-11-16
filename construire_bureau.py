"""Fabrique l'application de bureau autonome (PyInstaller), puis l'installateur Windows (Inno Setup).

Sortie : dist/ChainesDeCotes/ (dossier autonome, Python compris) et dist/ChainesDeCotes_Installation_<version>.exe.
L'installateur s'installe sans droits d'administrateur, crée l'icône du Bureau et l'entrée du menu Démarrer.
Usage : python construire_bureau.py   (depuis l'environnement de application/, PyInstaller installé)
Sur GitHub, le flux .github/workflows/bureau.yml le lance à chaque étiquette de version (v1.0.0…).
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

racine = Path(__file__).resolve().parent
appli = racine / "application"
build = racine / "build"
dist = racine / "dist"
version = re.search(r'__version__ = "([^"]+)"', (appli / "chainecotes" / "__init__.py").read_text(encoding="utf-8")).group(1)
NOM = "ChainesDeCotes"


def icone() -> Path:
    """Icône Windows (.ico, 16 à 256 px) dessinée d'après application/data/icone.svg : une seule source."""
    from PIL import Image
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    _app = QGuiApplication.instance() or QGuiApplication(["icone", "-platform", "offscreen"])
    rendu = QSvgRenderer(str(appli / "data" / "icone.svg"))
    image = QImage(256, 256, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    peintre = QPainter(image)
    rendu.render(peintre)
    peintre.end()
    build.mkdir(exist_ok=True)
    png = build / "icone.png"
    image.save(str(png))
    ico = build / "icone.ico"
    Image.open(png).save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return ico


def pyinstaller(ico: Path) -> Path:
    sep = os.pathsep
    args = [
        sys.executable, "-m", "PyInstaller", str(appli / "main.py"),
        "--name", NOM, "--windowed", "--noconfirm", "--clean", "--onedir",
        "--icon", str(ico),
        "--distpath", str(dist), "--workpath", str(build / "pyinstaller"), "--specpath", str(build),
        "--paths", str(appli),
        "--collect-submodules", "chainecotes",
        "--add-data", f"{appli / 'data'}{sep}data",
        "--add-data", f"{appli / 'chainecotes' / 'services' / 'templates'}{sep}chainecotes/services/templates",
        # le dossier de validation relit les valeurs MATLAB de référence des exemples
        "--add-data", f"{appli / 'tests' / 'golden' / 'golden_exemples.json'}{sep}tests/golden",
        "--exclude-module", "tkinter", "--exclude-module", "pytest", "--exclude-module", "IPython",
    ]  # fmt: skip
    subprocess.run(args, check=True)
    dossier = dist / NOM
    for inutile in dossier.rglob("qtwebengine_devtools_resources*.pak"):  # outils de développement du navigateur
        inutile.unlink()
    for nom in ("LICENSE", "LIMITES.md", "LISEZ-MOI.txt"):
        shutil.copyfile(racine / nom, dossier / nom)
    return dossier


def inno() -> Path | None:
    """Compile l'installateur si Inno Setup 6 est présent (toujours le cas sur les machines Windows de GitHub)."""
    candidats = [shutil.which("iscc"), r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
                 str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe")]  # fmt: skip
    iscc = next((c for c in candidats if c and Path(c).exists()), None)
    if iscc is None:
        print(f"Inno Setup absent : seul le dossier dist/{NOM} est fabriqué.")
        return None
    subprocess.run([iscc, f"/DVersion={version}", f"/DRacine={racine}", str(racine / "installateur.iss")], check=True)
    return dist / f"{NOM}_Installation_{version}.exe"


def taille(p: Path) -> str:
    octets = p.stat().st_size if p.is_file() else sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    return f"{octets / 1024 / 1024:.0f} Mo"


if __name__ == "__main__":
    dossier = pyinstaller(icone())
    print(f"Application : {dossier} ({taille(dossier)})")
    exe = inno()
    if exe:
        print(f"Installateur : {exe} ({taille(exe)})")
