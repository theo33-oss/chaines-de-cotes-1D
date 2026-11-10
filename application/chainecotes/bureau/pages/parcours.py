"""Page « Nouvelle étude » : parcours guidé en 5 étapes, de la cote condition au dossier de validation.

Chaque étape réutilise les éditeurs (chainecotes.bureau.editeur) et les services de calcul ; le mode expert est la
page Calcul. Le calcul du parcours est gardé sous « guide.bundle », avec une copie du problème : si la saisie change,
il est masqué jusqu'au prochain calcul.
"""

import copy

import pandas as pd

from chainecotes.bureau import editeur, etude, state, tache
from chainecotes.bureau.pages.calcul import problemeAvecCartouche
from chainecotes.bureau.widgets import COULEURS_VERDICT, Page, Zone
from chainecotes.core.chaine import libelleVerdict
from chainecotes.core.errors import ErreurChaine
from chainecotes.plots import graphiques
from chainecotes.plots.schema import figureSchema
from chainecotes.services import projet_io
from chainecotes.services.calcul import apercuChaine, calculerChaine
from chainecotes.services.conclusion import conclusionEtude
from chainecotes.services.controles import controlerProbleme
from chainecotes.services.dossier_fichier import AVERTISSEMENT_IMAGES, FORMATS_DOSSIER, fichierDossier
from chainecotes.services.exemples import chargerExemple, listeExemples

ETAPES = ["Point de départ", "Cote condition", "Maillons", "Calcul et verdict", "Dossier"]
CLE_ETAPE, CLE_BUNDLE, CLE_FICHIER, CLE_MESSAGE = "guide.etape", "guide.bundle", "guide.fichier", "guide.message"
N_TIRAGES = 50_000  # Monte-Carlo du parcours : assez pour un verdict, rapide à calculer
EXEMPLES = {e["id"]: e["titre"] for e in listeExemples()}


