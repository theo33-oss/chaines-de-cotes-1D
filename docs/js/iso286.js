"use strict";
// Page « Tables ISO 286 » : calculatrice d'écarts, tableau des IT, écarts fondamentaux. Tout vient de pont.py.

(() => {
  const { $, nombre, fr } = App;
  const AUTRE = "autre";
  let pont = null;
  let donnees = null;

  function mode() {
    return document.querySelector('input[name="iso-mode"]:checked').value;
  }

  function designation() {
    if (mode() === "texte") return $("iso-designation").value;
    const c = $("iso-cote").value === AUTRE ? nombre($("iso-autre").value) : Number($("iso-cote").value);
    const lettre = $("iso-lettre").value, q = $("iso-qualite").value;
    return `${c} ${lettre}${q}`;
  }

  function lire() {
    $("iso-listes").hidden = mode() !== "listes";
    $("iso-texte").hidden = mode() !== "texte";
    $("iso-autre-bloc").hidden = $("iso-cote").value !== AUTRE;
    const r = JSON.parse(pont.iso286Lire(designation()));
    App.message($("iso-erreur"), "erreur", r.erreur || "");
    App.message($("iso-avertissement"), "avertissement", r.avertissement || "");
    $("iso-resultat").replaceChildren(...(r.valeurs || []).map((v) => {
      const art = document.createElement("article");
      art.className = "carte";
      art.append(App.titre(v.titre, "h4"), App.metriques(v.valeurs), App.legende(v.legende));
      return art;
    }));
  }

  // Les lettres proposées dépendent de la pièce : majuscules pour un alésage, minuscules pour un arbre.
  function lettres() {
    const alesage = $("iso-piece").value === "Alésage";
    const liste = alesage ? donnees.lettresAlesage : donnees.lettresArbre;
    App.remplir($("iso-lettre"), liste.map((l) => [l, l]), alesage ? "H" : "h");
  }

  function fondamentaux() {
    const t = $("iso-fpiece").value === "Arbre" ? donnees.arbre : donnees.alesage;
    const noms = Object.keys(t.colonnes);
    if (!noms.includes($("iso-fposition").value)) App.remplir($("iso-fposition"), noms.map((n) => [n, n]), $("iso-fpiece").value === "Arbre" ? "h" : "H");
    const n = $("iso-fposition").value;
    $("iso-fond").replaceChildren(App.matrice({ plages: t.plages, colonnes: t.colonnes }, [n]));
  }

  async function apres(p) {
    pont = p;
    donnees = JSON.parse(pont.iso286Donnees());
    App.remplir($("iso-cote"), [...donnees.cotesUsuelles.map((c) => [c, fr(c)]), [AUTRE, "Autre valeur…"]], 50);
    App.remplir($("iso-qualite"), donnees.qualites.map((q) => [q.q, q.texte]), 7);
    lettres();
    for (const id of ["iso-cote", "iso-autre", "iso-lettre", "iso-qualite", "iso-designation"]) $(id).addEventListener("input", lire);
    $("iso-piece").addEventListener("change", () => { lettres(); lire(); });
    for (const r of document.querySelectorAll('input[name="iso-mode"]')) r.addEventListener("change", lire);
    $("iso-it").replaceChildren(App.matrice(donnees.it, Object.keys(donnees.it.colonnes)));
    $("iso-fpiece").addEventListener("change", () => { $("iso-fposition").replaceChildren(); fondamentaux(); });
    $("iso-fposition").addEventListener("change", fondamentaux);
    fondamentaux();
    $("iso-delta").replaceChildren(App.matrice(donnees.delta, Object.keys(donnees.delta.colonnes)));
    $("iso-source").textContent = donnees.source;
    lire();
  }

  App.enregistrerPage({ id: "iso286", titre: "Tables ISO 286", apres });
})();
