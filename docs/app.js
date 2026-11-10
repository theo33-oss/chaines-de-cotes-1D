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
        if (t.classes && j === ligne.length - 1) td.className = "verdict " + t.classes[i];
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

  // ---------- pages et démarrage ----------

  function enregistrerPage(page) {
    pages.push(page);
  }

  function afficherPage(id) {
    for (const p of pages) $("page-" + p.id).hidden = p.id !== id;
    for (const b of $("menu").children) b.setAttribute("aria-current", String(b.dataset.id === id));
    const page = pages.find((p) => p.id === id);
    if (page && page.afficher) page.afficher(); // la page se remet à jour d'après l'étude en cours
  }

  function menu() {
    $("menu").hidden = pages.length < 2; // une seule page : pas de menu
    $("menu").replaceChildren(...pages.map((p) => {
      const b = document.createElement("button");
      b.type = "button";
      b.dataset.id = p.id;
      b.textContent = p.titre;
      b.addEventListener("click", () => afficherPage(p.id));
      return b;
    }));
  }

  async function demarrer() {
    try {
      pyodide = await loadPyodide();
      $("etat").textContent = "Chargement de numpy et scipy…";
      await pyodide.loadPackage(["numpy", "scipy", "micropip"]);
      $("etat").textContent = "Chargement de plotly…";
      await pyodide.pyimport("micropip").install("plotly>=5.20,<7");
      $("etat").textContent = "Chargement du calcul…";
      // « no-cache » : le navigateur revalide à chaque visite (réponse 304 si rien n'a changé). Sans cela, GitHub Pages
      // fait garder ces fichiers 10 minutes, et une page mise à jour recevrait l'ancien calcul.
      const archive = await (await fetch("chainecotes.zip", { cache: "no-cache" })).arrayBuffer();
      pyodide.unpackArchive(archive, "zip", { extractDir: "/app" });
      pyodide.FS.writeFile("/app/pont.py", await (await fetch("pont.py", { cache: "no-cache" })).text());
      pyodide.runPython("import sys; sys.path.insert(0, '/app')");
      pont = pyodide.pyimport("pont");
    } catch (e) {
      $("etat").className = "message erreur";
      $("etat").textContent = "Le calcul n'a pas pu se charger (connexion Internet nécessaire la première fois) : " + e;
      return;
    }
    menu();
    for (const p of pages) await p.apres(pont);
    afficherPage(pages[0].id);
    $("etat").textContent = "Prêt. Choisissez un exemple ou saisissez votre chaîne, puis cliquez sur Calculer.";
  }

  const exposition = { $, nombre, fr, echapper, markdown, message, tableau, metriques, titre, legende, tracer, onglets, remplir, matrice, telecharger, enregistrerPage, afficherPage, demarrer };
  return exposition; // les pages ajoutent leurs propres points d'entrée (App.analyser)
})();
