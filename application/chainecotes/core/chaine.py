"""Chaîne de cotes 1D : saisie, fermeture, jeu au pire des cas, statistique (RSS) et effet thermique.

Port de Solveur_chaine_de_cotes_1D.m et des outils de graphiques.m (application MATLAB) :
- projection : sens « + » ↔ θ = 0° (cos = +1), sens « − » ↔ θ = 180° (cos = −1) ;
  un angle (°) ajouté à θ et un facteur (rapport de levier, défaut 1) donnent un coefficient libre
  a_i = facteur · cos θ_i, qui vaut ±1 par défaut comme MATLAB ;
- sensibilité en service a_i = cos θ_i · (1 + α_i · ΔT_i) ;
- pire des cas : demi-dispersion Σ |a_i| · IT_i / 2 autour du jeu moyen ;
- statistique : σ_i = |a_i| · IT_i / (2k) (loi normale, procédé garanti à ± k σ), σ_J = √Σ σ_i².

Ajouts par rapport à MATLAB (qui ne connaît que la loi normale et un procédé centré), tous optionnels, avec une
valeur par défaut qui redonne exactement MATLAB :
- loi uniforme, σ_i = |a_i| · IT_i / √12 ;
- loi triangulaire (demi-largeur h = IT/2), σ_i = |a_i| · h / √6 ;
- décentrage du procédé (réglage, en multiples de σ_J) : la moyenne du jeu est décalée vers la limite la plus proche ;
- dérive (maillon, µm / 1000 pièces) : stockée et validée seulement, hors du calcul principal ;
- capabilité mesurée à l'atelier (maillon) : écart type mesuré `sigma_reel` (mm, loi normale, remplace celui de la loi
  et de l'IT) et moyenne mesurée `moyenne_reelle` (mm, remplace la cote moyenne pour la moyenne du procédé).
"""

import math

import numpy as np
from scipy.signal import fftconvolve

from chainecotes.core import iso286, iso2768
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.geometrie import TYPES as TYPES_GEOMETRIE
from chainecotes.core.materiaux import PERSONNALISE, alphaMateriau
from chainecotes.core.nombres import fr

LOIS = ("normale", "uniforme", "triangulaire")
TOL_COMPARAISON = 1e-9  # mm : un jeu pile sur une limite reste conforme malgré l'arrondi flottant
SENS = ("+", "-")
MODES_T = ("uniforme", "par_cote")
_ID = "Chaine:Saisie:"
ZERO_ABSOLU_C = -273.15  # °C : constante physique, aucune température ne peut lui être inférieure


def _nombre(v, quoi: str, ligne: int) -> float:
    """Nombre fini d'une saisie, sinon ErreurChaine."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ErreurChaine(_ID + "nombre", f"Maillon {ligne} : {quoi} doit être un nombre (reçu {v!r}).") from None
    if not math.isfinite(x):
        raise ErreurChaine(_ID + "nombre", f"Maillon {ligne} : {quoi} doit être un nombre fini.")
    return x


def _reel(v, quoi: str) -> float:
    """Nombre fini d'un réglage ou de la cote condition, sinon ErreurChaine."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ErreurChaine(_ID + "nombre", f"{quoi} doit être un nombre (reçu {v!r}).") from None
    if not math.isfinite(x):
        raise ErreurChaine(_ID + "nombre", f"{quoi} doit être un nombre fini.")
    return x


def estVide(v) -> bool:
    """Vrai si une saisie est vide : None, case vide du tableau (nan) ou texte blanc.

    Entrée : v (valeur saisie). Sortie : booléen.
    """
    return v is None or (isinstance(v, float) and math.isnan(v)) or (isinstance(v, str) and not v.strip())


def coefficientSigma(loi: str, k: float) -> float:
    """Rapport σ / (|a| · IT) d'une loi : normale 1/(2k), uniforme 1/√12, triangulaire 1/(2√6).

    Entrées : loi (« normale », « uniforme » ou « triangulaire »), k (procédé garanti à ± k σ, loi normale).
    Sortie : coefficient sans unité. Erreur : ErreurChaine si la loi est inconnue.
    """
    if loi == "normale":
        if not k > 0:
            raise ErreurChaine(_ID + "k", f"Le facteur k doit être strictement positif (reçu {k!r}).")
        return 1 / (2 * k)
    if loi == "uniforme":
        return 1 / math.sqrt(12)
    if loi == "triangulaire":
        return 1 / (2 * math.sqrt(6))  # h = IT/2, σ = h/√6
    raise ErreurChaine(_ID + "loi", f"Loi {loi!r} inconnue : « normale », « uniforme » ou « triangulaire » attendue.")


