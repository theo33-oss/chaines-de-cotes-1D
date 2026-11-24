"use strict";
// Page « Analyser » : saisie de la chaîne, aperçu en direct, calcul complet, enregistrement et ouverture d'une étude.
// Aucun calcul ici : tout vient de pont.py (le Python de l'application de bureau).

(() => {
  const { $, nombre, icone } = App;
  let pont = null;
  let etude = { cartouche: null, revisions: [] }; // reportés tels quels dans le fichier enregistré (cartouche, révisions)
  let materiaux = [];
  let ongletActif = "resultats";

  const CHAMPS_CONNUS = ["nom", "sens", "cote", "iso", "es", "ei", "loi", "materiau", "alpha", "tservice", "image", "imageAngle", "sens2"];
  const MAILLON_VIDE = { nom: "", sens: "+", cote: "", iso: "", es: "", ei: "", loi: "normale", materiau: "", alpha: "", tservice: "", image: "", imageAngle: "", sens2: "" };

  // Silhouettes de pièces (symboles « img-… » de index.html) : image facultative de chaque maillon sur le schéma
  const IMAGES = { arbre: "Arbre", "arbre-epaule": "Arbre épaulé", carter: "Carter", roulement: "Roulement", entretoise: "Entretoise",
    rondelle: "Rondelle", circlips: "Circlips", ecrou: "Écrou", vis: "Vis", bague: "Bague à collerette", coussinet: "Coussinet", pignon: "Pignon",
    poulie: "Poulie", clavette: "Clavette", couvercle: "Couvercle", joint: "Joint torique", ressort: "Ressort", cale: "Cale de réglage",
    goupille: "Goupille", plaque: "Plaque" };
  // Le schéma est une image Plotly : la silhouette y entre en SVG autonome, aux couleurs de la figure (claire ou sombre).
  const STYLE_IMAGE = () => {
    const trait = App.sombre() ? "#EDE6F7" : "#3D246C", fond = App.sombre() ? "#4B3F7A" : "#CFC6EC";
    return `<style>.pi-s{stroke:${trait};stroke-width:1.6;fill:${fond};stroke-linejoin:round}`
      + `.pi-n{stroke:${trait};stroke-width:1.6;fill:none;stroke-linecap:round;stroke-linejoin:round}`
      + `.pi-a{stroke:${trait};stroke-width:1;stroke-dasharray:7 2 1.5 2;fill:none;opacity:.7}</style>`;
  };
  // Images personnelles : gardées dans ce navigateur seulement (jamais dans le fichier d'étude, jamais envoyées).
  // Un maillon y fait référence par « perso:<nom> ». Réduites à 256 px à l'ajout.
  const CLE_IMAGES = "chainecotes.images";
  const PERSO = "perso:";
  const MAX_IMAGES = 30;
  const IMAGE_VALIDE = /^data:image\/(png|jpeg);base64,[A-Za-z0-9+/=]+$/;
  let perso = {};
  function lirePerso() {
    try {
      const brut = JSON.parse(localStorage.getItem(CLE_IMAGES) || "{}");
      perso = Object.fromEntries(Object.entries(brut).filter(([, v]) => typeof v === "string" && IMAGE_VALIDE.test(v)));
    } catch (e) { perso = {}; }
  }
  function garderPerso() {
    try { localStorage.setItem(CLE_IMAGES, JSON.stringify(perso)); return true; } catch (e) { return false; }
  }
  const estPerso = (id) => typeof id === "string" && id.startsWith(PERSO);
  const imageConnue = (id) => (estPerso(id) ? Object.hasOwn(perso, id.slice(PERSO.length)) : Object.hasOwn(IMAGES, id));
  const angleDe = (v) => Number(App.nombre(v)) || 0;

  // Contenu SVG (boîte 40 × 40) d'une image : silhouette du catalogue ou image personnelle.
  function corpsImage(id) {
    if (estPerso(id)) return `<image href="${perso[id.slice(PERSO.length)]}" x="0" y="0" width="40" height="40" preserveAspectRatio="xMidYMid meet"/>`;
    return $("img-" + id).innerHTML;
  }
  const sourceImage = (id, angle) => "data:image/svg+xml," + encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">${STYLE_IMAGE()}<g transform="rotate(${angleDe(angle)} 20 20)">${corpsImage(id)}</g></svg>`);

  // Ajoute au schéma du pont la silhouette de chaque maillon qui en a une : sous sa flèche, au milieu, comme une pièce
  // sous sa ligne de cote. Le nom reste au-dessus de la flèche ; les lignes sont plus hautes pour loger la silhouette.
  function vignettes(fig, maillons, div = $("apercu-fig")) {
    const L = fig.layout, mg = L.margin || {}, notes = L.annotations || [];
    if (!maillons.some((m) => imageConnue(m.image))) return;
    const COTE = 44, LIGNE = 70; // px : côté de la silhouette, hauteur d'une ligne du schéma
    const hautY = L.yaxis.range[1] - L.yaxis.range[0];
    L.height = (mg.t ?? 100) + (mg.b ?? 80) + LIGNE * hautY;
    // Plotly place une image dans une boîte en unités des axes : on convertit les pixels d'après la taille du tracé
    const pxX = Math.max(div.clientWidth - (mg.l ?? 80) - (mg.r ?? 80), 100) / (L.xaxis.range[1] - L.xaxis.range[0]);
    L.images = [];
    maillons.forEach((m, i) => {
      const note = notes.find((n) => n.name === "libelle:" + i);
      const fleche = note && notes.find((n) => String(n.name).startsWith("maillon:") && n.y === note.y);
      if (!fleche || !imageConnue(m.image)) return;
      L.images.push({ source: sourceImage(m.image, m.imageAngle), xref: "x", yref: "y", x: (fleche.x + fleche.ax) / 2, y: fleche.y - 4 / LIGNE,
        xanchor: "center", yanchor: "top", sizex: COTE / pxX, sizey: COTE / LIGNE, sizing: "contain", layer: "above" });
    });
  }

  // Étude affichée à l'ouverture : 6 cotes (4 dans un sens, 2 dans l'autre) ; les cotes C et F ont une grande tolérance
  // (± 0,1 mm), les autres une tolérance fine. Jeu de 0,25 à 0,90 mm pour 0,20 à 1,00 demandé : conforme au pire des cas.
  const CAS_DE_BASE = {
    condition: { nom: "Jeu J", jmin: 0.2, jmax: 1 },
    maillons: [
      { nom: "Pièce A", sens: "+", cote: 20, es: 0.05, ei: 0 },
      { nom: "Pièce B", sens: "+", cote: 15, es: 0.05, ei: 0 },
      { nom: "Pièce C (grande tolérance)", sens: "+", cote: 30, es: 0.1, ei: -0.1 },
      { nom: "Pièce D", sens: "+", cote: 25, es: 0.05, ei: 0 },
      { nom: "Carter E", sens: "-", cote: 50, es: 0.05, ei: -0.05 },
      { nom: "Carter F (grande tolérance)", sens: "-", cote: 39.5, es: 0.1, ei: -0.1 },
    ],
  };

  // ---------- tableau des maillons ----------

  function champ(valeur, classe, numerique) {
    const el = document.createElement("input");
    el.type = "text";
    el.value = valeur ?? "";
    el.className = classe;
    if (numerique) el.inputMode = "decimal";
    return el;
  }

  function liste(classe, options, valeur) {
    const el = document.createElement("select");
    el.className = classe;
    for (const [v, texte] of options) {
      const o = document.createElement("option");
      o.value = v;
      o.textContent = texte;
      el.append(o);
    }
    el.value = valeur;
    return el;
  }

  // Options de la liste « Image » : catalogue, mes images, et l'image d'une étude ouverte si elle manque dans ce navigateur.
  function optionsImages(courante) {
    const options = [["", "(aucune)"], ...Object.entries(IMAGES), ...Object.keys(perso).map((n) => [PERSO + n, "Mes images : " + n])];
    if (courante && !imageConnue(courante)) options.push([courante, `${estPerso(courante) ? courante.slice(PERSO.length) : courante} (absente de ce navigateur)`]);
    return options;
  }

  // Sens d'une cote dans une chaîne : « + », « − » ; avec deux cotes condition, une cote peut aussi être hors de la chaîne.
  const optionsSens = (deux) => [["+", "+ (agrandit)"], ["-", "− (réduit)"], ...(deux ? [["", "— (hors chaîne)"]] : [])];
  const valeurSens = (v, deux) => (v === "-" ? "-" : v === "+" ? "+" : deux ? "" : "+");

  function ligneMaillon(m, numero) {
    const deux = $("deux-cf").checked;
    const tr = document.createElement("tr");
    tr._extra = m.extra || {}; // champs que la page ne saisit pas (facteur, angle, mesures de l'atelier…) : gardés intacts
    const cellules = [
      ["Nom", champ(m.nom, "m-nom")],
      ["Sens (CF1)", liste("m-sens", optionsSens(deux), valeurSens(m.sens, deux))],
      ["Sens CF2", liste("m-sens2", optionsSens(true), valeurSens(m.sens2, true))],
      ["Cote nominale", champ(m.cote, "m-cote", true)],
      ["Désignation ISO 286", champ(m.iso, "m-iso")],
      ["Écart supérieur ES", champ(m.es, "m-es", true)],
      ["Écart inférieur EI", champ(m.ei, "m-ei", true)],
      ["Loi", liste("m-loi", [["normale", "normale"], ["uniforme", "uniforme"], ["triangulaire", "triangulaire"]], m.loi || "normale")],
      ["Matériau", liste("m-mat", [["", "(aucun)"], ...materiaux.map((n) => [n, n])], materiaux.includes(m.materiau) ? m.materiau : "")],
      ["Coefficient de dilatation α", champ(m.alpha, "m-alpha", true)],
      ["Température de service", champ(m.tservice, "m-tserv", true)],
    ];
    cellules.forEach(([nom, el], i) => {
      el.setAttribute("aria-label", `${nom}, maillon ${numero}`);
      const td = document.createElement("td");
      if (i === 2) td.className = "td-cf2";
      if (i >= 8) td.className = "td-therm" + (i === 10 ? " td-tcote" : "");
      td.append(el);
      tr.append(td);
    });
    // désignation ISO 286 : liste déroulante des désignations courantes à cette cote ; le choix remplit ES et EI
    const f = (c) => tr.querySelector("." + c);
    f("m-iso").setAttribute("list", "liste-iso");
    f("m-iso").placeholder = "ex. h7";
    f("m-iso").addEventListener("focus", () => listeIso(f("m-cote").value));
    for (const c of ["m-iso", "m-cote"]) f(c).addEventListener("change", () => appliquerIso(tr));
    for (const c of ["m-es", "m-ei"]) f(c).addEventListener("input", () => { f("m-iso").value = ""; f("m-iso").classList.remove("invalide"); }); // écarts saisis : plus de désignation
    f("m-es").addEventListener("change", () => { // « ±0,1 » dans ES : ES = 0,1 et EI = −0,1
      const m = /^(?:±|\+\/-|\+-)\s*(\d*[.,]?\d+)$/.exec(f("m-es").value.trim());
      if (m) { f("m-es").value = m[1]; f("m-ei").value = "-" + m[1]; }
    });
    // image de la pièce : aperçu, liste (catalogue + mes images) et inclinaison ; colonne affichée si « Représentation » est cochée
    const tdImage = Object.assign(document.createElement("td"), { className: "td-image" });
    const choix = liste("m-image", optionsImages(m.image), m.image || "");
    choix.setAttribute("aria-label", `Image de la pièce, maillon ${numero}`);
    const angle = champ(m.imageAngle, "m-angle", true);
    angle.setAttribute("aria-label", `Inclinaison de l'image en degrés, maillon ${numero}`);
    angle.placeholder = "0°";
    const NS = "http://www.w3.org/2000/svg";
    const vue = document.createElementNS(NS, "svg");
    vue.setAttribute("viewBox", "0 0 40 40");
    vue.setAttribute("aria-hidden", "true");
    const montrer = () => {
      vue.replaceChildren();
      if (!imageConnue(choix.value)) return;
      const g = document.createElementNS(NS, "g");
      g.setAttribute("transform", `rotate(${angleDe(angle.value)} 20 20)`);
      const el = document.createElementNS(NS, estPerso(choix.value) ? "image" : "use");
      if (estPerso(choix.value)) {
        for (const [k, v] of [["href", perso[choix.value.slice(PERSO.length)]], ["x", 0], ["y", 0], ["width", 40], ["height", 40], ["preserveAspectRatio", "xMidYMid meet"]]) el.setAttribute(k, v);
      } else el.setAttribute("href", "#img-" + choix.value);
      g.append(el);
      vue.append(g);
    };
    const tourner = (delta, nom) => {
      const b = Object.assign(document.createElement("button"), { type: "button", className: "secondaire petit", textContent: delta < 0 ? "↺" : "↻", title: `Tourner de 90° ${delta < 0 ? "à gauche" : "à droite"}` });
      b.setAttribute("aria-label", `${nom}, maillon ${numero}`);
      b.addEventListener("click", () => {
        angle.value = String((((angleDe(angle.value) + delta) % 360) + 360) % 360);
        angle.dispatchEvent(new Event("input", { bubbles: true })); // l'aperçu suit
      });
      return b;
    };
    choix.addEventListener("change", montrer);
    angle.addEventListener("input", montrer);
    montrer();
    const haut = Object.assign(document.createElement("div"), { className: "image-haut" });
    haut.append(vue, choix);
    const bas = Object.assign(document.createElement("div"), { className: "image-bas" });
    bas.append(Object.assign(document.createElement("span"), { textContent: "Inclinaison" }), angle, Object.assign(document.createElement("span"), { textContent: "°" }),
      tourner(-90, "Tourner à gauche"), tourner(90, "Tourner à droite"));
    tdImage.append(haut, bas);
    tr.append(tdImage);
    const td = Object.assign(document.createElement("td"), { className: "actions" });
    const agir = (libelle, contenu, action) => { // dupliquer, monter, descendre, supprimer : un bouton par action sur la ligne
      const b = Object.assign(document.createElement("button"), { type: "button", className: "secondaire", title: libelle, innerHTML: contenu });
      b.setAttribute("aria-label", `${libelle}, maillon ${numero}`);
      b.addEventListener("click", () => {
        const lignes = lireMaillons();
        action(lignes);
        afficherMaillons(lignes);
        apercuDiffere();
      });
      return b;
    };
    td.append(
      agir("Dupliquer", icone("dupliquer"), (l) => l.splice(numero, 0, { ...l[numero - 1], nom: l[numero - 1].nom + " (copie)", extra: { ...l[numero - 1].extra } })),
      agir("Monter", icone("monter"), (l) => { if (numero > 1) l.splice(numero - 2, 0, ...l.splice(numero - 1, 1)); }),
      agir("Descendre", icone("descendre"), (l) => { if (numero < l.length) l.splice(numero, 0, ...l.splice(numero - 1, 1)); }),
      agir("Supprimer", "✕", (l) => l.splice(numero - 1, 1)),
    );
    tr.append(td);
    return tr;
  }

  function afficherMaillons(maillons) {
    const lignes = maillons.map((m, i) => ligneMaillon(m, i + 1));
    document.querySelector("#maillons tbody").replaceChildren(...lignes);
    if (pont) for (const tr of lignes) if (tr.querySelector(".m-iso").value.trim()) appliquerIso(tr); // les écarts suivent la désignation
  }

  function lireMaillons() {
    return [...document.querySelectorAll("#maillons tbody tr")].map((tr) => ({
      nom: tr.querySelector(".m-nom").value,
      sens: tr.querySelector(".m-sens").value,
      sens2: tr.querySelector(".m-sens2").value,
      cote: tr.querySelector(".m-cote").value,
      iso: tr.querySelector(".m-iso").value,
      es: tr.querySelector(".m-es").value,
      ei: tr.querySelector(".m-ei").value,
      loi: tr.querySelector(".m-loi").value,
      materiau: tr.querySelector(".m-mat").value,
      alpha: tr.querySelector(".m-alpha").value,
      tservice: tr.querySelector(".m-tserv").value,
      image: tr.querySelector(".m-image").value,
      imageAngle: tr.querySelector(".m-angle").value,
      extra: tr._extra,
    }));
  }

  // ---------- désignation ISO 286 : liste déroulante, écarts ES et EI remplis ----------

  const cacheIso = new Map(); // cote → liste [désignation, texte] : un seul appel du pont par cote

  function listeIso(coteTexte) {
    const c = nombre(coteTexte), dl = $("liste-iso");
    if (typeof c !== "number" || !(c > 0)) return dl.replaceChildren();
    if (!cacheIso.has(c)) cacheIso.set(c, JSON.parse(pont.isoListe(c)));
    dl.replaceChildren(...cacheIso.get(c).map(([d, texte]) => Object.assign(document.createElement("option"), { value: d, label: texte, textContent: texte })));
  }

  // Une désignation saisie ou choisie remplit ES et EI d'après la cote de la ligne ; une désignation fausse est signalée sur la case.
  function appliquerIso(tr) {
    const iso = tr.querySelector(".m-iso"), c = nombre(tr.querySelector(".m-cote").value), d = iso.value.trim();
    iso.classList.remove("invalide");
    iso.title = "";
    if (!d) return;
    const signaler = (texte) => { iso.classList.add("invalide"); iso.title = texte; };
    if (typeof c !== "number") return signaler("Saisissez d'abord la cote nominale : les écarts en dépendent.");
    const r = JSON.parse(pont.isoEcarts(d, c));
    if (r.erreur) return signaler(r.erreur);
    tr.querySelector(".m-es").value = String(r.es);
    tr.querySelector(".m-ei").value = String(r.ei);
  }

  // ---------- collage depuis un tableur ----------

  // Cellules copiées d'un tableur → lignes {nom, sens, iso, cote, es, ei} : un texte = nom, « + » ou « − » = sens, « h7 » après le nom = désignation
  // ISO 286, puis les nombres dans l'ordre cote, ES, EI. Une ligne sans nombre (titres de colonnes) est ignorée.
  function collage(texte) {
    const lignes = [];
    for (const l of texte.replace(/\r/g, "").split("\n")) {
      const m = {}, nombres = [];
      for (const c of l.split("\t").map((x) => x.trim()).filter(Boolean)) {
        if (/^[-+−]$/.test(c) && m.sens === undefined) m.sens = c === "+" ? "+" : "-";
        else if (/^[-+−]?\d+(?:[.,]\d+)?$/.test(c)) nombres.push(c.replace("−", "-"));
        else if (m.nom !== undefined && /^[A-Za-z]{1,2}\d{1,2}$/.test(c)) m.iso = c;
        else if (m.nom === undefined) m.nom = c;
      }
      if (!nombres.length) continue;
      ["cote", "es", "ei"].forEach((k, i) => { if (nombres[i] !== undefined) m[k] = nombres[i]; });
      lignes.push(m);
    }
    return lignes;
  }

  // ---------- sauvegarde automatique, nom de fichier, lien de partage ----------

  const CLE_ETUDE = "chainecotes.etude"; // dernière étude, reprise à la prochaine visite

  function etudeGardee() {
    try {
      const p = JSON.parse(localStorage.getItem(CLE_ETUDE) || "null");
      return p && p.condition && Array.isArray(p.maillons) && p.maillons.length ? p : null;
    } catch (e) { return null; }
  }

  // « chaine_jeu_axial » d'après le nom de la cote condition (sans accents ni espaces).
  const nomFichier = () => "chaine_" + ($("c-nom").value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, "").toLowerCase() || "de_cotes");

  // Le lien contient l'étude compressée, après le « # » : elle ne passe par aucun serveur.
  async function lireLimite(flux, max = 2e6) { // un lien piégé ne doit pas se décompresser en gigaoctets
    const lecteur = flux.getReader(), morceaux = [];
    let total = 0;
    for (;;) {
      const { done, value } = await lecteur.read();
      if (done) break;
      total += value.length;
      if (total > max) { lecteur.cancel(); throw new Error("contenu trop volumineux"); }
      morceaux.push(value);
    }
    return new TextDecoder().decode(await new Blob(morceaux).arrayBuffer());
  }

  async function copierLien() {
    try {
      const flux = new Blob([JSON.stringify(lireCommun())]).stream().pipeThrough(new CompressionStream("deflate-raw"));
      const octets = new Uint8Array(await new Response(flux).arrayBuffer());
      const lien = location.href.split("#")[0] + "#etude=" + btoa(String.fromCharCode(...octets)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
      if (lien.length > 8000) return messageFichier("avertissement", "Étude trop grande pour un lien : utilisez « Enregistrer l'étude » et envoyez le fichier.");
      const copie = await App.copier(lien);
      App.confirmer($("copier-lien"), copie, "Lien copié", "Copie impossible", copie ? "Lien copié : collez-le dans un message." : "Copie refusée par le navigateur.");
      messageFichier(copie ? "succes" : "erreur", copie ? "Lien copié : collez-le dans un message. Il contient l'étude, rien n'est envoyé sur Internet." : "Copie impossible : le navigateur l'a refusée.");
    } catch (e) { messageFichier("erreur", "Lien impossible : " + e.message); }
  }

  async function ouvrirLien() {
    const m = /^#etude=([A-Za-z0-9_-]+)$/.exec(location.hash);
    if (!m) return;
    history.replaceState(null, "", location.href.split("#")[0]); // un F5 ne doit pas écraser les modifications faites ensuite
    try {
      const octets = Uint8Array.from(atob(m[1].replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
      const p = JSON.parse(await lireLimite(new Blob([octets]).stream().pipeThrough(new DecompressionStream("deflate-raw"))));
      if (!p || !Array.isArray(p.maillons) || p.maillons.length > 200) throw new Error("contenu inattendu");
      etude = { cartouche: p.cartouche || null, revisions: [] };
      poserProbleme(p);
      $("resultats").hidden = true;
      apercu();
      messageFichier("succes", "Étude ouverte depuis un lien. Cliquez sur Calculer.");
    } catch (e) { messageFichier("erreur", "Lien illisible : " + e.message); }
    App.afficherPage("analyser");
  }

  // ---------- problème ↔ saisie ----------

  // État complet de la saisie : une chaîne, ou deux (condition2 et sens2 de chaque maillon) quand « Deux cotes condition » est cochée.
  function lireCommun() {
    const deux = $("deux-cf").checked;
    const therm = $("thermique").checked;
    const maillons = lireMaillons().map((m) => ({
      ...m.extra,
      nom: m.nom, sens: m.sens, ...(deux ? { sens2: m.sens2 } : {}), loi: m.loi, iso: m.iso.trim(),
      cote: nombre(m.cote), es: nombre(m.es), ei: nombre(m.ei),
      image: m.image, // gardée même si « Représentation » est décochée
      imageAngle: nombre(m.imageAngle),
      ...(therm ? { materiau: m.materiau, alpha: nombre(m.alpha), tservice: nombre(m.tservice) } : {}),
    }));
    const probleme = {
      condition: { nom: $("c-nom").value, jmin: nombre($("c-jmin").value), jmax: nombre($("c-jmax").value) },
      reglages: {
        kSigma: nombre($("r-k").value), tref: nombre($("r-tref").value), tservice: nombre($("r-tserv").value),
        modeT: $("r-mode").value, decentrage: nombre($("r-dec").value), tolGenerale: $("r-tolgen").value,
      },
      maillons,
    };
    if (deux) probleme.condition2 = { nom: $("c2-nom").value, jmin: nombre($("c2-jmin").value), jmax: nombre($("c2-jmax").value) };
    if (etude.cartouche) probleme.cartouche = etude.cartouche;
    return probleme;
  }

  // Une cote est dans la chaîne si son sens y est « + » ou « − » (toujours vrai avec une seule cote condition).
  const dansChaine = (sens, deux) => !deux || sens === "+" || sens === "-";
  const cfActive = () => ($("deux-cf").checked && document.querySelector('input[name="cf-actif"]:checked').value === "2" ? 2 : 1);

  // Problème d'une seule chaîne (CF1 ou CF2) tiré de l'état complet : ce que le calcul de l'application reçoit.
  function chaineCF(c, k) {
    const deux = c.condition2 !== undefined;
    const cle = k === 2 ? "sens2" : "sens";
    const { condition2, ...base } = c;
    return {
      ...base,
      condition: k === 2 ? condition2 : c.condition,
      maillons: c.maillons.filter((m) => dansChaine(m[cle], deux)).map((m) => { const { sens2, ...reste } = m; return { ...reste, sens: m[cle] }; }),
    };
  }
  const lignesCF = (k) => lireMaillons().filter((m) => dansChaine(k === 2 ? m.sens2 : m.sens, $("deux-cf").checked));
  const indicesCF = (k) => lireMaillons().map((m, i) => (dansChaine(k === 2 ? m.sens2 : m.sens, $("deux-cf").checked) ? i : -1)).filter((i) => i >= 0);

  // Problème de la cote condition active : celui des pages Optimiser, Comparer et Dossier.
  function lireProbleme() {
    return chaineCF(lireCommun(), cfActive());
  }

  // Maillon d'un problème (champs absents ou null possibles) → ligne du tableau ; les champs non saisis vont dans extra.
  function versLigne(m) {
    return {
      ...MAILLON_VIDE, ...Object.fromEntries(CHAMPS_CONNUS.filter((k) => m[k] != null).map((k) => [k, m[k]])),
      extra: Object.fromEntries(Object.entries(m).filter(([k]) => !CHAMPS_CONNUS.includes(k))),
    };
  }

  function poserProbleme(p) {
    const c = p.condition || {}, r = p.reglages || {};
    $("c-nom").value = c.nom ?? "Jeu J";
    $("c-jmin").value = c.jmin ?? "";
    $("c-jmax").value = c.jmax ?? "";
    $("r-k").value = r.kSigma ?? 3;
    $("r-tref").value = r.tref ?? 20;
    $("r-tserv").value = r.tservice ?? r.tref ?? 20;
    $("r-mode").value = r.modeT ?? "uniforme";
    $("r-dec").value = r.decentrage ?? 0;
    $("r-tolgen").value = r.tolGenerale ?? "";
    const c2 = p.condition2;
    $("deux-cf").checked = Boolean(c2);
    $("c2-nom").value = c2 ? c2.nom ?? "Jeu J2" : "Jeu J2";
    $("c2-jmin").value = c2 ? c2.jmin ?? "" : "";
    $("c2-jmax").value = c2 ? c2.jmax ?? "" : "";
    document.querySelector('input[name="cf-actif"][value="1"]').checked = true;
    const maillons = (p.maillons || []).map(versLigne);
    afficherMaillons(maillons);
    // la température de chaque maillon (20 °C dans les fichiers du bureau) ne compte pas : seuls un matériau, un α,
    // le mode « par cote » ou une température de service différente de la référence activent l'effet thermique
    const avecThermique = maillons.some((m) => m.materiau || m.alpha !== "")
      || r.modeT === "par_cote" || (r.tservice != null && r.tservice !== (r.tref ?? 20));
    $("thermique").checked = avecThermique;
    $("representation").checked = maillons.some((m) => m.image);
    colonnesThermiques();
  }

  function colonnesThermiques() {
    const t = $("maillons");
    t.classList.toggle("therm", $("thermique").checked);
    t.classList.toggle("tcote", $("thermique").checked && $("r-mode").value === "par_cote");
    t.classList.toggle("images", $("representation").checked);
    const deux = $("deux-cf").checked;
    t.classList.toggle("cf2", deux);
    $("cf2-champs").hidden = !deux;
    $("cf-choix").hidden = !deux;
    $("perso-zone").hidden = !$("representation").checked;
    $("zone-maillons").classList.toggle("large", $("representation").checked || $("thermique").checked || deux); // colonnes en plus : tableau plus large
  }

  // ---------- aperçu en direct ----------

  let minuterie = null;
  function apercuDiffere() {
    clearTimeout(minuterie);
    minuterie = setTimeout(apercu, 350);
  }

  // ---------- historique : Ctrl+Z / Ctrl+Y sur toute l'étude (ajout, suppression, exemple chargé, saisie) ----------

  const pile = []; // instantanés de l'étude (texte JSON) ; position = instantané affiché
  let position = -1;
  let restauration = false;
  const MAX_HISTORIQUE = 100;

  function majHistorique() {
    $("annuler").disabled = position <= 0;
    $("retablir").disabled = position >= pile.length - 1;
  }

  // Appelé à chaque aperçu (donc après chaque pause de saisie ou changement de structure) : garde l'état s'il a changé.
  let instantaneCalcule = null; // état de l'étude au dernier calcul : s'il change, le résultat affiché est « ancien »
  function marquerAncien(instantane) {
    const ancien = !$("resultats").hidden && instantaneCalcule !== null && instantane !== instantaneCalcule;
    $("resultats").classList.toggle("ancien", ancien);
    $("resultat-ancien").hidden = !ancien;
  }

  function memoriser() {
    if (restauration) return;
    const instantane = JSON.stringify(lireCommun());
    marquerAncien(instantane);
    if (instantane === pile[position]) return;
    pile.splice(position + 1);
    pile.push(instantane);
    if (pile.length > MAX_HISTORIQUE) pile.shift();
    try { localStorage.setItem(CLE_ETUDE, instantane); } catch (e) { /* sans mémoire : l'étude n'est pas reprise à la prochaine visite */ }
    position = pile.length - 1;
    majHistorique();
  }

  function aller(delta) {
    clearTimeout(minuterie);
    memoriser(); // une saisie en cours (moins de 350 ms) est d'abord gardée : on peut l'annuler
    const cible = position + delta;
    if (cible < 0 || cible >= pile.length) return;
    position = cible;
    const garder = $("representation").checked; // la case « Représentation » est un réglage d'affichage, pas une donnée
    restauration = true;
    try {
      poserProbleme(JSON.parse(pile[position]));
      $("representation").checked = garder;
      colonnesThermiques();
      $("resultats").hidden = true; // les résultats affichés ne sont plus ceux de l'étude
      apercu();
    } finally {
      restauration = false;
    }
    majHistorique();
  }

  // Résumé affiché dans le titre d'un bandeau, utile quand il est replié.
  function majResumes() {
    const lim = (v, vide) => (String(v).trim() === "" ? vide : String(v).trim()); // côté sans limite : −∞ ou +∞
    $("resume-condition").textContent = `${$("c-nom").value || "sans nom"} : ${lim($("c-jmin").value, "−∞")} à ${lim($("c-jmax").value, "+∞")} mm`;
    $("cf-nom1").textContent = "CF1 : " + ($("c-nom").value || "sans nom");
    $("cf-nom2").textContent = "CF2 : " + ($("c2-nom").value || "sans nom");
    if ($("deux-cf").checked) $("resume-condition").textContent += ` ; ${$("c2-nom").value || "sans nom"} : ${lim($("c2-jmin").value, "−∞")} à ${lim($("c2-jmax").value, "+∞")} mm`;
    $("resume-maillons").textContent = `${$("maillons").tBodies[0].rows.length} maillon(s)`;
  }

  // Aperçu d'une chaîne : verdict du pire des cas, schéma (avec silhouettes si demandé). Renvoie la réponse du pont, ou null.
  function apercuUne(probleme, lignes, ids) {
    let r;
    try {
      r = JSON.parse(pont.apercu(JSON.stringify(probleme)));
    } catch (e) {
      App.message($(ids.verdict), "erreur", "Aperçu impossible : " + e);
      return null;
    }
    if (r.erreur) App.message($(ids.verdict), "avertissement", "Saisie à compléter : " + r.erreur);
    else App.message($(ids.verdict), r.pireCas.niveau, r.pireCas.texte);
    if ($("representation").checked) vignettes(r.fig, lignes, $(ids.fig));
    App.tracer($(ids.fig), r.fig);
    $(ids.legende).textContent = r.erreur ? "" : r.legende;
    return r;
  }

  function apercu() {
    memoriser();
    majResumes();
    const c = lireCommun(), deux = c.condition2 !== undefined;
    $("apercu-cf2").hidden = !deux;
    $("apercu-cf1-titre").hidden = !deux;
    $("apercu-cf1-titre").textContent = "CF1 : " + (c.condition.nom || "sans nom");
    if (deux) $("apercu-cf2-titre").textContent = "CF2 : " + (c.condition2.nom || "sans nom");
    const r1 = apercuUne(chaineCF(c, 1), lignesCF(1), { verdict: "apercu-verdict", fig: "apercu-fig", legende: "apercu-legende" });
    const r2 = deux ? apercuUne(chaineCF(c, 2), lignesCF(2), { verdict: "apercu-verdict2", fig: "apercu-fig2", legende: "apercu-legende2" }) : null;
    if (!r1 || (deux && !r2)) return;
    const avec = (r, prefixe) => r.controles.map((x) => ({ ...x, message: prefixe + x.message }));
    $("controles").replaceChildren(...[...avec(r1, deux ? "CF1 : " : ""), ...(deux ? avec(r2, "CF2 : ") : [])].map((x) => {
      const li = document.createElement("li");
      li.className = x.niveau;
      li.textContent = ({ erreur: "Erreur : ", avertissement: "Attention : ", info: "À noter : " }[x.niveau] || "") + x.message;
      return li;
    }));
  }

  // ---------- résultats ----------

  function figures(panneau, liste) {
    for (const f of liste) {
      const d = document.createElement("div");
      d.className = "figure";
      panneau.append(d);
      App.tracer(d, f.fig);
      panneau.append(App.legende(f.legende));
    }
  }

  function onglets(r) {
    const res = r.resultats, st = r.statistiques;
    return [
      {
        id: "resultats", titre: "Résultats",
        rendu(p) {
          p.append(App.metriques(res.metriques));
          if (r.details.length) {
            const ul = document.createElement("ul");
            ul.className = "details";
            for (const d of r.details) ul.append(Object.assign(document.createElement("li"), { textContent: d }));
            p.append(ul);
          }
          p.append(App.titre("Verdicts"), App.legende(res.limites), App.tableau(res.verdicts));
          p.append(App.titre("Maillons"), App.tableau(res.maillons), App.legende(res.legendeMaillons));
          if (res.capabilite) p.append(App.titre("Capabilité de chaque cote"), App.tableau(res.capabilite));
        },
      },
      {
        id: "statistiques", titre: "Statistiques",
        rendu(p) {
          if (st.monteCarlo) p.append(App.legende(st.monteCarlo.texte), App.tableau(st.monteCarlo.table));
          else p.append(App.legende("Pas de tirage Monte-Carlo : l'écart-type du jeu est nul, il n'y a rien à simuler."));
          p.append(App.titre("Tolérancement inertiel (Pillet)"), App.metriques(st.inertiel.metriques));
          if (st.inertiel.table) {
            p.append(App.tableau(st.inertiel.table), App.legende(
              "L'inertie d'une cote mêle sa dispersion et son décentrage. Répartir l'inertie maxi du jeu également autorise des IT "
              + "environ √n fois plus larges que la répartition égale au pire des cas, à condition que chaque cote soit produite "
              + "avec cette inertie. Ordres de grandeur pour discuter d'une cotation, pas une cotation."));
          } else p.append(App.legende(st.inertiel.info));
          figures(p, r.figuresStatistiques);
        },
      },
      { id: "graphiques", titre: "Graphiques", rendu: (p) => figures(p, r.figuresGraphiques) },
      {
        id: "sensibilite", titre: "Sensibilité",
        rendu(p) {
          p.append(App.legende("L'indice de Sobol d'un maillon est la part de la variance du jeu qu'il explique (somme = 100 %). "
            + "Resserrer la tolérance du maillon au plus fort indice est le levier le plus efficace."));
          figures(p, [r.sensibilite.figure]);
          if (r.sensibilite.table) {
            p.append(App.tableau(r.sensibilite.table), App.legende(
              "Colonnes « si resserré » : un seul maillon est ramené à 50 % de son IT, les autres gardent leur tolérance ; moyenne du procédé et limites inchangées."));
          }
        },
      },
      {
        id: "explications", titre: "Explications du calcul",
        rendu(p) {
          for (const s of r.explications) {
            p.append(App.titre(s.titre));
            const texte = document.createElement("div");
            texte.innerHTML = App.markdown(s.texte); // texte échappé par App.markdown
            p.append(texte);
            for (const f of s.formules) {
              const d = document.createElement("div");
              d.className = "formule";
              d.innerHTML = f; // HTML produit par core/formules.texVersHtml, qui échappe le texte
              p.append(d);
            }
          }
        },
      },
    ];
  }

  // Chiffres clés et cause principale sous le verdict (données « decision » du pont) ; « Aller à la cause » ouvre le tableau
  // des maillons sur la cote qui pèse le plus.
  function afficherDecision(d) {
    $("decision").hidden = !d;
    if (!d) return;
    $("decision-chiffres").replaceChildren(...(d.chiffres?.length ? [App.metriques(d.chiffres)] : []));
    const cause = d.principaux && d.principaux[0] && d.principaux[0].part > 0 ? d.principaux[0] : null; // sans dispersion, pas de cause
    $("decision-cause").hidden = !cause;
    if (cause) {
      const autre = d.principaux[1];
      const egalite = autre && Math.abs(autre.part - cause.part) < 0.5; // deux cotes qui pèsent pareil : on le dit
      $("decision-cause-texte").textContent = egalite
        ? `« ${cause.nom} » et « ${autre.nom} » (${Math.round(cause.part)} % de la variance du jeu chacune, à égalité)`
        : `« ${cause.nom} » (${Math.round(cause.part)} % de la variance du jeu)`;
      $("decision-aller").onclick = () => {
        const ligne = [...document.querySelectorAll("#maillons tbody tr")].find((tr) => tr.querySelector(".m-nom").value === cause.nom);
        if (!ligne) return;
        $("b-maillons").open = true;
        ligne.scrollIntoView({ behavior: "smooth", block: "center" });
        (ligne.querySelector(".m-iso").value ? ligne.querySelector(".m-iso") : ligne.querySelector(".m-es")).focus();
      };
    }
  }

  function afficherResultats(r) {
    $("resultats").hidden = false;
    instantaneCalcule = JSON.stringify(lireCommun());
    $("resultats").classList.remove("ancien");
    $("resultat-ancien").hidden = true;
    afficherDecision(r.decision);
    $("t-resultats").textContent = $("deux-cf").checked ? `Résultats : CF${cfActive()} « ${lireProbleme().condition.nom || "sans nom"} »` : "Résultats";
    App.message($("verdict"), r.niveau, r.titre);
    $("conseil").textContent = r.conseil ? "À faire : " + r.conseil : "";
    $("opt-invite").hidden = r.niveau !== "erreur"; // jeu non tenu : on propose d'optimiser les tolérances
    // mode guidé : le verdict en langage courant (chiffres, puis conseils)
    const puces = (liste) => liste.map((t) => Object.assign(document.createElement("li"), { textContent: t }));
    $("plain-details").replaceChildren(...puces(r.details));
    const ul = Object.assign(document.createElement("ul"), { className: "details" });
    ul.append(...puces(r.conseils));
    $("plain-conseils").replaceChildren(...(r.conseils.length ? [App.titre("Que faire ?"), ul] : []));
    $("avertissements").replaceChildren(...r.avertissements.map((t) => Object.assign(document.createElement("li"), { textContent: t })));
    App.onglets($("onglets"), $("panneau"), onglets(r).map((o) => ({ ...o, rendu: (p) => { ongletActif = o.id; o.rendu(p); } })), ongletActif);
    App.majBlocs();
  }

  function calculer() {
    App.message($("erreur"), "erreur", "");
    $("calculer").disabled = true;
    $("calculer").textContent = "Calcul en cours…";
    // laisse le navigateur afficher le message avant le calcul, qui occupe le processeur quelques secondes
    setTimeout(() => {
      let r = null;
      try {
        r = JSON.parse(pont.calculer(JSON.stringify(lireProbleme())));
        if (r.erreur) {
          $("resultats").hidden = true;
          App.message($("erreur"), "erreur", r.erreur);
        } else {
          afficherResultats(r);
          // mode expert : le verdict est sous le tableau des maillons, on y amène l'utilisateur
          if (!guide.actif && !$("page-analyser").hidden) $("resultats").scrollIntoView({ behavior: "smooth", block: "start" });
        }
      } catch (e) {
        App.message($("erreur"), "erreur", "Erreur inattendue : " + e);
      } finally {
        $("calculer").disabled = false;
        $("calculer").textContent = "Calculer";
      }
    }, 30);
  }

  // ---------- exemples, fichiers ----------

  function messageFichier(niveau, texte) {
    App.message($("message-fichier"), niveau, texte);
  }

  // ---------- parcours guidé : les mêmes sections, montrées une étape à la fois ----------

  const ETAPES = [
    ["Point de départ", "Une chaîne de cotes répond à une question : <strong>le jeu entre deux pièces reste-t-il dans ses limites ?</strong> Partez d'un exemple, d'une étude déjà enregistrée, ou de la chaîne en cours."],
    ["Cote condition", "La <strong>cote condition</strong> est le jeu (ou le serrage, le dépassement) à garantir. Donnez-lui un nom et ses limites : <strong>Jmin</strong> est le plus petit jeu acceptable, <strong>Jmax</strong> le plus grand."],
    ["Maillons", "Ajoutez une ligne par cote de la chaîne : son <strong>sens</strong> (« + » si elle agrandit le jeu, « − » si elle le réduit), sa <strong>cote nominale</strong> et sa <strong>tolérance</strong> (désignation ISO comme H7, ou écarts ES / EI)."],
    ["Calcul et verdict", "Le calcul est lancé à l'ouverture de cette étape. Lisez le verdict : il dit si le jeu tient et sur quelle cote agir. Après une modification, cliquez sur <strong>Calculer</strong>."],
    ["Dossier", "Complétez le cartouche, gardez une révision, puis enregistrez le dossier et l'étude."],
  ];
  const guide = { actif: false, etape: 0 };

  function majGuide() {
    const page = $("page-analyser");
    page.classList.toggle("guidee", guide.actif);
    for (const el of page.querySelectorAll("[data-etape]")) {
      const courante = Number(el.dataset.etape) === guide.etape + 1;
      el.classList.toggle("etape-courante", courante);
      if (courante && guide.actif && el.tagName === "DETAILS") el.open = true; // un bandeau replié reste lisible dans le parcours guidé
    }
    $("guide-etapes").replaceChildren(...ETAPES.map(([titre], i) => {
      const li = document.createElement("li");
      const b = Object.assign(document.createElement("button"), { type: "button", textContent: `${i + 1}. ${titre}` });
      b.setAttribute("aria-current", String(i === guide.etape ? "step" : "false"));
      b.addEventListener("click", () => allerEtape(i));
      li.append(b);
      return li;
    }));
    $("guide-titre").textContent = `Étape ${guide.etape + 1} sur ${ETAPES.length} : ${ETAPES[guide.etape][0]}`;
    $("guide-texte").innerHTML = ETAPES[guide.etape][1]; // textes écrits ici, sans donnée de l'utilisateur
    for (const b of page.querySelectorAll(".js-precedent")) b.disabled = guide.etape === 0;
    for (const b of page.querySelectorAll(".js-suivant")) b.disabled = guide.etape === ETAPES.length - 1;
  }

  function allerEtape(i) {
    guide.etape = Math.min(Math.max(i, 0), ETAPES.length - 1);
    majGuide();
    window.scrollTo(0, 0);
    if (guide.etape === 3) calculer(); // étape « Calcul et verdict » : pas de clic de plus
  }

  function modeGuide(actif, etape = 0) {
    guide.actif = actif;
    guide.etape = etape;
    majGuide();
  }

  async function ouvrirFichier(fichier) {
    if (!fichier) return;
    let o;
    try {
      const texte = await fichier.text();
      o = JSON.parse(pont.ouvrir(texte));
      if (o.erreur) { // pas une étude : peut-être un fichier de mécanisme (une ou deux chaînes)
        const m = JSON.parse(pont.mecaImporter(texte));
        if (!m.erreur && m.chaines && m.chaines.length === 1) o = { probleme: m.chaines[0], revisions: [] };
        else if (!m.erreur && m.chaines && m.chaines.length === 2) {
          const f = JSON.parse(pont.cfFusionner(JSON.stringify({ chaines: m.chaines })));
          if (f.erreur) return messageFichier("erreur", f.erreur);
          etude = { cartouche: f.commun.cartouche || null, revisions: [] };
          poserProbleme(f.commun);
          $("resultats").hidden = true;
          App.message($("erreur"), "erreur", "");
          messageFichier(f.avertissement ? "avertissement" : "succes", `Mécanisme « ${fichier.name} » ouvert comme étude à deux cotes condition. ${f.avertissement}`.trim());
          apercu();
          return;
        } else if (!m.erreur && m.chaines) return messageFichier("erreur", `Ce mécanisme contient ${m.chaines.length} chaînes : ouvrez-le dans la page Mécanisme (l'étude en accepte 2 au plus).`);
      }
    } catch (e) {
      messageFichier("erreur", "Lecture impossible : " + e);
      return;
    }
    if (o.erreur) {
      messageFichier("erreur", o.erreur);
      return;
    }
    etude = { cartouche: o.probleme.cartouche || null, revisions: o.revisions || [] };
    poserProbleme(o.probleme);
    $("resultats").hidden = true;
    App.message($("erreur"), "erreur", "");
    messageFichier("succes", `Étude « ${fichier.name} » ouverte : ${o.probleme.maillons.length} maillon(s). Cliquez sur Calculer.`);
    apercu();
  }

  function enregistrer() {
    const c = lireCommun();
    if (c.condition2 !== undefined) { // deux cotes condition : fichier de mécanisme à deux chaînes, lisible aussi par le bureau
      const chaines = [];
      for (const chaine of [chaineCF(c, 1), chaineCF(c, 2)]) { // chaque chaîne est d'abord nettoyée et validée, comme dans la page Mécanisme
        const v = JSON.parse(pont.mecaChaine(JSON.stringify(chaine)));
        if (v.erreur) return messageFichier("erreur", "Enregistrement impossible : " + v.erreur);
        chaines.push(v.probleme);
      }
      const m = JSON.parse(pont.mecaExporter(JSON.stringify({ nom: "Étude à deux cotes condition", chaines })));
      if (m.erreur) return messageFichier("erreur", "Enregistrement impossible : " + m.erreur);
      App.telecharger(nomFichier() + "_2_CF.json", m.contenu);
      messageFichier("succes", `Étude à deux cotes condition enregistrée au format Mécanisme : ${nomFichier()}_2_CF.json. Les révisions du dossier ne sont gardées qu'avec une seule cote condition.`);
      return;
    }
    const r = JSON.parse(pont.sauver(JSON.stringify(lireProbleme()), JSON.stringify(etude.revisions)));
    if (r.erreur) {
      messageFichier("erreur", "Enregistrement impossible : " + r.erreur);
      return;
    }
    App.telecharger(nomFichier() + ".json", r.contenu);
    messageFichier("succes", `Étude enregistrée : ${nomFichier()}.json (dossier des téléchargements).`);
  }

  async function apres(p) {
    pont = p;
    materiaux = JSON.parse(pont.materiaux());
    const exemples = JSON.parse(pont.exemples());
    const choix = $("exemple");
    choix.replaceChildren(...exemples.map((e) => Object.assign(document.createElement("option"), { value: e.id, textContent: e.titre })));
    choix.prepend(Object.assign(document.createElement("option"), { value: "", textContent: "Cas de base : 6 cotes (modifiable)" }));
    choix.value = "";
    const decrire = () => {
      $("description").textContent = (exemples.find((e) => e.id === choix.value) || {}).description
        || "Cas de base affiché ci-dessous : 6 cotes (4 « + », 2 « − »), dont deux (C et F) à grande tolérance. Modifiez-le, ou choisissez un exemple.";
    };
    choix.addEventListener("change", decrire);
    decrire();
    $("charger").addEventListener("click", () => {
      if (!choix.value) return poserProbleme(CAS_DE_BASE), $("resultats").hidden = true, apercu(); // retour au cas de base
      etude = { cartouche: null, revisions: [] };
      poserProbleme(JSON.parse(pont.charger(choix.value)));
      $("resultats").hidden = true;
      App.message($("erreur"), "erreur", "");
      messageFichier("info", "");
      $("b-depart").open = false;
      calculer();
      apercu();
    });
    $("ouvrir").addEventListener("click", () => $("fichier").click());
    $("fichier").addEventListener("change", async (e) => { await ouvrirFichier(e.target.files[0]); e.target.value = ""; });
    $("enregistrer").addEventListener("click", enregistrer);
    $("annuler").addEventListener("click", () => aller(-1));
    $("retablir").addEventListener("click", () => aller(1));
    document.addEventListener("keydown", (e) => {
      if ($("page-analyser").hidden || e.altKey) return;
      const touche = e.key.toLowerCase(), ctrl = e.ctrlKey || e.metaKey;
      if (ctrl && touche === "z") aller(e.shiftKey ? 1 : -1);
      else if (ctrl && touche === "y") aller(1);
      else if (ctrl && touche === "s") enregistrer();
      else if (ctrl && touche === "o") $("fichier").click();
      else if (touche === "enter" && !e.target.closest("form, #page-comparer, #page-dossier, #page-repartir, #recherche") && (ctrl || (e.target.tagName === "INPUT" && e.target.type === "text"))) {
        if (!$("calculer").disabled) guide.actif ? allerEtape(3) : calculer();
      } else return;
      e.preventDefault();
    });
    $("ajouter").addEventListener("click", () => { afficherMaillons([...lireMaillons(), { ...MAILLON_VIDE }]); apercuDiffere(); });
    $("calculer").addEventListener("click", calculer);
    $("recalculer").addEventListener("click", calculer);
    // place du schéma par rapport au tableau des maillons : droite, gauche, dessus ou dessous (choix gardé dans ce navigateur)
    const PLACES = { droite: "à droite", gauche: "à gauche", dessus: "au-dessus", dessous: "en dessous" };
    const NOMS = Object.keys(PLACES);
    let place = "droite";
    try {
      place = localStorage.getItem("chainecotes.schemaPlace") || (localStorage.getItem("chainecotes.schemaDessous") === "1" ? "dessous" : "droite");
    } catch (e) { /* sans mémoire */ }
    if (!PLACES[place]) place = "droite";
    // sous 1200 px, « gauche » et « droite » n'existent pas : la page affiche le schéma dessous, et le bouton le dit
    const permises = () => (window.innerWidth >= 1200 ? NOMS : ["dessus", "dessous"]);
    const courante = () => (permises().includes(place) ? place : "dessous");
    const dispo = () => {
      for (const p of NOMS) $("zone-maillons").classList.toggle(p, p === place);
      $("disposition").textContent = "Schéma : " + PLACES[courante()];
    };
    window.addEventListener("resize", dispo);
    const poser = (p, annonce) => {
      place = p;
      try { localStorage.setItem("chainecotes.schemaPlace", place); } catch (e) { /* sans mémoire */ }
      dispo();
      apercu();
      if (annonce) App.messageFlottant("Schéma placé " + PLACES[courante()] + ".");
    };
    const suivante = () => permises()[(permises().indexOf(courante()) + 1) % permises().length];
    dispo();
    // poignée : on tire le schéma vers un bord du tableau des maillons ; un cadre pointillé montre la place visée
    const poignee = Object.assign(document.createElement("button"), { type: "button", className: "poignee", textContent: "⠿" });
    poignee.setAttribute("aria-label", "Déplacer le schéma : le tirer vers un bord, ou appuyer sur Entrée pour changer de place");
    poignee.title = "Tirer pour placer le schéma à gauche, à droite, au-dessus ou en dessous du tableau";
    $("apercu-section").querySelector("summary").prepend(poignee);
    const cibleDepot = (x, y) => { // bord le plus proche du pointeur, en fraction de la zone ; sous 1200 px, seulement dessus ou dessous
      const r = $("zone-maillons").getBoundingClientRect();
      const d = { gauche: (x - r.left) / r.width, droite: (r.right - x) / r.width, dessus: (y - r.top) / r.height, dessous: (r.bottom - y) / r.height };
      return permises().reduce((a, b) => (d[b] < d[a] ? b : a));
    };
    const cadreDepot = (cible) => {
      const r = $("zone-maillons").getBoundingClientRect();
      let c = $("depot-schema");
      if (!c) { c = document.createElement("div"); c.id = "depot-schema"; document.body.append(c); }
      const lateral = cible === "gauche" || cible === "droite";
      const w = lateral ? r.width * 0.4 : r.width, h = lateral ? r.height : Math.min(r.height * 0.3, 260);
      c.style.left = (cible === "droite" ? r.right - w : r.left) + "px";
      c.style.top = (cible === "dessous" ? r.bottom - h : r.top) + "px";
      c.style.width = w + "px";
      c.style.height = h + "px";
      c.dataset.texte = "Placer le schéma " + PLACES[cible];
    };
    let glisse = null;
    const finGlisse = () => { $("depot-schema")?.remove(); $("apercu-section").classList.remove("deplace"); document.body.classList.remove("glisse"); glisse = null; };
    poignee.addEventListener("pointerdown", (e) => {
      if (e.button) return;
      e.preventDefault();
      poignee.setPointerCapture(e.pointerId);
      glisse = { cible: cibleDepot(e.clientX, e.clientY), bouge: false };
      $("apercu-section").classList.add("deplace");
      document.body.classList.add("glisse");
      cadreDepot(glisse.cible);
    });
    poignee.addEventListener("pointermove", (e) => {
      if (!glisse) return;
      glisse.bouge = true;
      glisse.cible = cibleDepot(e.clientX, e.clientY);
      cadreDepot(glisse.cible);
    });
    poignee.addEventListener("pointerup", () => {
      if (!glisse) return;
      const { cible, bouge } = glisse;
      finGlisse();
      if (bouge && cible !== courante()) poser(cible, true);
    });
    poignee.addEventListener("pointercancel", finGlisse);
    poignee.addEventListener("keydown", (e) => { if (e.key === "Escape" && glisse) finGlisse(); });
    poignee.addEventListener("click", (e) => { // clic sans glisser (clavier) : place suivante
      e.preventDefault();
      e.stopPropagation();
      if (e.detail === 0) poser(suivante(), true);
    });
    // « Copier l'image » dans le titre des deux gros blocs (le schéma est copié avec son verdict et ses contrôles)
    $("apercu-section").querySelector("summary").append(App.boutonImage($("apercu-section"), "schema-et-controles.png"));
    $("resultats").querySelector("summary").append(App.boutonImage($("resultats"), "resultats.png"));
    $("disposition").addEventListener("click", () => poser(suivante()));
    // images personnelles (restent dans ce navigateur)
    lirePerso();
    const direImage = (niveau, texte) => App.message($("perso-message"), niveau, texte);
    const reduire = async (fichier) => {
      const bmp = await createImageBitmap(fichier);
      const k = Math.min(1, 256 / Math.max(bmp.width, bmp.height));
      const c = document.createElement("canvas");
      c.width = Math.max(1, Math.round(bmp.width * k));
      c.height = Math.max(1, Math.round(bmp.height * k));
      c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
      return c.toDataURL(fichier.type === "image/jpeg" ? "image/jpeg" : "image/png", 0.85);
    };
    $("perso-ajouter").addEventListener("click", () => $("perso-fichier").click());
    $("perso-fichier").addEventListener("change", async (e) => {
      const avant = { ...perso };
      let ajoutees = 0;
      for (const f of e.target.files) {
        if (!["image/png", "image/jpeg", "image/webp"].includes(f.type)) { direImage("avertissement", `« ${f.name} » n'est pas une image PNG, JPG ou WebP : ignorée.`); continue; }
        if (Object.keys(perso).length >= MAX_IMAGES) { direImage("avertissement", `Limite de ${MAX_IMAGES} images atteinte.`); break; }
        try {
          let nom = f.name.replace(/\.[^.]+$/, "").trim().slice(0, 40) || "image", i = 2;
          const base = nom;
          while (Object.hasOwn(perso, nom)) nom = `${base} (${i++})`;
          perso[nom] = await reduire(f);
          ajoutees++;
        } catch (err) { direImage("erreur", `Lecture impossible de « ${f.name} ».`); }
      }
      e.target.value = "";
      if (!ajoutees) return;
      if (!garderPerso()) {
        perso = avant;
        direImage("erreur", "Le navigateur n'a pas de place pour garder ces images : effacez-en d'abord.");
        return;
      }
      direImage("succes", `${ajoutees} image(s) ajoutée(s) : choisissez-les dans la liste « Image » de chaque maillon.`);
      afficherMaillons(lireMaillons());
      apercu();
    });
    $("perso-effacer").addEventListener("click", () => {
      perso = {};
      try { localStorage.removeItem(CLE_IMAGES); } catch (err) { /* rien à effacer */ }
      direImage("info", "Mes images effacées de ce navigateur.");
      afficherMaillons(lireMaillons());
      apercu();
    });
    $("deux-cf").addEventListener("change", () => {
      let lignes = lireMaillons();
      if ($("deux-cf").checked) {
        if (!$("c2-nom").value.trim()) $("c2-nom").value = "Jeu J2";
      } else {
        const gardees = lignes.filter((m) => m.sens === "+" || m.sens === "-");
        if (gardees.length < lignes.length) messageFichier("info", `${lignes.length - gardees.length} maillon(s) propre(s) à la CF2 retiré(s).`);
        lignes = gardees;
        document.querySelector('input[name="cf-actif"][value="1"]').checked = true;
      }
      afficherMaillons(lignes); // les listes « Sens » changent d'options
      colonnesThermiques();
      $("resultats").hidden = true;
      App.majBlocs();
      apercu();
    });
    for (const r of document.querySelectorAll('input[name="cf-actif"]')) {
      r.addEventListener("change", () => { $("resultats").hidden = true; App.majBlocs(); });
    }
    $("opt-aller").addEventListener("click", () => App.afficherPage("repartir"));
    $("guide-ouvrir").addEventListener("click", () => modeGuide(true, 0));
    $("guide-quitter").addEventListener("click", () => modeGuide(false));
    for (const b of document.querySelectorAll("#page-analyser .js-precedent")) b.addEventListener("click", () => allerEtape(guide.etape - 1));
    for (const b of document.querySelectorAll("#page-analyser .js-suivant")) b.addEventListener("click", () => allerEtape(guide.etape + 1));
    $("guide-vers-dossier").addEventListener("click", () => App.afficherPage("dossier"));
    $("guide-enregistrer").addEventListener("click", enregistrer);
    majGuide();
    $("thermique").addEventListener("change", () => { colonnesThermiques(); apercuDiffere(); });
    $("r-mode").addEventListener("change", colonnesThermiques);
    $("representation").addEventListener("change", colonnesThermiques); // l'aperçu suit (écouteur « change » de la page)
    $("page-analyser").addEventListener("input", apercuDiffere);
    $("page-analyser").addEventListener("change", apercuDiffere);
    // collage de cellules d'un tableur dans le tableau des maillons
    $("maillons").addEventListener("paste", (e) => {
      const texte = e.clipboardData.getData("text");
      if (!/[\t\n]/.test(texte.trim())) return; // une seule cellule : collage normal
      const nouvelles = collage(texte);
      if (!nouvelles.length) return;
      e.preventDefault();
      const tr = e.target.closest("tr"), debut = tr ? [...tr.parentNode.children].indexOf(tr) : 0;
      const lignes = lireMaillons();
      nouvelles.forEach((l, i) => { lignes[debut + i] = { ...(lignes[debut + i] || MAILLON_VIDE), iso: "", ...l }; });
      afficherMaillons(lignes);
      apercuDiffere();
      App.message($("coller-message"), "succes", `${nouvelles.length} ligne(s) collée(s) depuis le tableur (à partir de la ligne ${debut + 1}). Ctrl+Z pour annuler.`);
    });
    $("copier-lien").addEventListener("click", copierLien);
    window.addEventListener("hashchange", ouvrirLien); // lien collé dans la barre d'adresse de la page déjà ouverte
    document.addEventListener("themechange", () => { if (pont) apercu(); }); // silhouettes du schéma aux couleurs du thème
    // texte de l'étude (données, résultats, démarche) : fabriqué par le calcul, pour le bloc-notes et pour une IA
    const texteDeLEtude = (ia) => {
      const r = JSON.parse(ia ? pont.texteIA(JSON.stringify(lireProbleme())) : pont.texteEtude(JSON.stringify(lireProbleme())));
      if (r.erreur) throw new Error(r.erreur);
      return r.texte;
    };
    $("export-txt").addEventListener("click", () => {
      const b = $("export-txt");
      try {
        App.telecharger(nomFichier() + ".txt", texteDeLEtude(false), "text/plain;charset=utf-8");
        App.retour(b, true, "Enregistré", "");
      } catch (e) {
        App.confirmer(b, false, "", "Export impossible", "Export impossible : " + e.message);
      }
    });
    // « Demander à une IA » : copie la consigne et l'étude ; rien n'est envoyé, l'utilisateur colle lui-même
    const iaBouton = $("ia-bouton"), iaPanneau = $("ia-panneau");
    iaBouton.disabled = false;
    const iaFermer = () => { iaPanneau.hidden = true; iaBouton.setAttribute("aria-expanded", "false"); };
    iaBouton.addEventListener("click", async () => {
      iaBouton.disabled = true;
      // le texte se prépare après le clic (30 ms pour afficher l'état) mais la copie est demandée dans le clic même
      const texte = new Promise((r) => setTimeout(r, 30)).then(() => texteDeLEtude(true));
      let ok = false, erreur = "";
      try { ok = await App.copierDiffere(texte); } catch (e) { erreur = e.message; }
      iaBouton.disabled = false;
      App.confirmer(null, ok, "Étude copiée", erreur ? "Impossible : " + erreur : "Copie impossible",
        ok ? "Étude copiée : collez-la dans l'IA (Ctrl+V)." : (erreur ? "Impossible : " + erreur : "Copie refusée par le navigateur."));
      iaPanneau.hidden = !ok;
      iaBouton.setAttribute("aria-expanded", String(ok));
    });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") iaFermer(); });
    document.addEventListener("click", (e) => { if (!$("ia-flottant").contains(e.target)) iaFermer(); });
    $("export-excel").addEventListener("click", async () => {
      const b = $("export-excel"), etat = $("export-excel-etat");
      b.disabled = true;
      etat.textContent = "Préparation du classeur (la première fois, le module Excel se charge : quelques secondes)…";
      try {
        await App.pip("openpyxl>=3.1,<4"); // absent de Pyodide : pris sur PyPI, comme plotly au démarrage
        const r = JSON.parse(pont.exporterExcel(JSON.stringify(lireProbleme())));
        if (r.erreur) { etat.textContent = r.erreur; return; }
        App.telecharger(nomFichier() + ".xlsx", Uint8Array.from(atob(r.base64), (c) => c.charCodeAt(0)), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
        etat.textContent = `Classeur enregistré : ${nomFichier()}.xlsx (dossier des téléchargements).`;
      } catch (e) {
        etat.textContent = "Export impossible : " + e;
      } finally {
        b.disabled = false;
      }
    });
    let reprise = false;
    try {
      const gardee = etudeGardee();
      if (gardee) {
        etude = { cartouche: gardee.cartouche || null, revisions: [] };
        poserProbleme(gardee);
        messageFichier("info", "Dernière étude reprise (gardée dans ce navigateur). Pour repartir du cas de base : choisissez « Cas de base » dans la liste, puis « Charger cet exemple ».");
        reprise = true;
      }
    } catch (e) { reprise = false; } // étude gardée illisible : on repart du cas de base
    if (!reprise) poserProbleme(CAS_DE_BASE);
    colonnesThermiques();
    apercu();
  }

  // Points d'entrée pour les autres pages (exemples, assistant d'ajustement) : elles alimentent la chaîne de cette page.
  App.analyser = {
    guide: modeGuide, // modeGuide(true, 0) : parcours guidé à l'étape 1 ; modeGuide(false) : mode expert
    ouvrirFichier: () => $("fichier").click(),
    // Remplace l'étude par un problème (dict du pont) et lance le calcul.
    charger(probleme) {
      etude = { cartouche: null, revisions: [] };
      poserProbleme(probleme);
      $("resultats").hidden = true;
      App.message($("erreur"), "erreur", "");
      messageFichier("info", "");
      apercu();
      calculer();
    },
    // Ajoute des maillons (dicts du pont) à la suite de ceux de la chaîne.
    ajouterMaillons(liste) {
      afficherMaillons([...lireMaillons(), ...liste.map(versLigne)]);
      $("resultats").hidden = true;
      apercu();
    },
    // Étude complète (avec sa deuxième cote condition éventuelle) pour « Mes études » ; ouvrirEtude la remplace, sans la recalculer.
    etudeComplete: lireCommun,
    ouvrirEtude(probleme) {
      etude = { cartouche: probleme.cartouche || null, revisions: [] };
      poserProbleme(probleme);
      $("resultats").hidden = true;
      App.message($("erreur"), "erreur", "");
      messageFichier("info", "");
      apercu();
    },
    ouvrirLien, // appelé une fois toutes les pages prêtes : un lien « #etude=… » ouvre l'étude partagée
    noms: () => lignesCF(cfActive()).map((m) => m.nom),
    tref: () => nombre($("r-tref").value) || 20,
    probleme: lireProbleme,
    // cartouche et révisions de l'étude (reportés dans le fichier enregistré et dans le dossier de validation)
    cartouche: () => etude.cartouche,
    poserCartouche(c) { etude.cartouche = c && Object.keys(c).length ? c : null; },
    revisions: () => etude.revisions,
    limites: () => (cfActive() === 2 ? [$("c2-jmin").value, $("c2-jmax").value] : [$("c-jmin").value, $("c-jmax").value]),
    chaines: () => { const c = lireCommun(); return c.condition2 !== undefined ? [chaineCF(c, 1), chaineCF(c, 2)] : [chaineCF(c, 1)]; },
    poserLimites(jmin, jmax) {
      $(cfActive() === 2 ? "c2-jmin" : "c-jmin").value = jmin;
      $(cfActive() === 2 ? "c2-jmax" : "c-jmax").value = jmax;
      $("resultats").hidden = true;
      apercu();
    },
    // « Appliquer à l'étude » : remplace les écarts de chaque maillon (la désignation ISO est vidée).
    appliquerEcarts(ecarts) {
      const lignes = [...document.querySelectorAll("#maillons tbody tr")], indices = indicesCF(cfActive());
      indices.map((k) => lignes[k]).forEach((tr, i) => { // les écarts sont ceux de la chaîne active : ses maillons, dans l'ordre
        if (!ecarts[i]) return;
        tr.querySelector(".m-iso").value = "";
        // valeurs exactes, sans arrondi : un jeu qui tombe pile sur une limite deviendrait « non conforme » d'un millionième
        tr.querySelector(".m-es").value = String(ecarts[i].es);
        tr.querySelector(".m-ei").value = String(ecarts[i].ei);
      });
      $("resultats").hidden = true;
      apercu();
    },
  };

  App.enregistrerPage({ id: "analyser", titre: "Étude", apres });
})();
