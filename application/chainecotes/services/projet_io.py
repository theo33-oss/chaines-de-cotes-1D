"""Fichiers du site : problème enregistré en JSON, résultats exportés en xlsx et en csv.

Inspiré de mecastruct/services/project_io.py : JSON lisible (pas de pickle), signé par l'application et
numéroté par version ; l'ouverture refuse tout fichier dont la forme ou les types ne sont pas ceux attendus.
"""

import io
import json
import math
from typing import TYPE_CHECKING

import numpy as np

from chainecotes.core.chaine import LOIS, MODES_T, SENS
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.geometrie import TYPES as TYPES_GEOMETRIE
from chainecotes.services.cartouche import CHAMPS, MAX_REVISIONS, REVISIONS, STATUTS

if TYPE_CHECKING:  # pandas ne se charge que pour les exports tableur : la page web n'en a pas besoin pour enregistrer
    import pandas as pd

APPLICATION = "chaines-de-cotes-1d"
VERSION = 1
MAX_MAILLONS = 200
MAX_TEXTE = 200
_ID = "Chaine:Fichier:invalide"

# Champs de chaque bloc : nom → (genre attendu, None permis). Genres : « texte », « nombre », ou un tuple
# de valeurs permises. Un champ absent est permis (le calcul prend sa valeur par défaut), sauf ceux de _REQUIS.
_CONDITION = {"nom": ("texte", True), "jmin": ("nombre", True), "jmax": ("nombre", True)}
_REGLAGES = {"kSigma": ("nombre", False), "tref": ("nombre", False), "modeT": (MODES_T, False),
             "tservice": ("nombre", True), "decentrage": ("nombre", True),
             "tolGenerale": (("", "f", "m", "c", "v"), True)}  # fmt: skip
_MAILLON = {
    "nom": ("texte", True),
    "sens": (SENS, False),
    "cote": ("nombre", False),
    "iso": ("texte", True),
    "es": ("nombre", True),
    "ei": ("nombre", True),
    "loi": (LOIS, False),
    "materiau": ("texte", True),
    "alpha": ("nombre", True),
    "tservice": ("nombre", True),
    "derive": ("nombre", True),
    "facteur": ("nombre", True),
    "angle": ("nombre", True),
    "sigma_reel": ("nombre", True),
    "moyenne_reelle": ("nombre", True),
    "geometrie": (tuple(TYPES_GEOMETRIE), True),
    "image": ("texte", True),  # silhouette de la pièce sur le schéma de la page web ; sans effet sur le calcul
}
_REQUIS_MAILLON = ("sens", "cote")
_CARTOUCHE = {cle: ((*STATUTS, ""), True) if cle == "statut" else ("texte", True) for cle, _ in CHAMPS}
_CARTOUCHE["empreinte"] = ("texte", True)  # posée à la validation (services/cartouche.empreinte)
_REVISION = {cle: ("texte", True) for cle, _ in REVISIONS}
_REVISION_ETUDE = {cle: ("texte", True) for cle in ("indice", "date", "auteur", "objet")}
MAX_REVISIONS_ETUDE = 30


def _erreur(message: str) -> ErreurChaine:
    return ErreurChaine(_ID, f"Fichier non reconnu : {message}")


def _propre(v):
    """Valeur enregistrable en JSON strict : NumPy en types Python, case vide (NaN) en None."""
    if isinstance(v, dict):
        return {str(k): _propre(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, np.ndarray)):
        return [_propre(x) for x in v]
    if isinstance(v, np.generic):
        v = v.item()
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def exporterProbleme(probleme: dict) -> str:
    """Texte JSON d'un problème, à enregistrer dans un fichier .json.

    Entrée : probleme (dict condition, reglages, maillons ; cotes en mm, températures en °C, α en 1e-6/K).
    Sortie : texte JSON indenté {"application", "version", "probleme"} ; les cases vides (NaN) deviennent null.
    """
    enveloppe = {"application": APPLICATION, "version": VERSION, "probleme": _propre(probleme)}
    return json.dumps(enveloppe, ensure_ascii=False, indent=2, allow_nan=False)


