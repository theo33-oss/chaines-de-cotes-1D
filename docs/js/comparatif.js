"use strict";
// Comparatif de la page Comparer : plusieurs chaînes de cotes (chacune avec sa cote condition) ou plusieurs cotes condition
// sur les mêmes maillons, côte à côte (tableau, graphiques, export). Une colonne = un problème à UNE cote condition,
// calculé par le même solveur que la page Étude (pont.comparerN). Les colonnes viennent de l'étude en cours, de « Mes études »,
// des exemples ou d'un fichier ; la liste est gardée dans ce navigateur.

(() => {
  const { $ } = App;
  const CLE = "chainecotes.comparaison";
  const FORMAT = "chaines-de-cotes-comparaison";
  const VERSION = 1;
  const MAX_COLONNES = 12, MAX_FICHIER = 3e6, MAX_NOM = 60;
  const N_TIRAGES = 100000;

  let pont = null;
  let colonnes = []; // [{ id, nom, probleme (une CF), tous (tous les maillons, sens « 0 » = exclu), nom }]
  let reference = null; // id de la colonne de référence
  let editeur = null; // id de la colonne dont l'éditeur « nouvelle CF » est ouvert
  let resultat = null;
  let minuterie = 0;
  let jeton = 0;

  // ---------- petits outils ----------

  const el = (balise, attrs = {}, ...enfants) => {
    const e = document.createElement(balise);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "texte") e.textContent = v;
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else if (k === "class") e.className = v;
      else e.setAttribute(k, v === true ? "" : v);
    }
    e.append(...enfants.filter((x) => x !== null && x !== undefined && x !== false));
    return e;
  };
  const nouvelId = () => "c" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  const dansChaine = (sens) => sens === "+" || sens === "-";
  const nomPropre = (n) => String(n ?? "").replace(/\s+/g, " ").trim().slice(0, MAX_NOM);
  const dire = (niveau, texte) => App.message($("cmp-message"), niveau, texte);

  function nomLibre(base, sauf = null) {
    const pris = new Set(colonnes.filter((c) => c.id !== sauf).map((c) => c.nom));
    const b = nomPropre(base) || "Chaîne";
    if (!pris.has(b)) return b;
    for (let i = 2; ; i++) {
      const n = `${b.slice(0, MAX_NOM - 6)} (${i})`;
      if (!pris.has(n)) return n;
    }
  }

  // ---------- mémoire de la comparaison en cours ----------

  const proprete = (p) => (App.etudes ? App.etudes.nettoyerProbleme(p) : null);

  function nettoyerColonne(c) {
    if (!c || typeof c !== "object" || typeof c.id !== "string" || !/^[A-Za-z0-9_-]{1,40}$/.test(c.id)) return null;
    const probleme = proprete(c.probleme), nom = nomPropre(c.nom);
    if (!probleme || !nom) return null;
    const tousBrut = Array.isArray(c.tous) ? proprete({ condition: {}, maillons: c.tous }) : null;
    return { id: c.id, nom, probleme, tous: tousBrut ? tousBrut.maillons : probleme.maillons };
  }

  const etat = () => ({ format: FORMAT, version: VERSION, schema_version: VERSION, outil: "Chaînes de cotes 1D", reference, colonnes });

  function sauver() {
    try { localStorage.setItem(CLE, JSON.stringify(etat())); } catch (e) { /* stockage plein ou interdit : la comparaison reste à l'écran */ }
  }

  // Fichier de comparaison → { colonnes, reference } ou { erreur } (mêmes règles que « Mes études » : version, taille, clés inconnues).
  function lireEtat(texte) {
    if (typeof texte !== "string" || texte.length > MAX_FICHIER) return { erreur: "Fichier trop gros (3 Mo au plus)." };
    let d;
    try { d = JSON.parse(texte); } catch (e) { return { erreur: "Ce fichier n'est pas un fichier JSON lisible." }; }
    if (!d || d.format !== FORMAT) return { erreur: "Ce n'est pas un fichier de comparaison de Chaînes de cotes 1D." };
    const schema = d.schema_version === undefined ? 1 : d.schema_version;
    if (!Number.isInteger(d.version) || d.version > VERSION || !Number.isInteger(schema) || schema > VERSION) {
      return { erreur: "Fichier d'une version plus récente de Chaînes de cotes 1D : actualisez le site puis recommencez." };
    }
    if (!Array.isArray(d.colonnes)) return { erreur: "Le fichier ne contient aucune chaîne." };
    const cols = d.colonnes.slice(0, MAX_COLONNES).map(nettoyerColonne).filter(Boolean);
    if (!cols.length) return { erreur: "Aucune chaîne utilisable dans ce fichier." };
    return { colonnes: cols, reference: cols.some((c) => c.id === d.reference) ? d.reference : cols[0].id, ignorees: d.colonnes.length - cols.length };
  }

  function relire() {
    try {
      const r = lireEtat(localStorage.getItem(CLE) || "null");
      if (r.erreur) return;
      colonnes = r.colonnes;
      reference = r.reference;
    } catch (e) { colonnes = []; reference = null; }
  }

  // ---------- ajout de colonnes ----------

  // Une étude (éventuellement à deux cotes condition) → ses colonnes, une par cote condition.
  function colonnesDe(p, nomBase) {
    const base = { reglages: p.reglages || {} };
    if (!p.condition2) {
      return [{ nom: nomBase, probleme: { condition: p.condition, ...base, maillons: p.maillons }, tous: p.maillons.map((m) => ({ ...m })) }];
    }
    return [1, 2].map((k) => {
      const cle = k === 2 ? "sens2" : "sens";
      const maillons = p.maillons.filter((m) => dansChaine(m[cle])).map((m) => { const { sens2, ...reste } = m; return { ...reste, sens: m[cle] }; });
      const tous = p.maillons.map((m) => { const { sens2, ...reste } = m; return { ...reste, sens: dansChaine(m[cle]) ? m[cle] : "0" }; });
      const cond = k === 2 ? p.condition2 : p.condition;
      return { nom: nomBase === cond.nom ? `${nomBase} (CF${k})` : `${nomBase} – ${cond.nom || "CF" + k}`, probleme: { condition: cond, ...base, maillons }, tous };
    });
  }

  function ajouterColonnes(liste) {
    let ajoutees = 0;
    for (const c of liste) {
      if (colonnes.length >= MAX_COLONNES) { dire("avertissement", `Le comparatif garde ${MAX_COLONNES} chaînes au plus : retirez-en une pour en ajouter.`); break; }
      const probleme = proprete(c.probleme);
      if (!probleme) { dire("erreur", `« ${c.nom} » est vide ou trop grosse pour être comparée.`); continue; }
      const tous = proprete({ condition: {}, maillons: c.tous || probleme.maillons });
      const col = { id: nouvelId(), nom: nomLibre(c.nom), probleme, tous: tous ? tous.maillons : probleme.maillons };
      colonnes.push(col);
      if (!reference) reference = col.id;
      ajoutees++;
    }
    if (ajoutees) { sauver(); rendreColonnes(); planifier(); if (!/au plus|vide ou trop/.test($("cmp-message").textContent)) dire("succes", `${ajoutees} chaîne${ajoutees > 1 ? "s" : ""} ajoutée${ajoutees > 1 ? "s" : ""} au comparatif.`); }
    return ajoutees;
  }

  const ajouterProbleme = (p, nom) => ajouterColonnes(colonnesDe(p, nom));

  // ---------- cartes des colonnes ----------

  const limites = (c) => {
    const f = (v) => (v === null || v === undefined || v === "" ? "aucune" : App.fr(Number(v)));
    return `Jmin ${f(c.probleme.condition.jmin)}, Jmax ${f(c.probleme.condition.jmax)} mm`;
  };

  function carte(c) {
    const champNom = el("input", { type: "text", value: c.nom, maxlength: String(MAX_NOM), "aria-label": "Nom de la chaîne " + c.nom });
    champNom.addEventListener("change", () => {
      const n = nomPropre(champNom.value);
      if (n) { c.nom = nomLibre(n, c.id); sauver(); planifier(); }
      rendreColonnes();
    });
    const radio = el("input", { type: "radio", name: "cmp-ref", checked: c.id === reference, "aria-label": "Référence : " + c.nom });
    radio.addEventListener("change", () => { reference = c.id; sauver(); planifier(); });
    const li = el("li", { class: "cmp-col", "data-id": c.id },
      el("div", { class: "cmp-col-tete" }, champNom, el("label", { class: "case" }, radio, " référence")),
      el("p", { class: "legende", texte: `${c.probleme.maillons.length} maillon(s) · ${limites(c)}` }),
      el("div", { class: "etude-actions" },
        el("button", { type: "button", class: "secondaire petit", texte: "Nouvelle cote condition sur ces maillons", "aria-expanded": String(editeur === c.id), onclick: () => { editeur = editeur === c.id ? null : c.id; rendreColonnes(); } }),
        el("button", { type: "button", class: "secondaire petit", texte: "Dupliquer", "aria-label": "Dupliquer " + c.nom, onclick: () => ajouterColonnes([{ nom: c.nom + " (copie)", probleme: c.probleme, tous: c.tous }]) }),
        el("button", { type: "button", class: "secondaire petit", texte: "Retirer", "aria-label": "Retirer " + c.nom, onclick: () => retirer(c.id) })));
    if (editeur === c.id) li.append(formulaireCF(c));
    return li;
  }

  // Éditeur « nouvelle CF sur ces maillons » : nouvelle cote condition + sens de chaque maillon (+, −, exclu).
  function formulaireCF(c) {
    const cond = c.probleme.condition;
    const nom = el("input", { type: "text", value: `Cote condition ${colonnes.length + 1}`, "aria-label": "Nom de la nouvelle cote condition" });
    const jmin = el("input", { type: "text", inputmode: "decimal", value: cond.jmin ?? "", "aria-label": "Jmin de la nouvelle cote condition (mm)" });
    const jmax = el("input", { type: "text", inputmode: "decimal", value: cond.jmax ?? "", "aria-label": "Jmax de la nouvelle cote condition (mm)" });
    const sens = c.tous.map((m, i) => {
      const s = el("select", { "aria-label": `Sens de ${m.nom || "la cote " + (i + 1)} dans la nouvelle chaîne` },
        el("option", { value: "+", texte: "+ (agrandit)" }), el("option", { value: "-", texte: "− (réduit)" }), el("option", { value: "0", texte: "exclu" }));
      s.value = dansChaine(m.sens) ? m.sens : "0";
      return s;
    });
    const form = el("form", { class: "cmp-editeur", "aria-label": "Nouvelle cote condition sur les maillons de " + c.nom },
      el("div", { class: "grille" },
        el("label", {}, "Nom de la cote condition", nom), el("label", {}, "Jmin (mm)", jmin), el("label", {}, "Jmax (mm)", jmax)),
      el("div", { class: "defile" }, el("table", {},
        el("thead", {}, el("tr", {}, el("th", { texte: "Maillon" }), el("th", { texte: "Cote (mm)" }), el("th", { texte: "Sens dans la nouvelle chaîne" }))),
        el("tbody", {}, ...c.tous.map((m, i) => el("tr", {}, el("td", { texte: m.nom || "cote " + (i + 1) }), el("td", { class: "num", texte: App.fr(Number(m.cote)) }), el("td", {}, sens[i])))))),
      el("div", { class: "etude-actions" },
        el("button", { type: "submit", class: "primaire petit", texte: "Créer la colonne" }),
        el("button", { type: "button", class: "secondaire petit", texte: "Annuler", onclick: () => { editeur = null; rendreColonnes(); } })));
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const tous = c.tous.map((m, i) => ({ ...m, sens: sens[i].value }));
      const maillons = tous.filter((m) => dansChaine(m.sens));
      if (!maillons.length) return dire("erreur", "La nouvelle cote condition n'a aucun maillon : choisissez « + » ou « − » pour au moins une cote.");
      const nj = (v) => { const x = App.nombre(v); return x === "" || Number.isNaN(x) ? null : x; };
      const lo = nj(jmin.value), hi = nj(jmax.value);
      if (typeof lo === "string" || typeof hi === "string") return dire("erreur", "Jmin et Jmax doivent être des nombres (laissez vide un côté sans limite).");
      editeur = null;
      const n = ajouterColonnes([{ nom: nomPropre(nom.value) || "CF", tous, probleme: { condition: { nom: nomPropre(nom.value) || "CF", jmin: lo, jmax: hi }, reglages: c.probleme.reglages, maillons: maillons.map((m) => ({ ...m })) } }]);
      if (n) dire("succes", "Nouvelle colonne ajoutée : mêmes maillons, autre cote condition.");
      rendreColonnes();
    });
    return form;
  }

  function retirer(id) {
    colonnes = colonnes.filter((c) => c.id !== id);
    if (reference === id) reference = colonnes.length ? colonnes[0].id : null;
    if (editeur === id) editeur = null;
    sauver();
    rendreColonnes();
    planifier();
  }

  function rendreColonnes() {
    $("cmp-colonnes").replaceChildren(...colonnes.map(carte));
    $("cmp-actions").hidden = colonnes.length === 0;
    if (!colonnes.length) {
      $("cmp-sortie").hidden = true;
      dire("info", "Aucune chaîne à comparer. Ajoutez l'étude en cours, une étude de « Mes études », un exemple ou un fichier.");
    } else if ($("cmp-message").textContent.startsWith("Aucune chaîne")) dire("info", "");
    majSelecteurs();
  }

  function majSelecteurs() {
    const etudes = App.etudes ? App.etudes.liste() : [];
    const sel = $("cmp-etudes"), garde = sel.value;
    sel.replaceChildren(...(etudes.length ? etudes.map((e) => el("option", { value: e.id, texte: e.nom })) : [el("option", { value: "", texte: "(aucune étude gardée)" })]));
    if (garde && etudes.some((e) => e.id === garde)) sel.value = garde;
    $("cmp-ajouter-etude").disabled = !etudes.length;
  }

  // ---------- calcul et affichage ----------

  function planifier() {
    clearTimeout(minuterie);
    if (!colonnes.length) return;
    minuterie = setTimeout(calculer, 250);
  }

  function calculer() {
    if (!pont || !colonnes.length) return;
    const mien = ++jeton;
    $("cmp-sortie").hidden = false;
    $("cmp-phrases").className = "message info";
    $("cmp-phrases").textContent = "Calcul en cours…";
    setTimeout(() => { // laisse afficher le message avant le calcul, qui occupe le processeur
      if (mien !== jeton) return;
      let r;
      try {
        const ref = Math.max(0, colonnes.findIndex((c) => c.id === reference));
        r = JSON.parse(pont.comparerN(JSON.stringify({ colonnes: colonnes.map((c) => ({ nom: c.nom, probleme: c.probleme })), reference: ref, n: N_TIRAGES })));
      } catch (e) { r = { erreur: "Erreur inattendue : " + e }; }
      if (mien !== jeton) return;
      if (r.erreur) {
        resultat = null;
        $("cmp-phrases").className = "message erreur";
        $("cmp-phrases").textContent = r.erreur;
        $("cmp-tableau").replaceChildren();
        $("cmp-figures").replaceChildren();
        return;
      }
      resultat = r;
      afficher();
    }, 30);
  }

  const verdictTexte = { "conforme": "✓ conforme", "non conforme": "✗ non conforme", "indicatif": "• indicatif", "erreur": "! erreur" };

  function afficher() {
    const r = resultat;
    $("cmp-phrases").className = "message " + (r.niveau || "info");
    $("cmp-phrases").textContent = r.phrase || "";
    $("cmp-tableau").replaceChildren(tableau(r));
    $("cmp-tableau").classList.toggle("cmp-masque", $("cmp-masquer").checked);
    const hote = $("cmp-figures");
    hote.replaceChildren();
    for (const f of r.figures || []) {
      const div = el("div", { class: "figure", role: "img", "aria-label": f.titre + (f.description ? " : " + f.description : "") });
      const desc = el("p", { class: "legende", texte: f.description || "" });
      hote.append(el("h4", { texte: f.titre }), div, desc);
      App.tracer(div, f.fig);
    }
  }

  function tableau(r) {
    const cols = r.colonnes, n = cols.length;
    const tete = el("tr", {}, el("th", { scope: "col", texte: "Grandeur" }),
      ...cols.map((c, i) => el("th", { scope: "col", class: "cmp-tete" + (i === r.reference ? " cmp-ref" : "") },
        el("span", { texte: c.nom }), i === r.reference ? el("span", { class: "legende", texte: "référence" }) : null,
        el("span", { class: "verdict " + (c.niveau || "info"), texte: (verdictTexte[c.verdict] || c.verdict) + (c.verdict === "conforme" && c.niveau === "avertissement" ? " (statistique seulement)" : "") }),
        c.erreur ? el("span", { class: "legende", role: "alert", texte: c.erreur }) : null)));
    const corps = el("tbody", {});
    let groupe = null;
    for (const l of r.lignes) {
      if (l.groupe !== groupe) {
        groupe = l.groupe;
        corps.append(el("tr", { class: "cmp-groupe" }, el("th", { scope: "colgroup", colspan: String(n + 1), texte: groupe })));
      }
      const meilleurs = l.meilleurs || (l.meilleur !== null && l.meilleur !== undefined ? [l.meilleur] : []);
      const conf = l.libelle.startsWith("Conforme");
      corps.append(el("tr", { class: l.identique ? "cmp-identique" : null }, el("th", { scope: "row", texte: l.libelle }),
        ...l.valeurs.map((v, i) => {
          const t = v === null || v === undefined || v === "" ? "—" : v;
          const classe = conf && t === "oui" ? "verdict succes" : conf && t === "non" ? "verdict erreur" : "num";
          const marque = meilleurs.includes(i) && n > 1 && !l.identique;
          return el("td", { class: classe + (marque ? " cmp-meilleur" : "") },
            conf ? (t === "oui" ? "✓ oui" : t === "non" ? "✗ non" : t) : t,
            marque ? el("span", { class: "cache", texte: " (meilleure valeur)" }) : null,
            l.ecarts && l.ecarts[i] ? el("span", { class: "cmp-ecart", texte: l.ecarts[i] }) : null);
        })));
    }
    return el("table", { class: "cmp-table" }, el("caption", { class: "cache", texte: "Comparaison des chaînes de cotes, une colonne par chaîne" }), el("thead", {}, tete), corps);
  }

  // ---------- sources, exports ----------

  async function ajouterFichiers(fichiers) {
    for (const f of fichiers) {
      try {
        const texte = await f.text();
        const m = JSON.parse(pont.mecaImporter(texte)); // un mécanisme apporte une colonne par chaîne ; une étude simple en apporte une
        if (m.erreur) { dire("erreur", `${f.name} : ${m.erreur}`); continue; }
        const base = f.name.replace(/\.json$/i, "");
        const chaines = m.chaines || m.mecanisme?.chaines || [];
        if (!chaines.length) { dire("erreur", `${f.name} : aucune chaîne trouvée.`); continue; }
        ajouterColonnes(chaines.map((p, i) => ({ nom: chaines.length > 1 ? (p.condition && p.condition.nom) || `${base} ${i + 1}` : base, probleme: p })));
      } catch (e) { dire("erreur", `${f.name} : fichier illisible.`); }
    }
  }

  function csv() {
    if (!resultat) return dire("avertissement", "Rien à exporter : lancez d'abord la comparaison.");
    App.telecharger("comparaison.csv", resultat.csv, "text/csv;charset=utf-8");
  }

  async function copier() {
    if (!resultat) return dire("avertissement", "Rien à copier : lancez d'abord la comparaison.");
    const ok = await App.copier(resultat.texte);
    App.confirmer($("cmp-copier"), ok, "Copié", "Copie impossible", ok ? "Comparaison copiée : collez-la dans Excel." : "Copie refusée par le navigateur.");
  }

  async function ouvrirJson(f) {
    if (!f) return;
    const r = lireEtat(await f.text());
    if (r.erreur) return dire("erreur", r.erreur);
    colonnes = r.colonnes;
    reference = r.reference;
    editeur = null;
    sauver();
    rendreColonnes();
    planifier();
    dire(r.ignorees ? "avertissement" : "succes", `Comparaison ouverte : ${colonnes.length} chaîne(s)` + (r.ignorees ? `, ${r.ignorees} entrée(s) abîmée(s) ignorée(s).` : "."));
  }

  async function apres(p) {
    pont = p;
    relire();
    App.remplir($("cmp-exemple-n"), JSON.parse(pont.exemples()).map((e) => [e.id, e.titre]));
    $("cmp-encours").addEventListener("click", () => {
      const etude = App.analyser.etudeComplete();
      ajouterProbleme(etude, nomLibre(etude.condition.nom || "Étude en cours"));
    });
    $("cmp-ajouter-etude").addEventListener("click", () => {
      const e = App.etudes.obtenir($("cmp-etudes").value);
      if (e) ajouterProbleme(e.probleme, e.nom);
    });
    $("cmp-ajouter-exemple").addEventListener("click", () => {
      const id = $("cmp-exemple-n").value;
      const titre = $("cmp-exemple-n").selectedOptions[0]?.textContent || id;
      ajouterProbleme(JSON.parse(pont.charger(id)), titre);
    });
    $("cmp-ajouter-fichier").addEventListener("click", () => $("cmp-fichier-n").click());
    $("cmp-fichier-n").addEventListener("change", async (e) => { await ajouterFichiers([...e.target.files]); e.target.value = ""; });
    $("cmp-lancer").addEventListener("click", () => { clearTimeout(minuterie); calculer(); });
    $("cmp-vider").addEventListener("click", () => { colonnes = []; reference = null; editeur = null; resultat = null; sauver(); rendreColonnes(); });
    $("cmp-exporter-json").addEventListener("click", () => App.telecharger("comparaison.json", JSON.stringify(etat(), null, 1)));
    $("cmp-importer-json").addEventListener("click", () => $("cmp-fichier-json").click());
    $("cmp-fichier-json").addEventListener("change", async (e) => { await ouvrirJson(e.target.files[0]); e.target.value = ""; });
    $("cmp-copier").addEventListener("click", copier);
    $("cmp-csv").addEventListener("click", csv);
    $("cmp-imprimer").addEventListener("click", () => window.print());
    $("cmp-masquer").addEventListener("change", () => $("cmp-tableau").classList.toggle("cmp-masque", $("cmp-masquer").checked));
    document.addEventListener("etudes:maj", majSelecteurs);
    rendreColonnes();
    if (colonnes.length) planifier();
  }

  App.comparer = {
    ajouterEtude: (e) => ajouterProbleme(e.probleme, e.nom),
    ajouterProbleme,
    colonnes: () => colonnes.map((c) => ({ id: c.id, nom: c.nom })),
  };
  App.enregistrerPage({ id: "comparatif", module: true, titre: "Comparatif", apres });
})();
