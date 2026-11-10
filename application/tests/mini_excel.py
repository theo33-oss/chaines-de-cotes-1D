"""Petit évaluateur de formules Excel pour les tests (pas de LibreOffice sur les machines de test).

Couvre ce qu'écrit services/feuille_chaine : nombres, textes, références (A1, $A$1, A1:B2), + - * / ^, comparaisons
et les fonctions IF (paresseuse), AND, OR, NOT, ISNUMBER, ABS, COS, RADIANS, SQRT, SUM, MIN, MAX, NORMSDIST.
"""

import math
import re

_JETON = re.compile(
    r"""\s*(?:
    (?P<nombre>\d+\.?\d*(?:[Ee][+-]?\d+)?)|
    (?P<texte>"[^"]*")|
    (?P<plage>\$?[A-Z]{1,3}\$?\d+:\$?[A-Z]{1,3}\$?\d+)|
    (?P<ref>\$?[A-Z]{1,3}\$?\d+)|
    (?P<fonction>[A-Z][A-Z0-9.]*)\(|
    (?P<op><=|>=|<>|[-+*/^=<>(),])
    )""",
    re.VERBOSE,
)


def _jetons(formule: str) -> list[tuple[str, str]]:
    sortie, i = [], 0
    while i < len(formule):
        m = _JETON.match(formule, i)
        if not m or m.end() == i:
            raise ValueError(f"formule illisible en {i} : {formule!r}")
        i = m.end()
        genre = m.lastgroup
        sortie.append((genre, m.group(genre) if genre != "texte" else m.group("texte")[1:-1]))
    return sortie


def _adresse(ref: str) -> tuple[int, int]:
    m = re.fullmatch(r"\$?([A-Z]+)\$?(\d+)", ref)
    colonne = 0
    for lettre in m[1]:
        colonne = colonne * 26 + ord(lettre) - 64
    return int(m[2]), colonne


def _zero(x):
    """Case vide lue comme 0 dans une opération, comme Excel."""
    return 0 if x is None else x


def _normsdist(z: float) -> float:
    return 0.5 * math.erfc(-z / math.sqrt(2))


