"""Contrôles de cohérence d'un problème de chaîne de cotes, avant ou après calcul.

Le module ne duplique pas les contrôles bloquants de core/chaine.py : il les appelle maillon par maillon
(normaliserMaillon, normaliserReglages, normaliserCondition, verifierFermeture) pour les transformer en
messages listés avec le maillon fautif, puis il ajoute des contrôles de plausibilité.
"""

import math
import statistics

from chainecotes.core.chaine import (
    normaliserCondition,
    normaliserMaillon,
    normaliserReglages,
    verifierFermeture,
)
from chainecotes.core.donnees import chargerJson
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.nombres import fr

_SEUILS = chargerJson("controles.json")
FACTEUR_UNITE = _SEUILS["facteur_unite"]  # écart avec la médiane des autres maillons : erreur mm / m / µm
K_MIN, K_MAX = _SEUILS["k_min"], _SEUILS["k_max"]  # plage usuelle du procédé garanti k (± kσ)
_ISO = "Chaine:Iso286:"


def _g(x: float) -> str:
    """Nombre court à la française (virgule décimale) pour les messages."""
    return fr(x, "g")


def _ligne(niveau: str, maillon, code: str, message: str) -> dict:
    return {"niveau": niveau, "maillon": maillon, "code": code, "message": message}


def _codeErreur(e: ErreurChaine) -> str:
    """Code court d'une ErreurChaine du coeur (la désignation ISO illisible est distinguée de la cote qui diffère)."""
    if e.identifiant.startswith(_ISO):
        return "isoNonReconnue"
    suite = e.identifiant.rsplit(":", 1)[-1]
    return {"iso": "isoCoteDifferente", "ecarts": "ecartsInverses"}.get(suite, suite)


def _controlesMaillons(M: list[dict]) -> list[dict]:
    """Tolérance nulle ou supérieure à la cote, cote d'unité douteuse (médiane des autres maillons)."""
    sortie = []
    for i, m in enumerate(M):
        it = m["es"] - m["ei"]
        if it == 0:
            sortie.append(
                _ligne("avertissement", m["nom"], "toleranceNulle", f"{m['nom']} : tolérance nulle (ES = EI).")
            )
        elif m["cote"] > 0 and it > m["cote"]:
            sortie.append(
                _ligne(
                    "avertissement",
                    m["nom"],
                    "toleranceSuperieureCote",
                    f"{m['nom']} : la tolérance ({_g(it)} mm) dépasse la cote ({_g(m['cote'])} mm), "
                    "unité probablement confondue (mm, µm).",
                )
            )
        if abs(m["facteur"] * math.cos(math.radians(m["theta"]))) < 1e-9:
            sortie.append(
                _ligne(
                    "avertissement",
                    m["nom"],
                    "coefficientNul",
                    f"{m['nom']} : angle {_g(m['angle'])}° perpendiculaire à la chaîne, "
                    "le maillon ne contribue pas au jeu.",
                )
            )
        reelle = m["moyenne_reelle"]
        if reelle is not None and not m["cote"] + m["ei"] <= reelle <= m["cote"] + m["es"]:
            sortie.append(
                _ligne(
                    "avertissement",
                    m["nom"],
                    "moyenneMesureeHorsTolerance",
                    f"{m['nom']} : la moyenne mesurée {_g(reelle)} mm est hors de l'intervalle de tolérance "
                    f"[{_g(m['cote'] + m['ei'])} ; {_g(m['cote'] + m['es'])}] mm : "
                    "le procédé produit des pièces non conformes.",
                )
            )
        if m["facteur"] != 1 or m["angle"] != 0:
            sortie.append(
                _ligne(
                    "info",
                    m["nom"],
                    "coefficientLibre",
                    f"{m['nom']} : coefficient aᵢ = {_g(m['facteur'])} · cos({_g(m['theta'])}°) = "
                    f"{fr(m['facteur'] * math.cos(math.radians(m['theta'])), '.6g')} (levier ou angle saisi).",
                )
            )
        autres = [x["cote"] for j, x in enumerate(M) if j != i and x["cote"] > 0]
        if m["cote"] > 0 and autres:
            rapport = m["cote"] / statistics.median(autres)
            if rapport >= FACTEUR_UNITE or rapport <= 1 / FACTEUR_UNITE:
                sortie.append(
                    _ligne(
                        "avertissement",
                        m["nom"],
                        "uniteAberrante",
                        f"{m['nom']} : la cote {_g(m['cote'])} mm est {'plus de' if rapport > 1 else 'moins de'} "
                        f"{FACTEUR_UNITE} fois "
                        f"{'supérieure' if rapport > 1 else 'inférieure'} à la médiane des autres maillons : "
                        "mm confondu avec m ou µm ?",
                    )
                )
    return sortie


