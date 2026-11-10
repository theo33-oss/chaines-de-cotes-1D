"""Page « Problème inverse » : à partir de [Jmin ; Jmax], calcule les tolérances (IT) des maillons de la chaîne.

Le problème est celui de la page Calcul (state.probleme()). Le résultat du dernier calcul est gardé avec une copie
du problème calculé : si la saisie change ensuite, il est masqué jusqu'au prochain « Calculer ».
"""

import copy

import pandas as pd

from chainecotes.bureau import editeur, state
from chainecotes.bureau.widgets import Page, Zone
from chainecotes.core import cout as cout_mod
from chainecotes.core.errors import ErreurChaine
from chainecotes.plots._common import fr
from chainecotes.plots.optimisation import figureCoutsMaillons, figureITAvantApres
from chainecotes.plots.schema import figureSchema
from chainecotes.services import procedes_atelier
from chainecotes.services.calcul import apercuChaine
from chainecotes.services.repartition import (
    colonnesRepartition,
    coutsAvantApres,
    explicationRepartition,
    problemeRepartition,
    procedesDisponibles,
    repartir,
    specsProcedes,
    tableProcedes,
)

CRITERES = {"pire_cas": "Pire des cas (100 % garanti)", "statistique": "Statistique (± k σ)"}
METHODES = {
    "egale": "Égale",
    "proportionnelle": "Proportionnelle à l'unité de tolérance ISO i = 0,45∛D + 0,001D",
    "iso": "Qualité ISO la plus proche",
    "cout_minimal": "Coût minimal (procédés de l'atelier)",
}
CLE_RESULTAT, CLE_APPLIQUE, CLE_ERREUR = "inv.resultat", "inv.applique", "inv.erreur"
CHAMPS_ATELIER = (("c", "c (coût à IT = 0,1 mm)"), ("n", "n (exposant)"), ("itmin", "IT mini"), ("itmax", "IT maxi"))
CLE_ATELIER = "opt.cout.atelier."  # valeurs de l'atelier : CLE_ATELIER + « <procédé>.<champ> »
CLE_MESSAGE_ATELIER = "inv.atelier.message"


def poserValeursAtelier(valeurs: dict[str, dict]) -> None:
    """Met les valeurs d'atelier (sortie de services.procedes_atelier) dans les champs de saisie."""
    for pid, champs in valeurs.items():
        for champ, v in champs.items():
            state.v[f"{CLE_ATELIER}{pid}.{champ}"] = v


def valeursAtelier() -> dict[str, dict]:
    """Valeurs d'atelier saisies, par procédé : celles qui diffèrent de data/procedes.json."""
    sortie = {}
    for pr in cout_mod.listeProcedes():
        d = {c: state.v[f"{CLE_ATELIER}{pr['id']}.{c}"] for c, _ in CHAMPS_ATELIER if f"{CLE_ATELIER}{pr['id']}.{c}" in state.v}
        d = {c: v for c, v in d.items() if v != pr[c]}
        if d:
            sortie[pr["id"]] = d
    return sortie


_procedes = procedesDisponibles  # identifiant → nom des procédés, pour les listes de la page


def _tableProcedes(z: Zone, specs: list[dict]) -> None:
    """Tableau des procédés utilisés par la répartition : coût c, exposant n, qualités IT et source."""
    t = tableProcedes(specs)
    z.sousTitre("Procédés utilisés et leurs paramètres")
    z.legende(t["legende"])
    z.tableau(pd.DataFrame(t["lignes"]))
    if t["avertissement"]:
        z.avertissement(t["avertissement"])


def _explication(z: Zone, sortie: dict) -> None:
    """Méthode retenue et formule du critère remplie avec les valeurs obtenues."""
    for bloc in explicationRepartition(sortie):
        z.texte(bloc["texte"])
        for formule in bloc["formules"]:
            z.formule(formule)


