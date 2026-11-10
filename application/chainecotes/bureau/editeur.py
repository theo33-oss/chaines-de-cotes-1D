"""Éditeurs du problème courant : cote condition, réglages, tableau des maillons et curseurs de sensibilité.

Chaque éditeur modifie state.probleme() sur place. Les clés des champs commencent par « editeur. » :
state.definirProbleme les oublie, les éditeurs repartent alors du nouveau problème. `apres` signale un changement
de valeurs (la page met à jour sa visualisation) ; `relance` un changement de structure (la saisie est redessinée).
"""

import copy
import math
import re
from collections.abc import Callable
from typing import Any

from chainecotes.bureau import state
from chainecotes.bureau.widgets import Colonne, TableauEditable, Zone
from chainecotes.core import geometrie, iso2768
from chainecotes.core.chaine import LOIS, MODES_T, ZERO_ABSOLU_C, libelleVerdict
from chainecotes.core.chaine import estVide as _vide
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.geometrie import TYPES as TYPES_GEOMETRIE
from chainecotes.core.geometrie import maillonGeometrique
from chainecotes.core.iso286 import LETTRES_ALESAGE, LETTRES_ARBRE, QUALITES, lireDesignation
from chainecotes.core.materiaux import nomsMateriaux
from chainecotes.plots._common import fr
from chainecotes.services.calcul import apercuChaine
from chainecotes.services.cartouche import CHAMPS, MAX_REVISIONS, REVISIONS, STATUTS, empreinte
from chainecotes.services.projet_io import MAX_TEXTE

Rappel = Callable[[], None]
P = state.PREFIXE_EDITEUR
CLE_VERSION = P + "maillons.version"  # change à chaque modification : les listes de tolérance repartent du problème
CLE_SELECTION = P + "selection"
CLE_MESSAGE = P + "message"
MOINS = "−"
MODE_PERSO, MODE_ISO = "Personnalisée", "Normalisée ISO 286"
POSITIONS_PERSO = ("Centrée (± IT / 2)", "De 0 à + IT", "De − IT à 0")
_LETTRE_QUALITE = re.compile(r"([A-Za-z]{1,2})\s*(\d{1,2})\s*$")
PROCEDES_K = (3, 4, 5, 6)  # procédé garanti à ± k σ (liste de l'application MATLAB)
LIBELLES_MODE_T = {"uniforme": "Uniforme", "par_cote": "Par cote"}
LIBELLES_TOL_GENERALE = {"": "Aucune (écarts à saisir)", "f": "ISO 2768-f (fine)", "m": "ISO 2768-m (moyenne)",
                         "c": "ISO 2768-c (grossière)", "v": "ISO 2768-v (très grossière)"}  # fmt: skip
ETENDUE_IT_NUL = 0.2  # mm : étendue du curseur d'un maillon sans tolérance
COLONNES_NUMERIQUES = (
    "cote", "es", "ei", "alpha", "tservice", "derive", "facteur", "angle", "sigma_reel", "moyenne_reelle"
)  # fmt: skip
COLONNES_PROJECTION = ("facteur", "angle")  # affichées sur demande : le cas courant est a = ±1
COLONNES_ATELIER = ("sigma_reel", "moyenne_reelle")  # idem : le cas courant est le modèle de la loi


def _ecartsAffiches(m: dict) -> tuple[Any, Any, str]:
    """ES et EI à afficher (ceux de la norme si une désignation ISO 286 est saisie) et message d'erreur ISO."""
    if _vide(m.get("iso")):
        return m.get("es"), m.get("ei"), ""
    try:
        r = lireDesignation(str(m["iso"]), None if _vide(m.get("cote")) else float(m["cote"]))
    except ErreurChaine as e:
        return None, None, e.message
    return r["es"], r["ei"], ""


def _coteDeDesignation(iso: str) -> float | None:
    """Cote écrite dans la désignation (« 40 h7 » → 40), ou None si elle n'en contient pas ou est illisible."""
    try:
        return lireDesignation(iso)["cote"]
    except ErreurChaine:
        return None


def _versProbleme(col: str, v: Any) -> Any:
    """Valeur d'une case du tableau convertie au format du problème."""
    if col == "sens":
        return "-" if v in ("-", MOINS) else "+"
    if col == "nom":
        return "" if _vide(v) else str(v).strip()
    if col == "loi":
        return "normale" if _vide(v) else str(v)
    if col in COLONNES_NUMERIQUES:
        return None if _vide(v) else float(v)
    return None if _vide(v) else str(v).strip()


