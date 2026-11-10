"""Construction d'une chaîne de cotes à partir des pièces, de leurs surfaces et de leurs contacts.

Modèle (cotation fonctionnelle) : les nœuds sont les surfaces « Pièce.surface » ; une cote relie deux surfaces
d'une même
pièce (la seconde est à `cote` de la première, dans le sens positif de l'axe) ; un contact relie deux surfaces de pièces
différentes placées au même endroit. Le jeu à étudier va d'une surface de départ à une surface d'arrivée :
J = position(arrivée) − position(départ). Une chaîne est un chemin de départ à arrivée ; chaque cote parcourue dans son
sens compte « + », à l'envers « − ». La chaîne minimale est le chemin qui traverse le moins de cotes : elle ne passe
normalement qu'une fois par pièce. Ce module n'importe ni streamlit ni plotly.
"""

from collections import deque

from chainecotes.core.chaine import estVide
from chainecotes.core.donnees import chargerJson
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.nombres import fr

MAX_CHAINES = 12  # chaînes de même longueur proposées au plus
MAX_COTES = 400
_ID = "Chaine:Construction:"


def surface(piece: str, nom: str) -> str:
    """Identifiant « Pièce.surface » d'une surface. Entrées : textes. Sortie : texte."""
    return f"{str(piece).strip()}.{str(nom).strip()}"


def exempleAssistant() -> dict:
    """Exemple de l'assistant (data/assistant_exemple.json) : arbre dans un carter fermé par un couvercle."""
    return chargerJson("assistant_exemple.json")


def surfaces(cotes: list[dict]) -> list[str]:
    """Surfaces « Pièce.surface » citées par les cotes complètes, sans doublon, dans l'ordre."""
    noeuds = []
    for c in cotes:
        piece = str(c.get("piece") or "").strip()
        for cle in ("de", "vers"):
            if piece and not estVide(c.get(cle)):
                noeuds.append(surface(piece, c[cle]))
    return list(dict.fromkeys(noeuds))


def _lireCotes(cotes: list[dict]) -> list[dict]:
    """Cotes contrôlées : dict piece, de, vers (surfaces locales), cote ≥ 0, puis noeudDe, noeudVers, ligne."""
    if len(cotes) > MAX_COTES:
        raise ErreurChaine(_ID + "taille", f"Trop de cotes ({len(cotes)}, {MAX_COTES} au plus).")
    sortie = []
    for i, c in enumerate(cotes, start=1):
        piece, de, vers = (str(c.get(k) or "").strip() for k in ("piece", "de", "vers"))
        if not (piece and de and vers):
            raise ErreurChaine(_ID + "cote", f"Cote {i} : la pièce et les deux surfaces doivent être renseignées.")
        if de == vers:
            raise ErreurChaine(_ID + "cote", f"Cote {i} ({piece}) : les deux surfaces doivent être différentes.")
        try:
            valeur = float(c.get("cote"))
        except (TypeError, ValueError):
            raise ErreurChaine(_ID + "cote", f"Cote {i} ({piece}) : la cote nominale doit être un nombre.") from None
        if not valeur >= 0:
            raise ErreurChaine(
                _ID + "cote", f"Cote {i} ({piece}) : la cote doit être positive ; inversez « de » et « vers »."
            )
        sortie.append({**c, "piece": piece, "de": de, "vers": vers, "cote": valeur, "ligne": i,
                       "noeudDe": surface(piece, de), "noeudVers": surface(piece, vers)})  # fmt: skip
    return sortie


def _lireContacts(contacts: list[dict], noeuds: set[str]) -> list[tuple[str, str]]:
    """Contacts (a, b) entre deux surfaces connues, de pièces différentes."""
    sortie = []
    for i, c in enumerate(contacts, start=1):
        a, b = (str(c.get(k) or "").strip() for k in ("a", "b"))
        if not (a and b):
            continue  # ligne vide du tableau
        for x in (a, b):
            if x not in noeuds:
                raise ErreurChaine(_ID + "contact", f"Contact {i} : la surface « {x} » n'existe dans aucune cote.")
        if a.split(".", 1)[0] == b.split(".", 1)[0]:
            raise ErreurChaine(_ID + "contact", f"Contact {i} : {a} et {b} sont sur la même pièce.")
        sortie.append((a, b))
    return sortie