def decalageDecentrage(moy: float, sigma: float, jmin: float, jmax: float, decentrage: float) -> float:
    """Décalage de la moyenne du jeu (mm) pour un procédé décentré de `decentrage` σ_J vers la limite la plus proche.

    Entrées : moy, sigma (mm), jmin, jmax (mm, infinis acceptés), decentrage (multiples de σ_J, ≥ 0).
    Sortie : décalage signé en mm (négatif vers Jmin, positif vers Jmax) ; 0 si decentrage = 0 ou si aucune limite
    n'est finie. À égale distance des deux limites, Jmin est choisie.
    """
    if not decentrage > 0:
        return 0.0
    dmin = moy - jmin if math.isfinite(jmin) else math.inf
    dmax = jmax - moy if math.isfinite(jmax) else math.inf
    if math.isinf(dmin) and math.isinf(dmax):
        return 0.0
    return -decentrage * sigma if dmin <= dmax else decentrage * sigma


def normaliserMaillon(m: dict, ligne: int, reglages: dict) -> dict:
    """Contrôle un maillon saisi et résout sa désignation ISO 286 et son coefficient de dilatation.

    Entrées : m (dict nom, sens « + » ou « - », cote (mm), iso (texte ou vide), es, ei (mm, si pas d'ISO),
    loi (« normale », « uniforme » ou « triangulaire »), materiau, alpha (1e-6/K, prioritaire sur le matériau),
    tservice (°C), derive (µm / 1000 pièces, défaut 0, non utilisée par le calcul principal),
    facteur (> 0, défaut 1 : rapport de levier), angle (°, défaut 0 : écart de la cote avec l'axe de la chaîne),
    sigma_reel (mm, ≥ 0, écart type mesuré), moyenne_reelle (mm, moyenne mesurée),
    geometrie (identifiant de core.geometrie.TYPES si le maillon représente une tolérance géométrique)),
    ligne (numéro affiché dans les messages), reglages (dict tref, modeT, tservice).
    Sortie : dict nom, sens, theta (°, 0 ou 180 plus l'angle), facteur, angle (°), cote, iso, es, ei (mm), loi,
    materiau, alpha (1/K), tservice (°C, effective),
    derive (µm / 1000 pièces), horsDomaine (bool), motif (texte),
    avertissement (texte : écart connu MATLAB / ISO 286, vide sinon).
    Erreur : ErreurChaine avec un message en français désignant le maillon.
    """
    nom = str(m.get("nom") or f"Maillon {ligne}").strip()
    sens = str(m.get("sens", "+")).strip().replace("−", "-")
    if sens not in SENS:
        raise ErreurChaine(_ID + "sens", f"Maillon {ligne} ({nom}) : le sens doit être « + » ou « − ».")
    cote = _nombre(m.get("cote"), "la cote nominale", ligne)
    if cote < 0:
        raise ErreurChaine(_ID + "cote", f"Maillon {ligne} ({nom}) : la cote nominale doit être positive ou nulle.")
    iso = "" if estVide(m.get("iso")) else str(m["iso"]).strip()
    avertissement, origine = "", ""
    if iso:
        r = iso286.lireDesignation(iso, cote)
        if not math.isclose(r["cote"], cote, abs_tol=1e-9):
            raise ErreurChaine(
                _ID + "iso",
                f"Maillon {ligne} ({nom}) : la désignation {iso!r} donne la cote {fr(r['cote'], 'g')} mm, "
                f"différente de la cote saisie {fr(cote, 'g')} mm.",
            )
        es, ei, avertissement = r["es"], r["ei"], r["avertissement"]
    elif estVide(m.get("es")) and estVide(m.get("ei")) and reglages.get("tolGenerale"):
        classe = reglages["tolGenerale"]
        try:
            t = iso2768.tolGenerale(cote, classe)
        except ErreurChaine as e:
            raise ErreurChaine(e.identifiant, f"Maillon {ligne} ({nom}) : {e.message}") from None
        es, ei, origine = t, -t, f"2768-{classe}"
    else:
        es = _nombre(m.get("es"), "l'écart supérieur", ligne)
        ei = _nombre(m.get("ei"), "l'écart inférieur", ligne)
    if es < ei:
        raise ErreurChaine(
            _ID + "ecarts", f"Maillon {ligne} ({nom}) : l'écart supérieur doit être ≥ l'écart inférieur."
        )
    loi = "normale" if estVide(m.get("loi")) else str(m["loi"]).strip().lower()
    if loi not in LOIS:
        raise ErreurChaine(
            _ID + "loi", f"Maillon {ligne} ({nom}) : loi « normale », « uniforme » ou « triangulaire » attendue."
        )
    derive = 0.0 if estVide(m.get("derive")) else _nombre(m["derive"], "la dérive", ligne)
    facteur = 1.0 if estVide(m.get("facteur")) else _nombre(m["facteur"], "le facteur", ligne)
    if not facteur > 0:
        raise ErreurChaine(_ID + "facteur", f"Maillon {ligne} ({nom}) : le facteur doit être strictement positif.")
    angle = 0.0 if estVide(m.get("angle")) else _nombre(m["angle"], "l'angle", ligne)
    geometrie = "" if estVide(m.get("geometrie")) else str(m["geometrie"]).strip()
    if geometrie and geometrie not in TYPES_GEOMETRIE:
        raise ErreurChaine(
            _ID + "geometrie", f"Maillon {ligne} ({nom}) : tolérance géométrique {geometrie!r} inconnue."
        )
    sigma_reel = None if estVide(m.get("sigma_reel")) else _nombre(m["sigma_reel"], "l'écart type mesuré", ligne)
    if sigma_reel is not None and sigma_reel < 0:
        raise ErreurChaine(
            _ID + "sigmaReel", f"Maillon {ligne} ({nom}) : l'écart type mesuré doit être positif ou nul."
        )
    moyenne_reelle = (
        None if estVide(m.get("moyenne_reelle")) else _nombre(m["moyenne_reelle"], "la moyenne mesurée", ligne)
    )
    tref = reglages["tref"]
    tserv = reglages["tservice"] if reglages["modeT"] == "uniforme" else m.get("tservice", tref)
    tserv = tref if estVide(tserv) else _nombre(tserv, "la température de service", ligne)
    if tserv < ZERO_ABSOLU_C:
        raise ErreurChaine(
            _ID + "temperature", f"Maillon {ligne} ({nom}) : la température de service est sous le zéro absolu."
        )
    materiau = "" if estVide(m.get("materiau")) else str(m["materiau"])
    hors, motif = False, ""
    if not estVide(m.get("alpha")):
        alpha = _nombre(m["alpha"], "le coefficient de dilatation", ligne) * 1e-6
    elif materiau and materiau != PERSONNALISE:
        r = alphaMateriau(materiau, tserv, tref)
        if math.isnan(r["alpha"]):
            raise ErreurChaine(_ID + "materiau", f"Maillon {ligne} ({nom}) : matériau inconnu {materiau!r}.")
        alpha, hors, motif = r["alpha"], r["horsDomaine"], r["motif"]
    else:
        alpha = 0.0
    if materiau and materiau != PERSONNALISE and not estVide(m.get("alpha")):
        r = alphaMateriau(materiau, tserv, tref)
        hors, motif = r["horsDomaine"], r["motif"]
    return {
        "nom": nom,
        "sens": sens,
        "theta": (0.0 if sens == "+" else 180.0) + angle,
        "facteur": facteur,
        "angle": angle,
        "sigma_reel": sigma_reel,
        "moyenne_reelle": moyenne_reelle,
        "geometrie": geometrie,
        "cote": cote,
        "iso": iso,
        "origine": origine,
        "es": es,
        "ei": ei,
        "loi": loi,
        "materiau": materiau,
        "alpha": alpha,
        "tservice": tserv,
        "derive": derive,
        "horsDomaine": bool(hors),
        "motif": motif,
        "avertissement": avertissement,
    }