class Feuille:
    """Évalue les cellules d'une feuille openpyxl, récursivement, avec mémoire."""

    def __init__(self, ws):
        self.ws, self.memo = ws, {}

    def valeur(self, ref: str):
        ligne, colonne = _adresse(ref)
        cle = (ligne, colonne)
        if cle not in self.memo:
            v = self.ws.cell(ligne, colonne).value
            self.memo[cle] = self.evaluer(v[1:]) if isinstance(v, str) and v.startswith("=") else v
        return self.memo[cle]

    def evaluer(self, formule: str):
        ancien = (getattr(self, "jetons", None), getattr(self, "pos", 0))  # une référence relance une analyse
        self.jetons, self.pos = _jetons(formule), 0
        try:
            v = self._comparaison()
            if self.pos != len(self.jetons):
                raise ValueError(f"reste après la formule : {formule!r}")
            return v
        finally:
            self.jetons, self.pos = ancien

    # --- analyse récursive : chaque méthode lit les jetons et rend une valeur
    def _suivant(self):
        """(genre, texte) du jeton suivant ; le texte d'une chaîne « + » n'est pas un opérateur."""
        if self.pos >= len(self.jetons):
            return None, None
        genre, texte = self.jetons[self.pos]
        return genre, texte if genre == "op" else None

    def _comparaison(self):
        gauche = self._somme()
        while self._suivant()[1] in ("=", "<>", "<", ">", "<=", ">="):
            op = self.jetons[self.pos][1]
            self.pos += 1
            droite = self._somme()
            gauche, droite = _zero(gauche), _zero(droite)
            gauche = {
                "=": lambda a, b: a == b,
                "<>": lambda a, b: a != b,
                "<": lambda a, b: a < b,
                ">": lambda a, b: a > b,
                "<=": lambda a, b: a <= b,
                ">=": lambda a, b: a >= b,
            }[op](gauche, droite)
        return gauche

    def _somme(self):
        v = self._produit()
        while self._suivant()[1] in ("+", "-"):
            op = self.jetons[self.pos][1]
            self.pos += 1
            w = self._produit()
            v = _zero(v) + _zero(w) if op == "+" else _zero(v) - _zero(w)
        return v

    def _produit(self):
        v = self._puissance()
        while self._suivant()[1] in ("*", "/"):
            op = self.jetons[self.pos][1]
            self.pos += 1
            w = self._puissance()
            v = _zero(v) * _zero(w) if op == "*" else _zero(v) / _zero(w)
        return v

    def _puissance(self):
        v = self._unaire()
        while self._suivant()[1] == "^":
            self.pos += 1
            v = v ** self._unaire()
        return v

    def _unaire(self):
        if self._suivant()[1] in ("-", "+"):
            signe = -1 if self.jetons[self.pos][1] == "-" else 1
            self.pos += 1
            return signe * self._unaire()
        return self._primaire()

    def _plage(self, texte: str) -> list:
        a, b = texte.split(":")
        (l1, c1), (l2, c2) = _adresse(a), _adresse(b)
        return [self.valeur(f"{chr(64 + c)}{ligne}") for ligne in range(l1, l2 + 1) for c in range(c1, c2 + 1)]

    def _primaire(self):
        genre, texte = self.jetons[self.pos]
        self.pos += 1
        if genre == "nombre":
            return float(texte)
        if genre == "texte":
            return texte
        if genre == "ref":
            return self.valeur(texte)
        if genre == "plage":
            return self._plage(texte)
        if genre == "op" and texte == "(":
            v = self._comparaison()
            self.pos += 1  # ')'
            return v
        if genre == "fonction":
            return self._fonction(texte)
        raise ValueError(f"jeton inattendu {texte!r}")

    def _argument_paresseux(self):
        """Lit un argument sans l'évaluer : rend sa position de départ et avance après lui."""
        depart, profondeur = self.pos, 0
        while True:
            genre, texte = self.jetons[self.pos]
            if profondeur == 0 and genre == "op" and texte in (",", ")"):
                return depart
            if genre == "fonction" or (genre == "op" and texte == "("):
                profondeur += 1
            elif genre == "op" and texte == ")":
                profondeur -= 1
            self.pos += 1

    def _fonction(self, nom: str):
        if nom == "IF":
            positions = []
            while True:
                positions.append(self._argument_paresseux())
                fin = self.pos
                self.pos += 1
                if self.jetons[fin][1] == ")":
                    break
            apres = self.pos
            self.pos = positions[0]
            condition = self._comparaison()
            choisi = positions[1] if condition else (positions[2] if len(positions) > 2 else None)
            if choisi is None:
                self.pos = apres
                return False
            self.pos = choisi
            v = self._comparaison()
            self.pos = apres
            return v
        args = []
        if self._suivant()[1] != ")":
            while True:
                args.append(self._comparaison())
                if self.jetons[self.pos][1] == ",":
                    self.pos += 1
                    continue
                break
        self.pos += 1  # ')'
        plat = [x for a in args for x in (a if isinstance(a, list) else [a])]
        nombres = [x for x in plat if isinstance(x, (int, float)) and not isinstance(x, bool)]
        return {
            "AND": lambda: all(plat),
            "OR": lambda: any(plat),
            "NOT": lambda: not args[0],
            "ISNUMBER": lambda: isinstance(args[0], (int, float)) and not isinstance(args[0], bool),
            "ABS": lambda: abs(args[0]),
            "COS": lambda: math.cos(args[0]),
            "RADIANS": lambda: math.radians(args[0]),
            "SQRT": lambda: math.sqrt(args[0]),
            "SUM": lambda: sum(nombres),
            "MIN": lambda: min(nombres),
            "MAX": lambda: max(nombres),
            "NORMSDIST": lambda: _normsdist(args[0]),
        }[nom]()
