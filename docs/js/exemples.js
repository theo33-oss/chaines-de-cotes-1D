"use strict";
// Page « Bibliothèque d'exemples » : une carte par exemple (maillons, cote condition, pire des cas, schéma).

(() => {
  const { $ } = App;
  let pont = null;

  function carte(c) {
    const art = document.createElement("article");
    art.className = "carte";
    art.append(App.titre(c.titre), Object.assign(document.createElement("p"), { textContent: c.description }));
    if (c.source) art.append(App.legende("Source : " + c.source));
    if (c.methodologie.length) {
      const d = document.createElement("details");
      d.append(Object.assign(document.createElement("summary"), { textContent: "Méthodologie : " + c.titre }));
      const ol = document.createElement("ol");
      for (const e of c.methodologie) ol.append(Object.assign(document.createElement("li"), { textContent: e }));
      d.append(ol);
      art.append(d);
    }
    const cond = document.createElement("p");
    cond.innerHTML = "<strong>Cote condition</strong> : ";
    cond.append(document.createTextNode(c.condition));
    art.append(cond, App.tableau(c.maillons));
    if (c.erreur) {
      const m = document.createElement("p");
      App.message(m, "avertissement", "Aperçu impossible : " + c.erreur);
      art.append(m);
    } else {
      const m = document.createElement("p");
      App.message(m, c.pireCas.ok ? "succes" : "erreur",
        c.pireCas.ok ? "Conforme au pire des cas." : "Non conforme au pire des cas : ouvrez l'exemple pour voir le calcul statistique.");
      art.append(App.metriques([["Jeu mini (pire cas)", c.pireCas.mini], ["Jeu maxi (pire cas)", c.pireCas.maxi]]), m);
    }
    // schéma construit à l'ouverture : une figure par carte alourdirait la page
    const schema = document.createElement("details");
    schema.append(Object.assign(document.createElement("summary"), { textContent: "Schéma : " + c.titre }));
    const fig = document.createElement("div");
    fig.className = "figure";
    const leg = App.legende("");
    schema.append(fig, leg);
    schema.addEventListener("toggle", () => {
      if (!schema.open || fig.dataset.fait) return;
      fig.dataset.fait = "1";
      const s = JSON.parse(pont.schemaExemple(c.id));
      App.tracer(fig, s.fig);
      leg.textContent = s.legende;
    });
    art.append(schema);
    const b = document.createElement("button");
    b.type = "button";
    b.className = "primaire";
    b.textContent = "Ouvrir dans Analyser";
    b.addEventListener("click", () => {
      App.afficherPage("analyser");
      App.analyser.charger(JSON.parse(pont.charger(c.id)));
      window.scrollTo(0, 0);
    });
    art.append(b);
    return art;
  }

  async function apres(p) {
    pont = p;
    $("exemples-liste").replaceChildren(...JSON.parse(pont.cartes()).map(carte));
  }

  App.enregistrerPage({ id: "exemples", titre: "Exemples", apres });
})();
