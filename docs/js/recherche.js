"use strict";
// Recherche globale : « / » ou Ctrl+K ouvre une fenêtre pour aller à une page, une étape de l'étude ou un sujet
// (Cpk, Monte-Carlo, dilatation, ISO 286, Excel…). Flèches pour choisir, Entrée pour y aller, Échap pour fermer.

(() => {
  const { $ } = App;

  const sansAccent = (t) => String(t).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

  const etape = (id) => () => {
    App.afficherPage("analyser");
    const el = $(id);
    if (!el) return;
    if (el.hidden) { App.messageFlottant("Pas encore de résultat : cliquez sur « Calculer » dans la page Étude.", "info"); return; }
    if (el.tagName === "DETAILS") el.open = true;
    requestAnimationFrame(() => el.scrollIntoView({ behavior: "smooth", block: "start" }));
  };
  const page = (id) => () => App.afficherPage(id);

  // [titre, mots-clés, action]
  const ENTREES = [
    ["Accueil", "demarrer commencer presentation methodes limites", page("accueil")],
    ["Mes études", "enregistrer copies favoris exporter importer navigateur", () => { App.afficherPage("accueil"); requestAnimationFrame(() => $("mes-etudes")?.scrollIntoView({ behavior: "smooth" })); }],
    ["Étude : départ (exemple, ouvrir, lien)", "exemple charger ouvrir enregistrer fichier json lien partage reprendre", etape("b-depart")],
    ["Étude : cote condition (Jmin, Jmax)", "jeu limites jmin jmax condition k sigma temperature reference tolerance generale 2768 decentrage deux cotes condition cf2", etape("b-condition")],
    ["Étude : maillons (cotes, sens, tolérances)", "cotes tolerances iso 286 h7 sens plus moins loi normale uniforme triangulaire dilatation materiau alpha effet thermique image", etape("b-maillons")],
    ["Étude : résultats et verdict", "calculer verdict pire des cas statistique rss monte-carlo cp cpk ppm pareto excel", etape("resultats")],
    ["Optimiser les tolérances", "repartir repartition cout budget procedes atelier resserrer", page("repartir")],
    ["Comparer des chaînes et des cotes condition", "comparatif plusieurs chaines colonnes scenarios ab cf nouvelle cf cote condition tableau cote a cote", page("comparer")],
    ["Dossier de validation", "dossier validation cartouche note de calcul html pdf controles", page("dossier")],
    ["Mécanisme (plusieurs chaînes)", "mecanisme assemblage chaines jeux fonctionnels", page("mecanisme")],
    ["Assistant de chaîne", "assistant construire pieces contacts surfaces", page("assistant")],
    ["Bibliothèque d'exemples", "exemples reducteur roulement bibliotheque cas", page("exemples")],
    ["Ajustements ISO 286", "ajustement arbre alesage jeu serrage glissant", page("ajustement")],
    ["Tables ISO 286", "iso 286 ecarts it tolerances normalisees tables", page("iso286")],
    ["Matériaux et dilatation", "materiaux dilatation alpha acier aluminium temperature courbes", page("materiaux")],
    ["Capabilité Cp et Cpk", "cp cpk capabilite ppm hors tolerance", etape("resultats")],
    ["Monte-Carlo", "simulation tirages aleatoires rebut", etape("resultats")],
    ["Pire des cas et statistique (RSS)", "pire des cas statistique rss somme quadratique", etape("resultats")],
    ["Exporter en Excel", "excel xlsx formules classeur bloc-notes txt demander a une ia", etape("resultats")],
  ];

  let dialogue = null, champ = null, liste = null, trouvees = [], actif = 0, ouvertPar = null;

  function chercher(q) {
    const mots = sansAccent(q).split(/\s+/).filter(Boolean);
    if (!mots.length) return ENTREES.slice(0, 8).map((e) => ({ e, score: 0 }));
    return ENTREES.map((e) => {
      const titre = sansAccent(e[0]), tout = titre + " " + e[1];
      let score = 0;
      for (const m of mots) {
        if (titre.split(/[\s:()'’,-]+/).some((w) => w.startsWith(m))) score += 3;
        else if (tout.includes(m)) score += 1;
        else return { e, score: -1 };
      }
      return { e, score };
    }).filter((x) => x.score > 0).sort((a, b) => b.score - a.score).slice(0, 8);
  }

  function rendre() {
    trouvees = chercher(champ.value);
    actif = Math.min(actif, Math.max(0, trouvees.length - 1));
    liste.replaceChildren(...trouvees.map((x, i) => {
      const li = Object.assign(document.createElement("li"), { id: "rech-" + i, textContent: x.e[0] });
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", String(i === actif));
      li.addEventListener("mousedown", (ev) => { ev.preventDefault(); aller(i); });
      return li;
    }));
    if (!trouvees.length) liste.append(Object.assign(document.createElement("li"), { className: "rech-vide", textContent: "Rien ne correspond. Essayez « cpk », « excel », « dilatation »…" }));
    champ.setAttribute("aria-activedescendant", trouvees.length ? "rech-" + actif : "");
  }

  function aller(i) {
    const x = trouvees[i];
    fermer(false);
    if (x) x.e[2]();
  }

  function fermer(rendreFocus = true) {
    if (dialogue && dialogue.open) dialogue.close();
    if (rendreFocus && ouvertPar && ouvertPar.isConnected) ouvertPar.focus();
  }

  function ouvrir() {
    if (!dialogue) construire();
    if (dialogue.open) return;
    ouvertPar = document.activeElement;
    champ.value = "";
    actif = 0;
    rendre();
    dialogue.showModal();
    champ.focus();
  }

  function construire() {
    dialogue = document.createElement("dialog");
    dialogue.id = "recherche";
    dialogue.setAttribute("aria-label", "Rechercher dans l'outil");
    const titre = Object.assign(document.createElement("p"), { className: "legende", textContent: "Aller à… (page, étape ou sujet). Échap pour fermer." });
    champ = Object.assign(document.createElement("input"), { type: "search", placeholder: "Rechercher : cpk, excel, dilatation, comparer…" });
    champ.setAttribute("role", "combobox");
    champ.setAttribute("aria-expanded", "true");
    champ.setAttribute("aria-controls", "rech-liste");
    champ.setAttribute("aria-label", "Rechercher");
    liste = Object.assign(document.createElement("ul"), { id: "rech-liste" });
    liste.setAttribute("role", "listbox");
    dialogue.append(titre, champ, liste);
    champ.addEventListener("input", () => { actif = 0; rendre(); });
    champ.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { e.preventDefault(); actif = (actif + 1) % Math.max(1, trouvees.length); rendre(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); actif = (actif - 1 + Math.max(1, trouvees.length)) % Math.max(1, trouvees.length); rendre(); }
      else if (e.key === "Enter") { e.preventDefault(); aller(actif); }
    });
    dialogue.addEventListener("click", (e) => { if (e.target === dialogue) fermer(); }); // clic sur le fond
    document.body.append(dialogue);
  }

  function apres() {
    document.addEventListener("keydown", (e) => {
      const saisie = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName) || document.activeElement?.isContentEditable;
      if ((e.key === "k" || e.key === "K") && (e.ctrlKey || e.metaKey)) { e.preventDefault(); ouvrir(); }
      else if (e.key === "/" && !saisie && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); ouvrir(); }
    });
    const b = Object.assign(document.createElement("button"), { type: "button", className: "recherche-bouton", textContent: "Rechercher" });
    b.title = "Aller à une page ou un sujet (touche / ou Ctrl+K)";
    b.setAttribute("aria-keyshortcuts", "/ Control+K");
    b.addEventListener("click", ouvrir);
    document.querySelector("#menu .principal")?.insertBefore(b, document.querySelector("#menu .principal .theme"));
  }

  App.enregistrerPage({ id: "recherche", module: true, titre: "Recherche", apres });
})();
