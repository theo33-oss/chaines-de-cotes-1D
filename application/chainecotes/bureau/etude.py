"""Révisions de l'étude : enregistrer l'état du problème, le recharger, comparer deux états.

Les champs ont des clés « etude. » (elles survivent au remplacement du problème). Les révisions vivent dans
state.revisions() et partent avec le fichier .json de l'étude (services/projet_io.exporterProjet).
"""

import copy
from collections.abc import Callable
from datetime import date

import pandas as pd

from chainecotes.bureau import state
from chainecotes.bureau.widgets import Zone
from chainecotes.core.errors import ErreurChaine
from chainecotes.plots._common import fr
from chainecotes.services import revisions as rev

CLE_MESSAGE = "etude.message"


def _enregistrer(n: int) -> None:
    """Ajoute le problème courant aux révisions (n : nombre de révisions déjà là, il suffixe les clés)."""
    v = state.v
    try:
        r = rev.nouvelleRevision(
            state.probleme(), v[f"etude.indice.{n}"], date.today().isoformat(), v.get("etude.auteur", ""),
            v[f"etude.objet.{n}"],
        )  # fmt: skip
        state.definirRevisions(rev.ajouterRevision(state.revisions(), r))
    except ErreurChaine as e:
        v[CLE_MESSAGE] = ("erreur", e.message)
        return
    v[CLE_MESSAGE] = ("succes", f"Révision {r['indice']} enregistrée.")


def _comparaison(z: Zone, revs: list[dict]) -> None:
    """Compare deux états au choix (état actuel ou révision) : changements de saisie, puis effet sur les résultats."""
    etats = [(rev.ETAT_ACTUEL, state.probleme()), *[(rev.libelleRevision(r), r["probleme"]) for r in revs]]

    def rendu(s: Zone) -> None:
        indices = range(len(etats))
        a = s.liste("Avant (A)", indices, "etude.cmp.a", format=lambda j: etats[j][0], defaut=1,
                    apres=lambda: section.rafraichir())  # fmt: skip
        b = s.liste("Après (B)", indices, "etude.cmp.b", format=lambda j: etats[j][0], defaut=0,
                    apres=lambda: section.rafraichir())  # fmt: skip
        if a == b:
            s.info("Choisissez deux états différents.")
            return
        try:
            c = rev.comparerRevisions(etats[a][1], etats[b][1])
        except ErreurChaine as e:
            s.erreur(e.message)
            return
        s.texte("**Changements de saisie**")
        s.texte("\n".join(f"- {x}" for x in c["saisie"]) if c["saisie"] else "Saisie identique.")
        r = c["resultats"]
        s.texte("**Effet sur les résultats**\n\n" + "\n".join(f"- {x}" for x in r["phrases"]))

        def ligne(libelle: str, k: str, f: str) -> dict:
            return {
                "Grandeur": libelle,
                "A": "—" if r[k]["a"] is None else fr(r[k]["a"], f),
                "B": "—" if r[k]["b"] is None else fr(r[k]["b"], f),
                "B − A": "—" if r[k]["delta"] is None else fr(r[k]["delta"], "+" + f),
            }

        s.tableau(
            pd.DataFrame(
                [
                    ligne("Jeu mini (mm)", "jeuMini", ".4f"),
                    ligne("Jeu maxi (mm)", "jeuMaxi", ".4f"),
                    ligne("Cpk", "cpk", ".2f"),
                    ligne("ppm (formule)", "ppm", ".1f"),
                ]
            )
        )

    section = z.section(rendu)


def revisionsEtude(z: Zone, relance: Callable[[], None]) -> None:
    """Enregistrement, rechargement, suppression et comparaison des révisions de l'étude.

    relance : redessine la page quand une révision chargée remplace le problème.
    """

    def rendu(s: Zone) -> None:
        revs = state.revisions()
        s.legende(
            "Une révision est une photo datée du problème (cotes, tolérances, réglages). Elles sont enregistrées dans "
            "le fichier .json de l'étude, pour retrouver et comparer l'état d'un indice à l'autre."
        )
        n = len(revs)
        gauche, droite = s.colonnes(2)
        gauche.saisie("Indice", f"etude.indice.{n}", rev.indiceSuivant(revs))
        droite.saisie("Auteur", "etude.auteur")
        s.saisie("Objet de la révision", f"etude.objet.{n}", indice="Ex. IT de la bague resserré")

        def enregistrer() -> None:
            _enregistrer(n)
            section.rafraichir()

        s.bouton("Enregistrer l'état actuel comme révision", enregistrer)
        s.messageGarde(CLE_MESSAGE)
        if not revs:
            return
        s.tableau(
            pd.DataFrame(
                [
                    {
                        "Indice": r["indice"],
                        "Date": r["date"],
                        "Auteur": r["auteur"],
                        "Objet": r["objet"],
                        "Maillons": len(r["probleme"]["maillons"]),
                    }
                    for r in revs
                ]
            )
        )
        cle = "etude.choix"
        s.liste("Révision", range(n), cle, format=lambda j: rev.libelleRevision(revs[j]))

        def charger() -> None:
            r = state.revisions()[state.v[cle]]
            state.definirProbleme(copy.deepcopy(r["probleme"]))
            state.effacerResultat()
            state.v[CLE_MESSAGE] = ("succes", f"Révision {r['indice']} chargée.")
            relance()

        def supprimer() -> None:
            liste = list(state.revisions())
            r = liste.pop(state.v[cle])
            state.definirRevisions(liste)
            state.v[CLE_MESSAGE] = ("succes", f"Révision {r['indice']} supprimée.")
            section.rafraichir()

        c1, c2 = s.colonnes(2)
        c1.bouton("Charger cette révision", charger)
        c2.bouton("Supprimer", supprimer)
        s.texte("**Comparer deux états**")
        _comparaison(s, revs)

    section = z.section(rendu)
