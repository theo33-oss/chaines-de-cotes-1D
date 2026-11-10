"""Mécanisme : plusieurs chaînes de cotes (jeux fonctionnels) d'un même assemblage, enregistrées et calculées ensemble.

Format JSON versionné {"format": "mecanisme", "version": 1, "nom", "chaines": [problème, ...]}. Chaque chaîne est
un problème au format de projet_io (validé par importerProbleme). Un fichier de problème simple est promu en
mécanisme d'une chaîne.
"""

import copy
import io
import json
import math

import pandas as pd

from chainecotes.core.errors import ErreurChaine
from chainecotes.core.nombres import fr
from chainecotes.core.montecarlo import GRAINE_DEFAUT, N_DEFAUT
from chainecotes.services.calcul import calculerChaine
from chainecotes.services.projet_io import APPLICATION, exporterProbleme, importerProbleme

FORMAT = "mecanisme"
VERSION = 1
MAX_CHAINES = 50
TIRAGES_TOTAUX_MAX = 2_000_000  # tirages Monte-Carlo pour tout le mécanisme : borne le temps de calcul d'un clic
TIRAGES_PAR_CHAINE_MINI = 20_000
_ID = "Chaine:Mecanisme:invalide"


def _erreur(message: str) -> ErreurChaine:
    return ErreurChaine(_ID, f"Mécanisme non reconnu : {message}")


def _nomChaine(probleme: dict, i: int) -> str:
    """Nom d'une chaîne : nom de sa cote condition, sinon « Chaîne i » (i à partir de 1)."""
    nom = (probleme.get("condition") or {}).get("nom")
    return nom if isinstance(nom, str) and nom.strip() else f"Chaîne {i}"


def _validerChaine(probleme, i: int) -> dict:
    """Valide une chaîne avec importerProbleme ; l'erreur porte le numéro de la chaîne (à partir de 1)."""
    try:
        return importerProbleme(exporterProbleme(probleme))
    except ErreurChaine as e:
        raise ErreurChaine(_ID, f"Mécanisme non reconnu : chaîne {i} invalide. {e.message}") from e
    except (TypeError, ValueError, AttributeError) as e:
        raise _erreur(f"chaîne {i} illisible ({e}).") from e


def exporterMecanisme(mecanisme: dict) -> str:
    """Texte JSON d'un mécanisme, à enregistrer dans un fichier .json.

    Entrée : mecanisme (dict nom, chaines = liste de problèmes).
    Sortie : texte JSON indenté {"format", "version", "nom", "chaines"}.
    Erreur : ErreurChaine si la liste de chaînes est absente, vide ou trop longue, ou si une chaîne est invalide
    (le message donne son numéro).
    """
    chaines = mecanisme.get("chaines") if isinstance(mecanisme, dict) else None
    if not isinstance(chaines, list) or not chaines:
        raise _erreur("le mécanisme doit contenir au moins une chaîne.")
    if len(chaines) > MAX_CHAINES:
        raise _erreur(f"trop de chaînes ({len(chaines)}, {MAX_CHAINES} au plus).")
    valides = [_validerChaine(p, i + 1) for i, p in enumerate(chaines)]
    nom = mecanisme.get("nom") or ""
    if not isinstance(nom, str):
        raise _erreur("le nom du mécanisme doit être un texte.")
    return json.dumps(
        {"format": FORMAT, "version": VERSION, "nom": nom, "chaines": valides},
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )


def importerMecanisme(texte: str) -> dict:
    """Relit un mécanisme (ou un fichier de problème simple, promu en mécanisme d'une chaîne).

    Entrée : texte du fichier JSON.
    Sortie : dict nom, chaines (liste de problèmes validés).
    Erreur : ErreurChaine si le JSON est illisible, de format ou de version inconnus, sans chaîne, ou si une
    chaîne est invalide (le message donne le numéro de la chaîne fautive).
    """
    try:
        d = json.loads(texte)
    except (TypeError, ValueError) as err:
        raise _erreur(f"ce n'est pas un fichier JSON lisible ({err}).") from err
    if isinstance(d, dict) and d.get("application") == APPLICATION:
        p = importerProbleme(texte)
        return {"nom": _nomChaine(p, 1), "chaines": [p]}
    if not isinstance(d, dict) or d.get("format") != FORMAT:
        raise _erreur("ce fichier n'est ni un mécanisme ni un problème de l'application.")
    version = d.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise _erreur("numéro de version absent ou invalide.")
    if version > VERSION:
        raise _erreur(f"format {version} plus récent que celui lu par l'application (format {VERSION}).")
    nom = d.get("nom", "")
    if not isinstance(nom, str):
        raise _erreur("le nom du mécanisme doit être un texte.")
    chaines = d.get("chaines")
    if not isinstance(chaines, list) or not chaines:
        raise _erreur("le bloc « chaines » doit être une liste non vide.")
    if len(chaines) > MAX_CHAINES:
        raise _erreur(f"trop de chaînes ({len(chaines)}, {MAX_CHAINES} au plus).")
    return {"nom": nom, "chaines": [_validerChaine(p, i + 1) for i, p in enumerate(chaines)]}


def _fini(x):
    """Nombre fini en float, sinon None (Cp non défini, limite absente)."""
    return float(x) if x is not None and math.isfinite(float(x)) else None


def _verdict(v: dict) -> str:
    """Verdict global d'une chaîne : pire cas, sinon statistique ± kσ, sinon non conforme."""
    if v["pireCas"]["ok"]:
        return "conforme au pire des cas"
    if v["rssK"]["ok"] and v["rssProc"]["ok"]:
        return "conforme en statistique seulement"
    return "non conforme"


def lignePourBundle(nom: str, bundle: dict) -> dict:
    """Ligne récapitulative d'un calcul (utilisée par le mécanisme et par la comparaison de fichiers).

    Entrées : nom (texte), bundle (sortie de calculerChaine).
    Sortie : dict nom, jeuMini, jeuMaxi (pire des cas, mm), verdict, horsTolerance (bool), cp, cpk, ppmFormule,
    ppmMonteCarlo (None si pas de simulation), dominant (maillon de plus grande part de variance, ou du pire
    des cas si σ = 0), erreur (None).
    """
    v = bundle["verdicts"]
    contribs = bundle["contributions"]
    cle = "partVariance" if bundle["res"]["CF_sigma"] > 0 else "partPireCas"
    dominant = max(contribs, key=lambda c: c[cle])["nom"] if contribs else None
    mc = bundle["mc"]
    verdict = _verdict(v)
    return {
        "nom": nom,
        "jeuMini": float(v["pireCas"]["min"]),
        "jeuMaxi": float(v["pireCas"]["max"]),
        "verdict": verdict,
        "horsTolerance": verdict == "non conforme",
        "cp": _fini(v["cp"]),
        "cpk": _fini(v["cpk"]),
        "ppmFormule": _fini(v["ppm"]),
        "ppmMonteCarlo": _fini(mc["ppm"]) if mc is not None else None,
        "dominant": dominant,
        "erreur": None,
    }


def ligneErreur(nom: str, message: str) -> dict:
    """Ligne récapitulative d'une chaîne dont le calcul a échoué (mêmes clés, valeurs vides, erreur renseignée)."""
    return {
        "nom": nom,
        "jeuMini": None,
        "jeuMaxi": None,
        "verdict": "erreur de calcul",
        "horsTolerance": False,
        "cp": None,
        "cpk": None,
        "ppmFormule": None,
        "ppmMonteCarlo": None,
        "dominant": None,
        "erreur": message,
    }