def lireSaisie(cotes: list[dict], contacts: list[dict]) -> tuple[list[dict], list[tuple[str, str]]]:
    """Cotes et contacts contrôlés, prêts pour `positions` et la figure.

    Entrées : cotes et contacts, comme pour construireChaines. Sortie : (cotes lues, contacts (a, b)).
    Erreur : ErreurChaine si une cote ou un contact est invalide.
    """
    lues = _lireCotes(cotes)
    return lues, _lireContacts(contacts, {n for c in lues for n in (c["noeudDe"], c["noeudVers"])})


def _graphe(cotes: list[dict], contacts: list[tuple[str, str]]) -> dict[str, list[tuple[str, int, int | None]]]:
    """Voisins de chaque surface : (voisin, sens +1/−1 parcouru, indice de la cote ou None pour un contact)."""
    voisins: dict[str, list] = {}
    for i, c in enumerate(cotes):
        voisins.setdefault(c["noeudDe"], []).append((c["noeudVers"], 1, i))
        voisins.setdefault(c["noeudVers"], []).append((c["noeudDe"], -1, i))
    for a, b in contacts:
        voisins.setdefault(a, []).append((b, 0, None))
        voisins.setdefault(b, []).append((a, 0, None))
    return voisins


def _groupes(voisins: dict) -> list[list[str]]:
    """Composantes connexes (listes de surfaces), dans l'ordre de découverte."""
    vus, groupes = set(), []
    for depart in voisins:
        if depart in vus:
            continue
        groupe, file = [], deque([depart])
        vus.add(depart)
        while file:
            x = file.popleft()
            groupe.append(x)
            for y, _, _ in voisins[x]:
                if y not in vus:
                    vus.add(y)
                    file.append(y)
        groupes.append(groupe)
    return groupes


def _distances(voisins: dict, but: str) -> dict[str, int]:
    """Nombre minimal de cotes entre chaque surface et `but` (un contact ne compte pas) : parcours 0-1."""
    dist = {but: 0}
    file = deque([but])
    while file:
        x = file.popleft()
        for y, _, i in voisins[x]:
            poids = 0 if i is None else 1
            if y not in dist or dist[x] + poids < dist[y]:
                dist[y] = dist[x] + poids
                (file.appendleft if poids == 0 else file.append)(y)
    return dist


def positions(cotes: list[dict], contacts: list[tuple[str, str]], origine: str) -> tuple[dict[str, float], list[str]]:
    """Position nominale de chaque surface (mm) en partant de `origine` (position 0), et incohérences trouvées.

    Les surfaces non reliées à l'origine sont placées à part, chaque groupe à partir de 0. Une boucle dont la somme
    des cotes n'est pas nulle (cotes redondantes incompatibles) est signalée ; la première position trouvée est gardée.
    """
    voisins = _graphe(cotes, contacts)
    pos, incoherences = {}, []
    ordre = [origine, *[x for x in voisins if x != origine]]
    for racine in ordre:
        if racine in pos:
            continue
        pos[racine] = 0.0
        file = deque([racine])
        while file:
            x = file.popleft()
            for y, sens, i in voisins[x]:
                p = pos[x] + (sens * cotes[i]["cote"] if i is not None else 0.0)
                if y not in pos:
                    pos[y] = p
                    file.append(y)
                elif abs(pos[y] - p) > 1e-9:
                    incoherences.append(f"{x} → {y} : {fr(p, 'g')} mm au lieu de {fr(pos[y], 'g')} mm")
    return pos, list(dict.fromkeys(incoherences))