def normaliserReglages(reglages: dict | None) -> dict:
    """Réglages du calcul complétés et contrôlés.

    Entrée : dict kSigma (procédé garanti à ± k σ, défaut 3), tref (°C, défaut 20), modeT (« uniforme » ou
    « par_cote »), tservice (°C, mode uniforme),
    decentrage (≥ 0, multiples de σ_J, défaut 0 : procédé centré comme MATLAB),
    tolGenerale (classe ISO 2768 « f », « m », « c » ou « v » donnée aux maillons sans écarts ; vide : aucune).
    Sortie : dict kSigma, tref, modeT, tservice, decentrage, tolGenerale. Erreur ErreurChaine si une valeur est invalide
    (dont une température sous le zéro absolu, −273,15 °C).
    """
    r = dict(reglages or {})
    k = _reel(3 if r.get("kSigma") is None else r["kSigma"], "Le procédé garanti k")
    if not k > 0:
        raise ErreurChaine(_ID + "kSigma", "Le procédé garanti k doit être strictement positif.")
    modeT = str(r.get("modeT", "uniforme"))
    if modeT not in MODES_T:
        raise ErreurChaine(_ID + "modeT", "Mode de température « uniforme » ou « par_cote » attendu.")
    tref = 20.0 if r.get("tref") is None else _reel(r["tref"], "La température de référence")
    tserv = r.get("tservice")
    tserv = tref if tserv is None else _reel(tserv, "La température de service")
    if min(tref, tserv) < ZERO_ABSOLU_C:
        raise ErreurChaine(
            _ID + "temperature", f"Les températures de référence et de service doivent être ≥ {ZERO_ABSOLU_C} °C."
        )
    dec = 0.0 if r.get("decentrage") is None else _reel(r["decentrage"], "Le décentrage")
    if dec < 0:
        raise ErreurChaine(_ID + "decentrage", "Le décentrage doit être positif ou nul (multiples de σ_J).")
    classe = "" if estVide(r.get("tolGenerale")) else str(r["tolGenerale"]).strip().lower()
    if classe and classe not in iso2768.CLASSES:
        raise ErreurChaine(_ID + "tolGenerale", "La tolérance générale ISO 2768 doit être f, m, c ou v (ou vide).")
    return {"kSigma": k, "tref": tref, "modeT": modeT, "tservice": tserv, "decentrage": dec, "tolGenerale": classe}