def calculerMecanisme(
    mecanisme: dict, n: int = N_DEFAUT, graine: int = GRAINE_DEFAUT, seuilCpk: float | None = None
) -> dict:
    """Calcule toutes les chaînes d'un mécanisme ; une chaîne en erreur n'empêche pas le calcul des autres.

    Entrées : mecanisme (dict nom, chaines), n (tirages Monte-Carlo), graine (entier), seuilCpk (Cpk minimal visé ;
    None : aucun seuil).
    Sortie : dict nom, lignes (une par chaîne, voir lignePourBundle ; erreur renseignée si le calcul échoue),
    bundles (bundle ou None par chaîne), global {pireCpk (None si aucun Cpk défini), chainePireCpk,
    horsTolerance (noms des chaînes non conformes), enErreur (noms des chaînes en erreur), nChaines, ok},
    nTirages (tirages Monte-Carlo réellement utilisés par chaîne, réduits si le mécanisme a beaucoup de chaînes).
    ok vaut True si aucune chaîne n'est hors tolérance ni en erreur ; sousSeuil liste les chaînes dont le Cpk est
    inférieur à seuilCpk, et okSeuil vaut True si ok et aucune chaîne sous le seuil.
    """
    chaines = mecanisme.get("chaines") or []
    # plus il y a de chaînes, moins chacune reçoit de tirages (sans descendre sous TIRAGES_PAR_CHAINE_MINI)
    nEffectif = min(n, max(TIRAGES_PAR_CHAINE_MINI, TIRAGES_TOTAUX_MAX // max(1, len(chaines))))
    lignes, bundles = [], []
    for i, p in enumerate(chaines, start=1):
        nom = _nomChaine(p, i)
        try:
            b = calculerChaine(copy.deepcopy(p), True, nEffectif, graine)
            lignes.append(lignePourBundle(nom, b))
            bundles.append(b)
        except ErreurChaine as e:
            lignes.append(ligneErreur(nom, e.message))
            bundles.append(None)
        except (TypeError, ValueError, KeyError) as e:
            lignes.append(ligneErreur(nom, f"Saisie incomplète : {e}"))
            bundles.append(None)
    avecCpk = [x for x in lignes if x["cpk"] is not None]
    pire = min(avecCpk, key=lambda x: x["cpk"]) if avecCpk else None
    hors = [x["nom"] for x in lignes if x["horsTolerance"]]
    erreurs = [x["nom"] for x in lignes if x["erreur"]]
    sous = [x["nom"] for x in avecCpk if seuilCpk is not None and x["cpk"] < seuilCpk]
    return {
        "nom": mecanisme.get("nom", ""),
        "lignes": lignes,
        "bundles": bundles,
        "nTirages": nEffectif,
        "global": {
            "pireCpk": pire["cpk"] if pire else None,
            "chainePireCpk": pire["nom"] if pire else None,
            "horsTolerance": hors,
            "enErreur": erreurs,
            "nChaines": len(lignes),
            "ok": not hors and not erreurs,
            "seuilCpk": seuilCpk,
            "sousSeuil": sous,
            "okSeuil": not hors and not erreurs and not sous,
        },
    }


def tableauDeBord(lignes: list[dict], seuilCpk: float | None = None) -> pd.DataFrame:
    """Tableau de bord du mécanisme, une ligne par chaîne.

    Entrées : lignes (sortie « lignes » de calculerMecanisme), seuilCpk (ajoute la colonne « Cpk ≥ seuil »).
    Sortie : DataFrame Chaîne, Verdict, Jeu mini (mm), Jeu maxi (mm), Cp, Cpk, [Cpk ≥ seuil,] ppm (formule),
    ppm (Monte-Carlo), Maillon dominant, Erreur ; nombres à la française.
    """
    t = pd.DataFrame(
        {
            "Chaîne": [x["nom"] for x in lignes],
            "Verdict": [x["verdict"] for x in lignes],
            "Jeu mini (mm)": [fr(x["jeuMini"]) for x in lignes],
            "Jeu maxi (mm)": [fr(x["jeuMaxi"]) for x in lignes],
            "Cp": [fr(x["cp"], ".3g") for x in lignes],
            "Cpk": [fr(x["cpk"], ".3g") for x in lignes],
        }
    )
    if seuilCpk is not None:
        t["Cpk ≥ seuil"] = ["—" if x["cpk"] is None else ("oui" if x["cpk"] >= seuilCpk else "NON") for x in lignes]
    t["ppm (formule)"] = [fr(x["ppmFormule"], ".3g") for x in lignes]
    t["ppm (Monte-Carlo)"] = [fr(x["ppmMonteCarlo"], ".3g") for x in lignes]
    t["Maillon dominant"] = [x["dominant"] or "—" for x in lignes]
    t["Erreur"] = [x["erreur"] or "" for x in lignes]
    return t


def verdictGlobal(resultat: dict) -> tuple[str, str]:
    """Bandeau du mécanisme : (niveau « erreur », « avertissement » ou « succes », phrase).

    Rouge : une chaîne est hors tolérance ; orange : toutes tiennent mais une a un Cpk sous le seuil choisi ;
    vert sinon.
    """
    g = resultat["global"]
    if g["horsTolerance"]:
        return "erreur", "Hors tolérance : " + ", ".join(g["horsTolerance"]) + "."
    if g["sousSeuil"]:
        return "avertissement", f"Cpk sous le seuil de {fr(g['seuilCpk'], 'g')} : " + ", ".join(g["sousSeuil"]) + "."
    suite = f" et leur Cpk atteint {fr(g['seuilCpk'], 'g')}" if g["seuilCpk"] is not None else ""
    return "succes", f"Les {g['nChaines']} chaînes tiennent leurs limites au pire des cas ou en statistique{suite}."


def _synthese(resultat: dict) -> list[tuple[str, str]]:
    g = resultat["global"]
    return [
        ("Mécanisme", resultat.get("nom") or "—"),
        ("Verdict", verdictGlobal(resultat)[1]),
        ("Nombre de chaînes", str(g["nChaines"])),
        ("Pire Cpk", fr(g["pireCpk"], ".3g") + (f" ({g['chainePireCpk']})" if g["chainePireCpk"] else "")),
        ("Seuil de Cpk", fr(g["seuilCpk"], "g") if g["seuilCpk"] is not None else "aucun"),
        ("Chaînes hors tolérance", ", ".join(g["horsTolerance"]) or "aucune"),
        ("Chaînes sous le seuil de Cpk", ", ".join(g["sousSeuil"]) or "aucune"),
        ("Chaînes en erreur", ", ".join(g["enErreur"]) or "aucune"),
        ("Tirages Monte-Carlo par chaîne", str(resultat["nTirages"])),
    ]


def exporterTableauDeBord(resultat: dict) -> bytes:
    """Classeur Excel du tableau de bord d'un mécanisme calculé.

    Entrée : resultat (sortie de calculerMecanisme). Sortie : fichier .xlsx (bytes), feuilles « Tableau de bord » (une
    ligne par chaîne) et « Synthèse » (verdict global, pire Cpk, seuil, chaînes à reprendre).
    """
    from chainecotes.services.projet_io import _neutre

    tampon = io.BytesIO()
    with pd.ExcelWriter(tampon, engine="openpyxl") as writer:
        tableauDeBord(resultat["lignes"], resultat["global"]["seuilCpk"]).map(_neutre).to_excel(
            writer, sheet_name="Tableau de bord", index=False
        )
        pd.DataFrame(_synthese(resultat), columns=["Grandeur", "Valeur"]).map(_neutre).to_excel(
            writer, sheet_name="Synthèse", index=False
        )
    return tampon.getvalue()


def exporterRapportPdf(resultat: dict, date) -> bytes:
    """Rapport PDF du mécanisme : verdict global, synthèse et tableau de bord (une ligne par chaîne).

    Entrées : resultat (sortie de calculerMecanisme), date (date ou texte imprimé en tête, pour un PDF reproductible).
    Sortie : fichier PDF (bytes, commence par « %PDF »).
    """
    from chainecotes.services.rapport_pdf import _Pdf

    nom = resultat.get("nom") or "Mécanisme"
    pdf = _Pdf(f"Mécanisme — {nom}")
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font("DejaVu", "B", 18)
    pdf.cell(0, 12, f"Mécanisme : {nom}", new_x="LMARGIN", new_y="NEXT")
    pdf.paragraphe(f"Date : {date.strftime('%d/%m/%Y') if hasattr(date, 'strftime') else date}")
    pdf.titreSection("Synthèse")
    pdf.tableau(("Grandeur", "Valeur"), _synthese(resultat), (60, 120))
    pdf.titreSection("Tableau de bord")
    t = tableauDeBord(resultat["lignes"], resultat["global"]["seuilCpk"])
    avecSeuil = "Cpk ≥ seuil" in t
    colonnes = ["Chaîne", "Verdict", "Jeu mini (mm)", "Jeu maxi (mm)", "Cpk"] + (["Cpk ≥ seuil"] if avecSeuil else [])
    pdf.tableau(colonnes, t[colonnes].values.tolist(), (46, 50, 22, 22, 18, 22) if avecSeuil else (58, 58, 24, 24, 16))
    for x in resultat["lignes"]:
        if x["erreur"]:
            pdf.paragraphe(f"• {x['nom']} : {x['erreur']}")
    return bytes(pdf.output())