def lignesTableau(maillons: list[dict]) -> tuple[list[dict], list[str]]:
    """Lignes affichées (ES / EI de la norme quand l'ISO est lisible) et messages des désignations illisibles."""
    lignes, erreurs = [], []
    for i, m in enumerate(maillons):
        es, ei, erreur = _ecartsAffiches(m)
        if erreur:
            erreurs.append(
                f"Maillon {i + 1} ({m.get('nom', '')}) : {erreur} ES et EI restent vides tant que la désignation "
                "est illisible."
            )
        lignes.append(
            {
                "nom": m.get("nom", ""),
                "sens": MOINS if m.get("sens") == "-" else "+",
                "cote": m.get("cote"),
                "iso": "" if _vide(m.get("iso")) else str(m["iso"]),
                "es": es,
                "ei": ei,
                "loi": m.get("loi") or "normale",
                "derive": m.get("derive"),
                "facteur": m.get("facteur"),
                "angle": m.get("angle"),
                "sigma_reel": m.get("sigma_reel"),
                "moyenne_reelle": m.get("moyenne_reelle"),
                "materiau": None if _vide(m.get("materiau")) else m["materiau"],
                "alpha": m.get("alpha"),
                "tservice": m.get("tservice"),
            }
        )
    return lignes, erreurs


def modifierCase(m: dict, col: str, v: Any) -> None:
    """Recopie une case modifiée dans le maillon m (la désignation ISO reste prioritaire)."""
    es0, ei0, _ = _ecartsAffiches(m)
    m[col] = _versProbleme(col, v)
    if col in ("es", "ei") and not _vide(m.get("iso")):
        # écart saisi à la main sur une ligne ISO : il remplace la désignation
        m["iso"] = None
        m["es"] = m["es"] if col == "es" else es0
        m["ei"] = m["ei"] if col == "ei" else ei0
    if col == "iso" and m["iso"] and (c := _coteDeDesignation(m["iso"])) is not None:
        m["cote"] = c


def _version() -> int:
    return state.v.get(CLE_VERSION, 0)


def _apresModification(selection: int) -> None:
    """Après un changement de la liste : nouvelle version du tableau et maillon sélectionné."""
    state.v[CLE_VERSION] = _version() + 1
    state.v[CLE_SELECTION] = selection


def _selection(n: int) -> int:
    """Indice du maillon sélectionné, ramené dans [0 ; n − 1]."""
    i = state.v.get(CLE_SELECTION, 0)
    return min(max(int(i) if isinstance(i, int) else 0, 0), n - 1)


def _ajouter() -> None:
    """Insère un maillon « Maillon n » (nom unique) après le maillon sélectionné."""
    p = state.probleme()
    maillons = p["maillons"]
    noms = {m.get("nom") for m in maillons}
    n = len(maillons) + 1
    while f"Maillon {n}" in noms:
        n += 1
    i = _selection(len(maillons)) + 1
    tref = p.get("reglages", {}).get("tref", 20.0)
    maillons.insert(
        i,
        {
            "nom": f"Maillon {n}",
            "sens": "+",
            "cote": 0.0,
            "iso": None,
            "es": 0.0,
            "ei": 0.0,
            "loi": "normale",
            "materiau": None,
            "alpha": None,
            "tservice": tref,
        },
    )
    _apresModification(i)


def _ajouterGeometrie(cle: str) -> None:
    """Insère après le maillon sélectionné la tolérance géométrique choisie (voir core/geometrie)."""
    maillons = state.probleme()["maillons"]
    bonus = state.v.get(cle + "bonus", 0.0) if state.v.get(cle + "mmc") else 0.0
    try:
        m = maillonGeometrique(
            state.v[cle + "type"],
            float(state.v[cle + "valeur"]),
            "-" if state.v[cle + "sens"] == MOINS else "+",
            bonus=float(bonus),
        )
    except ErreurChaine as e:
        state.v[CLE_MESSAGE] = e.message
        return
    i = _selection(len(maillons)) + 1
    maillons.insert(i, m)
    _apresModification(i)


