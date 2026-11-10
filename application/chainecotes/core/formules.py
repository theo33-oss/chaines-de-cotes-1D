"""Formules en vrais caractères : conversion du LaTeX utilisé par l'application en HTML simple.

Les formules des explications sont écrites en LaTeX (fractions, racines, indices, sommes). Ce module les transforme en
texte lisible, avec les caractères Unicode (∑, √, ×, σ, µ…), des indices et exposants (<sub>, <sup>) et des
fractions écrites « (numérateur) / (dénominateur) ». Aucune image, aucune police mathématique, aucun script distant : le résultat s'affiche
dans une étiquette Qt comme dans un navigateur. Pur Python : n'importe ni Qt ni matplotlib.
"""

import html

GRECQUES = {
    "alpha": "α", "beta": "β", "delta": "δ", "Delta": "Δ", "mu": "µ", "sigma": "σ", "Sigma": "Σ", "theta": "θ",
    "Phi": "Φ", "phi": "φ", "lambda": "λ", "epsilon": "ε", "pi": "π",
}  # fmt: skip
SYMBOLES = {
    "sum": "∑", "times": " × ", "cdot": " · ", "pm": " ± ", "mp": " ∓ ", "min": "min", "max": "max", "cos": "cos",
    "sin": "sin", "infty": "∞", "circ": "°", "ldots": "…", "cdots": "⋯", "le": " ≤ ", "ge": " ≥ ", "neq": " ≠ ",
    "approx": " ≈ ", "ln": "ln", "exp": "exp", "log": "log", "lim": "lim", "to": " → ",
    "quad": "&nbsp;" * 4, "qquad": "&nbsp;" * 8, ",": "&thinsp;", ";": "&nbsp;", " ": " ", "!": "", "left": "",
    "right": "", "displaystyle": "",
}  # fmt: skip


def _jetons(tex: str) -> list[tuple[str, str]]:
    """Découpe le LaTeX en jetons (genre, valeur) : caractère, commande, accolade, indice ou exposant."""
    jetons, i = [], 0
    while i < len(tex):
        c = tex[i]
        if c == "\\":
            if i + 1 < len(tex) and tex[i + 1].isalpha():
                j = i + 1
                while j < len(tex) and tex[j].isalpha():
                    j += 1
                jetons.append(("cmd", tex[i + 1 : j]))
                i = j
                while i < len(tex) and tex[i] == " ":  # LaTeX ignore les espaces qui suivent un nom de commande
                    i += 1
            else:
                jetons.append(("cmd", tex[i + 1 : i + 2]))
                i += 2
            continue
        if c == "{":
            jetons.append(("ouvre", c))
        elif c == "}":
            jetons.append(("ferme", c))
        elif c == "_":
            jetons.append(("indice", c))
        elif c == "^":
            jetons.append(("exposant", c))
        else:
            jetons.append(("char", c))
        i += 1
    return jetons


class _Convertisseur:
    def __init__(self, tex: str):
        self.j = _jetons(tex)
        self.p = 0

    def _suivant(self):
        return self.j[self.p] if self.p < len(self.j) else (None, None)

    def sequence(self, dans_groupe: bool) -> str:
        """Suite de jetons jusqu'à la fin, ou jusqu'à l'accolade fermante si dans_groupe."""
        sortie = []
        while self.p < len(self.j):
            genre, val = self.j[self.p]
            if genre == "ferme":
                self.p += 1
                if dans_groupe:
                    break
                continue
            sortie.append(self.unite(genre, val))
        return "".join(sortie)

    def unite(self, genre: str, val: str) -> str:
        """Un élément : caractère, commande, groupe, avec son éventuel indice ou exposant."""
        if genre == "indice" or genre == "exposant":
            self.p += 1
            balise = "sub" if genre == "indice" else "sup"
            return f"<{balise}>{self.argument()}</{balise}>"
        self.p += 1
        if genre == "ouvre":
            return self.sequence(True)
        if genre == "char":
            return html.escape(val, quote=False)
        return self.commande(val)

    def argument(self) -> str:
        """Argument d'une commande ou d'un indice : un groupe, une commande ou un seul caractère."""
        while self._suivant() == ("char", " "):
            self.p += 1
        genre, val = self._suivant()
        if genre is None:
            return ""
        self.p += 1
        if genre == "ouvre":
            return self.sequence(True)
        if genre == "cmd":
            return self.commande(val)
        return html.escape(val, quote=False)

    def brut(self) -> str:
        """Contenu d'un groupe pris tel quel (texte de \\text, crochets de racine)."""
        genre, _ = self._suivant()
        if genre != "ouvre":
            return self.argument()
        self.p += 1
        profondeur, morceaux = 1, []
        while self.p < len(self.j):
            genre, val = self.j[self.p]
            self.p += 1
            if genre == "ouvre":
                profondeur += 1
            elif genre == "ferme":
                profondeur -= 1
                if profondeur == 0:
                    break
            morceaux.append(val)
        return html.escape("".join(morceaux), quote=False)

    def commande(self, nom: str) -> str:
        if nom == "frac":
            num, den = self.argument(), self.argument()
            return f'<span style="white-space:nowrap;">({num})&thinsp;/&thinsp;({den})</span>'
        if nom == "sqrt":
            indice = ""
            genre, val = self._suivant()
            if genre == "char" and val == "[":
                self.p += 1
                morceaux = []
                while self.p < len(self.j) and self.j[self.p] != ("char", "]"):
                    morceaux.append(self.j[self.p][1])
                    self.p += 1
                self.p += 1
                indice = "".join(morceaux)
            contenu = self.argument()
            racine = {"3": "∛"}.get(indice, "√")
            return f"{racine}({contenu})"
        if nom == "text" or nom == "mathrm":
            return self.brut()
        if nom == "bar":
            return self.argument() + "&#x0304;"
        if nom in GRECQUES:
            return GRECQUES[nom]
        if nom in SYMBOLES:
            return SYMBOLES[nom]
        return html.escape(nom, quote=False)


def texVersHtml(tex: str) -> str:
    """Formule LaTeX (sous-ensemble utilisé par l'application) en HTML avec de vrais caractères.

    Entrée : tex (texte LaTeX, sans les signes $). Sortie : fragment HTML (fractions écrites « (numérateur) / (dénominateur) », indices et
    exposants en <sub> et <sup>, symboles Unicode). En cas de syntaxe inattendue, le texte brut est rendu tel quel
    (sans barres obliques) plutôt que de planter.
    """
    try:
        rendu = _Convertisseur(tex).sequence(False)
    except (IndexError, ValueError):
        rendu = html.escape(tex.replace("\\", ""), quote=False)
    return rendu
