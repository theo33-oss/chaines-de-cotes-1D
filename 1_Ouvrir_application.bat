@echo off
rem Ouvre l'application dans sa fenetre. Tout reste sur ce poste : rien n'est envoye sur Internet.
rem Premier lancement : prepare Python et telecharge les bibliotheques (Internet necessaire une seule fois).
title Chaines de cotes 1D
cd /d "%~dp0application"
if exist ".venv\installation_ok.txt" goto lancer

set "PYTHON="
for %%v in (3.12 3.13 3.11 3.14 3.15) do (
  if not defined PYTHON py -%%v -c "" >nul 2>nul && set "PYTHON=py -%%v"
)
if not defined PYTHON python -c "import sys; sys.exit(sys.version_info[:2] < (3, 11))" >nul 2>nul && set "PYTHON=python"
if not defined PYTHON goto sans_python

echo Premier lancement : installation en cours, 5 a 10 minutes (environ 1 Go).
echo Ne fermez pas cette fenetre : l'application s'ouvrira toute seule.
%PYTHON% -m venv .venv || goto erreur
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements.txt || goto erreur
echo ok> ".venv\installation_ok.txt"

:lancer
rem pythonw : pas de fenetre noire, l'application a sa propre fenetre
start "" ".venv\Scripts\pythonw.exe" main.py
goto :eof

:sans_python
echo Python 3.12 n'est pas installe sur ce poste.
echo Installez-le depuis https://www.python.org/downloads/ puis relancez ce fichier.
pause
goto :eof

:erreur
echo L'installation a echoue. Verifiez la connexion Internet, puis relancez ce fichier.
pause
