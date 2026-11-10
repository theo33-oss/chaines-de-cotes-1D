"""Page « Calcul de la chaîne » : saisie du problème à gauche, schéma vivant et résultats à droite.

Port de la fenêtre principale de l'application MATLAB « Solveur » : tableau des maillons, calcul au pire des cas,
statistique et Monte-Carlo, graphiques, explications, dossier de validation et fichiers.
"""

import copy
import math

import pandas as pd
import plotly.graph_objects as go

from chainecotes.bureau import editeur, etude, state, tache
from chainecotes.bureau.widgets import COULEURS_VERDICT, Page, Zone
from chainecotes.core.chaine import TOL_COMPARAISON, capabilitesMaillons, libelleVerdict, sansLimite
from chainecotes.core.derive import deriveSerie
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.inertiel import analyseInertielle, verdictBender
from chainecotes.core.sensibilite import gainSiResserre, indicesSensibilite
from chainecotes.plots import graphiques
from chainecotes.plots._common import fr, intervalle
from chainecotes.plots.schema import figureSchema
from chainecotes.services import import_maillons, projet_io
from chainecotes.services.calcul import apercuChaine, calculerChaine
from chainecotes.services.cartouche import etatValidation
from chainecotes.services.conclusion import conclusionEtude
from chainecotes.services.controles import controlerProbleme
from chainecotes.services.cotation import exporterCotation
from chainecotes.services.dossier_fichier import AVERTISSEMENT_IMAGES, FORMATS_DOSSIER, fichierDossier
from chainecotes.services.exemples import chargerExemple, listeExemples
from chainecotes.services.explications import explicationsCalcul
from chainecotes.services.feuille_chaine import exporterFeuilleChaine
from chainecotes.services.validation import dossierValidation

TIRAGES = (20_000, 200_000, 1_000_000)
CLE_DOSSIER = "calc.dossier"
CLE_CURSEURS_DROITE = "calc.curseurs.droite"  # le module « Faire varier les tolérances » est dans la zone de droite
FIGURES_STATISTIQUES = {"montecarlo", "distribution", "risque"}  # diagrammes de l'onglet « Statistiques »
CLE_FICHIER = "calc.dossier.fichier"
CLE_ERREUR = "calc.erreur"
PIECES_PAR_DEFAUT = 10_000  # horizon de la courbe de dérive quand aucun re-réglage n'est calculable
CLE_MESSAGE_FICHIER = "calc.fichier.message"
MODE_REMPLACER, MODE_AJOUTER = "remplacent les maillons actuels", "s'ajoutent à la suite"
EXEMPLES = {e["id"]: e for e in listeExemples()}
XLSX, CSV = "Excel (*.xlsx)", "CSV (*.csv)"


def _texteTirages(n: int) -> str:
    """Nombre de tirages écrit avec des espaces entre les milliers (« 200 000 »)."""
    return f"{n:,}".replace(",", " ")


def _ppmMonteCarlo(mc: dict | None) -> str:
    """Taux hors tolérance simulé, ou sa résolution si aucun tirage n'est sorti des limites."""
    if mc is None:
        return "—"
    if mc["nHors"] == 0:
        return f"< {fr(mc['resolutionPpm'], '.3g')} ppm"
    return f"{fr(mc['ppm'], '.4g')} ppm"


def _metriquePpm(bundle: dict) -> tuple:
    """Métrique « Hors tolérance » : le taux exact (lois des maillons) s'il existe, sinon la formule normale."""
    exact = bundle.get("ppmExact")
    if exact is None:
        return ("Hors tolérance", f"{fr(bundle['verdicts']['ppm'], '.3g')} ppm", "Formule, jeu de loi normale.")
    return ("Hors tolérance", f"{fr(exact, '.3g')} ppm",
            f"Calcul exact selon la loi de chaque maillon. Formule normale (approchée) : "
            f"{fr(bundle['verdicts']['ppm'], '.3g')} ppm.")  # fmt: skip


def oublierDossiers() -> None:
    """Oublie le dossier de validation et le dossier préparés (ils décrivent un autre calcul)."""
    state.v.pop(CLE_DOSSIER, None)
    state.v.pop(CLE_FICHIER, None)


def problemeAvecCartouche(bundle: dict) -> dict:
    """Problème du dernier calcul avec le cartouche en cours de saisie (modifiable sans relancer le calcul)."""
    cartouche = dict(state.probleme().get("cartouche") or {})
    if not cartouche.get("revisions") and state.revisions():  # le tableau du dossier reprend les révisions de l'étude
        cartouche["revisions"] = [{k: r[k] for k in ("indice", "date", "auteur", "objet")} for r in state.revisions()]
    return {**bundle["probleme"], **({"cartouche": cartouche} if cartouche else {})}


