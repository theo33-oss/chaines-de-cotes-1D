"""Retour visible des actions du bureau : bouton vert avec coche, message flottant (comme sur le site)."""

from PySide6.QtWidgets import QMainWindow, QPushButton

from chainecotes.bureau import widgets


def _fenetre(qtbot):
    f = QMainWindow()
    f.resize(800, 600)
    qtbot.addWidget(f)
    f.show()
    return f


def test_messageFlottant_s_affiche_puis_disparait(qtbot):
    f = _fenetre(qtbot)
    widgets.messageFlottant(f, "Tableau copié.")
    assert f._messageFlottant.isVisible() and f._messageFlottant.text() == "Tableau copié." and f._messageFlottant.property("niveau") == "succes"
    widgets.messageFlottant(f, "Échec", "erreur")  # un seul message, réutilisé
    assert f._messageFlottant.property("niveau") == "erreur" and len(f.findChildren(type(f._messageFlottant))) == 1
    qtbot.waitUntil(lambda: not f._messageFlottant.isVisible(), timeout=6000)


def test_bouton_vert_puis_texte_d_origine(qtbot, monkeypatch):
    monkeypatch.setattr(widgets, "DUREE_RETOUR_MS", 50)
    b = QPushButton("Enregistrer")
    qtbot.addWidget(b)
    widgets.retour(b, True, "Enregistré")
    assert b.text() == "✓ Enregistré" and b.property("retour") == "ok"
    widgets.retour(b, False, "", "Impossible")  # un second retour garde le texte d'origine
    assert b.text() == "✗ Impossible" and b.property("retour") == "ko"
    qtbot.waitUntil(lambda: b.text() == "Enregistrer", timeout=2000)
    assert b.property("retour") is None


def test_confirmer_bouton_et_message(qtbot):
    f = _fenetre(qtbot)
    b = QPushButton("Copier")
    qtbot.addWidget(b)
    widgets.confirmer(f, b, True, "Copié", message="Copié dans le presse-papiers.")
    assert b.property("retour") == "ok" and f._messageFlottant.text() == "Copié dans le presse-papiers."
    widgets.confirmer(f, None, False, "", "Copie impossible")
    assert f._messageFlottant.property("niveau") == "erreur" and f._messageFlottant.text() == "Copie impossible"


def test_la_feuille_de_style_colore_le_retour(qtbot):
    from PySide6.QtWidgets import QApplication

    widgets.appliquerTheme(QApplication.instance())
    css = QApplication.instance().styleSheet()
    assert '#primaire[retour="ok"]' in css and '#messageFlottant[niveau="erreur"]' in css


def test_copier_l_image_d_un_long_tableau(qtbot):
    """Un tableau qui défile sur place est copié en entier (pas seulement la partie visible)."""
    import pandas as pd
    from PySide6.QtWidgets import QApplication

    f = _fenetre(qtbot)
    t = widgets.TableauDonnees(pd.DataFrame({"Maillon": [f"Cote_{i}" for i in range(40)], "Cpk": [1.5] * 40}))
    f.setCentralWidget(t)
    qtbot.wait(100)  # la fenêtre place le tableau avant la mesure
    avant = t.size()
    barre = widgets.barreImage(t, f)
    qtbot.addWidget(barre)
    bouton = barre.findChild(QPushButton)
    assert bouton.text() == "Copier l'image" and bouton.objectName() == "petit"
    bouton.click()
    qtbot.waitUntil(lambda: not QApplication.clipboard().pixmap().isNull(), timeout=3000)
    assert QApplication.clipboard().pixmap().height() > widgets.HAUTEUR_TABLEAU_MAX
    assert bouton.property("retour") == "ok" and f._messageFlottant.text().startswith("Image copiée")
    assert t.size() == avant  # le tableau reprend sa taille


def test_demander_a_une_ia_copie_la_consigne_et_l_etude(qtbot, monkeypatch):
    from PySide6.QtWidgets import QApplication

    from chainecotes.bureau import ia
    from chainecotes.services.calcul import calculerChaine
    from chainecotes.services.exemples import chargerExemple

    menus = []
    monkeypatch.setattr(ia, "_montrerMenu", lambda menu, position: menus.append([a.text() for a in menu.actions()]))
    f = _fenetre(qtbot)
    b = QPushButton("Demander à une IA", f)
    p = chargerExemple("tableau_depart")
    assert ia.demanderAUneIA(f, b, None) is False  # pas encore calculé : message, rien de copié
    assert f._messageFlottant.property("niveau") == "erreur" and "Calculez" in f._messageFlottant.text() and not menus
    assert ia.demanderAUneIA(f, b, calculerChaine(p, n=500)) is True
    texte = QApplication.clipboard().text()
    assert texte.startswith("Tu es un ingénieur") and "--- ÉTUDE ---" in texte and "Cote_1" in texte
    assert menus[0][-2:] == ["Ouvrir Claude", "Ouvrir ChatGPT"]


def test_les_champs_portent_le_nom_de_leur_etiquette(qtbot):
    """Lecteur d'écran : chaque champ de saisie a un nom accessible (celui de son libellé)."""
    from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

    from chainecotes.bureau.widgets import Zone

    class _Page:
        fenetre = None

    hote = QWidget()
    qtbot.addWidget(hote)
    z = Zone(_Page(), QVBoxLayout(hote))
    champ = QLineEdit()
    z._etiquette("Nom de la cote condition", champ, "aide")
    assert champ.accessibleName() == "Nom de la cote condition"
    from PySide6.QtWidgets import QLabel

    assert hote.findChild(QLabel).buddy() is champ


def test_theme_force_par_variable_n_est_pas_retenu(qtbot, tmp_path):
    """CHAINECOTES_THEME vaut pour la séance : la fermeture n'écrase pas le thème choisi par l'utilisateur."""
    from PySide6.QtCore import QSettings

    import main as application
    from chainecotes.bureau import state

    state.v.clear()
    state.init()
    reglages = QSettings(str(tmp_path / "reglages.ini"), QSettings.Format.IniFormat)
    reglages.setValue("sombre", False)
    f = application.Fenetre()
    qtbot.addWidget(f)
    f.reglages, f.themeForce = reglages, True
    state.v["sombre"] = True  # forcé par la variable
    f.close()
    assert reglages.value("sombre", type=bool) is False  # le choix enregistré reste

    state.v.clear()
    state.init()
    g = application.Fenetre()
    qtbot.addWidget(g)
    g.reglages, g.themeForce = reglages, True
    g.basculerTheme()  # choix fait à la main : il est retenu
    clair_sombre = bool(state.v["sombre"])
    g.close()
    assert reglages.value("sombre", type=bool) is clair_sombre


def test_les_cases_du_tableau_copiees_pour_excel_gardent_des_nombres(qtbot):
    """Une case écrite « 1,2·10⁵ » à l'écran est copiée « 1,2e5 » : Excel y lit un nombre, pas du texte."""
    import pandas as pd

    from chainecotes.core.nombres import fr

    t = widgets.TableauDonnees(pd.DataFrame({"Maillon": ["A"], "ppm": [fr(1.2e5, ".3g")]}))
    qtbot.addWidget(t)
    assert t.item(0, 1).text() == "1,2·10⁵"
    assert widgets.texteTableau(t).split("	")[-1] == "1,2e5"