def ajouterToleranceGeometrique(z: Zone, relance: Rappel) -> None:
    """Formulaire d'ajout d'une tolérance géométrique ISO 1101 comme maillon de la chaîne."""
    cle = P + "geo."

    def rendu(s: Zone) -> None:
        s.legende(
            "Une zone de tolérance de largeur t déplace la surface de ± t/2 au plus dans le sens de la chaîne : elle "
            "devient un maillon de cote nulle et d'IT = t. Au maximum de matière (Ⓜ), le bonus s'ajoute à t au pire "
            "des cas. Modèle 1D : une zone inclinée se règle avec les colonnes Facteur et Angle."
        )
        c = s.colonnes(2)
        c[0].liste("Type", list(TYPES_GEOMETRIE), cle + "type", format=geometrie.libelle)
        c[1].nombre("Zone t (mm)", cle + "valeur", 0.05, mini=0.0)
        c[0].radio("Sens dans la chaîne", ["+", MOINS], cle + "sens")
        mmc = c[1].case(f"Maximum de matière {geometrie.MAXIMUM_MATIERE}", cle + "mmc", apres=lambda: section.rafraichir())
        if mmc:
            s.nombre(
                "Bonus maximal (mm)", cle + "bonus", 0.0, mini=0.0,
                aide="Écart maximal entre la taille réelle et la taille au maximum de matière : l'IT de l'élément.",
            )  # fmt: skip

        def ajouter() -> None:
            _ajouterGeometrie(cle)
            relance()

        s.bouton("Ajouter à la chaîne", ajouter)

    section = z.section(rendu)


def _supprimer() -> None:
    """Supprime le maillon sélectionné, sauf s'il est le dernier."""
    maillons = state.probleme()["maillons"]
    if len(maillons) <= 1:
        state.v[CLE_MESSAGE] = "Suppression impossible : la chaîne garde au moins un maillon."
        return
    i = _selection(len(maillons))
    del maillons[i]
    _apresModification(min(i, len(maillons) - 1))


def _deplacer(pas: int) -> None:
    """Échange le maillon sélectionné avec son voisin (pas = −1 : monter, +1 : descendre)."""
    maillons = state.probleme()["maillons"]
    i = _selection(len(maillons))
    j = i + pas
    if 0 <= j < len(maillons):
        maillons[i], maillons[j] = maillons[j], maillons[i]
        _apresModification(j)


def editeurCondition(z: Zone, apres: Rappel) -> None:
    """Saisie de la cote condition : nom, Jmin, Jmax (avec la case « Pas de limite maxi »)."""
    c = state.probleme()["condition"]
    cleNom, cleMin, cleMax, cleSansMax = (P + f"condition.{k}" for k in ("nom", "jmin", "jmax", "sansMax"))

    def maj() -> None:
        c = state.probleme()["condition"]
        c["nom"] = state.v[cleNom]
        c["jmin"] = state.v[cleMin]
        c["jmax"] = None if state.v[cleSansMax] else state.v[cleMax]
        apres()

    def rendu(s: Zone) -> None:
        def sansMaxChange() -> None:
            section.rafraichir()
            maj()

        s.saisie("Nom de la cote condition", cleNom, c.get("nom") or "Jeu J", apres=maj)
        gauche, droite = s.colonnes(2)
        jmin = gauche.nombre("Jmin (mm)", cleMin, None if _vide(c.get("jmin")) else float(c["jmin"]), decimales=4,
                             vide=True, apres=maj, aide="Jeu minimal exigé. Vide : pas de limite mini.")  # fmt: skip
        sansMax = bool(state.v.get(cleSansMax, _vide(c.get("jmax"))))
        defautMax = c.get("jmax") if not _vide(c.get("jmax")) else (jmin or 0.0)
        droite.nombre("Jmax (mm)", cleMax, float(defautMax), decimales=4, apres=maj, actif=not sansMax,
                      aide="Jeu maximal exigé.")  # fmt: skip
        droite.case("Pas de limite maxi", cleSansMax, sansMax, apres=sansMaxChange)

    section = z.section(rendu)


def _libelleK(k: int) -> str:
    return f"± {fr(k, 'g')} σ (Cp = {fr(k / 3, '.3g')})"