def _controlesJeu(M: list[dict], condition: dict) -> list[dict]:
    """Fermeture et sens, par comparaison du jeu nominal, moyen et pire des cas aux limites de la condition.

    La cote condition n'a pas de cote nominale propre : elle est définie par ses limites Jmin et Jmax. La
    fermeture signée Σ aᵢ·cᵢ (aᵢ = facteur · cos θ, ±1 par défaut) donne le jeu nominal ; il peut sortir de
    [Jmin ; Jmax] sans défaut (ex. alésage H7 dont l'écart est tout positif), ce n'est donc qu'une information.
    Un défaut réel est un jeu moyen hors des limites (maillon oublié ou sens inversé probable), ou un pire des
    cas entièrement hors des limites (la condition ne peut jamais être tenue : erreur).
    """
    a = [m["facteur"] * math.cos(math.radians(m["theta"])) for m in M]
    nominal = sum(x * m["cote"] for x, m in zip(a, M, strict=True))
    moyen = sum(x * (m["cote"] + (m["es"] + m["ei"]) / 2) for x, m in zip(a, M, strict=True))
    demi = sum(abs(x) * (m["es"] - m["ei"]) / 2 for x, m in zip(a, M, strict=True))
    jmin, jmax = condition["jmin"], condition["jmax"]
    nom = condition["nom"]
    sortie = []
    if moyen + demi < jmin or moyen - demi > jmax:
        sortie.append(
            _ligne(
                "erreur",
                None,
                "conditionInatteignable",
                f"{nom} : le jeu au pire des cas [{_g(moyen - demi)} ; {_g(moyen + demi)}] mm est entièrement hors de "
                f"[{_g(jmin)} ; {_g(jmax)}] mm. Vérifier la fermeture (maillon oublié, sens ou cote erronés).",
            )
        )
    elif not jmin <= moyen <= jmax:
        sortie.append(
            _ligne(
                "avertissement",
                None,
                "moyenneHorsCondition",
                f"{nom} : le jeu moyen {_g(moyen)} mm est hors de [{_g(jmin)} ; {_g(jmax)}] mm : "
                "maillon oublié ou sens inversé possible.",
            )
        )
    elif not jmin <= nominal <= jmax:
        sortie.append(
            _ligne(
                "info",
                None,
                "nominalHorsCondition",
                f"{nom} : le jeu nominal {_g(nominal)} mm (Σ aᵢ·cᵢ) est hors de [{_g(jmin)} ; {_g(jmax)}] mm, "
                "mais le jeu moyen y est : cas normal avec des écarts non centrés.",
            )
        )
    if jmin >= 0 and nominal < 0 or jmax <= 0 and nominal > 0:
        sortie.append(
            _ligne(
                "info",
                None,
                "sensDouteux",
                f"{nom} : le signe du jeu nominal ({_g(nominal)} mm) est opposé à celui de la condition ; "
                "les sens « + » et « − » sont peut-être inversés.",
            )
        )
    return sortie


def _controlesThermiques(M: list[dict], reglages: dict) -> list[dict]:
    """Température de service sans coefficient de dilatation, matériau hors domaine (via core/materiaux)."""
    sortie = []
    for m in M:
        if m["horsDomaine"]:
            sortie.append(
                _ligne(
                    "avertissement",
                    m["nom"],
                    "temperatureHorsDomaine",
                    f"{m['nom']} ({m['materiau']}, {_g(m['tservice'])} °C) : hors domaine, {m['motif']}.",
                )
            )
    tref = reglages["tref"]
    if reglages["modeT"] == "uniforme":
        if reglages["tservice"] != tref and all(m["alpha"] == 0 for m in M):
            sortie.append(
                _ligne(
                    "info",
                    None,
                    "dilatationAbsente",
                    "La température de service diffère de Tref mais aucun maillon n'a de matériau ni de α : "
                    "aucun effet thermique n'est calculé.",
                )
            )
    else:
        for m in M:
            if m["tservice"] != tref and m["alpha"] == 0:
                sortie.append(
                    _ligne(
                        "info",
                        m["nom"],
                        "dilatationAbsente",
                        f"{m['nom']} : température de service {_g(m['tservice'])} °C sans matériau ni α : "
                        "dilatation ignorée.",
                    )
                )
    return sortie