def construireChaines(cotes: list[dict], contacts: list[dict], depart: str, arrivee: str) -> list[dict]:
    """Chaînes de cotes les plus courtes entre deux surfaces.

    Entrées : cotes (liste de dict piece, de, vers (surfaces de la pièce), cote (mm, ≥ 0 : `vers` est à `cote` de `de`),
    et facultatifs nom, iso, es, ei, loi), contacts (liste de dict a, b : surfaces « Pièce.surface » au même endroit),
    depart et arrivee (surfaces « Pièce.surface » : le jeu J est la position d'arrivée moins celle de départ).
    Sortie : liste (au plus MAX_CHAINES) de dict maillons (liste de maillons du problème, dans l'ordre du parcours),
    surfaces (suite des surfaces traversées), pieces (suite des pièces des cotes), nominal (Σ sens · cote, mm),
    avertissements (liste de textes, par exemple plusieurs cotes d'une même pièce), cotes (indices des cotes utilisées).
    Erreur : ErreurChaine si une saisie est invalide, si le départ ou l'arrivée est inconnu ou identique, ou si les deux
    surfaces ne sont reliées par aucun chemin (le message nomme les groupes de pièces séparés).
    """
    lues, liens = lireSaisie(cotes, contacts)
    noeuds = {n for c in lues for n in (c["noeudDe"], c["noeudVers"])}
    for nom, x in (("de départ", depart), ("d'arrivée", arrivee)):
        if x not in noeuds:
            raise ErreurChaine(_ID + "extremite", f"La surface {nom} « {x} » n'existe dans aucune cote.")
    if depart == arrivee:
        raise ErreurChaine(_ID + "extremite", "Les surfaces de départ et d'arrivée du jeu doivent être différentes.")
    voisins = _graphe(lues, liens)
    dist = _distances(voisins, arrivee)
    if depart not in dist:
        groupes = _groupes(voisins)
        pieces = lambda g: sorted({x.split(".", 1)[0] for x in g})  # noqa: E731
        g1 = next(g for g in groupes if depart in g)
        g2 = next(g for g in groupes if arrivee in g)
        raise ErreurChaine(
            _ID + "nonRelie",
            f"Aucun chemin entre {depart} et {arrivee}. Pièces du côté du départ : {', '.join(pieces(g1))} ; "
            f"du côté de l'arrivée : {', '.join(pieces(g2))}. Il manque un contact entre ces deux groupes "
            "(ou une cote qui relie deux surfaces d'une même pièce).",
        )
    chemins: list[list[tuple[str, int, int | None]]] = []

    def parcourir(x: str, vus: set[str], trace: list) -> None:
        if len(chemins) >= MAX_CHAINES:
            return
        if x == arrivee:
            chemins.append(list(trace))
            return
        for y, sens, i in voisins[x]:
            poids = 0 if i is None else 1
            if y not in vus and y in dist and dist[y] + poids == dist[x]:
                trace.append((y, sens, i))
                parcourir(y, vus | {y}, trace)
                trace.pop()

    parcourir(depart, {depart}, [])
    if not any(ch and any(i is not None for _, _, i in ch) for ch in chemins):
        raise ErreurChaine(
            _ID + "contactDirect",
            f"{depart} et {arrivee} sont en contact direct : le jeu est nul, il n'y a aucune cote à additionner.",
        )
    sortie = []
    for chemin in chemins:
        maillons, surfaces, pieces, utilisees, nominal = [], [depart], [], [], 0.0
        for y, sens, i in chemin:
            surfaces.append(y)
            if i is None:
                continue
            c = lues[i]
            signe = "+" if sens > 0 else "-"
            maillons.append(
                {
                    "nom": str(c.get("nom") or "").strip() or f"{c['piece']} : {c['de']} → {c['vers']}",
                    "sens": signe,
                    "cote": c["cote"],
                    "iso": None if estVide(c.get("iso")) else str(c["iso"]).strip(),
                    "es": None if estVide(c.get("es")) else float(c["es"]),
                    "ei": None if estVide(c.get("ei")) else float(c["ei"]),
                    "loi": "normale" if estVide(c.get("loi")) else str(c["loi"]).strip(),
                    "materiau": None,
                    "alpha": None,
                    "tservice": None,
                }
            )
            pieces.append(c["piece"])
            utilisees.append(i)
            nominal += sens * c["cote"]
        avertissements = []
        for p in dict.fromkeys(pieces):
            if pieces.count(p) > 1:
                avertissements.append(
                    f"La pièce « {p} » apparaît dans {pieces.count(p)} cotes de la chaîne : une chaîne minimale n'a "
                    "qu'une cote par pièce. Ses cotes ne sont pas indépendantes (cotation en cascade ?) : "
                    "préférez une cote directe entre les deux surfaces qui touchent le reste de la chaîne."
                )
        sortie.append(
            {
                "maillons": maillons,
                "surfaces": surfaces,
                "pieces": pieces,
                "nominal": nominal,
                "avertissements": avertissements,
                "cotes": utilisees,
            }  # fmt: skip
        )
    return sortie
