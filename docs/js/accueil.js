"use strict";
// Page « Accueil » : trois actions pour démarrer, le reste (méthodes, outils, limites) sous « En savoir plus ».

(() => {
  const { $ } = App;

  async function apres() {
    $("ac-exemple").addEventListener("click", () => App.afficherPage("exemples"));
    $("ac-guide").addEventListener("click", () => {
      App.afficherPage("analyser");
      App.analyser.guide(true, 0);
      window.scrollTo(0, 0);
    });
    $("ac-ouvrir").addEventListener("click", () => {
      App.afficherPage("analyser");
      App.analyser.guide(false);
      App.analyser.ouvrirFichier(); // le clic vient de l'utilisateur : le navigateur accepte d'ouvrir le sélecteur
    });
    $("ac-assistant").addEventListener("click", () => App.afficherPage("assistant"));
    // liens vers tous les outils : construits ici, une fois toutes les pages enregistrées
    const titres = { analyser: "Analyser une chaîne", repartir: "Répartir les tolérances", comparer: "Comparer deux scénarios", mecanisme: "Mécanisme (plusieurs chaînes)",
      dossier: "Dossier de validation", assistant: "Assistant de chaîne", exemples: "Bibliothèque d'exemples", ajustement: "Choisir un ajustement ISO 286",
      iso286: "Tables ISO 286", materiaux: "Matériaux et dilatation" };
    $("ac-outils").replaceChildren(...Object.entries(titres).map(([id, texte]) => {
      const b = Object.assign(document.createElement("button"), { type: "button", className: "secondaire", textContent: texte });
      b.addEventListener("click", () => App.afficherPage(id));
      return b;
    }));
  }

  App.enregistrerPage({ id: "accueil", titre: "Accueil", apres });
})();
