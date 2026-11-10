"""Page « Mécanisme (plusieurs chaînes) » : constitue un mécanisme, calcule toutes ses chaînes et les compare.

État dans state.v, clés préfixées « meca. » : meca.nom (nom du mécanisme), meca.chaines (liste d'entrées
{id, probleme}), meca.suivant (prochain identifiant), meca.resultat (dernier calcul avec la copie des chaînes
calculées : masqué si le mécanisme change ensuite).
"""

import copy
from datetime import date

import pandas as pd

from chainecotes.bureau import state, tache
from chainecotes.bureau.widgets import COULEURS_VERDICT, Page, Zone
from chainecotes.core.errors import ErreurChaine
from chainecotes.plots._common import fr
from chainecotes.plots.mecanisme import figureCpkMecanisme
from chainecotes.services.comparaison import MAX_FICHIERS
from chainecotes.services.exemples import chargerExemple, listeExemples
from chainecotes.services.mecanisme import (
    MAX_CHAINES,
    calculerMecanisme,
    exporterMecanisme,
    exporterRapportPdf,
    exporterTableauDeBord,
    importerMecanisme,
    tableauDeBord,
    verdictGlobal,
)

TIRAGES = [20_000, 50_000, 200_000, 1_000_000]
SEUIL_CPK = 1.33
EXEMPLES = {e["id"]: e for e in listeExemples()}


def _init() -> None:
    for cle, defaut in (("meca.nom", "Mécanisme"), ("meca.chaines", []), ("meca.suivant", 1), ("meca.resultat", None)):
        state.v.setdefault(cle, defaut)


def _chaines() -> list[dict]:
    """Entrées {id, probleme} du mécanisme en construction."""
    _init()
    return state.v["meca.chaines"]


def _mecanisme() -> dict:
    """Mécanisme au format du service : dict nom, chaines (liste de problèmes)."""
    return {"nom": state.v["meca.nom"], "chaines": [e["probleme"] for e in _chaines()]}


def _nomLibre(nom: str, sauf: int | None = None) -> str:
    """Nom de chaîne qui n'existe pas encore dans le mécanisme : « Jeu J », puis « Jeu J (2) », « Jeu J (3) »…

    Entrées : nom souhaité, sauf (identifiant de la chaîne en cours de renommage, ignorée dans la comparaison).
    """
    pris = {e["probleme"]["condition"].get("nom") for e in _chaines() if e["id"] != sauf}
    candidat, i = nom, 2
    while candidat in pris:
        candidat, i = f"{nom} ({i})", i + 1
    return candidat


def ajouterChaines(problemes: list[dict]) -> str | None:
    """Ajoute des chaînes (copies) au mécanisme, en rendant leurs noms uniques.

    Entrée : problemes (liste de dicts condition, reglages, maillons). Sortie : None si tout est ajouté, sinon un
    message d'erreur (limite de MAX_CHAINES chaînes atteinte ; celles qui tiennent sont ajoutées).
    """
    for p in problemes:
        if len(_chaines()) >= MAX_CHAINES:
            return f"Limite de {MAX_CHAINES} chaînes atteinte : les chaînes suivantes n'ont pas été ajoutées."
        p = copy.deepcopy(p)
        p["condition"]["nom"] = _nomLibre(p["condition"].get("nom") or f"Chaîne {len(_chaines()) + 1}")
        _chaines().append({"id": state.v["meca.suivant"], "probleme": p})
        state.v["meca.suivant"] += 1
    return None