def editeurReglages(z: Zone, apres: Rappel, relance: Rappel) -> None:
    """Saisie des réglages : procédé garanti k (Cp = k / 3), T de référence, mode thermique, T de service, décentrage."""
    r = state.probleme()["reglages"]
    k = r.get("kSigma", 3)
    # la valeur d'un fichier ouvert (ex. k = 2) reste proposée : sinon la liste la remplacerait par 3
    choix = sorted(set(PROCEDES_K) | {k})
    cles = {c: P + f"reglages.{c}" for c in ("k", "tref", "modeT", "tservice", "decentrage", "tolGenerale")}

    def maj() -> None:
        r = state.probleme()["reglages"]
        r["kSigma"] = state.v[cles["k"]]
        r["tref"] = state.v[cles["tref"]]
        r["tservice"] = state.v[cles["tservice"]]
        dec = state.v[cles["decentrage"]]
        if dec or "decentrage" in r:  # le champ reste absent tant qu'il vaut 0 : le problème garde sa forme d'origine
            r["decentrage"] = dec
        classe = state.v[cles["tolGenerale"]]
        if classe or "tolGenerale" in r:
            r["tolGenerale"] = classe
        apres()

    def modeChange() -> None:
        state.probleme()["reglages"]["modeT"] = state.v[cles["modeT"]]
        relance()  # la colonne « T service » apparaît ou disparaît

    z.liste("Procédé garanti", choix, cles["k"], format=_libelleK, defaut=k, apres=maj,
            aide="Le procédé tient l'IT de chaque cote à ± k σ (loi normale) : IT = 2 k σ et Cp = k / 3.")  # fmt: skip
    gauche, droite = z.colonnes(2)
    tref = gauche.nombre("T référence (°C)", cles["tref"], float(r.get("tref", 20.0)), mini=ZERO_ABSOLU_C, decimales=1,
                         apres=maj, aide="Température à laquelle les cotes sont définies.")  # fmt: skip
    modes = list(MODES_T)
    mode = z.radio(
        "Température de service", modes, cles["modeT"], format=LIBELLES_MODE_T.get,
        defaut=r.get("modeT") if r.get("modeT") in modes else modes[0], apres=modeChange,
        aide="Uniforme : une seule température pour toutes les pièces. Par cote : colonne « T service » du tableau.",
    )  # fmt: skip
    tserv = r.get("tservice")
    droite.nombre("T service (°C)", cles["tservice"], float(tref if _vide(tserv) else tserv), mini=ZERO_ABSOLU_C,
                  decimales=1, apres=maj, actif=mode != "par_cote",
                  aide="Température de toutes les pièces en service (mode uniforme).")  # fmt: skip
    gauche.nombre(
        "Décentrage du procédé (σ)", cles["decentrage"], float(r.get("decentrage") or 0.0), mini=0.0, decimales=2,
        apres=maj,
        aide="Décalage de la moyenne du jeu vers la limite la plus proche, en multiples de σ du jeu. "
        "0 : procédé centré (comme l'application MATLAB). Agit sur Cpk, les ppm et le Monte-Carlo.",
    )  # fmt: skip
    classes = ["", *iso2768.CLASSES]
    droite.liste(
        "Tolérance générale (ISO 2768)", classes, cles["tolGenerale"], format=LIBELLES_TOL_GENERALE.get,
        defaut=r.get("tolGenerale") if r.get("tolGenerale") in classes else "", apres=maj,
        aide="Les maillons dont ES et EI sont laissés vides reçoivent l'écart ± de cette classe (ISO 2768-1) selon "
        "leur cote : le plan indique alors « tolérances générales ISO 2768-m », sans écart sur la cote.",
    )  # fmt: skip