def preparerAffichage(bundle: dict) -> dict:
    """Figures et exports du calcul, construits une seule fois après « Calculer ».

    Entrée : bundle (calculerChaine). Sortie : dict figures (liste de (nom, figure, légende)), sensibilite
    (figure, légende), xlsx, csv, cotationXlsx, cotationCsv (bytes).
    """
    fonctions = [
        ("pareto", graphiques.figurePareto),
        ("montecarlo", graphiques.figureMonteCarlo),
        ("comparaison", graphiques.figureComparaison),
        ("distribution", graphiques.figureDistribution),
        ("risque", graphiques.figureRisqueCp),
    ]
    if bundle["res"]["thermique_actif"]:
        fonctions.append(("thermique", graphiques.figureEffetThermique))
    if bundle["jeuT"] is not None:
        fonctions.append(("temperature", graphiques.figureJeuTemperature))
    return {
        "figures": [(nom, *fonction(bundle)) for nom, fonction in fonctions],
        "xlsx": projet_io.exporterResultatsXlsx(bundle),
        "csv": projet_io.exporterResultatsCsv(bundle),
        "cotationXlsx": exporterCotation(bundle["probleme"], bundle, "xlsx"),
        "cotationCsv": exporterCotation(bundle["probleme"], bundle, "csv"),
        "sensibilite": graphiques.figureSensibilite(bundle),
    }