def _controleChamp(valeur, genre, videPermis: bool, ou: str) -> None:
    """Refuse une valeur dont le genre n'est pas celui du format (ErreurChaine)."""
    if valeur is None:
        if not videPermis:
            raise _erreur(f"{ou} ne peut pas être vide.")
        return
    if genre == "nombre":
        if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
            raise _erreur(f"{ou} doit être un nombre (reçu {valeur!r}).")
        if not math.isfinite(valeur):
            raise _erreur(f"{ou} doit être un nombre fini (reçu {valeur!r}).")
    elif genre == "texte":
        if not isinstance(valeur, str):
            raise _erreur(f"{ou} doit être un texte (reçu {valeur!r}).")
        if len(valeur) > MAX_TEXTE:
            raise _erreur(f"{ou} est trop long ({len(valeur)} caractères, {MAX_TEXTE} au plus).")
    elif valeur not in genre:
        permis = ", ".join(f"« {x} »" for x in genre)
        raise _erreur(f"{ou} vaut {valeur!r} ; valeurs permises : {permis}.")


def _controleBloc(bloc, champs: dict, ou: str, requis=()) -> None:
    """Contrôle un dict du problème : champs connus, genres, champs obligatoires présents."""
    if not isinstance(bloc, dict):
        raise _erreur(f"{ou} doit être un dictionnaire.")
    for cle in bloc:
        if cle not in champs:
            raise _erreur(f"champ inconnu « {cle} » dans {ou}.")
    for cle in requis:
        if cle not in bloc:
            raise _erreur(f"champ « {cle} » absent dans {ou}.")
    for cle, valeur in bloc.items():
        genre, videPermis = champs[cle]
        if ou.startswith("le "):
            de = "du " + ou[3:]
        elif ou.startswith("les "):
            de = "des " + ou[4:]
        else:
            de = "de " + ou
        _controleChamp(valeur, genre, videPermis, f"le champ « {cle} » {de}")


def _controleCartouche(c) -> None:
    """Contrôle le bloc facultatif « cartouche » : champs de texte, statut connu, historique des révisions."""
    if not isinstance(c, dict):
        raise _erreur("le cartouche doit être un dictionnaire.")
    _controleBloc({k: v for k, v in c.items() if k != "revisions"}, _CARTOUCHE, "le cartouche")
    revisions = c.get("revisions")
    if revisions is None:
        return
    if not isinstance(revisions, list):
        raise _erreur("les révisions du cartouche doivent former une liste.")
    if len(revisions) > MAX_REVISIONS:
        raise _erreur(f"trop de révisions ({len(revisions)}, {MAX_REVISIONS} au plus).")
    for i, r in enumerate(revisions):
        _controleBloc(r, _REVISION, f"la révision {i + 1}")


def _controleProbleme(p, ou: str = "le problème") -> None:
    """Contrôle la forme d'un problème : blocs, champs connus, genres, nombre de maillons (ErreurChaine sinon)."""
    if not isinstance(p, dict):
        raise _erreur(f"{ou} est absent ou n'est pas un dictionnaire.")
    for cle in p:
        if cle not in ("condition", "reglages", "maillons", "cartouche"):
            raise _erreur(f"clé inconnue « {cle} » dans {ou}.")
    for cle in ("condition", "reglages", "maillons"):
        if cle not in p:
            raise _erreur(f"le bloc « {cle} » est absent de {ou}.")
    _controleBloc(p["condition"], _CONDITION, "la cote condition")
    _controleBloc(p["reglages"], _REGLAGES, "les réglages")
    if "cartouche" in p:
        _controleCartouche(p["cartouche"])
    dec = p["reglages"].get("decentrage")
    if dec is not None and dec < 0:
        raise _erreur(f"le champ « decentrage » des réglages doit être positif ou nul (reçu {dec!r}).")
    maillons = p["maillons"]
    if not isinstance(maillons, list):
        raise _erreur("le bloc « maillons » doit être une liste.")
    if not maillons:
        raise _erreur("la chaîne n'a aucun maillon : il en faut au moins un.")
    if len(maillons) > MAX_MAILLONS:
        raise _erreur(f"trop de maillons ({len(maillons)}, {MAX_MAILLONS} au plus).")
    for i, m in enumerate(maillons):
        _controleBloc(m, _MAILLON, f"le maillon {i + 1}", _REQUIS_MAILLON)