def normaliserCondition(condition: dict | None) -> dict:
    """Cote condition contrôlée.

    Entrée : dict nom, jmin, jmax (mm ; vide = pas de limite de ce côté).
    Sortie : dict nom, jmin (mm, -inf si absent), jmax (mm, +inf si absent).
    Erreur : ErreurChaine si jmin > jmax.
    """
    c = dict(condition or {})
    jmin = -math.inf if c.get("jmin") is None else _reel(c["jmin"], "Jmin de la cote condition")
    jmax = math.inf if c.get("jmax") is None else _reel(c["jmax"], "Jmax de la cote condition")
    if jmin > jmax:
        raise ErreurChaine(_ID + "condition", "Cote condition : Jmin doit être ≤ Jmax.")
    return {"nom": str(c.get("nom") or "Jeu J"), "jmin": jmin, "jmax": jmax}


def verifierFermeture(maillons: list[dict]) -> None:
    """Contrôle bloquant : la chaîne doit être fermée sur la cote condition.

    Entrée : maillons normalisés (normaliserMaillon).
    Une chaîne 1D est fermée si elle part d'une surface du jeu et revient sur l'autre : il faut au moins
    un maillon dans chaque sens (« + » et « − ») et au moins deux maillons.
    Erreur : ErreurChaine 'Chaine:Saisie:nonFermee' avec l'explication.
    """
    if len(maillons) < 2:
        raise ErreurChaine(_ID + "nonFermee", "Chaîne non fermée : il faut au moins deux maillons.")
    sens = {m["sens"] for m in maillons}
    if sens != {"+", "-"}:
        manque = "−" if "+" in sens else "+"
        raise ErreurChaine(
            _ID + "nonFermee",
            f"Chaîne non fermée : aucun maillon de sens « {manque} ». Une chaîne de cotes part d'une surface de la "
            "cote condition et revient sur l'autre : elle a toujours des maillons dans les deux sens.",
        )


def preparerProbleme(probleme: dict) -> dict:
    """Contrôle complet d'un problème (cote condition, réglages, maillons) avant tout calcul.

    Entrée : dict condition, reglages, maillons (liste de dict, voir normaliserMaillon).
    Sortie : dict condition, reglages, maillons (normalisés).
    Erreur : ErreurChaine au premier défaut trouvé (dont la chaîne non fermée).
    """
    reglages = normaliserReglages(probleme.get("reglages"))
    condition = normaliserCondition(probleme.get("condition"))
    brut = list(probleme.get("maillons") or [])
    maillons = [normaliserMaillon(m, i + 1, reglages) for i, m in enumerate(brut)]
    verifierFermeture(maillons)
    return {"condition": condition, "reglages": reglages, "maillons": maillons}


def _sigmaMaillons(a, it, c_sigma, sigma_reel=None) -> np.ndarray:
    """σ de chaque maillon dans le jeu : |a|·IT·c_σ de la loi, ou |a|·σ mesuré là où il est connu (nan = inconnu)."""
    s = np.abs(a) * it * c_sigma
    if sigma_reel is None:
        return s
    return np.where(np.isnan(sigma_reel), s, np.abs(a) * np.nan_to_num(sigma_reel))


