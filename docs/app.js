"use strict";
// Page « Chaînes de cotes 1D » : l'interface est ici, le calcul est le Python de l'application de bureau (pont.py),
// exécuté dans le navigateur par Pyodide.

const $ = (id) => document.getElementById(id);
let pont = null; // module Python « pont », prêt après le chargement
let figures = [];
let ongletActif = null;

// ---------- saisie ----------

const MAILLON_VIDE = { nom: "", sens: "+", cote: "", iso: "", es: "", ei: "", loi: "normale" };

function champ(valeur, classe, type) {
  const el = document.createElement("input");
  el.type = "text";
  el.value = valeur ?? "";
  el.className = classe;
  if (type === "nombre") el.inputMode = "decimal";
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

function ligneMaillon(m, numero) {
  const tr = document.createElement("tr");
  const cellules = [
    champ(m.nom, "m-nom"),
    liste("m-sens", [["+", "+ (agrandit)"], ["-", "− (réduit)"]], m.sens === "-" ? "-" : "+"),
    champ(m.cote, "m-cote", "nombre"),
    champ(m.iso, "m-iso"),
    champ(m.es, "m-es", "nombre"),
    champ(m.ei, "m-ei", "nombre"),
    liste("m-loi", [["normale", "normale"], ["uniforme", "uniforme"], ["triangulaire", "triangulaire"]], m.loi || "normale"),
  ];
  const noms = ["Nom", "Sens", "Cote nominale", "Désignation ISO 286", "Écart supérieur ES", "Écart inférieur EI", "Loi"];
  cellules.forEach((el, i) => {
    el.setAttribute("aria-label", `${noms[i]}, maillon ${numero}`);
    const td = document.createElement("td");
    td.append(el);
    tr.append(td);
  });
  const sup = document.createElement("button");
  sup.type = "button";
  sup.textContent = "✕";
  sup.setAttribute("aria-label", `Supprimer le maillon ${numero}`);
  sup.addEventListener("click", () => {
    const lignes = lireMaillons();
    lignes.splice(numero - 1, 1);
    afficherMaillons(lignes);
  });
  const td = document.createElement("td");
  td.append(sup);
  tr.append(td);
  return tr;
}

function afficherMaillons(maillons) {
  const corps = document.querySelector("#maillons tbody");
  corps.replaceChildren(...maillons.map((m, i) => ligneMaillon(m, i + 1)));
}

function lireMaillons() {
  return [...document.querySelectorAll("#maillons tbody tr")].map((tr) => ({
    nom: tr.querySelector(".m-nom").value,
    sens: tr.querySelector(".m-sens").value,
    cote: tr.querySelector(".m-cote").value,
    iso: tr.querySelector(".m-iso").value,
    es: tr.querySelector(".m-es").value,
    ei: tr.querySelector(".m-ei").value,
    loi: tr.querySelector(".m-loi").value,
  }));
}

// Un nombre écrit « 0,25 » ou « 0.25 » devient un nombre ; un texte qui n'en est pas un reste texte (le calcul le signalera).
function nombre(v) {
  if (v === null || v === undefined) return "";
  if (typeof v === "number") return v;
  const t = String(v).trim().replace(",", ".");
  if (t === "") return "";
  return /^[-+−]?\d*\.?\d+(e[-+]?\d+)?$/i.test(t) ? Number(t.replace("−", "-")) : String(v);
}

function lireProbleme() {
  const maillons = lireMaillons().map((m) => ({
    nom: m.nom, sens: m.sens, loi: m.loi, iso: m.iso.trim(),
    cote: nombre(m.cote), es: nombre(m.es), ei: nombre(m.ei),
  }));
  return {
    condition: { nom: $("c-nom").value, jmin: nombre($("c-jmin").value), jmax: nombre($("c-jmax").value) },
    reglages: { kSigma: nombre($("r-k").value), tref: nombre($("r-tref").value), tservice: nombre($("r-tserv").value) },
    maillons,
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
  afficherMaillons((p.maillons || []).map((m) => ({
    nom: m.nom ?? "", sens: m.sens, cote: m.cote ?? "", iso: m.iso ?? "",
    es: m.es ?? "", ei: m.ei ?? "", loi: m.loi ?? "normale",
  })));
}

// ---------- résultats ----------

function montrerErreur(texte) {
  const e = $("erreur");
  e.textContent = texte;
  e.hidden = !texte;
}

function afficherOnglet(id) {
  ongletActif = id;
  const f = figures.find((x) => x.id === id);
  for (const b of $("onglets").children) b.setAttribute("aria-selected", String(b.dataset.id === id));
  const layout = { ...f.fig.layout, autosize: true };
  delete layout.width;
  if (layout.title && layout.title.text) {
    // les titres Plotly ne passent pas à la ligne : sur un écran étroit le sous-titre serait coupé
    layout.title = { ...layout.title, text: layout.title.text.replaceAll(" | ", "<br>"), x: 0.01, xanchor: "left" };
    if (layout.title.text.includes("<br>")) layout.margin = { ...layout.margin, t: Math.max((layout.margin || {}).t || 0, 90) };
  }
  if (layout.showlegend !== false) {
    // légende sous le graphique : en haut, elle recouvrirait le sous-titre du titre (le schéma n'en a pas)
    layout.legend = { ...layout.legend, orientation: "h", x: 0, xanchor: "left", y: -0.28, yanchor: "top" };
    layout.margin = { ...layout.margin, b: Math.max((layout.margin || {}).b || 0, 130) };
  }
  Plotly.react("graphique", f.fig.data, layout, { responsive: true, displaylogo: false });
  $("legende-graphique").textContent = f.legende;
}

function afficherResultats(r) {
  $("resultats").hidden = false;
  const v = $("verdict");
  v.className = "message " + r.niveau;
  v.textContent = r.titre;
  $("conseil").textContent = r.conseil ? "À faire : " + r.conseil : "";
  $("metriques").replaceChildren(...r.metriques.map(([nom, valeur]) => {
    const d = document.createElement("div");
    d.className = "metrique";
    const a = document.createElement("span"), b = document.createElement("strong");
    a.textContent = nom;
    b.textContent = valeur;
    d.append(a, b);
    return d;
  }));
  $("avertissements").replaceChildren(...r.avertissements.map((t) => {
    const li = document.createElement("li");
    li.textContent = t;
    return li;
  }));
  figures = r.figures;
  $("onglets").replaceChildren(...figures.map((f) => {
    const b = document.createElement("button");
    b.type = "button";
    b.setAttribute("role", "tab");
    b.dataset.id = f.id;
    b.textContent = f.titre;
    b.addEventListener("click", () => afficherOnglet(f.id));
    return b;
  }));
  afficherOnglet(figures.some((f) => f.id === ongletActif) ? ongletActif : figures[0].id);
}

function calculer() {
  montrerErreur("");
  $("calculer").disabled = true;
  $("etat").textContent = "Calcul en cours…";
  // laisse le navigateur afficher le message avant le calcul, qui occupe le processeur quelques secondes
  setTimeout(() => {
    try {
      const r = JSON.parse(pont.calculer(JSON.stringify(lireProbleme())));
      if (r.erreur) {
        $("resultats").hidden = true;
        montrerErreur(r.erreur);
      } else {
        afficherResultats(r);
      }
      $("etat").textContent = r.erreur ? "Corrigez la saisie signalée." : "Calcul terminé.";
    } catch (e) {
      montrerErreur("Erreur inattendue : " + e);
      $("etat").textContent = "Le calcul a échoué.";
    } finally {
      $("calculer").disabled = false;
    }
  }, 30);
}

// ---------- démarrage ----------

async function demarrer() {
  try {
    const pyodide = await loadPyodide();
    $("etat").textContent = "Chargement de numpy et scipy…";
    await pyodide.loadPackage(["numpy", "scipy", "micropip"]);
    $("etat").textContent = "Chargement de plotly…";
    await pyodide.pyimport("micropip").install("plotly>=5.20,<7");
    $("etat").textContent = "Chargement du calcul…";
    const archive = await (await fetch("chainecotes.zip")).arrayBuffer();
    pyodide.unpackArchive(archive, "zip", { extractDir: "/app" });
    pyodide.FS.writeFile("/app/pont.py", await (await fetch("pont.py")).text());
    pyodide.runPython("import sys; sys.path.insert(0, '/app')");
    pont = pyodide.pyimport("pont");
  } catch (e) {
    $("etat").className = "message erreur";
    $("etat").textContent = "Le calcul n'a pas pu se charger (connexion Internet nécessaire la première fois) : " + e;
    return;
  }
  const exemples = JSON.parse(pont.exemples());
  const choix = $("exemple");
  choix.replaceChildren(...exemples.map((e) => {
    const o = document.createElement("option");
    o.value = e.id;
    o.textContent = e.titre;
    o.title = e.description || "";
    return o;
  }));
  const decrire = () => { $("description").textContent = (exemples.find((e) => e.id === choix.value) || {}).description || ""; };
  choix.addEventListener("change", decrire);
  $("charger").addEventListener("click", () => {
    poserProbleme(JSON.parse(pont.charger(choix.value)));
    $("resultats").hidden = true;
    montrerErreur("");
    calculer();
  });
  decrire();
  for (const id of ["exemple", "charger", "calculer"]) $(id).disabled = false;
  $("etat").textContent = "Prêt. Choisissez un exemple ou saisissez votre chaîne, puis cliquez sur Calculer.";
}

$("ajouter").addEventListener("click", () => afficherMaillons([...lireMaillons(), { ...MAILLON_VIDE }]));
$("calculer").addEventListener("click", calculer);
afficherMaillons([{ ...MAILLON_VIDE, nom: "Maillon 1" }, { ...MAILLON_VIDE, nom: "Maillon 2", sens: "-" }]);
demarrer();