def editeurCartouche(z: Zone) -> None:
    """Cartouche du dossier : projet, repère, indice, statut, auteur, vérificateur, remarque, révisions.

    Le bloc est enregistré avec le problème et repris par les dossiers HTML, PDF et Word.
    """
    p = state.probleme()
    c = p.get("cartouche") if isinstance(p.get("cartouche"), dict) else {}
    cleLignes = P + "cartouche.revisions.lignes"
    if cleLignes not in state.v:
        state.v[cleLignes] = [dict(r) for r in c.get("revisions") or []]

    def maj() -> None:
        p = state.probleme()
        saisie: dict = {cle: str(state.v.get(f"{P}cartouche.{cle}") or "").strip() or None for cle, _ in CHAMPS}
        lignes = [{k: str(r.get(k) or "").strip() for k, _ in REVISIONS} for r in state.v[cleLignes]]
        saisie["revisions"] = [r for r in lignes if any(r.values())][:MAX_REVISIONS]
        avant = p.get("cartouche") if isinstance(p.get("cartouche"), dict) else {}
        if saisie.get("statut") == "Validé":  # validation : l'empreinte du problème est enregistrée, et gardée ensuite
            deja = avant.get("statut") == "Validé" and avant.get("empreinte")
            saisie["empreinte"] = avant["empreinte"] if deja else empreinte(p)
        if any(saisie.values()) or "cartouche" in p:
            p["cartouche"] = {k: v for k, v in saisie.items() if v}  # le bloc reste absent tant que rien n'est saisi

    colonnes = z.colonnes(2)
    for i, (cle, libelle) in enumerate(CHAMPS):
        zone = colonnes[i % 2]
        if cle == "statut":
            options = ["", *STATUTS]
            actuel = c.get(cle) if c.get(cle) in options else ""
            zone.liste(libelle, options, f"{P}cartouche.{cle}", defaut=actuel, apres=maj)
        else:
            zone.saisie(libelle, f"{P}cartouche.{cle}", str(c.get(cle) or ""), apres=maj, longueur=MAX_TEXTE)

    def changeLigne(i: int, cle: str, v: Any) -> None:
        state.v[cleLignes][i][cle] = v or ""
        maj()

    z.legende("Historique des révisions")
    table = TableauEditable([Colonne(k, t) for k, t in REVISIONS], changeLigne)
    table.charger(state.v[cleLignes])
    z._ajouter(table)

    def plus() -> None:
        state.v[cleLignes].append({})
        table.charger(state.v[cleLignes])

    def moins() -> None:
        if state.v[cleLignes]:
            state.v[cleLignes].pop(max(table.currentRow(), 0) if table.currentRow() >= 0 else -1)
            table.charger(state.v[cleLignes])
            maj()

    g, d = z.colonnes(2)
    g.bouton("Ajouter une révision", plus)
    d.bouton("Retirer la révision sélectionnée", moins)


def optionsIso(maillons: list[dict]) -> list[str]:
    """Désignations ISO 286 proposées dans la liste : position et qualité (H7, g6…), plus celles déjà saisies.

    Entrée : maillons (liste de dict du problème). Sortie : liste de textes, sans doublon, alésages puis arbres.
    """
    ajout = [f"{lettre}{q}" for lettre in LETTRES_ALESAGE + LETTRES_ARBRE for q in QUALITES]
    saisies = [str(m["iso"]).strip() for m in maillons if not _vide(m.get("iso"))]
    return list(dict.fromkeys(ajout + saisies))


def colonnesMaillons(maillons: list[dict]) -> dict[str, Colonne]:
    """Colonnes du tableau des maillons (libellés, listes, formats)."""
    return {
        "nom": Colonne("nom", "Nom"),
        "sens": Colonne("sens", "Sens", "liste", ["+", MOINS], aide="+ : s'ajoute au jeu ; − : se retranche du jeu."),
        "cote": Colonne("cote", "Cote (mm)", "nombre", fmt="%.3f", mini=0.0),
        "iso": Colonne(
            "iso", "ISO 286", "liste", optionsIso(maillons), libre=True,
            aide="Position et qualité, ex. H7 (alésage) ou g6 (arbre). Vide : ES et EI saisis, prioritaires.",
        ),  # fmt: skip
        "es": Colonne("es", "ES (mm)", "nombre", fmt="%.4f", aide="Écart supérieur (celui de la norme si ISO saisi)."),
        "ei": Colonne("ei", "EI (mm)", "nombre", fmt="%.4f", aide="Écart inférieur (celui de la norme si ISO saisi)."),
        "loi": Colonne(
            "loi", "Loi", "liste", list(LOIS),
            aide="Loi de la cote dans la tolérance. Normale : cas courant (IT = 2 k σ). Uniforme : toutes les valeurs "
            "de l'IT également probables (σ = IT / (2√3)). Triangulaire : valeurs proches du centre plus probables "
            "(σ = IT / (2√6)).",
        ),  # fmt: skip
        "derive": Colonne(
            "derive", "Dérive (µm / 1000 pièces)", "nombre", fmt="%.2f",
            aide="Glissement de la cote moyenne avec l'usure de l'outil, en µm par millier de pièces (signé). "
            "Vide ou 0 : pas de dérive. Sert à l'onglet « Dérive et réglage » ; le calcul principal l'ignore.",
        ),  # fmt: skip
        "facteur": Colonne(
            "facteur", "Facteur", "nombre", fmt="%.4g", mini=0.0,
            aide="Rapport de levier ou de transmission (> 0) : aᵢ = facteur · cos θ. Vide : 1.",
        ),  # fmt: skip
        "angle": Colonne(
            "angle", "Angle (°)", "nombre", fmt="%.2f",
            aide="Angle de la cote avec l'axe de la chaîne : aᵢ = facteur · cos θ (θ = 0° sens +, 180° sens −, plus "
            "cet angle). Vide : 0°, cote portée par l'axe.",
        ),  # fmt: skip
        "sigma_reel": Colonne(
            "sigma_reel", "σ mesuré (mm)", "nombre", fmt="%.5f", mini=0.0,
            aide="Écart type mesuré à l'atelier sur cette cote (loi normale). Vide : σ déduit de l'IT et de la loi.",
        ),  # fmt: skip
        "moyenne_reelle": Colonne(
            "moyenne_reelle", "Moyenne mesurée (mm)", "nombre", fmt="%.4f",
            aide="Moyenne mesurée de la cote produite. Vide : centrée sur la cote moyenne de la tolérance.",
        ),  # fmt: skip
        "materiau": Colonne("materiau", "Matériau", "liste", nomsMateriaux(), aide="Vide : pas de dilatation."),
        "alpha": Colonne("alpha", "α (1e-6/K)", "nombre", fmt="%.2f", aide="Vide : α du matériau."),
        "tservice": Colonne("tservice", "T service (°C)", "nombre", fmt="%.1f", aide="Mode « par cote » seulement."),
    }