def exporterProjet(probleme: dict, revisions: list[dict] | None = None) -> str:
    """Texte JSON d'une étude : le problème courant et l'historique de ses révisions.

    Entrées : probleme (dict condition, reglages, maillons), revisions (liste de dict indice, date, auteur, objet,
    probleme : voir services/revisions). Sortie : texte JSON ; sans révision, identique à exporterProbleme.
    """
    enveloppe = {"application": APPLICATION, "version": VERSION, "probleme": _propre(probleme)}
    if revisions:
        enveloppe["revisions"] = _propre(revisions)
    return json.dumps(enveloppe, ensure_ascii=False, indent=2, allow_nan=False)


def importerProjet(texte: str) -> dict:
    """Relit une étude enregistrée par exporterProjet (ou un simple problème) et contrôle sa forme.

    Entrée : texte du fichier JSON.
    Sortie : dict probleme (dict condition, reglages, maillons et, s'il a été saisi, cartouche) et revisions (liste de
    dict indice, date, auteur, objet (textes) et probleme ; vide si le fichier n'en a pas).
    Erreur : ErreurChaine avec un message clair si le JSON est illisible, vient d'une autre application ou
    d'une version future, contient une clé inconnue, un bloc absent ou mal typé, plus de 200 maillons, un nombre
    non fini, un décentrage négatif, un sens, une loi (normale, uniforme, triangulaire) ou un mode de
    température invalide, un texte de plus de 200 caractères, ou plus de MAX_REVISIONS_ETUDE révisions.
    La cohérence du calcul (fermeture, ISO, écarts) n'est pas contrôlée ici : elle l'est au calcul.
    """
    try:
        d = json.loads(texte)
    except (TypeError, ValueError) as err:
        raise _erreur(f"ce n'est pas un fichier JSON lisible ({err}).") from err
    if not isinstance(d, dict) or d.get("application") != APPLICATION:
        raise _erreur("ce fichier n'a pas été enregistré par l'application Chaînes de cotes 1D.")
    version = d.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise _erreur("numéro de version absent ou invalide.")
    if version > VERSION:
        raise _erreur(
            f"ce fichier vient d'une version plus récente de l'application (format {version}, "
            f"celle-ci lit jusqu'au format {VERSION})."
        )
    inconnues = [k for k in d if k not in ("application", "version", "probleme", "revisions")]
    if inconnues:
        raise _erreur(f"clé inconnue « {inconnues[0]} » au premier niveau du fichier.")
    p = d.get("probleme")
    _controleProbleme(p, "le bloc « probleme »")
    revisions = d.get("revisions") or []
    if not isinstance(revisions, list):
        raise _erreur("le bloc « revisions » doit être une liste.")
    if len(revisions) > MAX_REVISIONS_ETUDE:
        raise _erreur(f"trop de révisions ({len(revisions)}, {MAX_REVISIONS_ETUDE} au plus).")
    for i, r in enumerate(revisions, start=1):
        if not isinstance(r, dict):
            raise _erreur(f"la révision {i} doit être un dictionnaire.")
        _controleBloc({k: v for k, v in r.items() if k != "probleme"}, _REVISION_ETUDE, f"la révision {i}")
        _controleProbleme(r.get("probleme"), f"le problème de la révision {i}")
    return {"probleme": p, "revisions": revisions}