def _etatJeu(cote, cmoy, it, a, c_sigma, sigma_reel=None) -> dict:
    """Jeu nominal / moyen / mini / maxi / σ pour des coefficients a_i (port de etatJeu)."""
    nom = float(np.sum(cote * a))
    moy = float(np.sum(cmoy * a))
    demi = float(np.sum(np.abs(a) * it / 2))
    sigma = float(np.sqrt(np.sum(_sigmaMaillons(a, it, c_sigma, sigma_reel) ** 2)))
    return {"nom": nom, "moy": moy, "min": moy - demi, "max": moy + demi, "sigma": sigma}


def solveurChaine(probleme: dict) -> dict:
    """Résout une chaîne de cotes 1D : jeu au pire des cas, statistique et effet thermique.

    Entrée : problème (dict condition, reglages, maillons ; voir preparerProbleme).
    Sortie : dict avec les clés de Solveur_chaine_de_cotes_1D.m :
    CF_nom, CF_moy, CF_min, CF_max, CF_sigma (jeu en service, mm), CF_nom_ref … CF_sigma_ref (jeu à Tref),
    dJ_th (décalage thermique du jeu moyen, mm), dJ_th_i (contribution de chaque maillon), k_sigma, Nom, Cote,
    proj (facteur · cos θ), coef (a_i), C_moy, IT, alpha (1/K), dT (K), Tref, Tservice, mode_thermique,
    thermique_actif ; plus loi (liste), sigma_i (mm), condition (jmin, jmax), maillons (normalisés),
    decentrage (σ_J), decalage (mm, décalage appliqué à la moyenne du jeu) et CF_moy_proc = CF_moy + decalage
    (moyenne du procédé, utilisée par Cpk, ppm et Monte-Carlo ; CF_min, CF_max et Cp n'en dépendent pas).
    Erreur : ErreurChaine si la saisie est invalide ou la chaîne non fermée.
    """
    p = preparerProbleme(probleme)
    M, reg = p["maillons"], p["reglages"]
    k = reg["kSigma"]
    cote = np.array([m["cote"] for m in M])
    es = np.array([m["es"] for m in M])
    ei = np.array([m["ei"] for m in M])
    proj = np.array([m["facteur"] for m in M]) * np.cos(np.deg2rad([m["theta"] for m in M]))
    cmoy = cote + (es + ei) / 2
    it = es - ei
    alpha = np.array([m["alpha"] for m in M])
    tserv = np.array([m["tservice"] for m in M])
    dT = tserv - reg["tref"]
    coef = proj * (1 + alpha * dT)
    lois = [m["loi"] for m in M]
    c_sigma = np.array([coefficientSigma(loi, k) for loi in lois])
    mesure = any(m["sigma_reel"] is not None or m["moyenne_reelle"] is not None for m in M)
    sigma_reel = np.array([np.nan if m["sigma_reel"] is None else m["sigma_reel"] for m in M]) if mesure else None
    moyenne_reelle = np.array([np.nan if m["moyenne_reelle"] is None else m["moyenne_reelle"] for m in M])
    ref = _etatJeu(cote, cmoy, it, proj, c_sigma, sigma_reel)
    serv = _etatJeu(cote, cmoy, it, coef, c_sigma, sigma_reel)
    c = p["condition"]
    # moyenne mesurée de certains maillons : le procédé n'est plus centré sur la cote moyenne
    decalage_reel = float(np.sum(coef[~np.isnan(moyenne_reelle)] * (moyenne_reelle - cmoy)[~np.isnan(moyenne_reelle)]))
    decalage = decalage_reel + decalageDecentrage(
        serv["moy"] + decalage_reel, serv["sigma"], c["jmin"], c["jmax"], reg["decentrage"]
    )
    return {
        "CF_nom": serv["nom"],
        "CF_moy": serv["moy"],
        "CF_min": serv["min"],
        "CF_max": serv["max"],
        "CF_sigma": serv["sigma"],
        "decentrage": reg["decentrage"],
        "decalage": decalage,
        "decalage_reel": decalage_reel,
        "sigma_reel": np.full(len(M), np.nan) if sigma_reel is None else sigma_reel,
        "moyenne_reelle": moyenne_reelle,
        "CF_moy_proc": serv["moy"] + decalage,
        "CF_nom_ref": ref["nom"],
        "CF_moy_ref": ref["moy"],
        "CF_min_ref": ref["min"],
        "CF_max_ref": ref["max"],
        "CF_sigma_ref": ref["sigma"],
        "dJ_th_i": cmoy * alpha * dT * proj,
        "dJ_th": serv["moy"] - ref["moy"],
        "k_sigma": k,
        "Nom": [m["nom"] for m in M],
        "Cote": cote,
        "proj": proj,
        "coef": coef,
        "C_moy": cmoy,
        "IT": it,
        "ES": es,
        "EI": ei,
        "alpha": alpha,
        "dT": dT,
        "Tref": reg["tref"],
        "Tservice": tserv,
        "mode_thermique": reg["modeT"],
        "thermique_actif": bool(np.any(alpha * dT != 0)),
        "loi": lois,
        "sigma_i": _sigmaMaillons(coef, it, c_sigma, sigma_reel),
        "condition": p["condition"],
        "reglages": reg,
        "maillons": M,
    }


