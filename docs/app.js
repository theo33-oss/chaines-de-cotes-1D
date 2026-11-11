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
      tete.append(th);
    }
    const corps = tab.createTBody();
    t.lignes.forEach((ligne, i) => {
      const tr = corps.insertRow();
      ligne.forEach((c, j) => {
        const td = tr.insertCell();
        td.textContent = c;
        if (j > 0) td.className = "num";
        if (t.classes && j === (t.colonneClasse ?? ligne.length - 1)) td.className = "verdict " + t.classes[i];
      });
    });
    enveloppe.append(tab);
    return enveloppe;
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
      d.append(a, b);
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
      return b;
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

  const UTILISENT_ETUDE = ["repartir", "comparer", "mecanisme", "dossier"]; // pages qui travaillent sur l'étude de la page Analyser

  function afficherPage(id) {
    for (const p of pages) $("page-" + p.id).hidden = p.id !== id;
    for (const b of document.querySelectorAll("#menu button")) b.setAttribute("aria-current", String(b.dataset.id === id));
    const page = pages.find((p) => p.id === id);
    $("etude-cours").hidden = !(pont && UTILISENT_ETUDE.includes(id));
    if (!$("etude-cours").hidden) {
      const p = exposition.analyser.probleme();
      $("etude-texte").textContent = `Étude en cours : « ${p.condition.nom || "sans nom"} », ${p.maillons.length} maillon(s).`;
    }
    if (page && page.afficher) page.afficher(); // la page se remet à jour d'après l'étude en cours
  }

  const AIDES = ["assistant", "exemples", "ajustement", "iso286", "materiaux"]; // deuxième rangée du menu

  // Menu en deux rangées : l'étude (dans l'ordre du travail), puis les aides. Inactif tant que le calcul n'est pas chargé.
  function menu() {
    const rangee = (titre, liste) => {
      const d = document.createElement("div");
      d.className = "rangee";
      d.append(Object.assign(document.createElement("span"), { textContent: titre }), ...liste.map((p) => {
        const b = document.createElement("button");
        b.type = "button";
        b.dataset.id = p.id;
        b.textContent = p.titre;
        b.disabled = p.id !== "accueil";
        b.addEventListener("click", () => { afficherPage(p.id); window.scrollTo(0, 0); });
        return b;
      }));
      return d;
    };
    $("menu").hidden = false;
    $("menu").replaceChildren(rangee("Étude", pages.filter((p) => !AIDES.includes(p.id))), rangee("Aides", pages.filter((p) => AIDES.includes(p.id))));
  }

  async function demarrer() {
    menu();
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
    etat("");
    $("pret").hidden = false;
  }

  const exposition = { $, etat, nombre, fr, echapper, markdown, message, tableau, metriques, titre, legende, tracer, onglets, remplir, matrice, telecharger, paquets, enregistrerPage, afficherPage, demarrer };
  return exposition; // les pages ajoutent leurs propres points d'entrée (App.analyser)
})();
