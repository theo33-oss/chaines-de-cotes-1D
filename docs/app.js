"use strict";
// Socle de la page « Chaînes de cotes 1D » : démarrage de Pyodide et outils communs à toutes les pages.
// Le calcul est le Python de l'application de bureau (pont.py), exécuté dans le navigateur ; ici, seulement l'affichage.
// Chaque page (js/<outil>.js) s'enregistre avec App.enregistrerPage({ id, titre, apres(pont) }).

const App = (() => {
  const $ = (id) => document.getElementById(id);
  const pages = [];
  let pont = null;
  let pyodide = null;

  // ---------- nombres et textes ----------

  // « 0,25 » ou « 0.25 » devient un nombre ; un texte qui n'en est pas un reste texte (le calcul le signalera).
  function nombre(v) {
    if (v === null || v === undefined) return "";
    if (typeof v === "number") return v;
    const t = String(v).trim().replace(",", ".");
    if (t === "") return "";
    return /^[-+−]?\d*\.?\d+(e[-+]?\d+)?$/i.test(t) ? Number(t.replace("−", "-")) : String(v);
  }

  const echapper = (t) => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  // Markdown minimal des explications du calcul : tableaux, listes « - », gras. Le texte est échappé avant tout.
  function markdown(texte) {
    const gras = (t) => echapper(t).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    const lignes = String(texte).split("\n");
    let html = "", i = 0;
    while (i < lignes.length) {
      const l = lignes[i];
      if (l.startsWith("|")) {
        const bloc = [];
        while (i < lignes.length && lignes[i].startsWith("|")) bloc.push(lignes[i++]);
        const cellules = (x) => x.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        const [tete, , ...corps] = bloc;
        html += '<div class="defile"><table><thead><tr>' + cellules(tete).map((c) => `<th>${gras(c)}</th>`).join("") + "</tr></thead><tbody>"
          + corps.map((r) => "<tr>" + cellules(r).map((c) => `<td>${gras(c)}</td>`).join("") + "</tr>").join("") + "</tbody></table></div>";
      } else if (l.startsWith("- ")) {
        html += "<ul>";
        while (i < lignes.length && lignes[i].startsWith("- ")) html += `<li>${gras(lignes[i++].slice(2))}</li>`;
        html += "</ul>";
      } else {
        if (l.trim()) html += `<p>${gras(l)}</p>`;
        i++;
      }
    }
    return html;
  }

  // ---------- thème clair / sombre, icônes ----------

  const sombre = () => document.documentElement.dataset.theme === "dark";

  // Couleurs des figures du pont (plots/_common.py) → version sombre. Le script du <head> pose data-theme avant l'affichage.
  const COULEURS_SOMBRES = { "#FFFFFF": "#1A1626", "#3D246C": "#EDE6F7", "#E2DDF1": "#352E4D", "#5C4B99": "#9F91CC", "#17692F": "#4CC77A", "#B3141F": "#FF6B73" };
  const enSombre = (x) => JSON.parse(JSON.stringify(x).replace(/#[0-9A-Fa-f]{6}|rgba\(255,255,255,0\.8\)/g,
    (c) => COULEURS_SOMBRES[c.toUpperCase()] || (c[0] === "r" ? "rgba(26,22,38,0.8)" : c)));

  function poserTheme(theme) {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("chainecotes.theme", theme); } catch (e) { /* sans mémoire */ }
    for (const d of document.querySelectorAll(".js-plotly-plot")) if (d._figure) tracer(d, d._figure);
    document.dispatchEvent(new Event("themechange")); // les pages qui dessinent seules (silhouettes du schéma) se redessinent
  }

  const ICONES = {
    accueil: '<path d="M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10"/>',
    analyser: '<path d="M3 7v10M21 7v10M3 12h18M7 9l-4 3 4 3M17 9l4 3-4 3"/>',
    mecanisme: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/>',
    aides: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7M12 17h.01"/>',
    theme: '<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor"/>',
    dupliquer: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h8"/>',
    monter: '<path d="M6 15l6-6 6 6"/>',
    descendre: '<path d="M6 9l6 6 6-6"/>',
  };
  const icone = (id) => `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">${ICONES[id]}</svg>`;

  // Copie dans le presse-papiers ; vrai si c'est fait.
  async function copier(texte) {
    try { await navigator.clipboard.writeText(texte); return true; } catch (e) { /* page non sécurisée ou refus : copie de secours */ }
    const z = Object.assign(document.createElement("textarea"), { value: texte });
    document.body.append(z);
    z.select();
    const ok = document.execCommand("copy");
    z.remove();
    return ok;
  }

  // ---------- bulles d'aide au survol ----------

  // Lexique des termes affichés par le calcul (en-têtes, grandeurs, onglets) : le premier motif trouvé donne la bulle.
  const LEXIQUE = [
    [/^Pire des cas|pire cas\)/i, "Toutes les cotes à leur limite la plus défavorable en même temps : le jeu est garanti à 100 %, mais les tolérances demandées sont serrées."],
    [/Bender/, "Statistique prudente : la dispersion est multipliée par 1,5 pour couvrir des procédés mal centrés."],
    [/^RSS/, "Calcul statistique : les écarts des cotes se compensent en partie. Presque tous les assemblages ont leur jeu dans cet intervalle (moyenne ± k écarts-types σ)."],
    [/^Monte-Carlo/, "Des assemblages tirés au hasard par l'ordinateur, pour vérifier le calcul statistique."],
    [/Cpk/, "Capabilité réelle : marge entre le jeu moyen et la limite la plus proche, divisée par 3σ. Elle baisse si le jeu est décentré. On vise 1,33 ou plus."],
    [/^Cpi/, "Capabilité inertielle (Pillet) : inertie maxi divisée par l'inertie du jeu. Il faut 1 ou plus."],
    [/^Cp$/, "Capabilité potentielle : largeur de l'intervalle exigé (Jmax − Jmin) divisée par 6σ. Elle ne regarde pas le centrage."],
    [/^ppm/, "Parties par million : nombre d'assemblages hors limites sur un million fabriqués."],
    [/^IT inertiel/, "Intervalle de tolérance que le maillon pourrait avoir en tolérancement inertiel."],
    [/^IT /, "Intervalle de tolérance : ES − EI, la largeur permise autour de la cote."],
    [/^ES/, "Écart supérieur : cote maxi − cote nominale."],
    [/^EI/, "Écart inférieur : cote mini − cote nominale."],
    [/^C moy/, "Cote moyenne : le milieu de l'intervalle de tolérance."],
    [/^Jeu nominal/, "Jeu obtenu avec toutes les cotes à leur valeur nominale."],
    [/^Jeu moyen/, "Jeu obtenu avec toutes les cotes au milieu de leur tolérance."],
    [/^Jeu mini$|^Jeu maxi$/, "Limite du jeu au pire des cas : toutes les cotes au plus défavorable."],
    [/^Jeu mini|^Jeu maxi/, "Plus petit ou plus grand jeu possible, selon la méthode de la ligne."],
    [/^Verdict/, "Vert : le jeu reste dans ses limites. Orange : en statistique seulement. Rouge : il en sort."],
    [/^Écart-type|^σ \(/, "Écart-type σ : la dispersion habituelle autour de la moyenne. Environ 99,7 % des valeurs sont à moins de 3σ de la moyenne."],
    [/^α/, "Coefficient de dilatation : allongement en µm, par mètre de longueur et par degré."],
    [/^Part pire cas/, "Poids du maillon dans la dispersion du jeu au pire des cas."],
    [/^Part statistique|Sobol/, "Part de la variance du jeu due à ce maillon : le plus gros est celui à resserrer en premier."],
    [/^Inertie maxi/, "Inertie à ne pas dépasser : (Jmax − Jmin) / 6."],
    [/^Inertie/, "Inertie (Pillet) : elle réunit la dispersion et le décentrage en un seul nombre, √(σ² + écart²)."],
    [/^Décalage thermique/, "Variation du jeu moyen entre la température de référence et la température de service."],
    [/^Quantile/, "Valeur du jeu sous laquelle se trouve ce pourcentage des assemblages simulés."],
    [/si resserré/, "Valeur obtenue si l'on resserre ce seul maillon à la moitié de son IT."],
    [/^Sensibilité$/, "Quels maillons pèsent le plus sur le jeu, et ce que l'on gagne à en resserrer un."],
    [/^Statistiques$/, "Tirage Monte-Carlo et tolérancement inertiel."],
    [/^Graphiques$/, "Schéma, histogramme du jeu et Pareto des maillons."],
    [/^Explications du calcul$/, "Le calcul refait pas à pas, formule par formule."],
  ];

  // Pose la bulle du lexique sur un élément d'après son texte (rien si le terme n'y est pas).
  function aide(el) {
    const trouve = LEXIQUE.find(([motif]) => motif.test(el.textContent.trim()));
    if (trouve) el.dataset.aide = trouve[1];
    return el;
  }

  // Une seule bulle pour toute la page, montrée au survol ou au focus d'un élément [data-aide].
  // En position fixe : elle n'est pas rognée par les tableaux qui défilent.
  function bulles() {
    const b = Object.assign(document.createElement("div"), { id: "bulle", hidden: true });
    b.setAttribute("role", "tooltip");
    document.body.append(b);
    const cacher = () => { b.hidden = true; };
    const montrer = (e) => {
      const el = e.target.closest ? e.target.closest("[data-aide]") : null;
      if (!el) return cacher();
      b.textContent = el.dataset.aide;
      b.hidden = false;
      const r = el.getBoundingClientRect();
      b.style.left = Math.max(8, Math.min(r.left, innerWidth - b.offsetWidth - 8)) + "px";
      b.style.top = (r.bottom + 6 + b.offsetHeight > innerHeight ? Math.max(8, r.top - b.offsetHeight - 6) : r.bottom + 6) + "px";
    };
    document.addEventListener("mouseover", montrer);
    document.addEventListener("focusin", montrer);
    for (const ev of ["focusout", "keydown", "scroll", "mouseleave"]) document.addEventListener(ev, cacher, true); // Échap ou saisie : la bulle s'efface
    for (const el of document.querySelectorAll("th")) if (!el.dataset.aide) aide(el);
  }

  // ---------- éléments de page ----------

  function message(el, niveau, texte) {
    el.className = "message " + niveau;
    el.textContent = texte;
    el.hidden = !texte;
  }

  // Tableau {entetes, lignes, classes} du pont ; classes : une classe de couleur par ligne (dernière colonne).
  function tableau(t) {
    const enveloppe = document.createElement("div");
    enveloppe.className = "defile";
    const tab = document.createElement("table");
    const tete = tab.createTHead().insertRow();
    for (const e of t.entetes) {
      const th = document.createElement("th");
      th.textContent = e;
      tete.append(aide(th));
    }
    const corps = tab.createTBody();
    t.lignes.forEach((ligne, i) => {
      const tr = corps.insertRow();
      ligne.forEach((c, j) => {
        const td = tr.insertCell();
        td.textContent = c;
        if (j === 0) aide(td); // première colonne : nom de la méthode ou de la grandeur
        if (j > 0) td.className = "num";
        if (t.classes && j === (t.colonneClasse ?? ligne.length - 1)) td.className = "verdict " + t.classes[i];
      });
    });
    enveloppe.append(tab);
    const b = Object.assign(document.createElement("button"), { type: "button", className: "secondaire petit copier", textContent: "Copier le tableau" });
    b.dataset.aide = "Copie le tableau avec des tabulations : à coller directement dans Excel.";
    b.addEventListener("click", async () => {
      b.textContent = (await copier([t.entetes, ...t.lignes].map((l) => l.join("\t")).join("\n"))) ? "Copié" : "Copie impossible";
      setTimeout(() => { b.textContent = "Copier le tableau"; }, 1500);
    });
    const bloc = document.createElement("div");
    bloc.className = "tableau";
    bloc.append(enveloppe, b);
    return bloc;
  }

  function metriques(liste) {
    const grille = document.createElement("div");
    grille.className = "metriques";
    for (const [nom, valeur] of liste) {
      const d = document.createElement("div");
      d.className = "metrique";
      const a = document.createElement("span"), b = document.createElement("strong");
      a.textContent = nom;
      b.textContent = valeur;
      d.append(aide(a), b);
      grille.append(d);
    }
    return grille;
  }

  function titre(texte, niveau = "h3") {
    const h = document.createElement(niveau);
    h.textContent = texte;
    return h;
  }

  function legende(texte) {
    const p = document.createElement("p");
    p.className = "legende";
    p.textContent = texte;
    return p;
  }

  // Figure Plotly du pont : titre sur plusieurs lignes et légende sous le graphique pour tenir sur un téléphone.
  function tracer(div, f) {
    div._figure = f; // gardée pour redessiner au changement de thème
    if (sombre()) f = { data: enSombre(f.data), layout: { ...enSombre(f.layout), hoverlabel: { bgcolor: "#241F36", font: { color: "#EDE6F7" } } } };
    const layout = { ...f.layout, autosize: true };
    delete layout.width;
    if (layout.title && layout.title.text) {
      layout.title = { ...layout.title, text: layout.title.text.replaceAll(" | ", "<br>"), x: 0.01, xanchor: "left" };
      if (layout.title.text.includes("<br>")) layout.margin = { ...layout.margin, t: Math.max((layout.margin || {}).t || 0, 90) };
    }
    if (layout.showlegend !== false) {
      layout.legend = { ...layout.legend, orientation: "h", x: 0, xanchor: "left", y: -0.28, yanchor: "top" };
      layout.margin = { ...layout.margin, b: Math.max((layout.margin || {}).b || 0, 130) };
    }
    Plotly.react(div, f.data, layout, { responsive: true, displaylogo: false });
  }

  // Onglets : onglets = [{ id, titre, rendu(panneau) }] ; le rendu se fait à l'ouverture (Plotly a besoin d'un panneau visible).
  function onglets(barre, panneau, liste, actif) {
    const ouvrir = (id) => {
      for (const b of barre.children) b.setAttribute("aria-selected", String(b.dataset.id === id));
      panneau.replaceChildren();
      liste.find((o) => o.id === id).rendu(panneau);
    };
    barre.replaceChildren(...liste.map((o) => {
      const b = document.createElement("button");
      b.type = "button";
      b.setAttribute("role", "tab");
      b.dataset.id = o.id;
      b.textContent = o.titre;
      b.addEventListener("click", () => ouvrir(o.id));
      return aide(b);
    }));
    ouvrir(liste.some((o) => o.id === actif) ? actif : liste[0].id);
  }

  function telecharger(nomFichier, contenu, type = "application/json") {
    const url = URL.createObjectURL(new Blob([contenu], { type }));
    const a = document.createElement("a");
    a.href = url;
    a.download = nomFichier;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // Nombre venu d'une table JSON écrit à la française (« 0,8 ») ; case absente → vide.
  const fr = (v) => (v === null || v === undefined ? "" : String(v).replace(".", ","));

  // Liste déroulante remplie : options = [[valeur, texte], …].
  function remplir(select, options, valeur) {
    select.replaceChildren(...options.map(([v, t]) => Object.assign(document.createElement("option"), { value: v, textContent: t })));
    if (valeur !== undefined) select.value = String(valeur);
    return select;
  }

  // Tableau de valeurs de plages (data/iso286.json) : {plages, colonnes} → table, colonnes choisies.
  function matrice(t, noms, premiere = "Plage de cote (mm)") {
    return tableau({ entetes: [premiere, ...noms], lignes: t.plages.map((p, i) => [p, ...noms.map((n) => fr(t.colonnes[n][i]))]) });
  }

  // Paquets Python lourds, chargés à la première utilisation seulement (ex. jinja2 pour le dossier de validation).
  async function paquets(noms) {
    await pyodide.loadPackage(noms);
  }

  // Paquet Python pur absent de Pyodide, pris sur PyPI à la première utilisation (ex. openpyxl pour l'export Excel).
  const installes = new Set();
  async function pip(nom) {
    if (installes.has(nom)) return;
    await pyodide.pyimport("micropip").install(nom);
    installes.add(nom);
  }

  // ---------- pages et démarrage ----------

  function enregistrerPage(page) {
    pages.push(page);
  }

  // Bandeau d'état en haut de page : texte vide → bandeau caché ; pas (1 à 4) → barre d'avancement du démarrage.
  function etat(texte, pas) {
    $("etat").className = "message info";
    $("etat-texte").textContent = texte;
    $("etat").hidden = !texte;
    $("avance").hidden = !pas;
    if (pas) $("avance").value = pas;
  }

  const UTILISENT_ETUDE = ["mecanisme"]; // pages qui travaillent sur l'étude de la page Étude
  const AIDES = ["assistant", "exemples", "ajustement", "iso286", "materiaux"]; // regroupées sous « Aides »
  // Sommaire de la page Étude : [élément, titre]. Un élément « page-… » déclaré avec dans: "analyser" est un bloc de la page.
  const SOMMAIRE = [["b-depart", "Départ"], ["b-condition", "Condition"], ["b-maillons", "Maillons"], ["resultats", "Résultats"],
    ["page-repartir", "Optimiser"], ["page-comparer", "Comparer"], ["page-dossier", "Dossier"]];
  let derniereAide = "assistant";
  let courante = "accueil";

  const haut = (id) => {
    const p = pages.find((x) => x.id === id);
    return p && p.dans ? p.dans : AIDES.includes(id) ? "aides" : id;
  };

  // Un graphique tracé pendant que sa page était cachée a une largeur par défaut : on l'ajuste quand il devient visible.
  function ajusterGraphiques(racine) {
    for (const g of racine.querySelectorAll(".js-plotly-plot")) Plotly.Plots.resize(g);
  }

  function allerBandeau(el) {
    if (el.hidden) return;
    el.open = true;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function afficherPage(id) {
    const page = pages.find((p) => p.id === id);
    const ecran = page && page.dans ? page.dans : id; // les blocs de l'étude s'affichent dans la page Étude
    for (const p of pages) if (!p.dans) $("page-" + p.id).hidden = p.id !== ecran;
    if (AIDES.includes(id)) derniereAide = id;
    courante = id;
    $("etude-cours").hidden = !(pont && UTILISENT_ETUDE.includes(id));
    if (!$("etude-cours").hidden) {
      const p = exposition.analyser.probleme();
      $("etude-texte").textContent = `Étude en cours : « ${p.condition.nom || "sans nom"} », ${p.maillons.length} maillon(s).`;
    }
    majMenu();
    document.title = (page && id !== "accueil" ? page.titre + " · " : "") + "Chaînes de cotes 1D";
    requestAnimationFrame(() => ajusterGraphiques($("page-" + ecran)));
    if (page && page.dans) {
      if (exposition.analyser) exposition.analyser.guide(false); // un bloc d'étude se lit en mode expert
      const el = $("page-" + id);
      el.open = true;
      if (page.afficher) page.afficher();
      requestAnimationFrame(() => allerBandeau(el));
    } else if (page && page.afficher) page.afficher(); // la page se remet à jour d'après l'étude en cours
  }

  // Remet à jour les blocs ouverts de l'étude (Optimiser, Comparer, Dossier) d'après l'étude en cours.
  function majBlocs() {
    for (const p of pages) if (p.dans && p.afficher && $("page-" + p.id).open) p.afficher();
  }

  // Barre fixe en haut : Accueil, Étude, Mécanisme, Aides ; dessous, le sommaire de l'étude ou la liste des aides.
  function majMenu() {
    const h = haut(courante);
    for (const b of document.querySelectorAll("#menu .principal button")) b.setAttribute("aria-current", String(b.dataset.id === h));
    const sous = document.querySelector("#menu .sous");
    const bouton = (texte, clic, actif) => {
      const b = Object.assign(document.createElement("button"), { type: "button", textContent: texte, disabled: !pont });
      b.setAttribute("aria-current", String(actif));
      b.addEventListener("click", clic);
      return b;
    };
    sous.hidden = h !== "analyser" && h !== "aides";
    if (h === "analyser") {
      sous.replaceChildren(...SOMMAIRE.map(([cible, titre]) => bouton(titre, () => {
        const page = pages.find((p) => "page-" + p.id === cible);
        if (page) afficherPage(page.id);
        else allerBandeau($(cible));
      }, false)));
    } else if (h === "aides") {
      sous.replaceChildren(...AIDES.map((id) => bouton(pages.find((p) => p.id === id).titre, () => { afficherPage(id); window.scrollTo(0, 0); }, id === courante)));
    }
  }

  function menu() {
    const entrees = [["accueil", "Accueil", "Présentation et points de départ."], ["analyser", "Étude", "Saisir une chaîne de cotes et la calculer."],
      ["mecanisme", "Mécanisme", "Calculer d'un coup plusieurs chaînes d'un même assemblage."],
      ["aides", "Aides", "Assistant de chaîne, exemples, ajustements, tables ISO 286 et matériaux."]];
    const principal = document.createElement("div");
    principal.className = "principal";
    principal.append(...entrees.map(([id, titre, bulle]) => {
      const b = Object.assign(document.createElement("button"), { type: "button", innerHTML: icone(id) + titre, disabled: id !== "accueil" }); // icône et titre : textes écrits ici
      b.dataset.id = id;
      b.dataset.aide = bulle;
      b.addEventListener("click", () => { afficherPage(id === "aides" ? derniereAide : id); window.scrollTo(0, 0); });
      return b;
    }));
    const theme = Object.assign(document.createElement("button"), { type: "button", className: "theme" });
    const majTheme = () => {
      theme.innerHTML = icone("theme") + (sombre() ? "Thème clair" : "Thème sombre");
      theme.setAttribute("aria-label", sombre() ? "Passer au thème clair" : "Passer au thème sombre");
    };
    theme.addEventListener("click", () => poserTheme(sombre() ? "light" : "dark"));
    document.addEventListener("themechange", majTheme);
    majTheme();
    principal.append(theme);
    const sous = document.createElement("div");
    sous.className = "sous";
    sous.hidden = true;
    $("menu").hidden = false;
    $("menu").replaceChildren(principal, sous);
  }

  // Bandeaux repliables : l'état ouvert / replié de chacun est gardé dans ce navigateur ; l'ouverture d'un bloc le met à jour.
  function bandeaux() {
    let memo = {};
    try { memo = JSON.parse(localStorage.getItem("chainecotes.bandeaux") || "{}"); } catch (e) { memo = {}; }
    for (const d of document.querySelectorAll("details.bandeau")) {
      if (d.id in memo) d.open = memo[d.id];
      d.addEventListener("toggle", () => {
        memo[d.id] = d.open;
        try { localStorage.setItem("chainecotes.bandeaux", JSON.stringify(memo)); } catch (e) { /* stockage bloqué : sans mémoire */ }
        const page = pages.find((p) => p.dans && "page-" + p.id === d.id);
        if (d.open) ajusterGraphiques(d);
        if (d.open && page && page.afficher && pont) page.afficher();
      });
    }
  }

  async function demarrer() {
    menu();
    bandeaux();
    bulles();
    afficherPage("accueil"); // l'accueil se lit pendant le chargement ; ses boutons s'activent à la fin
    $("etude-modifier").addEventListener("click", () => afficherPage("analyser"));
    if (!exposition.analyser) { // un bloqueur de publicité ou un cache périmé a retenu un script
      $("etat").className = "message erreur";
      $("etat-texte").textContent = "Un script de la page n'a pas été chargé. Rechargez avec Ctrl+F5 ; si un bloqueur de publicité est actif, désactivez-le pour cette page.";
      $("avance").hidden = true;
      return;
    }
    try {
      pyodide = await loadPyodide();
      etat("Préparation 2/4 : bibliothèques de calcul (numpy, scipy)…", 2);
      await pyodide.loadPackage(["numpy", "scipy", "micropip"]);
      etat("Préparation 3/4 : graphiques (plotly)…", 3);
      await pyodide.pyimport("micropip").install("plotly>=5.20,<7");
      etat("Préparation 4/4 : tables ISO 286, matériaux et exemples…", 4);
      // « no-cache » : le navigateur revalide à chaque visite (réponse 304 si rien n'a changé). Sans cela, GitHub Pages
      // fait garder ces fichiers 10 minutes, et une page mise à jour recevrait l'ancien calcul.
      const archive = await (await fetch("chainecotes.zip", { cache: "no-cache" })).arrayBuffer();
      pyodide.unpackArchive(archive, "zip", { extractDir: "/app" });
      pyodide.FS.writeFile("/app/pont.py", await (await fetch("pont.py", { cache: "no-cache" })).text());
      pyodide.runPython("import sys; sys.path.insert(0, '/app')");
      pont = pyodide.pyimport("pont");
      for (const p of pages) await p.apres(pont);
    } catch (e) {
      pont = null;
      $("etat").className = "message erreur";
      $("etat-texte").textContent = "Le calcul n'a pas pu se charger (connexion Internet nécessaire ; rechargez la page avec Ctrl+F5) : " + e;
      $("avance").hidden = true;
      return;
    }
    for (const b of document.querySelectorAll("#menu button, #page-accueil button")) b.disabled = false;
    majMenu();
    majBlocs();
    etat("");
    $("pret").hidden = false;
    exposition.analyser.ouvrirLien();
  }

  const exposition = { $, sombre, icone, copier, etat, nombre, fr, echapper, markdown, message, tableau, metriques, titre, legende, tracer, onglets, remplir, matrice, telecharger, paquets, pip, enregistrerPage, afficherPage, majBlocs, demarrer };
  return exposition; // les pages ajoutent leurs propres points d'entrée (App.analyser)
})();