class PageInverse(Page):
    def construire(self) -> None:
        self.gauche, self.droite = self.deuxPanneaux(self._tete, self._saisie, self._visuel)
        self.haut = self.sections[0]  # en-tête : son bouton « Appliquer » dépend du résultat affiché

    def maj(self) -> None:
        self.parametres.rafraichir()
        self.droite.rafraichir()

    def tout(self) -> None:
        self.gauche.rafraichir()
        self.droite.rafraichir()

    def _tete(self, z: Zone) -> None:
        z.modes("inverse")
        titre, calculer, appliquer = z.colonnes([3, 1, 1])  # boutons visibles en haut, même quand la saisie défile
        titre.titre("Répartition des tolérances")
        calculer.bouton("Calculer (F5)", self._calculer, primaire=True)
        appliquer.bouton("Appliquer à l'étude", self._appliquer, actif=self._appliquable(),
                         aide="Remplace les écarts de chaque maillon par ceux calculés (la désignation ISO est "
                         "vidée). Disponible une fois le calcul fait. Édition > Annuler (Ctrl+Z) revient en arrière.")  # fmt: skip
        z.texte(
            "Vous fixez les limites de la cote condition (**Jmin** et **Jmax**) ; l'outil calcule les intervalles de "
            "tolérance (IT) des maillons qui les tiennent, à parts égales, selon l'ISO ou au coût minimal, puis centre "
            "le jeu avec un maillon de réglage. Les maillons se modifient dans le mode « Analyser »."
        )

    def _saisie(self, z: Zone) -> None:
        z.bouton("Calculer", self._calculer, primaire=True)
        z.sousTitre("Cote condition")
        editeur.editeurCondition(z, self.maj)
        z.sousTitre("Paramètres de la répartition")
        z.radio("Critère", list(CRITERES), "inv.critere", format=CRITERES.get, vertical=True)
        z.radio("Méthode de répartition", list(METHODES), "inv.methode", format=METHODES.get, vertical=True,
                apres=lambda: self.parametres.rafraichir())  # fmt: skip
        self.parametres = z.section(self._parametres)

    def _parametres(self, z: Zone) -> None:
        p = state.probleme()
        if p["condition"].get("jmin") is None or p["condition"].get("jmax") is None:
            z.avertissement("Saisissez Jmin et Jmax : la répartition a besoin des deux limites.")
            z.bouton("Proposer un jeu de 0,05 à 0,1 mm", self._proposerLimites,
                     aide="Remplit Jmin = 0,05 mm et Jmax = 0,1 mm, à modifier ensuite librement.")
        n = len(p["maillons"])
        noms = [m.get("nom") or f"Maillon {i + 1}" for i, m in enumerate(p["maillons"])]
        signature = "|".join(noms)  # oubliée si la liste ou l'ordre change : jamais le mauvais maillon
        self.cleFiges = "inv.figes." + signature
        figes = z.multi("Maillons figés (écarts gardés)", range(n), self.cleFiges, format=lambda i: noms[i],
                        apres=lambda: self.parametres.rafraichir(),
                        aide="Ces maillons gardent leurs écarts saisis ; seuls les autres reçoivent une nouvelle "
                        "tolérance.")  # fmt: skip
        libres = [i for i in range(n) if i not in figes]
        self.clesProcedes = [f"opt.cout.procede.{i}.{signature}" for i in range(n)]
        if state.v.get("inv.methode") == "cout_minimal":
            z.case("Arrondir chaque IT à une qualité ISO 286", "opt.cout.arrondi",
                   aide="Les IT deviennent des qualités normalisées (IT7, IT8…) ; le critère reste tenu.")  # fmt: skip
            procedes = _procedes()
            z.texte("**Procédé de chaque maillon**")
            for i in range(n):
                z.liste(noms[i], list(procedes), self.clesProcedes[i], format=procedes.get, actif=i not in figes,
                        apres=lambda: self.parametres.rafraichir())  # fmt: skip
            self._valeursAtelier(z)
        self.cleReglage = f"inv.reglage.{'-'.join(map(str, libres))}"
        z.liste("Maillon de réglage", libres, self.cleReglage, format=lambda i: noms[i],
                aide="Maillon non figé dont la cote moyenne est décalée pour amener le jeu au milieu de "
                "[Jmin ; Jmax].")  # fmt: skip

    def _valeursAtelier(self, z: Zone) -> None:
        """Saisie facultative des valeurs de l'atelier ; une valeur changée remplace celle fournie."""
        base = {p["id"]: p for p in cout_mod.listeProcedes()}
        choisis = list(dict.fromkeys(state.v[c] for c in self.clesProcedes))
        r = z.repliable("Mes valeurs d'atelier (remplacent les valeurs indicatives)")
        r.legende(
            "Coût = c × (IT / 0,1 mm)^(−n). Entrez ici le coût relatif et l'exposant de votre atelier et les qualités "
            "IT que le procédé tient ; une valeur laissée telle quelle reste la valeur indicative."
        )
        r.messageGarde(CLE_MESSAGE_ATELIER)
        for pid in choisis:
            r.texte(f"**{base[pid]['nom']}**")
            cols = r.colonnes(len(CHAMPS_ATELIER))
            for col, (champ, libelle) in zip(cols, CHAMPS_ATELIER, strict=True):
                entier = champ.startswith("it")
                col.nombre(libelle, f"opt.cout.atelier.{pid}.{champ}", base[pid][champ] if entier else float(base[pid][champ]),
                           mini=1 if entier else 0.01, maxi=18 if entier else None, decimales=0 if entier else 3)  # fmt: skip
        r.legende(f"Fichier de votre atelier, relu à chaque lancement : {procedes_atelier.cheminParDefaut()}")
        r.bouton("Enregistrer comme valeurs de mon atelier", self._enregistrerAtelier,
                 aide="Garde ces valeurs dans un fichier de votre poste : elles sont reprises à chaque lancement.")  # fmt: skip
        r.telecharger("Exporter (.json)", lambda: procedes_atelier.exporterProcedes(valeursAtelier()),
                      "procedes_atelier.json")  # fmt: skip
        r.ouvrirFichier("Importer (.json)", "Procédés de l'atelier (*.json)", self._importerAtelier,
                        aide="Fichier exporté par cette application (ou celui d'un collègue) : ses valeurs remplacent "
                        "les valeurs saisies.")  # fmt: skip
        r.bouton("Revenir aux valeurs indicatives", self._effacerAtelier)

    def _messageAtelier(self, niveau: str, texte: str) -> None:
        state.v[CLE_MESSAGE_ATELIER] = (niveau, texte)
        self.parametres.rafraichir()

    def _enregistrerAtelier(self) -> None:
        try:
            chemin = procedes_atelier.ecrireFichier(valeursAtelier())
        except (ErreurChaine, OSError) as e:
            self._messageAtelier("erreur", f"Enregistrement impossible : {getattr(e, 'message', e)}")
        else:
            self._messageAtelier("succes", f"Valeurs de l'atelier enregistrées dans {chemin}.")

    def _importerAtelier(self, fichiers: list[tuple[str, bytes]]) -> None:
        try:
            valeurs = procedes_atelier.importerProcedes(fichiers[0][1].decode("utf-8-sig"))
        except UnicodeDecodeError:
            self._messageAtelier("erreur", "Fichier non reconnu : ce n'est pas un texte UTF-8.")
        except ErreurChaine as e:
            self._messageAtelier("erreur", e.message)
        else:
            self._effacerValeurs()
            poserValeursAtelier(valeurs)
            self._messageAtelier("succes", f"Valeurs de l'atelier importées de « {fichiers[0][0]} ».")

    def _effacerValeurs(self) -> None:
        for cle in [k for k in state.v if str(k).startswith(CLE_ATELIER)]:
            del state.v[cle]

    def _effacerAtelier(self) -> None:
        self._effacerValeurs()
        self._messageAtelier("info", "Valeurs indicatives rétablies (le fichier de l'atelier n'est pas modifié).")

    def _specs(self) -> list[dict]:
        """Un dict « procede » par maillon, complété des valeurs d'atelier qui diffèrent de data/procedes.json."""
        return specsProcedes([state.v.get(cle) for cle in self.clesProcedes], valeursAtelier())

    def _proposerLimites(self) -> None:
        """Remplit Jmin et Jmax d'un exemple de jeu (0,05 à 0,1 mm) : les champs se redessinent avec ces valeurs."""
        p = copy.deepcopy(state.probleme())
        p["condition"].update(jmin=0.05, jmax=0.1)
        state.definirProbleme(p)
        state.effacerResultat()
        self.tout()

    def _calculer(self) -> None:
        """Lance la répartition et garde le résultat avec une copie du problème calculé."""
        p = state.probleme()
        state.v.pop(CLE_RESULTAT, None)
        c = p["condition"]
        if c.get("jmin") is None or c.get("jmax") is None:
            state.v[CLE_ERREUR] = (
                "La répartition demande les deux limites de la cote condition : saisissez Jmin et Jmax "
                "(décochez « Pas de limite maxi »)."
            )
            self.droite.rafraichir()
            return
        methode = state.v["inv.methode"]
        try:
            state.v[CLE_RESULTAT] = repartir(
                p, methode, state.v["inv.critere"], state.v[self.cleFiges], state.v[self.cleReglage],
                [state.v.get(cle) for cle in self.clesProcedes], valeursAtelier(), bool(state.v.get("opt.cout.arrondi")),
            )  # fmt: skip
        except ErreurChaine as e:
            state.v[CLE_ERREUR] = e.message
        self.droite.rafraichir()

    def _appliquer(self) -> None:
        """Écrit les ES / EI calculés (ISO vidée) dans le problème courant, qui reste le problème calculé."""
        garde = state.v[CLE_RESULTAT]
        nouveau = copy.deepcopy(garde["probleme"])
        for m, ligne in zip(nouveau["maillons"], garde["sortie"]["maillons"], strict=True):
            m.update({"iso": None, "es": ligne["es"], "ei": ligne["ei"]})
        state.definirProbleme(nouveau)
        state.effacerResultat()
        garde["probleme"] = copy.deepcopy(nouveau)
        state.v[CLE_APPLIQUE] = True
        self.tout()

    def _appliquable(self) -> bool:
        """Vrai si un résultat à jour de la saisie est affiché (sinon il n'y a rien à appliquer)."""
        garde = state.v.get(CLE_RESULTAT)
        return garde is not None and state.sansCartouche(garde["probleme"]) == state.sansCartouche(state.probleme())

    def _visuel(self, z: Zone) -> None:
        if hasattr(self, "haut"):
            self.haut.rafraichir()  # le bouton « Appliquer » de l'en-tête suit le résultat
        p = state.probleme()
        if CLE_ERREUR in state.v:
            z.erreur(state.v.pop(CLE_ERREUR))
        garde = state.v.get(CLE_RESULTAT)
        if garde is None or state.sansCartouche(garde["probleme"]) != state.sansCartouche(p):
            z.info(
                "Choisissez le critère et la méthode, puis cliquez sur « Calculer »."
                if garde is None
                else "Le problème a changé depuis le dernier calcul : cliquez sur « Calculer » pour mettre à jour."
            )
            z.figure(*figureSchema(p, apercuChaine(p)))
            return
        self._resultats(z, garde)

    def _resultats(self, z: Zone, garde: dict) -> None:
        """Message, schéma après répartition, valeurs clés, tableau, figures, bouton « Appliquer », explication."""
        sortie = garde["sortie"]
        if state.v.pop(CLE_APPLIQUE, False):
            z.succes(
                "Tolérances appliquées à l'étude : le mode « Analyser » utilise maintenant ces écarts. "
                "Édition > Annuler (Ctrl+Z) revient en arrière."
            )
        (z.succes if sortie["tenue"] else z.erreur)(sortie["message"])
        # schéma de la chaîne telle qu'elle sera après « Appliquer » (et non l'état d'avant à côté d'un message vert)
        apres = problemeRepartition(garde)
        z.legende("Schéma de la chaîne avec les tolérances réparties :")
        z.figure(*figureSchema(apres, apercuChaine(apres)))
        nomReglage = sortie["maillons"][sortie["reglage"]]["nom"]
        valeurs = [("Budget Jmax − Jmin", f"{fr(sortie['budget'])} mm")]
        if sortie["qualite"] is not None:
            valeurs.append(("Qualité ISO retenue", f"IT{sortie['qualite']}"))
        valeurs.append(
            (f"Décalage de « {nomReglage} »", f"{fr(sortie['decalage'] * 1000, '+.1f')} µm",
             "Déplacement de la cote moyenne du maillon de réglage pour centrer le jeu.")
        )  # fmt: skip
        z.metriques(valeurs, 3)
        lignes, itAvant = sortie["maillons"], garde["itAvant"]
        colonnes = colonnesRepartition(garde)
        formats = {"Cote (mm)": "%.3f", "IT avant (mm)": "%.4f", "IT après (mm)": "%.4f", "ES (mm)": "%+.4f",
                   "EI (mm)": "%+.4f"}  # fmt: skip
        info, specs = sortie.get("cout"), garde.get("specs")
        if info:
            z.metriques(
                [
                    ("Coût relatif optimisé", fr(info["total"], ".2f"), "Somme des coûts des maillons non figés."),
                    ("Gain vs répartition égale", fr(info["gainEgale"] * 100, "+.1f") + " %",
                     f"Coût d'une répartition égale : {fr(info['egale'], '.2f')}."),
                    ("Gain vs proportionnelle", fr(info["gainProportionnelle"] * 100, "+.1f") + " %",
                     f"Coût d'une répartition proportionnelle : {fr(info['proportionnelle'], '.2f')}."),
                ],
                3,
            )  # fmt: skip
            formats |= {"Coût avant": "%.3f", "Coût après": "%.3f"}
        z.tableau(pd.DataFrame(colonnes), formats)
        z.figure(*figureITAvantApres(sortie, itAvant))
        if info:
            avant, apresCout = coutsAvantApres(garde)
            z.figure(*figureCoutsMaillons([m["nom"] for m in lignes], avant, apresCout))
        z.sousTitre("Méthode retenue")
        _explication(z, sortie)
        if info:
            _tableProcedes(z, specs)