def phi(z):
    """Fonction de répartition de la loi normale centrée réduite : Φ(z) = ½ erfc(−z/√2)."""
    from scipy.special import erfc

    return 0.5 * erfc(-np.asarray(z, dtype=float) / math.sqrt(2))


def ppmHorsTolerance(mu: float, sigma: float, jmin: float, jmax: float) -> float:
    """Parties par million hors de [jmin ; jmax] pour un jeu de loi normale (port de ppm_hors_tol).

    Entrées : mu, sigma (mm), jmin, jmax (mm, infinis acceptés).
    Sortie : ppm (nan si sigma = 0).
    """
    if not sigma > 0:
        return math.nan
    ppm = 0.0
    if math.isfinite(jmin):
        ppm += 1e6 * float(phi((jmin - mu) / sigma))
    if math.isfinite(jmax):
        ppm += 1e6 * float(phi((mu - jmax) / sigma))
    return ppm


def _masseCellules(loi: str, h: float, pas: float) -> np.ndarray:
    """Masses de probabilité d'une loi centrée (uniforme ou triangulaire sur [−h ; h]) par cellule de largeur pas.

    Les masses sont des différences de fonction de répartition exactes : aucune erreur d'échantillonnage.
    """
    K = int(math.ceil(h / pas))
    bords = (np.arange(-K, K + 2) - 0.5) * pas
    x = np.clip(bords, -h, h)
    if loi == "uniforme":
        F = (x + h) / (2 * h)
    else:  # triangulaire symétrique de sommet 0
        F = np.where(x <= 0, (x + h) ** 2 / (2 * h * h), 1 - (h - x) ** 2 / (2 * h * h))
    return np.diff(F)


def ppmExact(res: dict) -> float | None:
    """ppm hors [jmin ; jmax] en tenant compte de la loi de chaque maillon (la formule normale n'est exacte qu'en normal).

    Le jeu vaut J = μ + N + S : N regroupe les maillons normaux et ceux à σ mesuré (loi normale, comme dans le
    Monte-Carlo), traités analytiquement ; S, somme centrée des maillons uniformes et triangulaires, a un support
    borné et se calcule par convolution de leurs masses de probabilité. La queue reste exacte même pour des ppm
    minuscules. μ est la moyenne du procédé (décentrage et moyennes mesurées compris).

    Entrée : res (sortie de solveurChaine). Sortie : ppm, ou None si tous les maillons sont normaux (la formule
    ppmHorsTolerance est alors exacte), s'il n'y a aucune limite ou si le jeu ne varie pas.
    """
    c = res["condition"]
    if not (math.isfinite(c["jmin"]) or math.isfinite(c["jmax"])) or not res["CF_sigma"] > 0:
        return None
    k, a, it = res["k_sigma"], np.abs(np.asarray(res["coef"], dtype=float)), np.asarray(res["IT"], dtype=float)
    mesure = np.asarray(res["sigma_reel"], dtype=float)
    varN, bornees = 0.0, []
    for i, loi in enumerate(res["loi"]):
        if not np.isnan(mesure[i]):
            varN += (a[i] * mesure[i]) ** 2
        elif loi == "normale":
            varN += (a[i] * it[i] / (2 * k)) ** 2
        elif a[i] * it[i] > 0:
            bornees.append((loi, a[i] * it[i] / 2))
    if not bornees:
        return None
    etendue = sum(h for _, h in bornees)
    pas = etendue / 4000
    masses = np.ones(1)
    for loi, h in bornees:
        masses = fftconvolve(masses, _masseCellules(loi, h, pas))
    masses = np.clip(masses, 0.0, None)
    masses /= masses.sum()
    s = (np.arange(len(masses)) - (len(masses) - 1) / 2) * pas  # support centré : la grille est symétrique
    mu, sigmaN = res["CF_moy_proc"], math.sqrt(varN)
    if sigmaN > 0:
        p = np.zeros_like(s)
        if math.isfinite(c["jmin"]):
            p += phi((c["jmin"] - mu - s) / sigmaN)
        if math.isfinite(c["jmax"]):
            p += phi((mu + s - c["jmax"]) / sigmaN)
        return float(1e6 * np.sum(masses * p))
    x = mu + s
    return float(1e6 * np.sum(masses[(x < c["jmin"] - TOL_COMPARAISON) | (x > c["jmax"] + TOL_COMPARAISON)]))