def importerProbleme(texte: str) -> dict:
    """Relit un problème enregistré par exporterProbleme (les révisions éventuelles sont ignorées) et le contrôle.

    Entrée : texte du fichier JSON. Sortie : probleme (dict condition, reglages, maillons et, s'il a été saisi,
    cartouche), tel qu'il a été enregistré. Erreur : ErreurChaine, voir importerProjet.
    """
    return importerProjet(texte)["probleme"]


def _fini(x):
    """Nombre fini en float, sinon None (case vide dans le tableur)."""
    x = float(x)
    return x if math.isfinite(x) else None


def _oui(ok: bool) -> str:
    return "conforme" if ok else "non conforme"


def _tableaux(bundle: dict) -> "dict[str, pd.DataFrame]":
    """Tableaux de résultats d'un calcul : Synthèse, Maillons, Contributions, Monte-Carlo."""
    import pandas as pd

    res, v, mc = bundle["res"], bundle["verdicts"], bundle["mc"]
    c = res["condition"]
    synthese = [
        ("Cote condition", c["nom"], ""),
        ("Limite basse Jmin", _fini(c["jmin"]), "mm"),
        ("Limite haute Jmax", _fini(c["jmax"]), "mm"),
        ("Jeu nominal", res["CF_nom"], "mm"),
        ("Jeu moyen", res["CF_moy"], "mm"),
        ("Jeu mini au pire des cas", v["pireCas"]["min"], "mm"),
        ("Jeu maxi au pire des cas", v["pireCas"]["max"], "mm"),
        ("Verdict au pire des cas", _oui(v["pireCas"]["ok"]), ""),
        ("Écart-type du jeu σJ", res["CF_sigma"], "mm"),
        ("Procédé garanti k", res["k_sigma"], "σ"),
        ("Jeu mini statistique (moyenne − kσ)", v["rssK"]["min"], "mm"),
        ("Jeu maxi statistique (moyenne + kσ)", v["rssK"]["max"], "mm"),
        ("Verdict statistique ± kσ", _oui(v["rssK"]["ok"]), ""),
        *(
            [("Décentrage du procédé", res["decentrage"], "σ"), ("Décalage de la moyenne", res["decalage"], "mm")]
            if res["decentrage"] > 0
            else []
        ),  # fmt: skip
        ("Cp", _fini(v["cp"]), ""),
        ("Cpk", _fini(v["cpk"]), ""),
        ("Hors tolérance (loi normale)", _fini(v["ppm"]), "ppm"),
        ("Température de référence", res["Tref"], "°C"),
        ("Décalage thermique du jeu moyen", res["dJ_th"], "mm"),
    ]
    maillons = pd.DataFrame(
        {
            "Maillon": res["Nom"],
            "Sens": [m["sens"] for m in res["maillons"]],
            "Cote nominale (mm)": res["Cote"],
            "ISO 286": [m["iso"] for m in res["maillons"]],
            "Écart supérieur ES (mm)": res["ES"],
            "Écart inférieur EI (mm)": res["EI"],
            "Intervalle de tolérance IT (mm)": res["IT"],
            "Cote moyenne (mm)": res["C_moy"],
            "Loi": res["loi"],
            "cos θ": res["proj"],
            "Coefficient a_i en service": res["coef"],
            "Écart-type σ_i (mm)": res["sigma_i"],
            "α (1e-6/K)": np.asarray(res["alpha"]) * 1e6,
            "Température de service (°C)": res["Tservice"],
            "ΔT (K)": res["dT"],
            "Décalage thermique ΔJ_i (mm)": res["dJ_th_i"],
        }
    )
    contrib = pd.DataFrame(
        [
            {
                "Maillon": x["nom"],
                "Pire des cas |a_i|·IT_i/2 (mm)": x["pireCas"],
                "Part au pire des cas (%)": x["partPireCas"],
                "Variance σ_i² (mm²)": x["variance"],
                "Part de la variance (%)": x["partVariance"],
            }
            for x in bundle["contributions"]
        ]
    )
    if mc is None:
        lignes_mc = [("Monte-Carlo", "non calculé (aucune dispersion ou simulation désactivée)", "")]
    else:
        lignes_mc = [
            ("Nombre de tirages", mc["n"], ""),
            ("Graine", mc["graine"], ""),
            ("Jeu moyen simulé", mc["moyenne"], "mm"),
            ("Écart-type simulé", mc["ecartType"], "mm"),
            ("Tirages hors tolérance", mc["nHors"], ""),
            ("Hors tolérance simulé", _fini(mc["ppm"]), "ppm"),
            ("Hors tolérance par la formule (loi normale)", _fini(v["ppm"]), "ppm"),
            ("Résolution de la simulation", _fini(mc["resolutionPpm"]), "ppm"),
            ("Cp simulé", _fini(mc["cp"]), ""),
            ("Cpk simulé", _fini(mc["cpk"]), ""),
            ("Quantile 0,135 %", mc["quantiles"]["bas"], "mm"),
            ("Médiane", mc["quantiles"]["mediane"], "mm"),
            ("Quantile 99,865 %", mc["quantiles"]["haut"], "mm"),
        ]
    colonnes = ["Grandeur", "Valeur", "Unité"]
    return {
        "Synthèse": pd.DataFrame(synthese, columns=colonnes),
        "Maillons": maillons,
        "Contributions": contrib,
        "Monte-Carlo": pd.DataFrame(lignes_mc, columns=colonnes),
    }


