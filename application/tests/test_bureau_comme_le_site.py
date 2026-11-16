"""Le bureau offre ce que le site offre : thème, icônes du menu, dupliquer, « ±0,1 », copie de tableau, reprise."""

import os

import pandas as pd
import pytest
from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401 : à importer avant QApplication
from PySide6.QtWidgets import QApplication, QPushButton, QTableWidget, QTableWidgetSelectionRange

os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")

import main as application  # noqa: E402
from chainecotes.bureau import icones, state, widgets  # noqa: E402
from chainecotes.services import projet_io  # noqa: E402


@pytest.fixture
def fenetre(qtbot):
    state.v.clear()
    state.init()
    f = application.Fenetre()
    qtbot.addWidget(f)
    f.show()
    return f


def bouton(widget, texte):
    return next(b for b in widget.findChildren(QPushButton) if b.text() == texte)


def tableMaillons(p):
    return next(t for t in p.findChildren(QTableWidget) if isinstance(t, widgets.TableauEditable))


def test_menu_avec_icones_et_sans_emoji(fenetre):
    lignes = [fenetre.menu.item(rang) for rang, _ in set(fenetre.pages.values())]
    assert lignes and all(not it.icon().isNull() for it in lignes)
    assert all(ord(c) < 0x2190 for it in lignes for c in it.text())  # ni flèche ni pictogramme dans les libellés
    assert not icones.iconeApplication().isNull()
    for ident, libelle, classe in application.MENU:  # chaque ligne du menu a son tracé
        if classe is not None and libelle is not None:
            assert not icones.iconeMenu(ident).isNull()


def test_theme_sombre_par_le_menu(fenetre):
    avant = QApplication.instance().styleSheet()
    fenetre.basculerTheme()
    assert state.v["sombre"] is True and fenetre.actionSombre.isChecked()
    assert "#0F0C18" in QApplication.instance().styleSheet()
    fenetre.basculerTheme()
    assert state.v["sombre"] is False and not fenetre.actionSombre.isChecked()
    assert QApplication.instance().styleSheet() == avant or "#F6F4FA" in QApplication.instance().styleSheet()


def test_couleurs_du_bureau_identiques_au_site(fenetre):
    """Fond, texte, bordures et accent du bureau sont ceux de docs/style.css (palette de MecaStruct), en clair et en sombre."""
    import re
    from pathlib import Path

    css = (Path(application.__file__).resolve().parent.parent / "docs" / "style.css").read_text(encoding="utf-8")
    clair, sombre = css.split(':root[data-theme="dark"]')[0], css.split(':root[data-theme="dark"]')[1].split("}")[0]
    noms = ("fond", "carte", "encre", "discret", "bord", "bord-fort", "accent", "bandeau", "lien")
    state.v["sombre"] = False
    widgets.appliquerTheme(QApplication.instance())
    for bloc, sombre_voulu in ((clair, False), (sombre, True)):
        if bool(state.v.get("sombre")) != sombre_voulu:
            fenetre.basculerTheme()
        feuille = QApplication.instance().styleSheet()
        for nom in noms:
            couleur = re.search(rf"--{nom}: (#[0-9A-Fa-f]{{6}});", bloc)[1]
            assert couleur in feuille, f"--{nom} {couleur} absent du thème {'sombre' if sombre_voulu else 'clair'} du bureau"
        assert "#FFDBC3" not in feuille  # plus de fond pêche
    if state.v.get("sombre"):
        fenetre.basculerTheme()


def test_dupliquer_un_maillon(fenetre, qtbot):
    fenetre.aller("calcul")
    p = fenetre.pages["calcul"][1]
    maillons = state.probleme()["maillons"]
    n, premier = len(maillons), dict(maillons[0])
    bouton(p, "Dupliquer").click()
    qtbot.wait(20)
    bouton(p, "Dupliquer").click()  # la sélection est passée sur la copie : seconde copie, nom encore unique
    qtbot.wait(20)
    maillons = state.probleme()["maillons"]
    assert len(maillons) == n + 2
    assert maillons[1]["nom"] == f"{premier['nom']} (copie)" and maillons[1]["cote"] == premier["cote"]
    assert len({m["nom"] for m in maillons}) == n + 2
    maillons[1]["cote"] = 999.0
    assert maillons[0]["cote"] == premier["cote"]  # copie indépendante


