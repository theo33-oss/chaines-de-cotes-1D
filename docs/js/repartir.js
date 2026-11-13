"use strict";
// Page « Répartir les tolérances » : à partir de [Jmin ; Jmax], calcule les IT des maillons de la page Analyser.
// Le calcul est celui du bureau (core/inverse.py, services/repartition.py) ; ici, seulement la saisie et l'affichage.

(() => {
  const { $, nombre } = App;
  const CLE_ATELIER = "chainecotes.atelier"; // valeurs d'atelier gardées dans ce navigateur (même fichier que le bureau)
  const CHAMPS = [["c", "c (coût à IT = 0,1 mm)"], ["n", "n (exposant)"], ["itmin", "IT mini"], ["itmax", "IT maxi"]];
  let pont = null;
  let base = []; // procédés et valeurs indicatives
  let noms = []; // noms des maillons de la page Analyser
  let signatureNoms = "";
  let figes = new Set();
  let procedesMaillons = [];
  let atelier = {}; // valeurs d'atelier qui diffèrent des valeurs indicatives : {procédé: {c, n, itmin, itmax}}
  let dernier = null; // dernier résultat : { ecarts, apres, signature }

  const choix = (nom) => document.querySelector(`input[name="${nom}"]:checked`).value;
  const cout = () => choix("rp-methode") === "cout_minimal";

  // ---------- valeurs d'atelier ----------

  function messageAtelier(niveau, texte) {
    App.message($("rp-at-message"), niveau, texte);
  }

  function garderAtelier() {
    const r = JSON.parse(pont.atelierExporter(JSON.stringify(atelier)));
    if (r.erreur) return messageAtelier("erreur", r.erreur);
    try {
      localStorage.setItem(CLE_ATELIER, r.contenu);
      messageAtelier("succes", "Valeurs de l'atelier gardées dans ce navigateur (reprises à chaque visite).");
    } catch (e) {
      messageAtelier("avertissement", "Ce navigateur refuse de garder les valeurs : utilisez « Exporter (.json) ».");
    }
  }

  function lireAtelierGarde() {
    try {
      const texte = localStorage.getItem(CLE_ATELIER);
      if (!texte) return;
      const r = JSON.parse(pont.atelierImporter(texte));
      if (r.valeurs) atelier = r.valeurs;
    } catch (e) { /* stockage indisponible : valeurs indicatives */ }
  }

  function champsAtelier() {
    const utilises = [...new Set(procedesMaillons)];
    $("rp-atelier").replaceChildren(...utilises.map((pid) => {
      const b = base.find((x) => x.id === pid);
      const bloc = document.createElement("div");
      bloc.append(App.titre(b.nom, "h4"));
      const grille = document.createElement("div");
      grille.className = "grille";
      for (const [champ, libelle] of CHAMPS) {
        const l = document.createElement("label");
        l.textContent = libelle;
        const i = Object.assign(document.createElement("input"), { type: "text", inputMode: "decimal", value: String((atelier[pid] || {})[champ] ?? b[champ]).replace(".", ",") });
        i.addEventListener("input", () => {
          const v = nombre(i.value);
          const entier = champ.startsWith("it");
          if (typeof v !== "number" || !(v > 0) || (entier && !Number.isInteger(v))) return; // valeur incomplète : ignorée
          atelier[pid] = { ...(atelier[pid] || {}), [champ]: v };
          if (v === b[champ]) delete atelier[pid][champ];
          if (!Object.keys(atelier[pid]).length) delete atelier[pid];
        });
        l.append(i);
        grille.append(l);
      }
      bloc.append(grille);
      return bloc;
    }));
  }

  // ---------- saisie ----------

  function figesEtReglage() {
    const signature = noms.join("|");
    if (signature !== signatureNoms) { // la liste ou l'ordre a changé : jamais le mauvais maillon
      signatureNoms = signature;
      figes = new Set();
      procedesMaillons = noms.map(() => base[0].id);
    }
    $("rp-figes").replaceChildren(...noms.map((n, i) => {
      const l = document.createElement("label");
      l.className = "case";
      const c = Object.assign(document.createElement("input"), { type: "checkbox", checked: figes.has(i) });
      c.addEventListener("change", () => { c.checked ? figes.add(i) : figes.delete(i); reglage(); });
      l.append(c, document.createTextNode(" " + n));
      return l;
    }));
    reglage();
    procedesChoix();
  }

  function reglage() {
    const libres = noms.map((n, i) => [i, n]).filter(([i]) => !figes.has(i));
    const ancien = $("rp-reglage").value;
    App.remplir($("rp-reglage"), libres.map(([i, n]) => [i, n]), libres.some(([i]) => String(i) === ancien) ? ancien : libres[0]?.[0]);
  }

  function procedesChoix() {
    $("rp-cout").hidden = !cout();
    if (!cout()) return;
    $("rp-procedes").replaceChildren(...noms.map((n, i) => {
      const l = document.createElement("label");
      l.textContent = n;
      const s = document.createElement("select");
      App.remplir(s, base.map((b) => [b.id, b.nom]), procedesMaillons[i]);
      s.disabled = figes.has(i);
      s.addEventListener("change", () => { procedesMaillons[i] = s.value; champsAtelier(); });
      l.append(s);
      return l;
    }));
    champsAtelier();
  }

  function afficher() {
    noms = App.analyser.noms();
    const [jmin, jmax] = App.analyser.limites();
    $("rp-jmin").value = jmin;
    $("rp-jmax").value = jmax;
    figesEtReglage();
    $("rp-appliquer").disabled = !dernier || dernier.signature !== JSON.stringify(App.analyser.probleme());
  }

  // ---------- calcul et résultat ----------

  function resultat(r) {
    $("rp-resultat").hidden = false;
    App.message($("rp-message"), r.tenue ? "succes" : "erreur", r.message);
    App.tracer($("rp-schema"), r.schema.fig);
    $("rp-schema-legende").textContent = r.schema.legende;
    $("rp-valeurs").replaceChildren(App.metriques(r.valeurs));
    $("rp-valeurs-cout").replaceChildren(...(r.metriquesCout ? [App.metriques(r.metriquesCout)] : []));
    $("rp-tableau").replaceChildren(App.tableau(r.tableau));
    $("rp-figures").replaceChildren(...r.figures.flatMap((f) => {
      const d = document.createElement("div");
      d.className = "figure";
      setTimeout(() => App.tracer(d, f.fig), 0); // le tracé a besoin que la figure soit dans la page
      return [d, App.legende(f.legende)];
    }));
    $("rp-explication").replaceChildren(...r.explication.flatMap((b) => {
      const t = document.createElement("div");
      t.innerHTML = App.markdown(b.texte); // texte échappé par App.markdown
      return [t, ...b.formules.map((f) => Object.assign(document.createElement("div"), { className: "formule", innerHTML: f }))]; // HTML de texVersHtml
    }));
    const pr = r.procedes;
    $("rp-procedes-utilises").replaceChildren(...(pr ? [
      App.titre("Procédés utilisés et leurs paramètres"), App.legende(pr.legende), App.tableau(pr.tableau),
      ...(pr.avertissement ? [Object.assign(document.createElement("p"), { className: "message avertissement", textContent: pr.avertissement })] : []),
    ] : []));
  }

  function calculer() {
    App.message($("rp-erreur"), "erreur", "");
    App.message($("rp-appliquee"), "succes", "");
    const probleme = App.analyser.probleme();
    $("rp-calculer").disabled = true;
    setTimeout(() => {
      try {
        const r = JSON.parse(pont.repartir(
          JSON.stringify(probleme), choix("rp-methode"), choix("rp-critere"), JSON.stringify([...figes]),
          Number($("rp-reglage").value || 0), JSON.stringify(procedesMaillons), JSON.stringify(atelier), $("rp-arrondi").checked));
        if (r.erreur) {
          $("rp-resultat").hidden = true;
          dernier = null;
          App.message($("rp-erreur"), "erreur", r.erreur + (r.erreur.includes("Jmin") ? " Saisissez les deux limites." : ""));
        } else {
          dernier = { ecarts: r.ecarts, apres: r.apres, signature: JSON.stringify(probleme) };
          resultat(r);
        }
      } catch (e) {
        App.message($("rp-erreur"), "erreur", "Erreur inattendue : " + e);
      } finally {
        $("rp-calculer").disabled = false;
        $("rp-appliquer").disabled = !dernier;
      }
    }, 30);
  }

  function appliquer() {
    if (!dernier) return;
    App.analyser.appliquerEcarts(dernier.ecarts);
    dernier.signature = JSON.stringify(App.analyser.probleme());
    $("rp-appliquer").disabled = false;
    App.message($("rp-appliquee"), "succes", "Tolérances appliquées à l'étude : la page Analyser utilise maintenant ces écarts (la désignation ISO est vidée).");
  }

  async function apres(p) {
    pont = p;
    const d = JSON.parse(pont.procedes());
    base = d.procedes;
    lireAtelierGarde();
    for (const id of ["rp-jmin", "rp-jmax"]) $(id).addEventListener("input", () => App.analyser.poserLimites($("rp-jmin").value, $("rp-jmax").value));
    for (const r of document.querySelectorAll('input[name="rp-methode"]')) r.addEventListener("change", procedesChoix);
    $("rp-calculer").addEventListener("click", calculer);
    $("rp-appliquer").addEventListener("click", appliquer);
    $("rp-at-garder").addEventListener("click", garderAtelier);
    $("rp-at-effacer").addEventListener("click", () => {
      atelier = {};
      try { localStorage.removeItem(CLE_ATELIER); } catch (e) { /* rien à effacer */ }
      champsAtelier();
      messageAtelier("info", "Valeurs indicatives rétablies.");
    });
    $("rp-at-exporter").addEventListener("click", () => {
      const r = JSON.parse(pont.atelierExporter(JSON.stringify(atelier)));
      if (r.erreur) return messageAtelier("erreur", r.erreur);
      App.telecharger("procedes_atelier.json", r.contenu);
      messageAtelier("succes", "Valeurs de l'atelier exportées : procedes_atelier.json.");
    });
    $("rp-at-importer").addEventListener("click", () => $("rp-at-fichier").click());
    $("rp-at-fichier").addEventListener("change", async (e) => {
      const f = e.target.files[0];
      e.target.value = "";
      if (!f) return;
      const r = JSON.parse(pont.atelierImporter(await f.text()));
      if (r.erreur) return messageAtelier("erreur", r.erreur);
      atelier = r.valeurs;
      champsAtelier();
      messageAtelier("succes", `Valeurs de l'atelier importées de « ${f.name} ».`);
    });
    afficher();
  }

  App.repartition = { dernier: () => (dernier ? dernier.apres : null) };
  App.enregistrerPage({ id: "repartir", dans: "analyser", titre: "Répartir", apres, afficher: () => { if (pont) afficher(); } });
})();