def _neutre(v):
    """Texte que le tableur ne peut pas lire comme une formule : apostrophe devant = @ + - (sauf un nombre)."""
    if not isinstance(v, str) or not v:
        return v
    if v[0] in "=@\t\r":
        return "'" + v
    if v[0] in "+-" and len(v) > 1:
        try:
            float(v.replace(",", "."))
        except ValueError:
            return "'" + v
    return v


def exporterResultatsXlsx(bundle: dict) -> bytes:
    """Classeur Excel des résultats d'un calcul.

    Entrée : bundle (sortie de calculerChaine ; mc peut valoir None).
    Sortie : contenu du fichier .xlsx (onglets Synthèse, Maillons, Contributions, Monte-Carlo ; mm, °C, ppm).
    """
    import pandas as pd

    tampon = io.BytesIO()
    with pd.ExcelWriter(tampon, engine="openpyxl") as writer:
        for nom, t in _tableaux(bundle).items():
            t.map(_neutre).to_excel(writer, sheet_name=nom, index=False)
    return tampon.getvalue()


def _celluleCsv(v):
    """Cellule csv : nombre à virgule décimale, texte neutralisé, case vide pour None."""
    if isinstance(v, (bool, np.bool_)) or v is None:
        return v
    if isinstance(v, (float, np.floating)):
        return f"{float(v):.12g}".replace(".", ",")
    return _neutre(v)


def exporterResultatsCsv(bundle: dict) -> bytes:
    """Fichier csv des résultats d'un calcul, lisible par Excel en français.

    Entrée : bundle (sortie de calculerChaine ; mc peut valoir None).
    Sortie : contenu du fichier .csv (UTF-8 avec BOM, séparateur « ; », virgule décimale) : une ligne par
    maillon, une ligne vide, puis le bloc de synthèse (Grandeur ; Valeur ; Unité).
    """
    t = _tableaux(bundle)
    blocs = [
        t[nom].map(_celluleCsv).to_csv(sep=";", index=False, lineterminator="\r\n") for nom in ("Maillons", "Synthèse")
    ]
    return ("\r\n".join(blocs)).encode("utf-8-sig")
