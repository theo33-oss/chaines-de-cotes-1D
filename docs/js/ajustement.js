"use strict";
// Page « Assistant d'ajustement » : ajustements ISO 286 classés selon la fonction souhaitée, jeux calculés par le pont.

(() => {
  const { $, nombre, fr } = App;
  const AUTRE = "autre";
  let pont = null;
  let cotes = [];
  let borneMax = 3150;
  let courant = null; // dernier résultat du pont (pour « Utiliser dans la chaîne »)

  function cote() {
    return $("aj-cote").value === AUTRE ? nombre($("aj-autre").value) : Number($("aj-cote").value);
  }

  function afficher(choix = "") {
    const c = cote();
    $("aj-autre-bloc").hidden = $("aj-cote").value !== AUTRE;
    $("aj-message").hidden = true;
    if (typeof c !== "number" || !(c > 0) || c > borneMax) {
      courant = null;
      $("aj-resultat").hidden = true;
      App.message($("aj-erreur"), "erreur", `Cote nominale hors des tables ISO 286 : 0 < d ≤ ${fr(borneMax)} mm.`);
      return;
    }
    const r = JSON.parse(pont.ajustement(c, $("aj-fonction").value, $("aj-systeme").value, choix));
    courant = r.choisi ? { ...r, cote: c } : null;
    $("aj-resultat").hidden = !courant;
    if (r.erreur) App.message($("aj-erreur"), "erreur", r.erreur);
    else if (!r.choisi) App.message($("aj-erreur"), "info", "Aucun ajustement recommandé pour cette fonction à cette cote : essayez l'autre système.");
    else App.message($("aj-erreur"), "info", "");
    if (!courant) return;
    $("aj-candidats").replaceChildren(App.tableau(r.candidats));
    App.remplir($("aj-choix"), r.noms.map((n) => [n, n]), r.choisi.designation);
    $("aj-titre-detail").textContent = "Détail de " + r.choisi.designation;
    $("aj-pieces").replaceChildren(...r.choisi.pieces.map((p) => App.metriques(p)));
    $("aj-description").textContent = r.choisi.description;
    $("aj-usage").textContent = r.choisi.usage;
    App.message($("aj-avertissement"), "avertissement", r.choisi.avertissement);
    $("aj-jeux").replaceChildren(App.metriques(r.choisi.jeux));
    App.tracer($("aj-fig"), r.fig);
    $("aj-legende").textContent = r.legende;
    $("aj-nature").textContent = r.choisi.nature;
  }

  function utiliser() {
    if (!courant) return;
    const r = JSON.parse(pont.maillonsAjustement(courant.choisi.designation, courant.cote, JSON.stringify(App.analyser.noms()), App.analyser.tref()));
    if (r.erreur) {
      App.message($("aj-message"), "erreur", r.erreur);
      return;
    }
    App.analyser.ajouterMaillons(r.maillons);
    App.message($("aj-message"), "succes", `${courant.choisi.designation} ajouté à la chaîne (alésage en sens +, arbre en sens −). `
      + "Ouvrez la page Analyser : la chaîne doit se fermer, ajustez les autres maillons si besoin.");
  }

  async function apres(p) {
    pont = p;
    const d = JSON.parse(pont.ajustementFonctions());
    cotes = d.cotes;
    borneMax = d.borneMax;
    App.remplir($("aj-cote"), [...cotes.map((c) => [c, fr(c)]), [AUTRE, "Autre valeur…"]], 50);
    const codes = Object.keys(d.fonctions);
    App.remplir($("aj-fonction"), codes.map((k) => [k, d.fonctions[k]]), codes[2]);
    for (const id of ["aj-cote", "aj-autre", "aj-fonction", "aj-systeme"]) $(id).addEventListener("input", () => afficher());
    $("aj-choix").addEventListener("change", (e) => afficher(e.target.value));
    $("aj-utiliser").addEventListener("click", utiliser);
    afficher();
  }

  App.enregistrerPage({ id: "ajustement", titre: "Ajustements", apres });
})();