def decomposerIso(iso: Any) -> tuple[str, str, int] | None:
    """Désignation « 40 h7 » ou « H7 » décomposée en (pièce, position, qualité), ou None si elle est illisible."""
    trouve = _LETTRE_QUALITE.search("" if _vide(iso) else str(iso))
    if not trouve or int(trouve[2]) not in QUALITES:
        return None
    lettre = trouve[1]
    if lettre in LETTRES_ALESAGE:
        return "Alésage", lettre, int(trouve[2])
    if lettre in LETTRES_ARBRE:
        return "Arbre", lettre, int(trouve[2])
    return None


def _panneauTolerance(z: Zone, i: int, m: dict, tout: Rappel) -> None:
    """Tolérance du maillon sélectionné : personnalisée (IT et position) ou normalisée par listes (H7, g6…)."""
    cle = f"{P}tol.{_version()}.{i}."  # nouvelle clé à chaque modification : les listes repartent du problème
    decomp = decomposerIso(m.get("iso"))

    def appliquerIso() -> None:
        m["iso"] = f"{state.v[cle + 'lettre']}{state.v[cle + 'qualite']}"
        _apresModification(i)
        tout()

    def appliquerPerso() -> None:
        it = float(state.v[cle + "it"]) / 1000
        ecarts = {POSITIONS_PERSO[0]: (it / 2, -it / 2), POSITIONS_PERSO[1]: (it, 0.0), POSITIONS_PERSO[2]: (0.0, -it)}
        es, ei = ecarts[state.v[cle + "position"]]
        m.update(iso=None, es=es, ei=ei)
        _apresModification(i)
        tout()

    def rendu(s: Zone) -> None:
        mode = s.radio(
            "Tolérance du maillon sélectionné", [MODE_ISO, MODE_PERSO], cle + "mode",
            defaut=MODE_ISO if decomp else MODE_PERSO, apres=lambda: section.rafraichir(),
            aide="Normalisée : choisissez la position et la qualité dans les listes (ex. H7 pour un alésage, g6 pour "
            "un arbre), les écarts viennent de l'ISO 286. Personnalisée : donnez l'IT et la position de la zone.",
        )  # fmt: skip
        if mode == MODE_ISO:
            piece, lettre, qualite = decomp or ("Alésage", "H", 7)
            c = s.colonnes(3)
            choixPiece = c[0].liste("Pièce", ["Alésage", "Arbre"], cle + "piece", defaut=piece,
                                    apres=lambda: section.rafraichir())  # fmt: skip
            lettres = LETTRES_ALESAGE if choixPiece == "Alésage" else LETTRES_ARBRE
            if lettre not in lettres:  # pièce changée : position équivalente (H ↔ h)
                lettre = lettre.upper() if choixPiece == "Alésage" else lettre.lower()
            if state.v.get(cle + "lettre") not in lettres:
                state.v[cle + "lettre"] = lettre
            c[1].liste("Position", lettres, cle + "lettre", defaut=lettre, apres=appliquerIso)
            c[2].liste("Qualité IT", QUALITES, cle + "qualite", format=lambda q: f"IT{q}", defaut=qualite,
                       apres=appliquerIso)  # fmt: skip
            if decomp is None:
                s.legende("Choisissez une position ou une qualité pour appliquer une tolérance normalisée à ce maillon.")
        else:
            es, ei = _ecartsAffiches(m)[:2]
            itActuel = 0.0 if _vide(es) or _vide(ei) else round((float(es) - float(ei)) * 1000, 3)
            c = s.colonnes(2)
            c[0].nombre("IT (µm)", cle + "it", itActuel, mini=0.0, apres=appliquerPerso)
            c[1].liste("Position de la zone", POSITIONS_PERSO, cle + "position", apres=appliquerPerso,
                       aide="Écarts quelconques : ES et EI dans le tableau.")  # fmt: skip

    section = z.section(rendu)


