"use strict";
// « Mes études » : copies nommées des études, gardées dans ce navigateur (localStorage), avec favoris, renommer,
// dupliquer, supprimer, export et import JSON. Elles alimentent le comparatif (page Comparer) et se rouvrent dans la page Étude.
// Les fonctions de contrôle (lireImport, nettoyerProbleme, fusionner) ne touchent pas à la page : elles se testent sous Node.

(() => {
  const CLE = "chainecotes.etudes";
  const FORMAT = "chaines-de-cotes-etudes";
  const VERSION = 1; // version du fichier ; schema_version suit le même numéro (absent = 1)
  const MAX_ETUDES = 30, MAX_CARACTERES = 100000, MAX_FICHIER = 3e6, MAX_MAILLONS = 200, MAX_NOM = 60;
  const CLES_PROBLEME = ["condition", "reglages", "maillons", "condition2", "cartouche"];

  // ---------- contrôle des données (aussi pour un fichier importé) ----------

  const objet = (x) => x !== null && typeof x === "object" && !Array.isArray(x);

  // Une clé « __proto__ » n'a rien à faire dans une étude : refus net (pas de pollution de prototype plus tard).
  function aProto(x, profondeur = 0) {
    if (profondeur > 12 || x === null || typeof x !== "object") return false;
    if (Array.isArray(x)) return x.some((v) => aProto(v, profondeur + 1));
    return Object.keys(x).some((k) => k === "__proto__" || aProto(x[k], profondeur + 1));
  }

  // Problème d'étude (condition, reglages, maillons, condition2, cartouche) copié sans rien d'autre ; null s'il est inutilisable.
  function nettoyerProbleme(p) {
    if (!objet(p) || !objet(p.condition) || !Array.isArray(p.maillons)) return null;
    if (p.maillons.length < 1 || p.maillons.length > MAX_MAILLONS || !p.maillons.every(objet)) return null;
    if (aProto(p)) return null;
    const copie = {};
    for (const k of CLES_PROBLEME) if (p[k] !== undefined) copie[k] = p[k];
    const texte = JSON.stringify(copie);
    return texte.length > MAX_CARACTERES ? null : JSON.parse(texte);
  }

  const nomPropre = (n) => String(n ?? "").replace(/\s+/g, " ").trim().slice(0, MAX_NOM);
  const idValide = (id) => typeof id === "string" && /^[A-Za-z0-9_-]{1,40}$/.test(id);
  const dateValide = (t) => (typeof t === "number" && Number.isFinite(t) && t > 0 ? t : 0);

  // Une copie complète {id, nom, cree, modif, favori, probleme} ; null si elle est abîmée.
  function nettoyerCopie(e) {
    if (!objet(e) || !idValide(e.id)) return null;
    const probleme = nettoyerProbleme(e.probleme), nom = nomPropre(e.nom);
    if (!probleme || !nom) return null;
    const cree = dateValide(e.cree);
    return { id: e.id, nom, cree, modif: dateValide(e.modif) || cree, favori: e.favori === true, probleme };
  }

  // Fichier d'export → {copies, ignorees} ou {erreur}. Version absente = 1 ; format plus récent refusé ; clés inconnues ignorées.
  function lireImport(texte) {
    if (typeof texte !== "string" || texte.length > MAX_FICHIER) return { erreur: "Fichier trop gros (3 Mo au plus)." };
    let d;
    try { d = JSON.parse(texte); } catch (e) { return { erreur: "Ce fichier n'est pas un fichier JSON lisible." }; }
    if (!objet(d) || d.format !== FORMAT) return { erreur: "Ce n'est pas un export « Mes études » de Chaînes de cotes 1D." };
    const schema = d.schema_version === undefined ? 1 : d.schema_version;
    if (!Number.isInteger(d.version) || d.version > VERSION || !Number.isInteger(schema) || schema > VERSION) {
      return { erreur: "Fichier d'une version plus récente de Chaînes de cotes 1D : actualisez le site (bouton « Actualiser le site » du pied de page) puis recommencez." };
    }
    if (!Array.isArray(d.copies)) return { erreur: "Le fichier ne contient aucune étude." };
    const copies = d.copies.map(nettoyerCopie).filter(Boolean);
    return { copies, ignorees: d.copies.length - copies.length };
  }

  // Ajoute les copies importées à celles qui existent : même id = la plus récente gagne ; au plus MAX_ETUDES (les plus récentes).
  function fusionner(existantes, importees) {
    const parId = new Map(existantes.map((e) => [e.id, e]));
    let ajoutees = 0, remplacees = 0;
    for (const e of importees) {
      const avant = parId.get(e.id);
      if (!avant) { parId.set(e.id, e); ajoutees++; } else if (e.modif > avant.modif) { parId.set(e.id, e); remplacees++; }
    }
    const toutes = [...parId.values()].sort((a, b) => b.modif - a.modif);
    return { copies: toutes.slice(0, MAX_ETUDES), ajoutees, remplacees, coupees: Math.max(0, toutes.length - MAX_ETUDES) };
  }

  if (typeof App === "undefined") { // chargé sous Node : seulement les contrôles
    if (typeof module !== "undefined") module.exports = { lireImport, nettoyerProbleme, nettoyerCopie, fusionner, MAX_ETUDES };
    return;
  }

  // ---------- stockage (localStorage abîmé ou absent : la page reste utilisable) ----------

  let abime = false; // le stockage contient quelque chose d'illisible : la page le dit, et en garde une copie
  function lire() {
    try {
      const brut = localStorage.getItem(CLE) || "[]";
      let l;
      try { l = JSON.parse(brut); } catch (e) {
        abime = true;
        try { localStorage.setItem(CLE + ".abimee", brut); } catch (e2) { /* plein : tant pis */ } // avant qu'un enregistrement ne l'écrase
        return [];
      }
      return (Array.isArray(l) ? l : []).map(nettoyerCopie).filter(Boolean).slice(0, MAX_ETUDES);
    } catch (e) { return []; }
  }
  function ecrire(liste) {
    try { localStorage.setItem(CLE, JSON.stringify(liste)); } catch (e) { return false; } // plein ou interdit
    document.dispatchEvent(new Event("etudes:maj")); // le comparatif relit sa liste
    return true;
  }
  const nouvelId = () => "e" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);

  // Nom libre : « Jeu J », puis « Jeu J (2) »…
  function nomLibre(base, liste, sauf = null) {
    const pris = new Set(liste.filter((e) => e.id !== sauf).map((e) => e.nom));
    const b = nomPropre(base) || "Étude";
    if (!pris.has(b)) return b;
    for (let i = 2; ; i++) {
      const n = `${b.slice(0, MAX_NOM - 6)} (${i})`;
      if (!pris.has(n)) return n;
    }
  }

  const { $ } = App;
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

  // ---------- API pour les autres pages ----------

  const api = {
    liste: lire,
    obtenir: (id) => lire().find((e) => e.id === id) || null,
    // Enregistre un problème (étude complète, avec condition2 éventuelle) ; rend la copie, ou null si le stockage est refusé.
    ajouter(probleme, nom) {
      const p = nettoyerProbleme(probleme);
      if (!p) return { erreur: "Cette étude est vide ou trop grosse pour être gardée." };
      const liste = lire();
      if (liste.length >= MAX_ETUDES) return { erreur: `Mes études est plein (${MAX_ETUDES} au plus) : supprimez une étude d'abord.` };
      const t = Date.now();
      const copie = { id: nouvelId(), nom: nomLibre(nom || p.condition.nom || "Étude", liste), cree: t, modif: t, favori: false, probleme: p };
      return ecrire([copie, ...liste]) ? { copie } : { erreur: "Le navigateur refuse de garder l'étude (stockage plein ou interdit). Exportez vos études en JSON." };
    },
    lireImport,
    nettoyerProbleme,
  };
  App.etudes = api;

  // ---------- interface : section de l'accueil ----------

  const resume = (e) => {
    const p = e.probleme, n = p.maillons.length;
    const jeux = p.condition2 ? `2 cotes condition (${p.condition.nom || "CF1"}, ${p.condition2.nom || "CF2"})` : `cote condition « ${p.condition.nom || "sans nom"} »`;
    return `${jeux}, ${n} maillon${n > 1 ? "s" : ""} · ${new Date(e.modif).toLocaleDateString("fr-FR")}`;
  };

  let zoneMessage = null, zoneListe = null, ouverte = null; // ouverte : id de la ligne en cours de renommage

  const dire = (niveau, texte) => { if (zoneMessage) App.message(zoneMessage, niveau, texte); };

  // Confirmation en ligne (pas de boîte de dialogue) : le message et ses deux boutons remplacent les actions de la ligne.
  function demander(li, texte, libelleOui, siOui) {
    const actions = li.querySelector(".etude-actions");
    const ancien = [...actions.childNodes];
    const retour = () => actions.replaceChildren(...ancien);
    actions.replaceChildren(
      el("span", { class: "legende", role: "status", texte }),
      el("button", { type: "button", class: "primaire petit", texte: libelleOui, onclick: siOui }),
      el("button", { type: "button", class: "secondaire petit", texte: "Annuler", onclick: retour }),
    );
    actions.querySelector("button").focus();
  }

  function changer(id, modif) {
    const liste = lire(), e = liste.find((x) => x.id === id);
    if (!e) return rendre();
    modif(e, liste);
    e.modif = Date.now();
    if (!ecrire(liste)) dire("erreur", "Le navigateur refuse de garder ce changement (stockage plein ou interdit).");
    rendre();
  }

  function ligne(e) {
    const li = el("li", { class: "etude", "data-id": e.id });
    const etoile = el("button", {
      type: "button", class: "favori secondaire petit", "aria-pressed": String(e.favori),
      "aria-label": (e.favori ? "Retirer des favoris : " : "Ajouter aux favoris : ") + e.nom, title: e.favori ? "Retirer des favoris" : "Ajouter aux favoris",
      texte: e.favori ? "★" : "☆", onclick: () => changer(e.id, (x) => { x.favori = !x.favori; }),
    });
    let tete;
    if (ouverte === e.id) { // renommage en ligne
      const champ = el("input", { type: "text", value: e.nom, maxlength: String(MAX_NOM), "aria-label": "Nouveau nom de " + e.nom });
      tete = el("form", { class: "etude-nom", onsubmit: (ev) => {
        ev.preventDefault();
        const nom = nomPropre(champ.value);
        if (!nom) return;
        ouverte = null;
        changer(e.id, (x, liste) => { x.nom = nomLibre(nom, liste, x.id); });
      } }, champ,
      el("button", { type: "submit", class: "primaire petit", texte: "Valider" }),
      el("button", { type: "button", class: "secondaire petit", texte: "Annuler", onclick: () => { ouverte = null; rendre(); } }));
    } else tete = el("strong", { texte: e.nom });
    const actions = el("div", { class: "etude-actions" },
      el("button", { type: "button", class: "secondaire petit", texte: "Ouvrir", "aria-label": "Ouvrir " + e.nom, onclick: () => {
        App.afficherPage("analyser");
        App.analyser.guide(false);
        App.analyser.ouvrirEtude(e.probleme);
        window.scrollTo(0, 0);
      } }),
      el("button", { type: "button", class: "secondaire petit", texte: "Comparer", "aria-label": "Ajouter au comparatif : " + e.nom, onclick: () => {
        if (!App.comparer || !App.comparer.ajouterEtude) return dire("erreur", "Le comparatif n'est pas encore prêt.");
        App.comparer.ajouterEtude(e);
        App.afficherPage("comparer");
      } }),
      el("button", { type: "button", class: "secondaire petit", texte: "Renommer", "aria-label": "Renommer " + e.nom, onclick: () => { ouverte = e.id; rendre(); } }),
      el("button", { type: "button", class: "secondaire petit", texte: "Dupliquer", "aria-label": "Dupliquer " + e.nom, onclick: () => {
        const r = api.ajouter(e.probleme, "Copie de " + e.nom);
        if (r.erreur) dire("erreur", r.erreur);
        else { dire("succes", `Copie créée : « ${r.copie.nom} ».`); rendre(); }
      } }),
      el("button", { type: "button", class: "secondaire petit", texte: "Supprimer", "aria-label": "Supprimer " + e.nom, onclick: () => {
        demander(li, `Supprimer « ${e.nom} » ?`, "Supprimer", () => { ecrire(lire().filter((x) => x.id !== e.id)); dire("succes", `« ${e.nom} » supprimée.`); rendre(); });
      } }),
    );
    li.append(el("div", { class: "etude-tete" }, etoile, tete), el("p", { class: "legende etude-resume", texte: resume(e) }), actions);
    return li;
  }

  function rendre() {
    if (!zoneListe) return;
    const liste = lire().sort((a, b) => Number(b.favori) - Number(a.favori) || b.modif - a.modif);
    if (abime && zoneMessage && zoneMessage.hidden) dire("avertissement", "Les études gardées dans ce navigateur sont illisibles (données abîmées) : une copie brute est conservée, et le prochain enregistrement repart de zéro.");
    if (!liste.length) {
      zoneListe.replaceChildren(el("p", { class: "legende", texte: "Aucune étude gardée pour l'instant. « Enregistrer l'étude en cours » la garde ici, dans ce navigateur, pour la rouvrir ou la comparer à d'autres." }));
      return;
    }
    zoneListe.replaceChildren(el("ul", { class: "etudes-liste" }, ...liste.map(ligne)));
    const champ = zoneListe.querySelector(".etude-nom input");
    if (champ) champ.focus();
  }

  function enregistrerEnCours(bouton) {
    const r = api.ajouter(App.analyser.etudeComplete(), null);
    if (r.erreur) { App.confirmer(bouton, false, "", "Enregistrement impossible", r.erreur); dire("erreur", r.erreur); return; }
    App.confirmer(bouton, true, "Enregistrée", "", `Étude gardée dans Mes études : « ${r.copie.nom} ».`);
    dire("succes", `Étude gardée dans Mes études : « ${r.copie.nom} ».`);
    rendre();
  }

  function exporter() {
    const liste = lire();
    if (!liste.length) return dire("info", "Rien à exporter : Mes études est vide.");
    const contenu = JSON.stringify({ format: FORMAT, version: VERSION, schema_version: VERSION, outil: "Chaînes de cotes 1D " + (document.getElementById("version")?.textContent || ""), copies: liste }, null, 1);
    App.telecharger("mes_etudes.json", contenu);
  }

  async function importer(fichier) {
    if (!fichier) return;
    const r = lireImport(await fichier.text());
    if (r.erreur) return dire("erreur", r.erreur);
    if (!r.copies.length) return dire("avertissement", "Aucune étude utilisable dans ce fichier.");
    const f = fusionner(lire(), r.copies);
    if (!ecrire(f.copies)) return dire("erreur", "Le navigateur refuse de garder les études importées (stockage plein ou interdit).");
    rendre();
    const notes = [];
    if (r.ignorees) notes.push(`${r.ignorees} entrée(s) abîmée(s) ignorée(s)`);
    if (f.coupees) notes.push(`${f.coupees} étude(s) en trop non gardées (${MAX_ETUDES} au plus)`);
    dire(notes.length ? "avertissement" : "succes", `${f.ajoutees} étude(s) ajoutée(s), ${f.remplacees} mise(s) à jour.` + (notes.length ? " " + notes.join(" ; ") + "." : ""));
  }

  function monter() {
    const hote = document.querySelector("#page-accueil .trois");
    if (!hote) return;
    const fichier = el("input", { type: "file", accept: ".json,application/json", hidden: true, "aria-label": "Fichier Mes études à importer" });
    fichier.addEventListener("change", async (e) => { await importer(e.target.files[0]); e.target.value = ""; });
    zoneMessage = el("p", { class: "message", role: "status", "aria-live": "polite", hidden: true });
    zoneListe = el("div", { class: "etudes-corps" });
    const bEnregistrer = el("button", { type: "button", class: "secondaire", texte: "Enregistrer dans Mes études", onclick: () => enregistrerEnCours(bEnregistrer) });
    const section = el("section", { class: "mes-etudes", id: "mes-etudes", "aria-labelledby": "mes-etudes-titre" },
      el("h3", { id: "mes-etudes-titre", texte: "Mes études" }),
      el("p", { class: "legende", texte: "Vos études, gardées dans ce navigateur (rien n'est envoyé sur Internet). Rouvrez-les, ou mettez-les côte à côte dans « Comparer »." }),
      el("div", { class: "ligne" }, bEnregistrer,
        el("button", { type: "button", class: "secondaire", texte: "Exporter Mes études (.json)", onclick: exporter }),
        el("button", { type: "button", class: "secondaire", texte: "Importer…", onclick: () => fichier.click() }), fichier),
      zoneMessage, zoneListe);
    hote.after(section);
    rendre();
    document.addEventListener("etudes:maj", rendre);
    // bouton de la page Étude
    const b = $("mes-etudes-enregistrer");
    if (b) b.addEventListener("click", () => enregistrerEnCours(b));
  }

  App.enregistrerPage({ id: "etudes", module: true, titre: "Mes études", apres: monter }); // module : pas de page à afficher
})();
