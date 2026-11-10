"use strict";
// Page « Comparer » : l'étude en cours (A) contre le résultat de la répartition, un exemple ou un fichier (B).

(() => {
  const { $ } = App;
  let pont = null;
  let fichierB = null; // problème lu dans le fichier choisi : { nom, probleme }

  const source = () => document.querySelector('input[name="cp-source"]:checked').value;

  function majSource() {
    $("cp-repartition").hidden = source() !== "repartition";
    $("cp-exemple-bloc").hidden = source() !== "exemple";
    $("cp-fichier-bloc").hidden = source() !== "fichier";
  }

  // Problème du scénario B ; null (et message) s'il n'est pas disponible.
  function scenarioB() {
    if (source() === "repartition") {
      const p = App.repartition.dernier();
      if (!p) App.message($("cp-erreur"), "erreur", "Aucune répartition calculée : ouvrez la page « Répartir », cliquez sur « Calculer », puis revenez ici.");
      return p && { probleme: p, nom: "B (répartition)" };
    }
    if (source() === "exemple") return { probleme: JSON.parse(pont.charger($("cp-exemple").value)), nom: "B (exemple)" };
    if (!fichierB) App.message($("cp-erreur"), "erreur", "Choisissez un exemple ou ouvrez un fichier valide pour le scénario B.");
    return fichierB && { probleme: fichierB.probleme, nom: "B (fichier)" };
  }

  function comparer() {
    App.message($("cp-erreur"), "erreur", "");
    $("cp-resultat").hidden = true;
    const b = scenarioB();
    if (!b) return;
    $("cp-calculer").disabled = true;
    setTimeout(() => {
      try {
        const r = JSON.parse(pont.comparer(JSON.stringify(App.analyser.probleme()), JSON.stringify(b.probleme), b.nom));
        if (r.erreur) return App.message($("cp-erreur"), "erreur", r.erreur);
        $("cp-resultat").hidden = false;
        $("cp-phrases").textContent = r.phrases.join(" ");
        $("cp-grandeurs").replaceChildren(App.tableau(r.grandeurs));
        $("cp-maillons").replaceChildren(App.tableau(r.maillons));
        App.tracer($("cp-fig"), r.fig);
        $("cp-legende").textContent = r.legende;
      } catch (e) {
        App.message($("cp-erreur"), "erreur", "Erreur inattendue : " + e);
      } finally {
        $("cp-calculer").disabled = false;
      }
    }, 30);
  }

  async function ouvrirFichier(f) {
    if (!f) return;
    const o = JSON.parse(pont.ouvrir(await f.text()));
    if (o.erreur) {
      fichierB = null;
      $("cp-fichier-nom").textContent = "";
      return App.message($("cp-erreur"), "erreur", o.erreur);
    }
    fichierB = { nom: f.name, probleme: o.probleme };
    $("cp-fichier-nom").textContent = "Fichier choisi : " + f.name;
    App.message($("cp-erreur"), "erreur", "");
  }

  async function apres(p) {
    pont = p;
    App.remplir($("cp-exemple"), JSON.parse(pont.exemples()).map((e) => [e.id, e.titre]));
    for (const r of document.querySelectorAll('input[name="cp-source"]')) r.addEventListener("change", majSource);
    $("cp-ouvrir").addEventListener("click", () => $("cp-fichier").click());
    $("cp-fichier").addEventListener("change", async (e) => { await ouvrirFichier(e.target.files[0]); e.target.value = ""; });
    $("cp-calculer").addEventListener("click", comparer);
    majSource();
  }

  App.enregistrerPage({ id: "comparer", titre: "Comparer", apres });
})();
