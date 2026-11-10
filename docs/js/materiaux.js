"use strict";
// Page « Matériaux et dilatation » : tableau filtrable, calculatrice α moyen et courbe de dilatation.

(() => {
  const { $, nombre } = App;
  let pont = null;

  function tableau() {
    const familles = [...document.querySelectorAll("#mat-familles input:checked")].map((c) => c.value);
    const r = JSON.parse(pont.materiauxTableau($("mat-recherche").value, JSON.stringify(familles)));
    $("mat-compte").textContent = `${r.tableau.lignes.length} matériau(x) sur ${r.total}.`;
    $("mat-tableau").replaceChildren(r.tableau.lignes.length ? App.tableau(r.tableau)
      : Object.assign(document.createElement("p"), { className: "message info", textContent: "Aucun matériau ne correspond : essayez moins de mots ou retirez une catégorie." }));
    return r;
  }

  function calculatrice() {
    const tref = nombre($("mat-tref").value), t = nombre($("mat-t").value);
    if (typeof tref !== "number" || typeof t !== "number") {
      App.message($("mat-erreur"), "erreur", "Tref et T de service doivent être des nombres.");
      return;
    }
    const r = JSON.parse(pont.dilatation($("mat-nom").value, tref, t));
    App.message($("mat-erreur"), "erreur", r.erreur || "");
    if (r.erreur) return;
    $("mat-metriques").replaceChildren(App.metriques(r.metriques));
    $("mat-messages").replaceChildren(...r.messages.map((m) => Object.assign(document.createElement("p"), { className: "message " + m.niveau, textContent: m.texte })));
    App.tracer($("mat-fig"), r.fig);
    $("mat-legende").textContent = r.legende;
  }

  async function apres(p) {
    pont = p;
    const r = tableau();
    $("mat-familles").replaceChildren(...r.familles.map((f) => {
      const l = document.createElement("label");
      l.className = "case";
      const c = Object.assign(document.createElement("input"), { type: "checkbox", value: f });
      c.addEventListener("change", tableau);
      l.append(c, document.createTextNode(" " + f));
      return l;
    }));
    $("mat-recherche").addEventListener("input", tableau);
    const noms = JSON.parse(pont.materiaux());
    App.remplir($("mat-nom"), noms.map((n) => [n, n]), noms.includes("Acier C45") ? "Acier C45" : noms[0]);
    for (const id of ["mat-nom", "mat-tref", "mat-t"]) $(id).addEventListener("input", calculatrice);
    const s = JSON.parse(pont.materiauxSources());
    $("mat-sources").append(App.titre("Sources"), App.tableau(s.sources), App.titre("Courbes de dilatation du classeur"), App.tableau(s.courbes),
      App.legende("Une courbe « recalée » est celle d'un matériau voisin, mise à l'échelle pour redonner l'α du tableau. "
        + "Au-delà des points d'une courbe, la déformation est extrapolée linéairement : la zone est grisée."));
    calculatrice();
  }

  App.enregistrerPage({ id: "materiaux", titre: "Matériaux", apres });
})();