def capabilites(mu: float, sigma: float, jmin: float, jmax: float) -> dict:
    """Indices de capabilité du jeu (port de capabilites de graphiques.m).

    Entrées : mu, sigma (mm), jmin, jmax (mm, infinis acceptés).
    Sortie : dict cp (nan si une limite manque), cpk (nan si sigma = 0 ou aucune limite).
    """
    if not sigma > 0:
        return {"cp": math.nan, "cpk": math.nan}
    cotes = []
    if math.isfinite(jmin):
        cotes.append((mu - jmin) / (3 * sigma))
    if math.isfinite(jmax):
        cotes.append((jmax - mu) / (3 * sigma))
    cp = (jmax - jmin) / (6 * sigma) if math.isfinite(jmin) and math.isfinite(jmax) else math.nan
    return {"cp": cp, "cpk": min(cotes) if cotes else math.nan}


def capabilitesMaillons(res: dict) -> list[dict]:
    """Cp et Cpk de chaque cote de la chaîne, avec les mesures de l'atelier quand elles existent.

    Entrée : res (sortie de solveurChaine). L'écart type d'une cote est celui mesuré (sigma_reel) sinon celui de sa
    loi (IT / 2k en loi normale) ; sa moyenne est celle mesurée (moyenne_reelle) sinon la cote moyenne.
    Sortie : liste (ordre des maillons) de dict nom, mesure (bool : au moins une valeur mesurée), sigma, moyenne (mm),
    cp = IT / 6σ et cpk = min(cote maxi − moyenne ; moyenne − cote mini) / 3σ (nan si σ = 0).
    """
    sortie = []
    for i, nom in enumerate(res["Nom"]):
        m, it = res["maillons"][i], float(res["IT"][i])
        sigma = m["sigma_reel"] if m["sigma_reel"] is not None else it * coefficientSigma(m["loi"], res["k_sigma"])
        moyenne = m["moyenne_reelle"] if m["moyenne_reelle"] is not None else float(res["C_moy"][i])
        haut, bas = m["cote"] + m["es"], m["cote"] + m["ei"]
        ok = sigma > 0
        sortie.append(
            {
                "nom": nom,
                "mesure": m["sigma_reel"] is not None or m["moyenne_reelle"] is not None,
                "sigma": sigma,
                "moyenne": moyenne,
                "cp": it / (6 * sigma) if ok else math.nan,
                "cpk": min(haut - moyenne, moyenne - bas) / (3 * sigma) if ok else math.nan,
            }
        )
    return sortie


def contributions(res: dict) -> list[dict]:
    """Contribution de chaque maillon au jeu (Pareto, port de graph_pareto).

    Entrée : res (sortie de solveurChaine).
    Sortie : liste de dict nom, pireCas (mm, |a_i|·IT_i/2), partPireCas (%), variance (mm², σ_i²),
    partVariance (%), dans l'ordre des maillons.
    """
    wc = np.abs(res["coef"]) * res["IT"] / 2
    vr = np.asarray(res["sigma_i"]) ** 2
    swc, svr = wc.sum(), vr.sum()
    return [
        {
            "nom": n,
            "pireCas": float(w),
            "partPireCas": float(100 * w / swc) if swc > 0 else 0.0,
            "variance": float(v),
            "partVariance": float(100 * v / svr) if svr > 0 else 0.0,
        }
        for n, w, v in zip(res["Nom"], wc, vr, strict=True)
    ]


def sansLimite(condition: dict) -> bool:
    """Vrai si la cote condition n'a ni Jmin ni Jmax (res["condition"], bornes en ±inf)."""
    return not (math.isfinite(condition["jmin"]) or math.isfinite(condition["jmax"]))


