"""Page « Assistant de chaîne » : des pièces, leurs surfaces et leurs contacts à la chaîne de cotes minimale.

L'utilisateur décrit chaque pièce par ses cotes (entre deux de ses surfaces) et les contacts entre pièces, puis
choisit les deux surfaces dont il veut étudier le jeu. L'assistant cherche les chaînes qui traversent le moins de cotes
(chainecotes.core.construction), contrôle « une cote par pièce », dessine le plan et envoie la chaîne choisie à la page
Calcul.
"""

import copy
from typing import Any

import pandas as pd

from chainecotes.bureau import state
from chainecotes.bureau.widgets import Colonne, Page, TableauEditable, Zone
from chainecotes.core.chaine import LOIS, estVide
from chainecotes.core.construction import construireChaines, lireSaisie, surface
from chainecotes.core.donnees import chargerJson
from chainecotes.core.errors import ErreurChaine
from chainecotes.plots._common import fr
from chainecotes.plots.assistant import figureConstruction

COTES, CONTACTS = "asst.cotes", "asst.contacts"
COLONNES_COTES = [
    Colonne("piece", "Pièce"),
    Colonne("de", "De (surface)", aide="Surface de départ de la cote, ex. « fond »."),
    Colonne("vers", "Vers (surface)", aide="Surface d'arrivée, à `cote` de la première."),
    Colonne("cote", "Cote (mm)", "nombre", fmt="%.3f", mini=0.0),
    Colonne("iso", "ISO 286", aide="Ex. H7 ou g6 ; vide si les écarts sont saisis."),
    Colonne("es", "ES (mm)", "nombre", fmt="%.4f"),
    Colonne("ei", "EI (mm)", "nombre", fmt="%.4f"),
    Colonne("loi", "Loi", "liste", list(LOIS)),
    Colonne("nom", "Nom du maillon", aide="Facultatif : sinon « Pièce : de → vers »."),
]


def exemple() -> dict:
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