class PageCalcul(Page):
    def construire(self) -> None:
        self.gauche, self.droite = self.deuxPanneaux(self._tete, self._saisie, self._visuel)

    def tout(self) -> None:
        """Redessine la saisie et la visualisation (problème remplacé, calcul terminé)."""
        self.gauche.rafraichir()
        self.droite.rafraichir()

    def maj(self) -> None:
        """Saisie modifiée : la visualisation suit, la colonne de saisie garde le curseur."""
        self.droite.rafraichir()
        self.controles.rafraichir()

    def _tete(self, z: Zone) -> None:
        z.modes("calcul")
        titre, action = z.colonnes([3, 1])  # le bouton reste visible en haut, même quand la colonne de saisie défile
        titre.titre("Analyse de la chaîne de cotes")
        action.bouton("Calculer (F5)", self._calculer, primaire=True)

    def _calculer(self) -> None:
        oublierDossiers()
        state.v.pop(CLE_ERREUR, None)
        apercu = apercuChaine(state.probleme())
        if "erreur" in apercu:
            state.effacerResultat()
            state.v[CLE_ERREUR] = f"Calcul impossible : {apercu['erreur']}"
            self.tout()
            return
        n, graine = state.v["calc.tirages"], int(state.v["calc.graine"])
        # copie : les éditeurs modifient le problème sur place, le résultat doit garder sa saisie
        probleme = copy.deepcopy(state.probleme())

        def travail() -> dict:
            bundle = calculerChaine(probleme, n=n, graine=graine)
            bundle["affichage"] = preparerAffichage(bundle)
            return bundle

        def fini(bundle: dict) -> None:
            state.definirResultat(bundle)
            state.ajouterHistorique(bundle, n, graine)
            self.tout()
            self.fenetre.statusBar().showMessage("Calcul terminé.", 5000)

        def echec(e: Exception) -> None:
            state.effacerResultat()
            state.v[CLE_ERREUR] = f"Calcul impossible : {getattr(e, 'message', e)}"
            self.tout()

        tache.lancer(travail, fini, echec)

    def _saisie(self, z: Zone) -> None:
        z.bouton("Calculer", self._calculer, primaire=True)
        z.messageGarde("calc.vide")
        if CLE_ERREUR in state.v:
            z.erreur(state.v.pop(CLE_ERREUR))
        self.controles = z.section(self._controles)
        replis = z.repliable("Cote condition et réglages", ouvert=True)
        editeur.editeurCondition(replis, self.maj)
        editeur.editeurReglages(replis, self.maj, self.tout)
        z.sousTitre("Maillons")
        editeur.editeurMaillons(z, self.maj)
        editeur.ajouterToleranceGeometrique(z.repliable("Ajouter une tolérance géométrique (ISO 1101)"), self.tout)
        self._importer(z.repliable("Importer des maillons (Excel, CSV, collage)"))
        self._enregistrerOuvrir(z.repliable("Enregistrer / ouvrir"), "saisie")
        etude.revisionsEtude(z.repliable("Révisions de l'étude (indices, comparaison)"), self.tout)
        if not state.v.get(CLE_CURSEURS_DROITE, False):
            self._moduleCurseurs(z)
        options = z.repliable("Options du calcul").colonnes(2)
        options[0].liste("Tirages Monte-Carlo", TIRAGES, "calc.tirages", format=_texteTirages, defaut=TIRAGES[1],
                         aide="200 000 comme l'application MATLAB. Plus de tirages : ppm simulé plus précis, calcul "
                         "plus long.")  # fmt: skip
        options[1].nombre("Graine", "calc.graine", 1, mini=0, decimales=0, aide="Même graine : mêmes tirages.")
        self._historique(z.repliable(f"Historique des calculs ({len(state.historique())})"))

    def _historique(self, z: Zone) -> None:
        """Calculs réalisés depuis l'ouverture de l'application, rechargeables."""
        h = state.historique()
        if not h:
            z.legende("Aucun calcul pour l'instant : cliquez sur « Calculer ».")
            return
        z.tableau(
            pd.DataFrame(
                {
                    "Heure": [e["heure"] for e in h],
                    "Chaîne": [e["nom"] for e in h],
                    "Maillons": [e["nMaillons"] for e in h],
                    "Jeu mini (mm)": [fr(e["jeuMin"]) for e in h],
                    "Jeu maxi (mm)": [fr(e["jeuMax"]) for e in h],
                    "Pire cas": [e["verdict"] for e in h],
                    "ppm": [fr(e["ppm"], ".3g") for e in h],
                    "Cpk": [fr(e["cpk"], ".3g") for e in h],
                    "Tirages": [e["tirages"] for e in h],
                }
            ),
            couleurs={"Pire cas": COULEURS_VERDICT.get},
        )
        z.liste("Calcul à rouvrir", range(len(h)), "historique.choix", format=lambda i: f"{h[i]['heure']} · {h[i]['nom']}",
                defaut=len(h) - 1)  # fmt: skip

        def recharger() -> None:
            state.definirProbleme(copy.deepcopy(state.historique()[state.v["historique.choix"]]["probleme"]))
            state.effacerResultat()
            self.tout()

        z.bouton("Recharger sa saisie", recharger)

    def _chargerExemple(self) -> None:
        if not self.fenetre.confirmerAbandon():
            return
        state.definirProbleme(chargerExemple(state.v["calc.exemple"]))
        state.definirRevisions([])
        state.nouvelleEtude()
        state.effacerResultat()
        oublierDossiers()
        self.tout()

    def _controles(self, z: Zone) -> None:
        """Contrôles de cohérence de la saisie : avertissements et remarques, jamais bloquants."""
        probleme = state.probleme()
        if "erreur" in apercuChaine(probleme):  # l'éditeur affiche déjà l'erreur de saisie
            return
        for c in controlerProbleme(probleme):
            nom, message = c["maillon"], c["message"]
            texte = message if not nom or nom in message else f"{nom} : {message}"
            z.info(texte) if c["niveau"] == "info" else z.avertissement(texte)

    def _moduleCurseurs(self, z: Zone) -> None:
        """Module « Faire varier les tolérances » : à gauche (2 valeurs par ligne) ou à droite (4)."""
        droite = state.v.get(CLE_CURSEURS_DROITE, False)
        r = z.repliable("Faire varier les tolérances", ouvert=True)

        def deplacer() -> None:
            state.v[CLE_CURSEURS_DROITE] = not state.v.get(CLE_CURSEURS_DROITE, False)
            self.tout()

        r.bouton("Ramener à gauche" if droite else "Déplacer à droite", deplacer,
                 aide="Place ce module dans la zone de droite, plus large, ou le ramène dans la colonne de saisie.")  # fmt: skip
        r.legende(
            "Si la chaîne ne passe pas, faites varier ici la cote voulue. Pour une répartition au coût minimal, "
            "passez au mode « Répartir les tolérances »."
        )
        editeur.curseursSensibilite(r, state.probleme(), 4 if droite else 2, self.tout)

    def _ouvrirFichier(self, fichiers: list[tuple[str, bytes]], cle: str) -> None:
        """Relit un problème JSON ; il remplace le problème en cours."""
        nom, octets = fichiers[0]
        cleMessage = f"{CLE_MESSAGE_FICHIER}.{cle}"
        if not self.fenetre.confirmerAbandon():
            return
        try:
            ouvert = projet_io.importerProjet(octets.decode("utf-8-sig"))
        except UnicodeDecodeError:
            state.v[cleMessage] = ("erreur", "Fichier non reconnu : ce n'est pas un texte UTF-8.")
        except ErreurChaine as e:
            state.v[cleMessage] = ("erreur", e.message)
        else:
            state.definirProbleme(ouvert["probleme"])
            state.definirRevisions(ouvert["revisions"])
            state.nouvelleEtude(state.v.pop("fichier.chemin", None))
            state.effacerResultat()
            oublierDossiers()
            state.v[cleMessage] = ("succes", f"Problème « {nom} » ouvert.")
        self.tout()

    def _importer(self, z: Zone) -> None:
        """Import des maillons depuis un fichier csv ou xlsx, ou un tableau copié depuis Excel."""
        cleFichier, cleTexte, cleMode = "calc.import.fichier", "calc.import.texte", "calc.import.mode"
        cleMessage = f"{CLE_MESSAGE_FICHIER}.{cleFichier}"

        def rendu(s: Zone) -> None:
            def choisir(fichiers: list[tuple[str, bytes]]) -> None:
                state.v[cleFichier] = fichiers[0]
                section.rafraichir()

            s.legende(
                "Colonnes reconnues : nom, sens (+/−), cote, ISO 286, ES, EI (ou ± tolérance, ou IT), loi, matériau, "
                "α, T service. La première ligne donne les titres. Une feuille exportée ici se relit telle quelle."
            )
            s.ouvrirFichier("Choisir un fichier (.csv, .xlsx)", "Tableaux (*.csv *.xlsx *.txt)", choisir)
            if cleFichier in state.v:
                s.legende(f"Fichier choisi : {state.v[cleFichier][0]}")
            s.zoneTexte("…ou collez le tableau copié depuis Excel", cleTexte)
            s.radio("Les maillons lus…", [MODE_REMPLACER, MODE_AJOUTER], cleMode)
            s.bouton("Importer", self._lireImport)
            s.telecharger("Modèle de fichier (.csv)", import_maillons.MODELE_CSV, "modele_maillons.csv")
            s.messageGarde(cleMessage)

        section = z.section(rendu)
        self.sectionImport = section

    def _lireImport(self) -> None:
        """Lit le fichier choisi ou le texte collé et remplace ou complète les maillons."""
        cleFichier, cleTexte, cleMode = "calc.import.fichier", "calc.import.texte", "calc.import.mode"
        cleMessage = f"{CLE_MESSAGE_FICHIER}.{cleFichier}"
        fichier, texte = state.v.get(cleFichier), state.v.get(cleTexte, "")
        if fichier is None and not texte.strip():
            state.v[cleMessage] = ("erreur", "Choisissez un fichier ou collez un tableau avant d'importer.")
            self.sectionImport.rafraichir()
            return
        try:
            lu = import_maillons.lireMaillons(fichier[1] if fichier is not None else texte)
        except ErreurChaine as e:
            state.v[cleMessage] = ("erreur", e.message)
            self.sectionImport.rafraichir()
            return
        if lu["erreurs"]:
            corrections = "\n".join(f"- {e}" for e in lu["erreurs"])
            state.v[cleMessage] = ("erreur", f"Import annulé, à corriger :\n\n{corrections}")
            self.sectionImport.rafraichir()
            return
        p = state.probleme()
        remplacer = state.v.get(cleMode) == MODE_REMPLACER
        if not remplacer and len(p["maillons"]) + len(lu["maillons"]) > projet_io.MAX_MAILLONS:
            state.v[cleMessage] = ("erreur", f"Trop de maillons ({projet_io.MAX_MAILLONS} au plus).")
            self.sectionImport.rafraichir()
            return
        p["maillons"] = lu["maillons"] if remplacer else [*p["maillons"], *lu["maillons"]]
        state.definirProbleme(p)
        state.effacerResultat()
        oublierDossiers()
        state.v[cleTexte] = ""
        state.v.pop(cleFichier, None)
        state.v[cleMessage] = ("succes", f"{len(lu['maillons'])} maillon(s) importé(s).")
        self.tout()

    def _enregistrerOuvrir(self, z: Zone, suffixe: str) -> None:
        """Enregistrement du problème en JSON et ouverture d'un fichier JSON."""
        z.bouton("Enregistrer le problème (.json)", self.fenetre.enregistrerSous)
        z.ouvrirFichier("Ouvrir un problème (.json)", "Problème (*.json)", lambda f: self._ouvrirFichier(f, suffixe),
                        aide="Fichier enregistré par cette application. Il remplace le problème en cours.")  # fmt: skip
        z.messageGarde(f"{CLE_MESSAGE_FICHIER}.{suffixe}")
        if suffixe == "saisie":  # une seule liste d'exemples par page (clé d'état partagée)
            z.liste("Repartir d'un exemple", list(EXEMPLES), "calc.exemple", format=lambda i: EXEMPLES[i]["titre"])
            z.bouton("Charger cet exemple", self._chargerExemple)

    def _verdictEnTete(self, z: Zone, probleme: dict, apercu: dict, bundle: dict | None) -> None:
        """Verdict en tête de page, une seule fois : celui du calcul s'il est à jour, sinon celui de la saisie.

        Calcul à jour : phrase et couleur de conclusionEtude (vert : tient au pire des cas ; orange : en statistique
        seulement ; rouge : ne tient pas), puis jeu mini, jeu maxi, Cpk et ppm. Sinon : pire des cas de la saisie.
        """
        if etatValidation(probleme) == "modifie":
            z.avertissement(
                "Étude marquée « Validé » mais modifiée depuis sa validation (l'empreinte ne correspond plus) : "
                "repassez-la en brouillon et validez-la de nouveau."
            )
        if "erreur" in apercu:
            z.erreur("Saisie invalide : corrigez les valeurs signalées dans la colonne de gauche.")
            return
        v, c = apercu["verdicts"], apercu["res"]["condition"]
        jeu = [
            ("Jeu mini", f"{fr(v['pireCas']['min'])} mm", "Au pire des cas."),
            ("Jeu maxi", f"{fr(v['pireCas']['max'])} mm", "Au pire des cas."),
        ]
        if bundle is not None and state.sansCartouche(bundle["probleme"]) == state.sansCartouche(probleme):
            conclusion = conclusionEtude(bundle)
            z.message(conclusion["niveau"], f"**{conclusion['titre']}**")
            if conclusion["conseils"]:  # action recommandée : le premier conseil, ex. « Commencez par la cote X »
                z.texte("**À faire :** " + conclusion["conseils"][0])
            elif conclusion["principaux"] and conclusion["principaux"][0]["part"] > 0:
                haut = conclusion["principaux"][0]
                z.texte(f"**Cause principale :** « {haut['nom']} » ({fr(haut['part'], '.0f')} % de la variance du jeu).")
            vb = bundle["verdicts"]
            z.metriques(
                [
                    *jeu,
                    ("Cpk", fr(vb["cpk"], ".3g"), "Capabilité du jeu face à la limite la plus proche."),
                    _metriquePpm(bundle),
                ]
            )
            return
        texte = libelleVerdict(v["pireCas"]["ok"], c)
        niveau = "info" if sansLimite(c) else ("succes" if v["pireCas"]["ok"] else "erreur")
        z.message(
            niveau,
            f"**Pire des cas : {texte.lower()}.** Limites exigées : {intervalle(c['jmin'], c['jmax'])} mm. "
            "Cliquez sur « Calculer » (F5) pour la statistique et Monte-Carlo.",
        )
        z.metriques(jeu, 2)

    def _visuel(self, z: Zone) -> None:
        probleme = state.probleme()
        apercu = apercuChaine(probleme)
        self._verdictEnTete(z, probleme, apercu, state.resultat())
        z.figure(*figureSchema(probleme, apercu))
        if state.v.get(CLE_CURSEURS_DROITE, False):
            self._moduleCurseurs(z)
        bundle = state.resultat()
        if bundle is not None:
            self._resultats(z, probleme, bundle)

    def _resultats(self, z: Zone, probleme: dict, bundle: dict) -> None:
        """Bandeau de résultat périmé, avertissements du calcul et onglets des résultats."""
        if state.sansCartouche(bundle["probleme"]) != state.sansCartouche(probleme):
            z.info("Le problème a changé depuis le dernier calcul : cliquez sur « Calculer » pour mettre à jour.")
        for a in bundle["avertissements"]:
            z.avertissement(a)
        # l'onglet « Dérive et réglage » est masqué quand aucun maillon ne dérive
        onglets = {
            "Résultats": lambda o: self._ongletResultats(o, bundle),
            "Statistiques": lambda o: self._ongletStatistiques(o, bundle),
            "Graphiques": lambda o: self._afficherFigures(o, bundle, FIGURES_STATISTIQUES, inverse=True),
            "Sensibilité": lambda o: self._ongletSensibilite(o, bundle),
        }
        if any(m["derive"] != 0 for m in bundle["res"]["maillons"]):
            onglets["Dérive et réglage"] = lambda o: self._ongletDerive(o, bundle)
        onglets["Explications du calcul"] = lambda o: self._ongletExplications(o, bundle)
        onglets["Dossier de validation"] = lambda o: self._ongletValidation(o, bundle)
        onglets["Fichiers"] = lambda o: self._ongletFichiers(o, bundle)
        z.onglets(onglets, cle="calc.onglet")

    def _ongletResultats(self, z: Zone, bundle: dict) -> None:
        """Valeurs clés, verdicts selon la méthode et tableau des maillons."""
        res, v, mc = bundle["res"], bundle["verdicts"], bundle["mc"]
        c, k = res["condition"], res["k_sigma"]
        valeurs = [
            ("Jeu nominal", f"{fr(res['CF_nom'])} mm", "Somme des cotes nominales projetées."),
            ("Jeu moyen", f"{fr(res['CF_moy'])} mm", "Somme des cotes moyennes projetées (centre des tolérances)."),
            ("Jeu mini", f"{fr(res['CF_min'])} mm", "Au pire des cas."),
            ("Jeu maxi", f"{fr(res['CF_max'])} mm", "Au pire des cas."),
            ("Écart-type σ", f"{fr(res['CF_sigma'], '.5f')} mm", "Écart-type du jeu (somme quadratique des σ_i)."),
            ("Cp", fr(v["cp"], ".3g"), "(Jmax − Jmin) / 6σ."),
            ("Cpk", fr(v["cpk"], ".3g"), "Distance de la moyenne à la limite la plus proche, divisée par 3σ."),
            ("ppm (formule normale)" if bundle.get("ppmExact") is not None else "ppm (formule)",
             f"{fr(v['ppm'], '.4g')} ppm", "Parties par million hors limites, jeu supposé de loi normale."),
            *([("ppm (lois des maillons)", f"{fr(bundle['ppmExact'], '.4g')} ppm",
                "Calcul exact en tenant compte de la loi de chaque maillon (convolution).")]
              if bundle.get("ppmExact") is not None else []),
            ("ppm (Monte-Carlo)", _ppmMonteCarlo(mc), "Parties par million hors limites parmi les tirages."),
        ]
        if res["thermique_actif"]:
            valeurs.append(
                ("Décalage thermique", f"{fr(res['dJ_th'], '+.4f')} mm", "Variation du jeu due à la dilatation.")
            )
        z.metriques(valeurs)

        z.sousTitre("Verdicts")
        plages = [
            ("Pire des cas", v["pireCas"]),
            (f"RSS ± {fr(k, 'g')} σ", v["rssK"]),
            ("RSS ± 6 σ", v["rss6"]),
            *([(f"RSS ± {fr(k, 'g')} σ (moyenne du procédé)", v["rssProc"])] if res["decalage"] != 0 else []),
            ("Statistique majorée (Bender, × 1,5)", verdictBender(res)),
        ]
        lignes = [
            {"Méthode": nom, "Jeu mini (mm)": p["min"], "Jeu maxi (mm)": p["max"],
             "Verdict": libelleVerdict(p["ok"], c)}
            for nom, p in plages
        ]
        if mc is not None:
            bas, haut = mc["quantiles"]["bas"], mc["quantiles"]["haut"]
            ok = bas >= c["jmin"] - TOL_COMPARAISON and haut <= c["jmax"] + TOL_COMPARAISON
            lignes.append(
                {
                    "Méthode": "Monte-Carlo 0,135–99,865 %",
                    "Jeu mini (mm)": bas,
                    "Jeu maxi (mm)": haut,
                    "Verdict": libelleVerdict(ok, c),
                }
            )
        z.legende(f"Limites exigées : {intervalle(c['jmin'], c['jmax'])} mm.")
        z.tableau(pd.DataFrame(lignes), {"Jeu mini (mm)": "%.4f", "Jeu maxi (mm)": "%.4f"},
                  couleurs={"Verdict": COULEURS_VERDICT.get})  # fmt: skip

        z.sousTitre("Maillons")
        tableau = pd.DataFrame(
            {
                "Maillon": res["Nom"],
                "ES (mm)": res["ES"],
                "EI (mm)": res["EI"],
                "IT (mm)": res["IT"],
                "C moy (mm)": res["C_moy"],
                "α (1e-6/K)": [1e6 * float(a) for a in res["alpha"]],
                "Part pire cas (%)": [x["partPireCas"] for x in bundle["contributions"]],
                "Part statistique (%)": [x["partVariance"] for x in bundle["contributions"]],
            }
        )
        z.tableau(
            tableau,
            {"ES (mm)": "%.4f", "EI (mm)": "%.4f", "IT (mm)": "%.4f", "C moy (mm)": "%.4f", "α (1e-6/K)": "%.2f",
             "Part pire cas (%)": "%.1f", "Part statistique (%)": "%.1f"},
        )  # fmt: skip
        z.legende("Part pire cas : |aᵢ|·ITᵢ/2 rapporté à la somme. Part statistique : σᵢ² rapporté à la variance du jeu.")
        caps = capabilitesMaillons(res)
        if any(x["mesure"] for x in caps):
            z.sousTitre("Capabilité de chaque cote")
            z.tableau(
                pd.DataFrame(
                    {
                        "Maillon": [x["nom"] for x in caps],
                        "Origine": ["Mesures de l'atelier" if x["mesure"] else "Modèle de la loi" for x in caps],
                        "Moyenne (mm)": [x["moyenne"] for x in caps],
                        "σ (mm)": [x["sigma"] for x in caps],
                        "Cp": [x["cp"] for x in caps],
                        "Cpk": [x["cpk"] for x in caps],
                    }
                ),
                {"Moyenne (mm)": "%.4f", "σ (mm)": "%.5f", "Cp": "%.2f", "Cpk": "%.2f"},
            )
            z.legende(
                "Cp = IT / 6σ ; Cpk = distance de la moyenne à la cote la plus proche / 3σ. "
                "Un Cpk sous 1,33 est fragile."
            )

    def _afficherFigures(self, z: Zone, bundle: dict, noms: set[str], inverse: bool = False) -> None:
        """Figures du calcul, chacune suivie de sa légende : celles de `noms` (ou toutes les autres si `inverse`)."""
        for nom, fig, legende in bundle["affichage"]["figures"]:
            if (nom in noms) != inverse:
                z.figure(go.Figure(fig), legende)  # copie : l'affichage retouche la figure, l'original reste intact

    def _ongletStatistiques(self, z: Zone, bundle: dict) -> None:
        """Statistiques du tirage Monte-Carlo et diagrammes : histogramme, distribution et risque selon Cp."""
        mc, v = bundle["mc"], bundle["verdicts"]
        if mc is None:
            z.info("Pas de tirage Monte-Carlo : l'écart-type du jeu est nul, il n'y a rien à simuler.")
        else:
            z.texte(
                f"**{_texteTirages(mc['n'])} tirages** (graine {mc['graine']}). Les écarts avec la formule viennent du "
                "tirage au sort et de la forme de la loi du jeu."
            )
            q = mc["quantiles"]
            z.tableau(
                pd.DataFrame(
                    {
                        "Grandeur": ["Moyenne (mm)", "Écart-type (mm)", "Quantile 0,135 % (mm)", "Médiane (mm)",
                                     "Quantile 99,865 % (mm)", "Tirages hors limites", "ppm (Monte-Carlo)",
                                     "ppm (formule)", "Cp", "Cpk"],
                        "Monte-Carlo": [fr(mc["moyenne"], ".5f"), fr(mc["ecartType"], ".5f"), fr(q["bas"], ".5f"),
                                        fr(q["mediane"], ".5f"), fr(q["haut"], ".5f"), f"{mc['nHors']} sur {mc['n']}",
                                        _ppmMonteCarlo(mc), "", fr(mc["cp"], ".3g"), fr(mc["cpk"], ".3g")],
                        "Formule": [fr(bundle["res"]["CF_moy"], ".5f"), fr(bundle["res"]["CF_sigma"], ".5f"), "", "",
                                    "", "", "", f"{fr(v['ppm'], '.4g')} ppm", fr(v["cp"], ".3g"), fr(v["cpk"], ".3g")],
                    }
                )
            )  # fmt: skip
        self._inertiel(z, bundle)
        self._afficherFigures(z, bundle, FIGURES_STATISTIQUES)

    def _inertiel(self, z: Zone, bundle: dict) -> None:
        """Tolérancement inertiel (Pillet) : inertie du jeu, Cpi et tolérances que permet la répartition inertielle."""
        z.sousTitre("Tolérancement inertiel (Pillet)")
        r = analyseInertielle(bundle["res"])
        z.metriques(
            [
                ("Inertie du jeu", f"{fr(r['inertieJeu'], '.5f')} mm", "I = √(σ² + δ²), δ : écart à la cible."),
                ("Cible du jeu", f"{fr(r['cible'], '.4f')} mm", "Milieu de [Jmin ; Jmax]."),
                ("Inertie maxi", f"{fr(r['inertieMax'], '.5f')} mm", "(Jmax − Jmin) / 6."),
                ("Cpi", fr(r["cpi"], ".3g"), "Inertie maxi / inertie du jeu ; Cpi ≥ 1,33 visé."),
            ]
        )
        if math.isfinite(r["inertieMax"]):
            colonnes = {
                "σ (mm)": "sigma",
                "Écart à la cote moyenne (mm)": "ecart",
                "Inertie (mm)": "inertie",
                "IT inertiel possible (mm)": "itInertiel",
                "IT égal au pire des cas (mm)": "itPireCas",
            }
            df = {"Maillon": [x["nom"] for x in r["liens"]]}
            df |= {titre: [x[k] for x in r["liens"]] for titre, k in colonnes.items()}
            z.tableau(pd.DataFrame(df), dict.fromkeys(colonnes, "%.4f"))
            z.legende(
                "L'inertie d'une cote mêle sa dispersion et son décentrage. Pour n cotes, répartir l'inertie maxi du "
                "jeu également autorise des IT environ √n fois plus larges que la répartition égale au pire des cas, "
                "mais à condition que chaque cote soit produite avec cette inertie (dispersion et décentrage "
                "compris). Ce sont des ordres de grandeur pour discuter d'une cotation, pas une cotation."
            )
        else:
            z.info("Le tolérancement inertiel demande les deux limites Jmin et Jmax de la cote condition.")

    def _ongletSensibilite(self, z: Zone, bundle: dict) -> None:
        """Indices de Sobol (figure et tableau) et gain obtenu en resserrant la tolérance d'un seul maillon."""
        z.texte(
            "L'indice de Sobol d'un maillon est la part de la variance du jeu qu'il explique (somme = 100 %). "
            "Resserrer la tolérance du maillon au plus fort indice est le levier le plus efficace."
        )
        fig, legende = bundle["affichage"]["sensibilite"]
        z.figure(go.Figure(fig), legende)
        res = bundle["res"]
        if not res["CF_sigma"] > 0:
            return

        def rendu(s: Zone) -> None:
            pct = s.curseur(
                "Tolérance resserrée à (% de l'IT actuel)", "calc.sensibilite.facteur", 50, 10, 90, 5,
                apres=lambda: section.rafraichir(),
                aide="Un seul maillon est resserré à la fois ; les autres gardent leur tolérance.",
            )  # fmt: skip
            indices = indicesSensibilite(res)
            gains = gainSiResserre(res, pct / 100)
            s.tableau(
                pd.DataFrame(
                    {
                        "Maillon": [x["nom"] for x in indices],
                        "Rang": [x["rang"] for x in indices],
                        "Indice de Sobol (%)": [100 * x["indice"] for x in indices],
                        "Part pire cas (%)": [100 * x["partPireCas"] for x in indices],
                        "σ du jeu si resserré (mm)": [g["sigma"] for g in gains],
                        "Gain sur σ (%)": [g["gainSigmaPct"] for g in gains],
                        "Cpk si resserré": [g["cpk"] for g in gains],
                        "ppm si resserré": [g["ppm"] for g in gains],
                    }
                ),
                {"Indice de Sobol (%)": "%.1f", "Part pire cas (%)": "%.1f", "σ du jeu si resserré (mm)": "%.5f",
                 "Gain sur σ (%)": "%.1f", "Cpk si resserré": "%.3f", "ppm si resserré": "%.3g"},
            )  # fmt: skip
            s.legende("Moyenne du procédé et limites inchangées ; seul le maillon de la ligne est resserré.")

        section = z.section(rendu)

    def _ongletDerive(self, z: Zone, bundle: dict) -> None:
        """Courbe du jeu moyen et des ppm selon le nombre de pièces, seuil de ppm réglable, recommandation."""

        def pieces(x: float) -> str:
            return f"{x:,.0f}".replace(",", " ")

        z.texte(
            "La dérive des maillons (colonne « Dérive » du tableau) fait glisser la moyenne du jeu au fil de la "
            "production ; l'écart-type reste celui du calcul. Fixez le taux de ppm toléré pour obtenir la cadence "
            "de re-réglage."
        )
        probleme = bundle["probleme"]

        def rendu(s: Zone) -> None:
            cols = s.colonnes(2)
            seuil = cols[0].nombre(
                "Seuil de ppm toléré", "calc.derive.seuil", 1000.0, mini=0.0, decimales=1,
                apres=lambda: section.rafraichir(),
                aide="Taux hors tolérance (parties par million) au-delà duquel il faut re-régler le procédé.",
            )  # fmt: skip
            inter = deriveSerie(probleme, 1000, 1000, seuilPpm=seuil)["intervalleRecalage"]
            defaut = max(int(1.5 * inter) if inter else PIECES_PAR_DEFAUT, 100)
            horizon = cols[1].nombre(
                "Pièces affichées", f"calc.derive.horizon.{hash(repr(probleme)) % 10**9}", defaut, mini=100, decimales=0,
                apres=lambda: section.rafraichir(), aide="Dernière pièce de la courbe.",
            )  # fmt: skip
            serie = deriveSerie(probleme, int(horizon), max(1, int(horizon) // 200), seuilPpm=seuil)
            fig, legende = graphiques.figureDerive(bundle, serie, seuil)
            s.figure(fig, legende)
            s.metrique("Dérive du jeu", f"{fr(1000 * serie['vitesse'], '+.2f')} µm / 1000 pièces", "Somme des aᵢ·dᵢ.")
            pm, pp, r = serie["piecesSortieMoyenne"], serie["piecesSeuilPpm"], serie["intervalleRecalage"]
            if r is None:
                s.succes("Aucun re-réglage nécessaire : la dérive n'éloigne jamais le procédé des limites.")
            elif r == 0:
                s.erreur("Le procédé est déjà hors limites ou au-delà du seuil de ppm dès le réglage initial.")
            else:
                s.avertissement(
                    f"Recommandation : re-régler au plus tard toutes les {pieces(r)} pièces "
                    f"(moyenne hors limites après {'—' if pm is None else pieces(pm)} pièces, "
                    f"seuil de {fr(seuil, 'g')} ppm après {'—' if pp is None else pieces(pp)} pièces)."
                )

        section = z.section(rendu)

    def _ongletExplications(self, z: Zone, bundle: dict) -> None:
        """Démarche du calcul, section par section, avec les formules remplies."""
        for section in explicationsCalcul(bundle):
            z.sousTitre(section["titre"])
            z.texte(section["texte"])
            for formule in section["formules"]:
                z.formule(formule)

    def _ongletValidation(self, z: Zone, bundle: dict) -> None:
        """Dossier de validation : contrôles refaits sans le solveur, bilan, puis fichier HTML, PDF ou Word."""
        z.texte(
            "Le dossier refait chaque grandeur à la main, sans le solveur, et la compare au résultat affiché ; il "
            "relit aussi la table ISO 286 et confronte le Monte-Carlo à la formule."
        )
        editeur.editeurCartouche(z.repliable("Cartouche du dossier (projet, indice, auteur, révisions)"))

        def generer() -> None:
            state.v[CLE_DOSSIER] = dossierValidation(bundle["probleme"], bundle)
            state.v.pop(CLE_FICHIER, None)
            section.rafraichir()

        def preparer(format_: str) -> None:
            def fini(fichier: dict) -> None:
                state.v[CLE_FICHIER] = fichier
                state.v["calc.dossier.alerte"] = fichier["imagesManquantes"]
                section.rafraichir()

            def echec(e: Exception) -> None:
                state.v.pop(CLE_FICHIER, None)
                state.v["calc.dossier.erreur"] = f"Dossier {format_} impossible : {e}"
                section.rafraichir()

            tache.lancer(lambda: fichierDossier(problemeAvecCartouche(bundle), bundle, format_), fini, echec)

        def rendu(s: Zone) -> None:
            s.bouton("Générer le dossier de validation", generer)
            dossier = state.v.get(CLE_DOSSIER)
            if dossier is not None:
                (s.succes if dossier["nOk"] == dossier["nTotal"] else s.erreur)(dossier["bilan"])
                for c in [c for c in dossier["controles"] if c["statut"] != "OK"]:
                    s.texte(f"- {c['nom']} : attendu {fr(c['attendu'], '.6g')}, obtenu {fr(c['obtenu'], '.6g')}")
            format_ = s.radio("Format du fichier", list(FORMATS_DOSSIER), "calc.dossier.format",
                              apres=lambda: section.rafraichir())  # fmt: skip
            s.legende(
                "Le fichier reprend la saisie, les hypothèses, les résultats, les avertissements, ce bilan et tous les "
                "graphiques du calcul (comptez quelques secondes pour les images)."
            )
            s.bouton("Préparer le fichier", lambda: preparer(format_))
            if state.v.pop("calc.dossier.alerte", False):
                s.avertissement(AVERTISSEMENT_IMAGES)
            if "calc.dossier.erreur" in state.v:
                s.erreur(state.v.pop("calc.dossier.erreur"))
            fichier = state.v.get(CLE_FICHIER)
            if fichier:
                s.telecharger(f"Enregistrer le dossier (.{fichier['extension']})", fichier["contenu"],
                              f"dossier_calcul.{fichier['extension']}")  # fmt: skip

        section = z.section(rendu)

    def _ongletFichiers(self, z: Zone, bundle: dict) -> None:
        """Enregistrement et ouverture du problème, export des résultats en tableur."""
        self._enregistrerOuvrir(z, "onglet")
        z.sousTitre("Résultats du dernier calcul")
        a = bundle["affichage"]
        z.telecharger("Résultats Excel (.xlsx)", a["xlsx"], "resultats_chaine.xlsx")
        z.telecharger("Résultats tableur (.csv)", a["csv"], "resultats_chaine.csv")
        z.sousTitre("Feuille de chaîne Excel")
        z.legende(
            "Classeur à formules vivantes : modifiez une cote ou une tolérance dans Excel, le jeu, le Cpk et les ppm "
            "se recalculent. Une colonne garde le résultat de l'application pour contrôler la feuille."
        )
        z.telecharger(
            "Feuille de chaîne à formules (.xlsx)",
            lambda: exporterFeuilleChaine(problemeAvecCartouche(bundle), bundle),
            "feuille_chaine.xlsx",
        )
        z.sousTitre("Tableau de cotation")
        z.telecharger("Tableau de cotation (.xlsx)", a["cotationXlsx"], "tableau_cotation.xlsx")
        z.telecharger("Tableau de cotation (.csv)", a["cotationCsv"], "tableau_cotation.csv")