def controlerProbleme(probleme) -> list[dict]:
    """Contrôles de cohérence d'un problème (saisie, fermeture, unités, tolérances, sens, lois, thermique, ISO).

    Entrée : probleme (dict condition, reglages, maillons ; cotes en mm). Toute valeur est acceptée.
    Sortie : liste de dict niveau (« erreur » : le calcul est impossible ou la condition ne peut pas être tenue ;
    « avertissement » : défaut probable ; « info » : remarque), maillon (nom ou None), code (identifiant stable),
    message (français). Liste vide si rien à signaler. Les erreurs bloquantes du coeur sont reprises telles
    quelles, maillon par maillon ; les contrôles de plausibilité ne portent que sur les maillons valides.
    Erreur : aucune, un problème invalide renvoie des lignes de niveau « erreur ».
    """
    if not isinstance(probleme, dict):
        return [_ligne("erreur", None, "problemeInvalide", "Le problème doit être un dictionnaire.")]
    sortie = []
    try:
        reglages = normaliserReglages(probleme.get("reglages"))
    except (ErreurChaine, AttributeError, TypeError) as e:
        sortie.append(_ligne("erreur", None, getattr(e, "identifiant", "reglages").rsplit(":", 1)[-1], str(e)))
        reglages = normaliserReglages(None)
    try:
        condition = normaliserCondition(probleme.get("condition"))
    except (ErreurChaine, AttributeError, TypeError) as e:
        sortie.append(_ligne("erreur", None, "condition", str(e)))
        condition = normaliserCondition(None)
    brut = probleme.get("maillons")
    if not isinstance(brut, list):
        return [*sortie, _ligne("erreur", None, "maillonsInvalides", "Les maillons doivent former une liste.")]
    M, defauts = [], False
    for i, m in enumerate(brut):
        etiquette = str(m.get("nom") or f"Maillon {i + 1}") if isinstance(m, dict) else f"Maillon {i + 1}"
        try:
            if not isinstance(m, dict):
                raise ErreurChaine("Chaine:Saisie:maillon", f"Maillon {i + 1} : doit être un dictionnaire.")
            M.append(normaliserMaillon(m, i + 1, reglages))
        except ErreurChaine as e:
            defauts = True
            sortie.append(_ligne("erreur", etiquette, _codeErreur(e), e.message))
    try:
        verifierFermeture(M)
        ferme = True
    except ErreurChaine as e:
        ferme = False
        if not defauts:  # sinon la chaîne est incomplète à cause des maillons déjà signalés
            sortie.append(_ligne("erreur", None, "nonFermee", e.message))
    if not 0 < reglages["kSigma"]:  # défense : normaliserReglages l'exclut déjà
        sortie.append(_ligne("erreur", None, "kSigma", "Le procédé garanti k doit être strictement positif."))
    elif not K_MIN <= reglages["kSigma"] <= K_MAX:
        sortie.append(
            _ligne(
                "avertissement",
                None,
                "kAtypique",
                f"Procédé garanti k = {_g(reglages['kSigma'])} : valeur inhabituelle (usuel : {_g(K_MIN)} à {_g(K_MAX)}).",
            )
        )
    if not (condition["jmin"] > float("-inf") or condition["jmax"] < float("inf")):
        sortie.append(
            _ligne("info", None, "conditionSansLimite", "Aucune limite Jmin ni Jmax : la chaîne n'a pas de verdict.")
        )
    sortie += _controlesMaillons(M) + _controlesThermiques(M, reglages)
    if ferme and not defauts:
        sortie += _controlesJeu(M, condition)
    return sortie