class PageAssistant(Page):
    def rendre(self, z: Zone) -> None:
        z.titre("Assistant de construction de chaîne")
        z.texte(
            "Décrivez les pièces par leurs **cotes** (entre deux de leurs surfaces) et les **contacts** entre pièces, "
            "puis choisissez les deux surfaces dont vous voulez le jeu. L'assistant trouve la **chaîne minimale** (le "
            "moins de cotes possible, une seule par pièce), dessine le plan et prépare le calcul."
        )
        if COTES not in state.v:
            self._charger(False)
        c = z.colonnes(2)
        c[0].bouton("Charger l'exemple (arbre dans un carter)", self._charger)
        c[1].bouton("Tout effacer", self._vider)
        z.sousTitre("1. Les cotes de chaque pièce")
        z.legende(
            "Une ligne par cote : la surface « vers » est à « cote » de la surface « de », dans le sens de l'axe. "
            "Mettez des valeurs positives (inversez De et Vers sinon). Une pièce peut avoir plusieurs cotes."
        )
        self._tableau(z, COTES, COLONNES_COTES)
        z.sousTitre("2. Les contacts entre pièces")
        z.legende("Deux surfaces de pièces différentes qui se touchent sont au même endroit.")
        self.contacts = z.section(self._contacts)
        z.sousTitre("3. Le jeu et la chaîne")
        self.resultat = z.section(self._resultat)

    def relance(self) -> None:
        self.sections[0].rafraichir()

    def _charger(self, redessiner: bool = True) -> None:
        """Remplace les tableaux et la condition par l'exemple."""
        d = copy.deepcopy(exemple())
        state.v[COTES], state.v[CONTACTS] = d["cotes"], d["contacts"]
        for cle, v in (("depart", d["depart"]), ("arrivee", d["arrivee"]), ("nom", d["condition"]["nom"]),
                       ("jmin", d["condition"]["jmin"]), ("jmax", d["condition"]["jmax"])):  # fmt: skip
            state.v[f"asst.{cle}"] = v
        if redessiner:
            self.relance()

    def _vider(self) -> None:
        state.v[COTES], state.v[CONTACTS] = [], []
        self.relance()

    def _tableau(self, z: Zone, cle: str, colonnes: list[Colonne]) -> None:
        """Tableau éditable d'une liste gardée dans state.v, avec ajout et retrait de lignes."""

        def apresChange() -> None:
            self.resultat.rafraichir()
            if cle == COTES:  # les contacts proposent les surfaces des cotes
                self.contacts.rafraichir()

        def surChange(i: int, col: str, v: Any) -> None:
            state.v[cle][i][col] = v
            apresChange()

        table = TableauEditable(colonnes, surChange)
        table.charger(state.v[cle])
        z._ajouter(table)

        def plus() -> None:
            state.v[cle].append({})
            table.charger(state.v[cle])

        def moins() -> None:
            if state.v[cle]:
                i = table.currentRow()
                state.v[cle].pop(i if i >= 0 else -1)
                table.charger(state.v[cle])
                apresChange()

        c = z.colonnes(2)
        c[0].bouton("Ajouter une ligne", plus)
        c[1].bouton("Retirer la ligne sélectionnée", moins)

    def _contacts(self, z: Zone) -> None:
        noeuds = surfaces(state.v[COTES])
        self._tableau(z, CONTACTS, [Colonne("a", "Surface 1", "liste", noeuds), Colonne("b", "Surface 2", "liste", noeuds)])

    def _utiliser(self, chaine: dict, condition: dict) -> None:
        """La chaîne choisie devient le problème courant (réglages gardés), le résultat est oublié."""
        if not self.fenetre.confirmerAbandon():
            return
        reglages = copy.deepcopy(state.probleme().get("reglages") or {})
        state.definirProbleme(
            {"condition": condition, "reglages": reglages, "maillons": copy.deepcopy(chaine["maillons"])}
        )
        state.definirRevisions([])
        state.nouvelleEtude(propre=False)  # chaîne bâtie ici : à enregistrer
        state.effacerResultat()
        self.aller("calcul")

    def _resultat(self, z: Zone) -> None:
        """Chaînes proposées entre les deux surfaces choisies : tableau, avertissements, plan, envoi vers Calcul."""
        cotes, contacts = state.v[COTES], state.v[CONTACTS]
        noeuds = surfaces(cotes)
        if len(noeuds) < 2:
            z.info("Décrivez au moins une cote (pièce, deux surfaces, valeur) pour choisir les surfaces du jeu.")
            return
        for cle, defaut in (("asst.depart", noeuds[0]), ("asst.arrivee", noeuds[1])):
            if state.v.get(cle) not in noeuds:  # surface renommée ou supprimée : on repart d'une surface connue
                state.v[cle] = defaut
        rafraichir = lambda: self.resultat.rafraichir()  # noqa: E731
        gauche, droite = z.colonnes(2)
        depart = gauche.liste("Surface de départ du jeu", noeuds, "asst.depart", apres=rafraichir)
        arrivee = droite.liste("Surface d'arrivée du jeu", noeuds, "asst.arrivee", apres=rafraichir)
        nom = gauche.saisie("Nom de la cote condition", "asst.nom", "Jeu J", apres=rafraichir)
        jmin = gauche.nombre("Jmin (mm)", "asst.jmin", 0.0, apres=rafraichir)
        jmax = droite.nombre("Jmax (mm)", "asst.jmax", 1.0, apres=rafraichir)
        z.legende(
            "Le jeu J est la position de la surface d'arrivée moins celle de la surface de départ "
            "(l'axe croît de « de » vers « vers »)."
        )
        try:
            chaines = construireChaines(cotes, contacts, depart, arrivee)
            lues, liens = lireSaisie(cotes, contacts)
        except ErreurChaine as e:
            z.erreur(e.message)
            return
        i = 0
        if len(chaines) > 1:
            z.info(f"{len(chaines)} chaînes de même longueur relient ces surfaces : choisissez celle de votre mécanisme.")
            i = z.liste(
                "Chaîne proposée", range(len(chaines)), "asst.choix",
                format=lambda j: f"Chaîne {j + 1} : {len(chaines[j]['maillons'])} cotes, jeu nominal "
                f"{fr(chaines[j]['nominal'], 'g')} mm",
                apres=rafraichir,
            )  # fmt: skip
        chaine = chaines[i]
        for a in chaine["avertissements"]:
            z.avertissement(a)
        nominal = chaine["nominal"]
        if not jmin <= nominal <= jmax:
            z.avertissement(
                f"Le jeu nominal de cette chaîne ({fr(nominal, 'g')} mm) est hors de "
                f"[{fr(jmin, 'g')} ; {fr(jmax, 'g')}] mm : "
                "ce peut être normal si les tolérances sont dissymétriques, sinon un sens ou une cote est faux."
            )
        z.tableau(
            pd.DataFrame(
                [
                    {
                        "Maillon": m["nom"],
                        "Sens": "−" if m["sens"] == "-" else "+",
                        "Cote (mm)": m["cote"],
                        "ISO 286": m["iso"] or "",
                        "ES (mm)": m["es"],
                        "EI (mm)": m["ei"],
                    }
                    for m in chaine["maillons"]
                ]
            )
        )
        z.figure(*figureConstruction(lues, liens, depart, arrivee, chaine))
        manquants = [m["nom"] for m in chaine["maillons"] if not m["iso"] and (m["es"] is None or m["ei"] is None)]
        if manquants:
            z.avertissement("Tolérance manquante (désignation ISO, ou ES et EI) : " + ", ".join(manquants) + ".")
        condition = {"nom": nom or "Jeu J", "jmin": float(jmin), "jmax": float(jmax)}
        z.bouton("Utiliser cette chaîne comme étude en cours", lambda: self._utiliser(chaine, condition),
                 actif=not manquants)  # fmt: skip
