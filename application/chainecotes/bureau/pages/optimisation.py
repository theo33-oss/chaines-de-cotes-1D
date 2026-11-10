"""Page « Comparaison » (mode « Comparer » de l'étude) : deux scénarios, ou un lot de fichiers.

Deux onglets : (1) comparer le problème courant à un autre scénario ; (2) comparer plusieurs fichiers. Le problème
courant est celui de l'étude (state.probleme()). Les résultats sont gardés avec une copie du problème calculé : si
la saisie change, ils sont masqués jusqu'au prochain calcul. La répartition au coût minimal est dans le mode
« Répartir » (pages/inverse.py).
"""

import copy

import pandas as pd

from chainecotes.bureau import state, tache
from chainecotes.bureau.pages.inverse import problemeRepartition
from chainecotes.bureau.widgets import COULEURS_VERDICT, Page, Zone
from chainecotes.core.errors import ErreurChaine
from chainecotes.plots.optimisation import figureScenarios
from chainecotes.services.calcul import calculerChaine
from chainecotes.services.comparaison import MAX_FICHIERS, comparerFichiers, comparerScenarios
from chainecotes.services.exemples import chargerExemple, listeExemples
from chainecotes.services.projet_io import importerProbleme

SOURCE_REPARTITION = "Résultat de la répartition (mode Répartir)"
SOURCE_EXEMPLE, SOURCE_FICHIER = "Exemple de la bibliothèque", "Fichier JSON"
CLE_SCENARIOS = "opt.scen.resultat"
CLE_FICHIERS = "opt.fich.resultat"
N_MC = 20000  # tirages Monte-Carlo des comparaisons de fichiers (la synthèse n'a pas besoin de plus)