def test_plus_ou_moins_dans_es(fenetre, qtbot):
    fenetre.aller("calcul")
    table = tableMaillons(fenetre.pages["calcul"][1])
    colonne = next(j for j, c in enumerate(table.colonnes) if c.cle == "es")
    table.item(0, colonne).setText("±0,2")
    qtbot.wait(50)
    m = state.probleme()["maillons"][0]
    assert m["es"] == pytest.approx(0.2) and m["ei"] == pytest.approx(-0.2) and not m.get("iso")


def test_copie_d_un_tableau_pour_excel(qtbot):
    t = widgets.TableauDonnees(pd.DataFrame({"Maillon": ["A", "B"], "Cpk": [1.5, 2.25]}), {"Cpk": "%.2f"})
    qtbot.addWidget(t)
    assert widgets.texteTableau(t) == "Maillon\tCpk\nA\t1,50\nB\t2,25"
    assert "Capabilité réelle" in t.horizontalHeaderItem(1).toolTip()  # bulle du lexique, comme sur le site
    t.setRangeSelected(QTableWidgetSelectionRange(1, 0, 1, 1), True)
    assert widgets.texteTableau(t, selection=True) == "B\t2,25"
    assert [a.text() for a in t.actions()] == ["Copier le tableau"]


def test_reprise_apres_arret_imprevu(fenetre, tmp_path):
    fenetre.fichierReprise = tmp_path / "sous" / "derniere_etude.json"
    state.probleme()["maillons"][0]["cote"] = 123.456
    fenetre._surveiller()  # la veille voit la modification : copie de secours
    assert fenetre.fichierReprise.exists()
    garde = projet_io.importerProjet(fenetre.fichierReprise.read_text(encoding="utf-8"))
    assert garde["probleme"]["maillons"][0]["cote"] == 123.456

    state.v.clear()  # nouveau lancement
    state.init()
    autre = application.Fenetre()
    autre.fichierReprise = fenetre.fichierReprise
    autre.reprendre()
    assert state.probleme()["maillons"][0]["cote"] == 123.456 and state.modifiee()
    autre.close()  # fermeture voulue : plus rien à reprendre
    assert not autre.fichierReprise.exists()


def test_copie_de_secours_illisible_ignoree(fenetre, tmp_path):
    fenetre.fichierReprise = tmp_path / "derniere_etude.json"
    fenetre.fichierReprise.write_text("pas du json", encoding="utf-8")
    avant = state.probleme()
    fenetre.reprendre()
    assert state.probleme() is avant and not fenetre.fichierReprise.exists()


def test_menu_du_haut_comme_le_site():
    """Accueil, Étude, Mécanisme, Aides et les pages d'Aides ont, sur le bureau, les noms et l'ordre du site."""
    import re
    from pathlib import Path

    docs = Path(application.__file__).resolve().parent.parent / "docs"
    app_js = (docs / "app.js").read_text(encoding="utf-8")
    entrees = re.search(r"const entrees = \[(.*?)\];\n", app_js, re.S)[1]
    noms_site = re.findall(r'\["[a-z]+", "([^"]+)"', entrees)
    assert noms_site == ["Accueil", "Étude", "Mécanisme", "Aides"]
    assert [nom for nom, _ in application.FAMILLES] == noms_site[1:]
    ids = re.search(r"const AIDES = \[(.*?)\];", app_js)[1]
    ids_site = re.findall(r'"([a-z0-9]+)"', ids)
    titres = {}
    for js in (docs / "js").glob("*.js"):
        for ident, titre in re.findall(r'enregistrerPage\(\{ id: "([a-z0-9]+)"(?:, dans: "[a-z]+")?, titre: "([^"]+)"', js.read_text(encoding="utf-8")):
            titres[ident] = titre
    aides = dict(application.FAMILLES)["Aides"]
    assert [libelle for _, libelle in aides if libelle != "À propos"] == [titres[i] for i in ids_site]
    assert [libelle for _, libelle in dict(application.FAMILLES)["Étude"] if libelle != "Nouvelle étude (guidé)"] == ["Étude", titres["repartir"], titres["comparer"]]