def editeurMaillons(z: Zone, apres: Rappel) -> None:
    """Tableau éditable des maillons, boutons Ajouter / Supprimer / Monter / Descendre, messages de l'aperçu."""

    def tout() -> None:
        section.rafraichir()
        apres()

    def rendu(s: Zone) -> None:
        p = state.probleme()
        maillons = p["maillons"]
        utilisees = any(
            not _vide(m.get(c)) and m.get(c) != d for m in maillons for c, d in (("facteur", 1), ("angle", 0))
        )
        def decocher(cle: str, colonnes: tuple) -> Rappel:
            """Case décochée : les valeurs cachées reviennent aux défauts, sinon elles resteraient dans le calcul."""

            def faire() -> None:
                if not state.v.get(cle):
                    for m in state.probleme()["maillons"]:
                        for c in colonnes:
                            m.pop(c, None)
                    state.v[CLE_VERSION] = _version() + 1
                section.rafraichir()
                apres()

            return faire

        projection = s.case(
            "Coefficients de projection (levier, angle)", P + "projection", utilisees,
            apres=decocher(P + "projection", COLONNES_PROJECTION),
            aide="Ajoute les colonnes Facteur et Angle : aᵢ = facteur · cos θ au lieu de ±1 (levier, cote inclinée).",
        )  # fmt: skip
        atelier = s.case(
            "Mesures de l'atelier (σ et moyenne mesurés)", P + "atelier",
            any(not _vide(m.get(c)) for m in maillons for c in COLONNES_ATELIER),
            apres=decocher(P + "atelier", COLONNES_ATELIER),
            aide="Ajoute les colonnes σ mesuré et Moyenne mesurée : le calcul utilise la capabilité réelle du procédé "
            "à la place de celle déduite de l'IT. Les problèmes inverse et d'optimisation ne s'en servent pas.",
        )  # fmt: skip
        colonnes = colonnesMaillons(maillons)
        if p.get("reglages", {}).get("modeT") != "par_cote":
            del colonnes["tservice"]
        if not projection:
            colonnes = {k: c for k, c in colonnes.items() if k not in COLONNES_PROJECTION}
        if not atelier:
            colonnes = {k: c for k, c in colonnes.items() if k not in COLONNES_ATELIER}

        def surChange(i: int, col: str, v: Any) -> None:
            if col == "cote" and v is None:  # une cote est obligatoire : la case reprend sa valeur
                table.charger(lignesTableau(state.probleme()["maillons"])[0])
                return
            modifierCase(state.probleme()["maillons"][i], col, v)
            table.charger(lignesTableau(state.probleme()["maillons"])[0])
            state.v[CLE_VERSION] = _version() + 1
            bas.rafraichir()
            apres()

        def surSelection(i: int) -> None:
            state.v[CLE_SELECTION] = i
            bas.rafraichir()

        table = TableauEditable(list(colonnes.values()), surChange, surSelection)
        table.charger(lignesTableau(maillons)[0])
        n = len(maillons)
        state.v[CLE_SELECTION] = _selection(n)
        table.setCurrentCell(state.v[CLE_SELECTION], 0)
        s._ajouter(table)

        def rendreBas(b: Zone) -> None:
            maillons = state.probleme()["maillons"]
            n = len(maillons)
            i = _selection(n)
            b.legende(f"Maillon sélectionné (cliquez une ligne du tableau) : {i + 1}. {maillons[i].get('nom', '')}")
            c = b.colonnes(4)

            def geste(action: Callable[[], None]) -> Callable[[], None]:
                def faire() -> None:
                    action()
                    tout()

                return faire

            c[0].bouton("Ajouter", geste(_ajouter))
            c[1].bouton("Supprimer", geste(_supprimer))
            c[2].bouton("Monter", geste(lambda: _deplacer(-1)), actif=i > 0)
            c[3].bouton("Descendre", geste(lambda: _deplacer(1)), actif=i < n - 1)
            _panneauTolerance(b, i, maillons[i], tout)
            if CLE_MESSAGE in state.v:
                b.avertissement(state.v.pop(CLE_MESSAGE))
            erreursIso = lignesTableau(maillons)[1]
            for e in erreursIso:
                b.erreur(e)
            apercu = apercuChaine(state.probleme())
            if "erreur" in apercu:
                if not erreursIso:  # sinon le même défaut serait signalé deux fois
                    b.erreur(apercu["erreur"])
            else:
                for a in apercu["avertissements"]:
                    b.avertissement(a)

        bas = s.section(rendreBas)

    section = z.section(rendu)