class PageMecanisme(Page):
    def construire(self) -> None:
        _init()
        self.gauche, self.droite = self.deuxPanneaux(self._tete, self._constitution, self._resultats)

    def tout(self) -> None:
        self.gauche.rafraichir()
        self.droite.rafraichir()

    def _dire(self, genre: str, texte: str) -> None:
        state.v["meca.message"] = (genre, texte)

    def _tete(self, z: Zone) -> None:
        z.titre("Mécanisme (plusieurs chaînes)")
        z.texte(
            "Un mécanisme réunit les chaînes de cotes (jeux fonctionnels) d'un même assemblage. Constituez-le à partir "
            "d'exemples, de fichiers ou de la chaîne courante, calculez toutes les chaînes d'un coup et repérez la plus "
            "fragile. Une chaîne en erreur n'empêche pas le calcul des autres."
        )

    def _ajouterExemple(self) -> None:
        erreur = ajouterChaines([chargerExemple(state.v["meca.exemple"])])
        self._dire("erreur", erreur) if erreur else self._dire("succes", "Exemple ajouté.")
        self.tout()

    def _ajouterCourante(self) -> None:
        erreur = ajouterChaines([state.probleme()])
        self._dire("erreur", erreur) if erreur else self._dire("succes", "Chaîne courante ajoutée.")
        self.tout()

    def _lireFichiers(self, fichiers: list[tuple[str, bytes]], remplacer: bool) -> None:
        """Ajoute les chaînes de chaque fichier, ou remplace tout le mécanisme (remplacer : un seul fichier lu)."""
        lus, erreurs = [], []
        if len(fichiers) > MAX_FICHIERS:
            erreurs.append(f"{len(fichiers) - MAX_FICHIERS} fichier(s) ignoré(s) : au plus {MAX_FICHIERS} à la fois.")
            fichiers = fichiers[:MAX_FICHIERS]
        for nom, octets in fichiers:
            try:
                lus.append((nom, importerMecanisme(octets.decode("utf-8-sig"))))
            except UnicodeDecodeError:
                erreurs.append(f"{nom} : ce n'est pas un texte UTF-8.")
            except ErreurChaine as e:
                erreurs.append(f"{nom} : {e.message}")
        if remplacer and lus:
            state.v["meca.chaines"] = []
            state.v["meca.nom"] = lus[0][1]["nom"] or "Mécanisme"
            lus = lus[:1]
        for _, m in lus:
            trop = ajouterChaines(m["chaines"])
            if trop:
                erreurs.append(trop)
        if erreurs:
            self._dire("erreur", " ".join(erreurs))
        elif lus:
            self._dire("succes", f"{len(lus)} fichier(s) lu(s), {len(_chaines())} chaîne(s) dans le mécanisme.")
        self.tout()

    def _renommer(self, identifiant: int) -> None:
        """Le nom saisi devient celui de la cote condition de la chaîne, rendu unique et non vide."""
        cle = f"meca.nom.{identifiant}"
        for e in _chaines():
            if e["id"] == identifiant:
                c = e["probleme"]["condition"]
                saisi = str(state.v[cle] or "").strip()
                c["nom"] = _nomLibre(saisi or c.get("nom") or f"Chaîne {identifiant}", identifiant)
                state.v[cle] = c["nom"]
        self.tout()

    def _retirer(self, identifiant: int) -> None:
        state.v["meca.chaines"] = [e for e in _chaines() if e["id"] != identifiant]
        state.v.pop(f"meca.nom.{identifiant}", None)
        self.tout()

    def _ouvrirDansCalcul(self, probleme: dict) -> None:
        if not self.fenetre.confirmerAbandon():
            return
        state.definirProbleme(copy.deepcopy(probleme))
        state.definirRevisions([])
        state.nouvelleEtude()
        state.effacerResultat()
        self.aller("calcul")

    def _calculer(self) -> None:
        if not _chaines():
            self._dire("erreur", "Le mécanisme ne contient aucune chaîne.")
            self.gauche.rafraichir()
            return
        n, graine, seuil = state.v["meca.n"], int(state.v["meca.graine"]), float(state.v["meca.seuil"])
        mecanisme = copy.deepcopy(_mecanisme())

        def fini(resultat: dict) -> None:
            state.v["meca.resultat"] = {"resultat": resultat, "n": n, "chaines": mecanisme["chaines"], "seuil": seuil}
            self.droite.rafraichir()

        def echec(e: Exception) -> None:
            self._dire("erreur", f"Calcul impossible : {getattr(e, 'message', e)}")
            self.gauche.rafraichir()

        tache.lancer(lambda: calculerMecanisme(mecanisme, n, graine, seuil), fini, echec)

    def _constitution(self, z: Zone) -> None:
        """Colonne de saisie : constitution, liste des chaînes, enregistrement, ouverture."""
        z.bouton("Calculer toutes les chaînes", self._calculer, primaire=True)
        z.sousTitre("Constituer le mécanisme")
        z.saisie("Nom du mécanisme", "meca.nom")
        z.liste("Exemple à ajouter", list(EXEMPLES), "meca.exemple", format=lambda i: EXEMPLES[i]["titre"])
        z.bouton("Ajouter l'exemple", self._ajouterExemple)
        z.bouton("Ajouter l'étude en cours", self._ajouterCourante)
        z.ouvrirFichier("Ajouter des fichiers (.json) : problèmes ou mécanismes", "Études (*.json)",
                        lambda f: self._lireFichiers(f, False), multiple=True,
                        aide="Chaque fichier de problème ajoute une chaîne ; un fichier mécanisme ajoute toutes ses "
                        "chaînes.")  # fmt: skip
        z.messageGarde("meca.message")

        z.sousTitre(f"Chaînes ({len(_chaines())})")
        if not _chaines():
            z.info("Aucune chaîne : ajoutez un exemple, la chaîne courante ou un fichier.")
        for e in _chaines():
            i, p = e["id"], e["probleme"]
            carte = z.cadre()
            state.v[f"meca.nom.{i}"] = p["condition"].get("nom") or ""
            carte.saisie("Nom de la chaîne", f"meca.nom.{i}", apres=lambda i=i: self._renommer(i))
            c = carte.colonnes(2)
            c[0].bouton("Retirer", lambda i=i: self._retirer(i))
            c[1].bouton("Ouvrir dans Calcul", lambda p=p: self._ouvrirDansCalcul(p))
            carte.legende(f"{len(p['maillons'])} maillon(s).")

        z.sousTitre("Enregistrer / ouvrir")
        if _chaines():

            def enregistrer() -> str:
                try:
                    return exporterMecanisme(_mecanisme())
                except ErreurChaine as erreur:
                    self._dire("erreur", erreur.message)
                    self.gauche.rafraichir()
                    raise

            z.telecharger("Enregistrer le mécanisme (.json)", enregistrer, "mecanisme.json")
        z.ouvrirFichier("Ouvrir un mécanisme (.json)", "Mécanisme (*.json)", lambda f: self._lireFichiers(f, True),
                        aide="Remplace toutes les chaînes du mécanisme en cours.")  # fmt: skip
        cols = z.repliable("Options du calcul").colonnes(3)
        cols[0].liste("Tirages Monte-Carlo", TIRAGES, "meca.n", format=lambda n: f"{n:,}".replace(",", " "),
                      defaut=TIRAGES[1], aide="Plus de tirages : ppm simulé plus précis, calcul plus long.")  # fmt: skip
        cols[1].nombre("Graine", "meca.graine", 1, mini=0, decimales=0, aide="Même graine : mêmes tirages.")
        cols[2].nombre("Seuil de Cpk", "meca.seuil", SEUIL_CPK, mini=0.0, decimales=2,
                       aide="Cpk minimal visé (1,33 est courant) : ligne de seuil du graphique.")  # fmt: skip

    def _resultats(self, z: Zone) -> None:
        """Zone de visualisation : verdict global, graphique des Cpk, tableau de bord, erreurs isolées."""
        garde = state.v["meca.resultat"]
        if garde is None:
            z.legende("Ajoutez des chaînes puis cliquez sur « Calculer » : le tableau de bord apparaît ici.")
            return
        if garde["chaines"] != [e["probleme"] for e in _chaines()]:
            z.info("Le mécanisme a changé depuis le dernier calcul : cliquez sur « Calculer ».")
            return
        res, g = garde["resultat"], garde["resultat"]["global"]
        if res["nTirages"] < garde["n"]:
            z.legende(f"Monte-Carlo réduit à {res['nTirages']} tirages par chaîne pour tenir le temps de calcul.")
        niveau, phrase = verdictGlobal(res)
        z.message(niveau, phrase)
        for nom in g["enErreur"]:
            z.avertissement(f"Chaîne « {nom} » : calcul impossible, les autres chaînes sont calculées.")
        pire = g["pireCpk"]
        z.metriques(
            [
                ("Pire Cpk", fr(pire, ".3g") if pire is not None else "—", f"Chaîne : {g['chainePireCpk']}"),
                ("Chaînes hors tolérance", f"{len(g['horsTolerance'])} sur {g['nChaines']}"),
            ],
            2,
        )
        z.figure(*figureCpkMecanisme(res["lignes"], garde["seuil"]))
        z.tableau(tableauDeBord(res["lignes"], garde["seuil"]), couleurs={"Verdict": COULEURS_VERDICT.get})
        z.telecharger("Tableau de bord (.xlsx)", lambda: exporterTableauDeBord(res), "mecanisme_tableau_de_bord.xlsx")
        z.telecharger("Rapport (.pdf)", lambda: exporterRapportPdf(res, date.today()), "mecanisme_rapport.pdf")
        for x in res["lignes"]:
            if x["erreur"]:
                z.erreur(f"{x['nom']} : {x['erreur']}")
