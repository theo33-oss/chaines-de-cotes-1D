"use strict";
// Page « Mécanisme » : plusieurs chaînes d'un même assemblage, calculées ensemble (services/mecanisme.py du bureau).

(() => {
  const { $, nombre } = App;
  const MAX_CHAINES = 50;
  const TIRAGES = [20000, 50000, 100000];
  let pont = null;
  let chaines = []; // [{ id, probleme }]
  let suivant = 1;
  let csv = "";

  function dire(niveau, texte) {
    App.message($("mc-message"), niveau, texte);
  }

  // Nom de cote condition qui n'existe pas encore : « Jeu J », puis « Jeu J (2) », « Jeu J (3) »…
  function nomLibre(nom, sauf) {
    const pris = new Set(chaines.filter((c) => c.id !== sauf).map((c) => c.probleme.condition.nom));
    let candidat = nom, i = 2;
    while (pris.has(candidat)) candidat = `${nom} (${i++})`;
    return candidat;
  }

  // Ajoute des copies de problèmes ; renvoie un message si la limite est atteinte (les premières sont ajoutées).
  function ajouter(problemes) {
    for (const p of problemes) {
      if (chaines.length >= MAX_CHAINES) return `Limite de ${MAX_CHAINES} chaînes atteinte : les chaînes suivantes n'ont pas été ajoutées.`;
      const c = structuredClone(p);
      c.condition = c.condition || {};
      c.condition.nom = nomLibre(c.condition.nom || `Chaîne ${chaines.length + 1}`);
      chaines.push({ id: suivant++, probleme: c });
    }
    return null;
  }

  function liste() {
    $("mc-resultat").hidden = true; // le mécanisme a changé : le dernier calcul ne le décrit plus
    $("mc-titre-liste").textContent = `Chaînes (${chaines.length})`;
    if (!chaines.length) {
      $("mc-liste").replaceChildren(Object.assign(document.createElement("p"), { className: "message info", textContent: "Aucune chaîne : ajoutez un exemple, l'étude en cours ou un fichier." }));
      return;
    }
    $("mc-liste").replaceChildren(...chaines.map((c) => {
      const art = document.createElement("article");
      art.className = "carte";
      const l = document.createElement("label");
      l.textContent = "Nom de la chaîne";
      const nom = Object.assign(document.createElement("input"), { type: "text", value: c.probleme.condition.nom || "" });
      nom.addEventListener("change", () => { // le nom saisi devient celui de la cote condition, rendu unique et non vide
        c.probleme.condition.nom = nomLibre(nom.value.trim() || `Chaîne ${c.id}`, c.id);
        liste();
      });
      l.append(nom);
      const retirer = Object.assign(document.createElement("button"), { type: "button", className: "secondaire", textContent: "Retirer" });
      retirer.addEventListener("click", () => { chaines = chaines.filter((x) => x.id !== c.id); liste(); });
      const ouvrir = Object.assign(document.createElement("button"), { type: "button", className: "secondaire", textContent: "Ouvrir dans Analyser" });
      ouvrir.addEventListener("click", () => { App.afficherPage("analyser"); App.analyser.charger(structuredClone(c.probleme)); window.scrollTo(0, 0); });
      const ligne = document.createElement("div");
      ligne.className = "ligne";
      ligne.append(retirer, ouvrir);
      art.append(l, ligne, App.legende(`${c.probleme.maillons.length} maillon(s).`));
      return art;
    }));
  }

  async function ajouterFichiers(fichiers, remplacer) {
    const erreurs = [];
    const lus = [];
    for (const f of [...fichiers].slice(0, 20)) {
      const r = JSON.parse(pont.mecaImporter(await f.text()));
      if (r.erreur) erreurs.push(`${f.name} : ${r.erreur}`);
      else lus.push(r);
    }
    if (fichiers.length > 20) erreurs.push(`${fichiers.length - 20} fichier(s) ignoré(s) : au plus 20 à la fois.`);
    if (remplacer && lus.length) {
      chaines = [];
      $("mc-nom").value = lus[0].nom || "Mécanisme";
      lus.length = 1;
    }
    for (const m of lus) {
      const trop = ajouter(m.chaines);
      if (trop) erreurs.push(trop);
    }
    if (erreurs.length) dire("erreur", erreurs.join(" "));
    else if (lus.length) dire("succes", `${lus.length} fichier(s) lu(s), ${chaines.length} chaîne(s) dans le mécanisme.`);
    liste();
  }

  function mecanisme() {
    return { nom: $("mc-nom").value, chaines: chaines.map((c) => c.probleme) };
  }

  function enregistrer() {
    const r = JSON.parse(pont.mecaExporter(JSON.stringify(mecanisme())));
    if (r.erreur) return dire("erreur", r.erreur);
    App.telecharger("mecanisme.json", r.contenu);
    dire("succes", "Mécanisme enregistré : mecanisme.json (dossier des téléchargements).");
  }

  function afficherResultat(r) {
    $("mc-resultat").hidden = false;
    App.message($("mc-verdict"), r.niveau, r.phrase);
    $("mc-reduit").textContent = r.reduit;
    $("mc-metriques").replaceChildren(App.metriques(r.metriques));
    App.tracer($("mc-fig"), r.fig);
    $("mc-legende").textContent = r.legende;
    $("mc-tableau").replaceChildren(App.tableau(r.tableau));
    $("mc-erreurs").replaceChildren(...r.enErreur.map((e) => Object.assign(document.createElement("p"), { className: "message erreur", textContent: `${e.nom} : ${e.message}` })));
    csv = r.csv;
  }

  function calculer() {
    App.message($("mc-erreur"), "erreur", "");
    if (!chaines.length) return dire("erreur", "Le mécanisme ne contient aucune chaîne.");
    $("mc-calculer").disabled = true;
    setTimeout(() => {
      try {
        const graine = nombre($("mc-graine").value), seuil = nombre($("mc-seuil").value);
        if (typeof graine !== "number" || typeof seuil !== "number") return App.message($("mc-erreur"), "erreur", "La graine et le seuil de Cpk doivent être des nombres.");
        const r = JSON.parse(pont.mecaCalculer(JSON.stringify(mecanisme()), Number($("mc-n").value), graine, seuil));
        if (r.erreur) return App.message($("mc-erreur"), "erreur", r.erreur);
        afficherResultat(r);
      } catch (e) {
        App.message($("mc-erreur"), "erreur", "Erreur inattendue : " + e);
      } finally {
        $("mc-calculer").disabled = false;
      }
    }, 30);
  }

  async function apres(p) {
    pont = p;
    App.remplir($("mc-exemple"), JSON.parse(pont.exemples()).map((e) => [e.id, e.titre]));
    App.remplir($("mc-n"), TIRAGES.map((n) => [n, n.toLocaleString("fr-FR")]), TIRAGES[0]);
    $("mc-ajout-exemple").addEventListener("click", () => {
      const erreur = ajouter([JSON.parse(pont.charger($("mc-exemple").value))]);
      erreur ? dire("erreur", erreur) : dire("succes", "Exemple ajouté.");
      liste();
    });
    $("mc-ajout-etude").addEventListener("click", () => {
      const valides = [];
      for (const chaine of App.analyser.chaines()) { // une chaîne par cote condition de l'étude
        const r = JSON.parse(pont.mecaChaine(JSON.stringify(chaine)));
        if (r.erreur) return dire("erreur", "L'étude en cours n'est pas valide : " + r.erreur);
        valides.push(r.probleme);
      }
      const erreur = ajouter(valides);
      erreur ? dire("erreur", erreur) : dire("succes", valides.length > 1 ? "Étude en cours ajoutée (2 chaînes)." : "Étude en cours ajoutée.");
      liste();
    });
    $("mc-ajout-fichiers").addEventListener("click", () => $("mc-fichiers").click());
    $("mc-fichiers").addEventListener("change", async (e) => { await ajouterFichiers(e.target.files, false); e.target.value = ""; });
    $("mc-ouvrir").addEventListener("click", () => $("mc-fichier").click());
    $("mc-fichier").addEventListener("change", async (e) => { await ajouterFichiers(e.target.files, true); e.target.value = ""; });
    $("mc-enregistrer").addEventListener("click", enregistrer);
    $("mc-calculer").addEventListener("click", calculer);
    $("mc-csv").addEventListener("click", () => App.telecharger("mecanisme_tableau_de_bord.csv", "﻿" + csv, "text/csv;charset=utf-8"));
    liste();
  }

  App.enregistrerPage({ id: "mecanisme", titre: "Mécanisme", apres });
})();