def libelleVerdict(ok: bool, condition: dict) -> str:
    """Verdict écrit d'une plage du jeu face à [Jmin ; Jmax] : le seul vocabulaire de l'application.

    Entrées : ok (la plage tient dans les limites), condition (res["condition"]).
    Sortie : « Conforme », « Non conforme », ou « Sans limite » si aucune limite n'est exigée.
    """
    if sansLimite(condition):
        return "Sans limite"
    return "Conforme" if ok else "Non conforme"


def verdicts(res: dict) -> dict:
    """Verdicts du jeu face à la cote condition (pire des cas, RSS ± kσ, RSS ± 6σ, comme graph_comparaison).

    Entrée : res (sortie de solveurChaine).
    Sortie : dict pireCas, rssK, rss6 : chacun dict min, max (mm), ok (bool) ; plus cp, cpk, ppm (loi normale,
    moyenne décentrée si le réglage decentrage est > 0 ; rssK et rss6 restent centrés sur CF_moy) et rssProc
    (± kσ autour de la moyenne du procédé : c'est elle qui décide du verdict « conforme en statistique »).
    """
    c = res["condition"]
    mu, sg, k = res["CF_moy"], res["CF_sigma"], res["k_sigma"]
    muProc = res["CF_moy_proc"]

    def plage(lo, hi):
        return {"min": lo, "max": hi, "ok": bool(lo >= c["jmin"] - TOL_COMPARAISON and hi <= c["jmax"] + TOL_COMPARAISON)}

    cap = capabilites(muProc, sg, c["jmin"], c["jmax"])
    return {
        "pireCas": plage(res["CF_min"], res["CF_max"]),
        "rssK": plage(mu - k * sg, mu + k * sg),
        "rss6": plage(mu - 6 * sg, mu + 6 * sg),
        "rssProc": plage(muProc - k * sg, muProc + k * sg),
        "cp": cap["cp"],
        "cpk": cap["cpk"],
        "ppm": ppmHorsTolerance(muProc, sg, c["jmin"], c["jmax"]),
    }


def risqueSelonCp(res: dict, cps=None) -> dict:
    """Risque hors tolérance (ppm) selon le Cp du procédé d'usinage (port de graph_risque_cp).

    Entrées : res (sortie de solveurChaine), cps (liste de Cp, défaut 1 ; 1,33 ; 1,67 ; 2).
    σ du jeu pour un Cp donné : σ_J(1) / Cp, avec σ_J(1) = √Σ (|a_i| IT_i / 6)² (lois et σ mesurés ignorés).
    La moyenne est celle du procédé (CF_moy_proc, décentrage compris, décalage en mm gardé fixe).
    Sortie : dict cp (liste), ppm (liste).
    """
    cps = [1.0, 1.33, 1.67, 2.0] if cps is None else list(cps)
    c = res["condition"]
    # σ_J pour IT = 6σ (Cp = 1), quelle que soit la loi saisie ou le σ mesuré : le graphique fait varier le procédé
    sg1 = float(np.sqrt(np.sum((np.abs(res["coef"]) * res["IT"] / 6) ** 2)))
    return {"cp": cps, "ppm": [ppmHorsTolerance(res["CF_moy_proc"], sg1 / x, c["jmin"], c["jmax"]) for x in cps]}


def jeuSelonTemperature(res: dict, temperatures) -> dict:
    """Jeu nominal, mini et maxi pour une température uniforme balayée (port de graph_jeu_temperature).

    Entrées : res (sortie de solveurChaine), temperatures (°C). L'α de chaque maillon lié à un matériau est
    recalculé à chaque température (courbes du classeur) ; sinon l'α du calcul est gardé.
    Sortie : dict T, nom, min, max (listes, mm).
    """
    Tb = np.asarray(temperatures, dtype=float)
    tref = res["Tref"]
    AL = np.tile(res["alpha"][:, None], (1, len(Tb)))
    for i, m in enumerate(res["maillons"]):
        if m["materiau"] and m["materiau"] != PERSONNALISE:
            a = alphaMateriau(m["materiau"], Tb, tref)["alpha"]
            if not np.any(np.isnan(a)):
                AL[i, :] = a
    nom, jmin, jmax = [], [], []
    for j, t in enumerate(Tb):
        a = res["proj"] * (1 + AL[:, j] * (t - tref))
        nom.append(float(np.sum(res["Cote"] * a)))
        mo = float(np.sum(res["C_moy"] * a))
        d = float(np.sum(np.abs(a) * res["IT"] / 2))
        jmin.append(mo - d)
        jmax.append(mo + d)
    return {"T": list(Tb), "nom": nom, "min": jmin, "max": jmax}