class PageOptimisation(Page):
    def rendre(self, z: Zone) -> None:
        z.modes("optimisation")
        z.titre("Comparaison de scénarios et de fichiers")
        z.texte(
            "Comparez l'étude en cours à un autre scénario, ou comparez un lot de fichiers d'études. La répartition "
            "des tolérances, y compris au coût minimal, est dans le mode « Répartir les tolérances »."
        )
        z.onglets(
            {
                "Comparer deux scénarios": self._ongletScenarios,
                "Comparer des fichiers": self._ongletFichiers,
            },
            cle="opt.onglet",
        )

    # --- Comparer deux scénarios ---

    def _ongletScenarios(self, z: Zone) -> None:
        gauche, droite = z.colonnes([2, 3])
        self.scenG = gauche.section(self._saisieScenarios)
        self.scenD = droite.section(self._visuelScenarios)

    def _saisieScenarios(self, z: Zone) -> None:
        z.bouton("Calculer", self._calculerScenarios, primaire=True)
        z.legende("Le scénario A est l'étude en cours.")
        source = z.radio("Scénario B", [SOURCE_REPARTITION, SOURCE_EXEMPLE, SOURCE_FICHIER], "opt.scen.source",
                         apres=lambda: self.scenG.rafraichir())  # fmt: skip
        if source == SOURCE_REPARTITION:
            z.legende("Compare l'étude en cours à la chaîne obtenue par le dernier calcul du mode « Répartir les "
                      "tolérances » (avant « Appliquer à l'étude »).")  # fmt: skip
        elif source == SOURCE_EXEMPLE:
            exemples = {e["id"]: e["titre"] for e in listeExemples()}
            z.liste("Exemple", list(exemples), "opt.scen.exemple", format=exemples.get)
        else:

            def lire(fichiers: list[tuple[str, bytes]]) -> None:
                state.v["opt.scen.fichier"] = fichiers[0]
                self.scenG.rafraichir()

            z.ouvrirFichier("Fichier du scénario B (.json)", "Problème (*.json)", lire)
            if "opt.scen.fichier" in state.v:
                z.legende(f"Fichier choisi : {state.v['opt.scen.fichier'][0]}")
        if "opt.scen.erreur" in state.v:
            z.erreur(state.v.pop("opt.scen.erreur"))

    def _scenarioB(self) -> dict | None:
        """Problème du scénario B ; None et message d'erreur gardé s'il n'est pas lisible."""
        source = state.v.get("opt.scen.source", SOURCE_REPARTITION)
        if source == SOURCE_REPARTITION:
            garde = state.v.get("inv.resultat")
            if garde is None:
                state.v["opt.scen.erreur"] = (
                    "Aucune répartition calculée : ouvrez le mode « Répartir les tolérances », cliquez sur "
                    "« Calculer », puis revenez ici."
                )
                return None
            return problemeRepartition(garde)
        if source == SOURCE_EXEMPLE:
            return chargerExemple(state.v["opt.scen.exemple"])
        fichier = state.v.get("opt.scen.fichier")
        if fichier is None:
            state.v["opt.scen.erreur"] = "Choisissez un exemple ou ouvrez un fichier valide pour le scénario B."
            return None
        try:
            return importerProbleme(fichier[1].decode("utf-8-sig"))
        except (ErreurChaine, UnicodeDecodeError) as e:
            state.v["opt.scen.erreur"] = getattr(e, "message", "ce fichier n'est pas un texte UTF-8 lisible.")
            return None

    def _calculer(self) -> None:
        """F5 : calcule l'onglet affiché (scénarios ou fichiers)."""
        if state.v.get("opt.onglet") == "Comparer des fichiers":
            self._comparer()
        else:
            self._calculerScenarios()

    def _calculerScenarios(self) -> None:
        """Calcule les deux scénarios et garde la comparaison."""
        state.v.pop(CLE_SCENARIOS, None)
        a, b = copy.deepcopy(state.probleme()), self._scenarioB()
        if b is None:
            self.scenG.rafraichir()
            self.scenD.rafraichir()
            return

        def travail() -> dict:
            return comparerScenarios(calculerChaine(copy.deepcopy(a), False), calculerChaine(copy.deepcopy(b), False))

        def fini(cmp: dict) -> None:
            state.v[CLE_SCENARIOS] = {"a": a, "b": b, "cmp": cmp}
            self.scenD.rafraichir()

        def echec(e: Exception) -> None:
            state.v["opt.scen.erreur"] = getattr(e, "message", str(e))
            self.scenG.rafraichir()

        tache.lancer(travail, fini, echec)

    def _visuelScenarios(self, z: Zone) -> None:
        garde = state.v.get(CLE_SCENARIOS)
        if garde is None:
            z.info("Choisissez le scénario B, puis cliquez sur « Calculer ».")
        elif garde["a"] != state.probleme():
            z.info("L'étude en cours a changé depuis le dernier calcul : cliquez sur « Calculer ».")
        else:
            self._resultatsScenarios(z, garde["cmp"])

    def _resultatsScenarios(self, z: Zone, cmp: dict) -> None:
        """Phrases de synthèse, tableau d'écarts, barres jumelées."""
        z.info("\n\n".join(cmp["phrases"]))
        unites = {"jeuMini": "Jeu mini (mm)", "jeuMaxi": "Jeu maxi (mm)", "cpk": "Cpk", "ppm": "ppm"}
        z.tableau(
            pd.DataFrame(
                [
                    {"Grandeur": lib, "A": cmp[k]["a"], "B": cmp[k]["b"], "Écart B − A": cmp[k]["delta"]}
                    for k, lib in unites.items()
                ]
            ),
            dict.fromkeys(("A", "B", "Écart B − A"), "%.4f"),
        )
        z.tableau(
            pd.DataFrame(
                {
                    "Maillon": [m["nom"] for m in cmp["maillons"]],
                    "Statut": [m["statut"] for m in cmp["maillons"]],
                    "IT A (mm)": [m["itA"] for m in cmp["maillons"]],
                    "IT B (mm)": [m["itB"] for m in cmp["maillons"]],
                    "Écart (mm)": [m["delta"] for m in cmp["maillons"]],
                }
            ),
            dict.fromkeys(("IT A (mm)", "IT B (mm)", "Écart (mm)"), "%.4f"),
        )
        nomB = "B (répartition)" if state.v.get("opt.scen.source", SOURCE_REPARTITION) == SOURCE_REPARTITION else "B"
        z.figure(*figureScenarios(cmp["maillons"], "A (étude en cours)", nomB))

    # --- Comparer des fichiers ---

    def _ongletFichiers(self, z: Zone) -> None:
        self.fich = z.section(self._fichiers)

    def _comparer(self) -> None:
        """Compare les fichiers choisis ; les erreurs de fichiers sont listées sans bloquer."""
        fichiers = list(state.v.get("opt.fich.depot") or [])
        textes, erreurs = {}, []
        if len(fichiers) > MAX_FICHIERS:
            erreurs.append({"fichier": "(trop de fichiers)", "message": f"seuls les {MAX_FICHIERS} premiers sont lus."})
            fichiers = fichiers[:MAX_FICHIERS]
        for nomFichier, octets in fichiers:
            nom, k = nomFichier, 2
            while nom in textes:  # deux fichiers de même nom : suffixe
                nom, k = f"{nomFichier} ({k})", k + 1
            try:
                textes[nom] = octets.decode("utf-8-sig")
            except UnicodeDecodeError:
                erreurs.append({"fichier": nom, "message": "ce fichier n'est pas un texte UTF-8 lisible."})
        if not textes and not erreurs:
            state.v["opt.fich.erreur"] = "Choisissez au moins un fichier JSON."
            self.fich.rafraichir()
            return

        def fini(r: dict) -> None:
            r["erreurs"] = erreurs + r["erreurs"]
            state.v[CLE_FICHIERS] = r
            self.fich.rafraichir()

        def echec(e: Exception) -> None:
            state.v["opt.fich.erreur"] = getattr(e, "message", str(e))
            self.fich.rafraichir()

        tache.lancer(lambda: comparerFichiers(textes, N_MC), fini, echec)

    def _fichiers(self, z: Zone) -> None:
        def choisir(fichiers: list[tuple[str, bytes]]) -> None:
            state.v["opt.fich.depot"] = fichiers
            self.fich.rafraichir()

        z.ouvrirFichier("Choisir des fichiers de problèmes ou de mécanismes (.json)", "Études (*.json)", choisir,
                        multiple=True)  # fmt: skip
        if state.v.get("opt.fich.depot"):
            z.legende("Fichiers choisis : " + ", ".join(n for n, _ in state.v["opt.fich.depot"]))
        z.bouton("Comparer les fichiers", self._comparer, primaire=True)
        if "opt.fich.erreur" in state.v:
            z.erreur(state.v.pop("opt.fich.erreur"))
        r = state.v.get(CLE_FICHIERS)
        if r is None:
            z.info("Choisissez plusieurs fichiers puis cliquez sur « Comparer les fichiers ».")
            return
        for e in r["erreurs"]:
            z.avertissement(f"{e['fichier']} : {e['message']}")
        if r["lignes"]:
            z.tableau(
                pd.DataFrame(
                    {
                        "Fichier": [x["fichier"] for x in r["lignes"]],
                        "Chaîne": [x["nom"] for x in r["lignes"]],
                        "Jeu mini (mm)": [x["jeuMini"] for x in r["lignes"]],
                        "Jeu maxi (mm)": [x["jeuMaxi"] for x in r["lignes"]],
                        "Verdict": [x["verdict"] for x in r["lignes"]],
                        "Cp": [x["cp"] for x in r["lignes"]],
                        "Cpk": [x["cpk"] for x in r["lignes"]],
                        "ppm (formule)": [x["ppmFormule"] for x in r["lignes"]],
                        "ppm (Monte-Carlo)": [x["ppmMonteCarlo"] for x in r["lignes"]],
                        "Maillon dominant": [x["dominant"] for x in r["lignes"]],
                        "Erreur": [x["erreur"] or "" for x in r["lignes"]],
                    }
                ),
                {"Jeu mini (mm)": "%.4f", "Jeu maxi (mm)": "%.4f", "Cp": "%.2f", "Cpk": "%.2f"},
                couleurs={"Verdict": COULEURS_VERDICT.get},
            )
        elif not r["erreurs"]:
            z.info("Aucune chaîne à afficher.")