def curseursSensibilite(z: Zone, probleme: dict, colonnes: int, relance: Rappel) -> None:
    """Un curseur d'IT par maillon (centre gardé) ; jeu mini / maxi, ppm et verdict recalculés en direct.

    Le bouton « Appliquer au problème » recopie les nouveaux ES / EI dans le problème.
    """
    base = apercuChaine(probleme)
    if "erreur" in base:
        z.info("Curseurs indisponibles tant que la saisie contient une erreur.")
        return
    res = base["res"]
    lignes = [(i, n, float(it), float(es + ei) / 2)
              for i, (n, it, es, ei) in enumerate(zip(res["Nom"], res["IT"], res["ES"], res["EI"], strict=True))]  # fmt: skip

    def cleDe(i: int, it: float) -> str:
        return f"{P}curseur.{i}.{it:.9g}"

    def modifies() -> dict:
        m = {}
        for i, _nom, it, centre in lignes:
            v = state.v.get(cleDe(i, it), it)
            if not math.isclose(v, it, rel_tol=1e-9, abs_tol=1e-12):
                m[i] = (centre + v / 2, centre - v / 2)
        return m

    def appliquer() -> None:
        for i, (es, ei) in modifies().items():
            probleme["maillons"][i].update(iso=None, es=es, ei=ei)
        state.definirProbleme(probleme)
        relance()

    def rendreBilan(s: Zone) -> None:
        copie = copy.deepcopy(probleme)
        change = modifies()
        for i, (es, ei) in change.items():
            copie["maillons"][i].update(iso=None, es=es, ei=ei)
        apercu = apercuChaine(copie)
        if "erreur" in apercu:
            s.erreur(apercu["erreur"])
            return
        v, c = apercu["verdicts"], apercu["res"]["condition"]
        verdict = libelleVerdict(v["pireCas"]["ok"], c)
        ppm = v["ppm"]
        s.metriques(
            [
                ("Jeu mini", f"{fr(v['pireCas']['min'])} mm", "Au pire des cas."),
                ("Jeu maxi", f"{fr(v['pireCas']['max'])} mm", "Au pire des cas."),
                (
                    "Hors tolérance",
                    "—" if math.isnan(ppm) else f"{fr(ppm, '.3g')} ppm",
                    "Parties par million hors de [Jmin ; Jmax], jeu de loi normale (calcul statistique).",
                ),
                ("Verdict", verdict, "Jeu au pire des cas face à [Jmin ; Jmax]."),
            ],
            colonnes,
        )
        s.bouton("Appliquer au problème", appliquer, actif=bool(change),
                 aide="Remplace ES et EI des maillons modifiés (la désignation ISO de ces maillons est effacée).")  # fmt: skip

    for i, nom, it, _centre in lignes:
        haut = 4 * it if it > 0 else ETENDUE_IT_NUL
        z.curseur(
            f"IT {nom} (mm)", cleDe(i, it), it, 0.0, haut, haut / 200, fmt="%.4f",
            continu=lambda: bilan.rafraichir(),
            aide="Intervalle de tolérance de ce maillon ; le centre de la tolérance reste en place.",
        )  # fmt: skip
    bilan = z.section(rendreBilan)