class PageParcours(Page):
    def rendre(self, z: Zone) -> None:
        z.titre("Nouvelle étude")
        z.texte(
            "Parcours guidé en cinq étapes pour mener une chaîne de cotes du jeu à garantir jusqu'au dossier à joindre "
            "à votre note de calcul. Vous préférez tout voir d'un coup ? Ouvrez « Étude en cours »."
        )
        z.lien("calcul", "Tout voir d'un coup : Étude en cours, mode Analyser")
        state.v.setdefault(CLE_ETAPE, ETAPES[0])
        self.corps = None
        z.radio("", ETAPES, CLE_ETAPE, apres=self.relance)
        self.corps = z.section(self._etape)

    def relance(self) -> None:
        self.sections[0].rafraichir()

    def _etape(self, z: Zone) -> None:
        i = ETAPES.index(state.v[CLE_ETAPE])
        z.sousTitre(f"Étape {i + 1} sur {len(ETAPES)} : {ETAPES[i]}")
        (self._depart, self._condition, self._maillons, self._verdict, self._dossier)[i](z)
        precedent, suivant = z.colonnes(2)
        precedent.bouton("Précédent", lambda: self._aller(-1), actif=i > 0)
        suivant.bouton("Suivant", lambda: self._aller(1), primaire=True, actif=i < len(ETAPES) - 1)

    def _aller(self, pas: int) -> None:
        i = ETAPES.index(state.v[CLE_ETAPE]) + pas
        state.v[CLE_ETAPE] = ETAPES[min(max(i, 0), len(ETAPES) - 1)]
        self.relance()

    def _chargerExemple(self) -> None:
        if not self.fenetre.confirmerAbandon():
            return
        state.definirProbleme(chargerExemple(state.v["guide.exemple"]))
        state.definirRevisions([])
        state.nouvelleEtude()
        state.v.pop(CLE_BUNDLE, None)
        state.v[CLE_MESSAGE] = ("succes", f"Exemple chargé : {EXEMPLES[state.v['guide.exemple']]}.")
        self.corps.rafraichir()

    def _ouvrirFichier(self, fichiers: list[tuple[str, bytes]]) -> None:
        nom, octets = fichiers[0]
        if not self.fenetre.confirmerAbandon():
            return
        try:
            ouvert = projet_io.importerProjet(octets.decode("utf-8-sig"))
        except UnicodeDecodeError:
            state.v[CLE_MESSAGE] = ("erreur", "Fichier non reconnu : ce n'est pas un texte UTF-8.")
        except ErreurChaine as e:
            state.v[CLE_MESSAGE] = ("erreur", e.message)
        else:
            state.definirProbleme(ouvert["probleme"])
            state.definirRevisions(ouvert["revisions"])
            state.nouvelleEtude(state.v.pop("fichier.chemin", None))
            state.v.pop(CLE_BUNDLE, None)
            state.v[CLE_MESSAGE] = ("succes", f"Étude « {nom} » ouverte.")
        self.corps.rafraichir()

    def _depart(self, z: Zone) -> None:
        z.texte(
            "Une chaîne de cotes répond à une question : **le jeu entre deux pièces reste-t-il dans ses limites ?** "
            "Partez d'un exemple, d'une étude déjà enregistrée, ou de la chaîne en cours."
        )
        p = state.probleme()
        z.info(f"Étude en cours : « {p['condition'].get('nom') or 'Jeu J'} », {len(p['maillons'])} maillon(s).")
        z.liste("Exemple", list(EXEMPLES), "guide.exemple", format=EXEMPLES.get)
        z.bouton("Charger cet exemple", self._chargerExemple)
        z.ouvrirFichier("Ou ouvrir une étude (.json)", "Étude (*.json)", self._ouvrirFichier,
                        aide="Fichier enregistré par cette application, avec ses révisions éventuelles.")  # fmt: skip
        z.lien("assistant", "Je pars de pièces et de contacts : Assistant de chaîne")
        z.messageGarde(CLE_MESSAGE)

    def _condition(self, z: Zone) -> None:
        z.texte(
            "La **cote condition** est le jeu (ou le serrage, le dépassement) à garantir. Donnez-lui un nom et ses "
            "limites : **Jmin** est le plus petit jeu acceptable, **Jmax** le plus grand."
        )
        editeur.editeurCondition(z, lambda: None)
        editeur.editeurReglages(z.repliable("Réglages du calcul (procédé, température)"), lambda: None, lambda: self.corps.rafraichir())

    def _maillons(self, z: Zone) -> None:
        z.texte(
            "Ajoutez une ligne par cote de la chaîne : son **sens** (« + » si elle agrandit le jeu, « − » si elle le "
            "réduit), sa **cote nominale** et sa **tolérance** (désignation ISO comme H7, ou écarts ES / EI)."
        )
        editeur.editeurMaillons(z, lambda: schema.rafraichir())

        def rendu(s: Zone) -> None:
            p = state.probleme()
            apercu = apercuChaine(p)
            s.figure(*figureSchema(p, apercu))
            if "erreur" in apercu:
                return
            controles = controlerProbleme(p)
            if not controles:
                s.succes("Aucun défaut repéré dans la saisie.")
            for c in controles:
                {"erreur": s.erreur, "avertissement": s.avertissement, "info": s.info}[c["niveau"]](c["message"])

        schema = z.section(rendu)

    def _calculer(self) -> None:
        p = copy.deepcopy(state.probleme())

        def fini(bundle: dict) -> None:
            state.v[CLE_BUNDLE] = bundle
            state.v.pop(CLE_FICHIER, None)
            state.ajouterHistorique(bundle, N_TIRAGES, 1)
            self.corps.rafraichir()

        def echec(e: Exception) -> None:
            state.v.pop(CLE_BUNDLE, None)
            state.v[CLE_MESSAGE] = ("erreur", f"Calcul impossible : {getattr(e, 'message', e)}")
            self.corps.rafraichir()

        tache.lancer(lambda: calculerChaine(p, n=N_TIRAGES), fini, echec)

    def _verdict(self, z: Zone) -> None:
        z.texte("Lancez le calcul, puis lisez le verdict : il dit si le jeu tient et sur quelle cote agir.")
        z.bouton("Calculer", self._calculer, primaire=True)
        z.messageGarde(CLE_MESSAGE)
        bundle = state.v.get(CLE_BUNDLE)
        if bundle is None:
            return
        if state.sansCartouche(bundle["probleme"]) != state.sansCartouche(state.probleme()):
            z.info("La saisie a changé depuis le dernier calcul : cliquez sur « Calculer » pour mettre à jour.")
            return
        c = conclusionEtude(bundle)
        z.message(c["niveau"], c["titre"])
        z.texte("\n".join(f"- {x}" for x in c["details"]))
        if c["conseils"]:
            z.texte("**Que faire ?**\n\n" + "\n".join(f"- {x}" for x in c["conseils"]))
        z.figure(*graphiques.figurePareto(bundle))
        if bundle["mc"] is not None:
            z.figure(*graphiques.figureMonteCarlo(bundle))
        v, cond = bundle["verdicts"], bundle["res"]["condition"]
        z.tableau(
            pd.DataFrame(
                [
                    {
                        "Méthode": "Pire des cas",
                        "Jeu mini (mm)": v["pireCas"]["min"],
                        "Jeu maxi (mm)": v["pireCas"]["max"],
                        "Verdict": libelleVerdict(v["pireCas"]["ok"], cond),
                    },
                    {
                        "Méthode": "Statistique ± kσ",
                        "Jeu mini (mm)": v["rssK"]["min"],
                        "Jeu maxi (mm)": v["rssK"]["max"],
                        "Verdict": libelleVerdict(v["rssK"]["ok"] and v["rssProc"]["ok"], cond),
                    },
                ]
            ),
            {"Jeu mini (mm)": "%.4f", "Jeu maxi (mm)": "%.4f"},
            couleurs={"Verdict": COULEURS_VERDICT.get},
        )
        z.lien("calcul", "Aller plus loin : Étude en cours, mode Analyser")

    def _dossier(self, z: Zone) -> None:
        z.texte("Complétez le cartouche, gardez une révision, puis enregistrez le dossier et l'étude.")
        editeur.editeurCartouche(z.repliable("Cartouche du dossier (projet, indice, auteur)", ouvert=True))
        etude.revisionsEtude(z.repliable("Révisions de l'étude"), lambda: self.corps.rafraichir())
        bundle = state.v.get(CLE_BUNDLE)

        def preparer(format_: str) -> None:
            def fini(fichier: dict) -> None:
                state.v[CLE_FICHIER] = fichier
                self.corps.rafraichir()

            def echec(e: Exception) -> None:
                state.v.pop(CLE_FICHIER, None)
                state.v["guide.erreur"] = f"Dossier {format_} impossible : {e}"
                self.corps.rafraichir()

            tache.lancer(lambda: fichierDossier(problemeAvecCartouche(bundle), bundle, format_), fini, echec)

        if bundle is None:
            z.info("Calculez d'abord à l'étape « Calcul et verdict » pour préparer le dossier.")
        else:
            format_ = z.radio("Format du dossier", list(FORMATS_DOSSIER), "guide.format")
            z.bouton("Préparer le dossier", lambda: preparer(state.v["guide.format"] or format_))
            if "guide.erreur" in state.v:
                z.erreur(state.v.pop("guide.erreur"))
            fichier = state.v.get(CLE_FICHIER)
            if fichier:
                if fichier["imagesManquantes"]:
                    z.avertissement(AVERTISSEMENT_IMAGES)
                z.telecharger(f"Enregistrer le dossier (.{fichier['extension']})", fichier["contenu"],
                              f"dossier_calcul.{fichier['extension']}")  # fmt: skip
        z.bouton("Enregistrer l'étude (.json)", self.fenetre.enregistrerSous)
