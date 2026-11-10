"use strict";
// Page « Assistant de chaîne » : des pièces, leurs cotes et leurs contacts à la chaîne de cotes minimale
// (core/construction.py du bureau). Le tableau des cotes et celui des contacts sont saisis ici ; le calcul vient du pont.

(() => {
  const { $, nombre } = App;
  const LOIS = ["normale", "uniforme", "triangulaire"];
  const COLONNES = [
    ["piece", "Pièce"], ["de", "De (surface)"], ["vers", "Vers (surface)"], ["cote", "Cote (mm)"], ["iso", "ISO 286"],
    ["es", "ES (mm)"], ["ei", "EI (mm)"], ["loi", "Loi"], ["nom", "Nom du maillon"],
  ];
  let pont = null;
  let cotes = []; // [{ piece, de, vers, cote, iso, es, ei, loi, nom }]
  let contacts = []; // [{ a, b }]
  let noeuds = []; // surfaces « Pièce.surface » connues (renvoyées par le pont)
  let courant = null; // dernier résultat du pont
  let minuterie = null;

  const differe = () => { clearTimeout(minuterie); minuterie = setTimeout(maj, 300); };

  // ---------- tableaux ----------

  function ligneCote(c, i) {
    const tr = document.createElement("tr");
    for (const [cle, libelle] of COLONNES) {
      const td = document.createElement("td");
      let champ;
      if (cle === "loi") {
        champ = App.remplir(document.createElement("select"), LOIS.map((l) => [l, l]), c.loi || "normale");
      } else {
        champ = Object.assign(document.createElement("input"), { type: "text", value: c[cle] ?? "" });
        if (["cote", "es", "ei"].includes(cle)) champ.inputMode = "decimal";
      }
      champ.setAttribute("aria-label", `${libelle}, ligne ${i + 1}`);
      champ.addEventListener("input", () => { c[cle] = champ.value; differe(); });
      td.append(champ);
      tr.append(td);
    }
    tr.append(boutonRetrait(`Retirer la cote ${i + 1}`, () => { cotes.splice(i, 1); tableaux(); maj(); }));
    return tr;
  }

  function ligneContact(c, i) {
    const tr = document.createElement("tr");
    for (const cle of ["a", "b"]) {
      const td = document.createElement("td");
      const options = [["", "(choisir)"], ...noeuds.map((n) => [n, n])];
      if (c[cle] && !noeuds.includes(c[cle])) options.push([c[cle], c[cle]]); // surface plus connue : garde la saisie, le pont la signalera
      const s = App.remplir(document.createElement("select"), options, c[cle] || "");
      s.setAttribute("aria-label", `Surface ${cle === "a" ? 1 : 2}, contact ${i + 1}`);
      s.addEventListener("change", () => { c[cle] = s.value; differe(); });
      td.append(s);
      tr.append(td);
    }
    tr.append(boutonRetrait(`Retirer le contact ${i + 1}`, () => { contacts.splice(i, 1); tableaux(); maj(); }));
    return tr;
  }

  function boutonRetrait(libelle, action) {
    const td = document.createElement("td");
    const b = Object.assign(document.createElement("button"), { type: "button", textContent: "✕" });
    b.setAttribute("aria-label", libelle);
    b.addEventListener("click", action);
    td.append(b);
    return td;
  }

  function tableaux() {
    const tete = (titres) => { const tr = document.createElement("tr"); tr.append(...titres.map((t) => Object.assign(document.createElement("th"), { textContent: t })), document.createElement("th")); return tr; };
    $("as-cotes").tHead.replaceChildren(tete(COLONNES.map(([, l]) => l)));
    $("as-cotes").tBodies[0].replaceChildren(...cotes.map(ligneCote));
    $("as-contacts").tHead.replaceChildren(tete(["Surface 1", "Surface 2"]));
    $("as-contacts").tBodies[0].replaceChildren(...contacts.map(ligneContact));
  }

  // ---------- calcul ----------

  // Cotes envoyées au pont : nombres écrits « 0,25 » compris ; une case vide reste vide.
  const cotesPourPont = () => cotes.map((c) => ({ ...c, cote: nombre(c.cote), es: nombre(c.es), ei: nombre(c.ei) }));

  function maj(choix = 0) {
    const jmin = nombre($("as-jmin").value), jmax = nombre($("as-jmax").value);
    const r = JSON.parse(pont.assistant(JSON.stringify(cotesPourPont()), JSON.stringify(contacts), $("as-depart").value, $("as-arrivee").value,
      $("as-nom").value, typeof jmin === "number" ? jmin : 0, typeof jmax === "number" ? jmax : 1, choix));
    const anciens = noeuds.join("|");
    noeuds = r.surfaces;
    if (noeuds.join("|") !== anciens) {
      App.remplir($("as-depart"), noeuds.map((n) => [n, n]), r.depart ?? noeuds[0]);
      App.remplir($("as-arrivee"), noeuds.map((n) => [n, n]), r.arrivee ?? noeuds[1]);
      const enCours = document.activeElement;
      if (!(enCours && enCours.closest && enCours.closest("#as-contacts"))) tableaux(); // les listes des contacts suivent les surfaces
    } else {
      if (r.depart) $("as-depart").value = r.depart;
      if (r.arrivee) $("as-arrivee").value = r.arrivee;
    }
    App.message($("as-info"), "info", r.info || "");
    App.message($("as-erreur"), "erreur", r.erreur || "");
    courant = r.maillons ? r : null;
    $("as-resultat").hidden = !courant;
    if (!courant) return;
    $("as-plusieurs").hidden = !r.plusieurs.length;
    if (r.plusieurs.length) {
      App.remplir($("as-choix"), r.plusieurs.map((t, j) => [j, t]), r.choisi);
      App.message($("as-info"), "info", `${r.plusieurs.length} chaînes de même longueur relient ces surfaces : choisissez celle de votre mécanisme.`);
    }
    $("as-avertissements").replaceChildren(...r.avertissements.map((t) => Object.assign(document.createElement("p"), { className: "message avertissement", textContent: t })));
    $("as-tableau").replaceChildren(App.tableau(r.tableau));
    App.tracer($("as-fig"), r.fig);
    $("as-legende").textContent = r.legende;
    $("as-utiliser").disabled = !r.utilisable;
  }

  function charger() {
    const d = JSON.parse(pont.assistantExemple());
    cotes = d.cotes.map((c) => ({ ...c, iso: c.iso ?? "", es: c.es ?? "", ei: c.ei ?? "", nom: c.nom ?? "" }));
    contacts = d.contacts.map((c) => ({ ...c }));
    $("as-nom").value = d.condition.nom;
    $("as-jmin").value = d.condition.jmin;
    $("as-jmax").value = d.condition.jmax;
    noeuds = [];
    $("as-depart").replaceChildren();
    $("as-arrivee").replaceChildren();
    maj(); // renvoie les surfaces ; les listes de départ et d'arrivée prennent la première et la deuxième
    $("as-depart").value = d.depart;
    $("as-arrivee").value = d.arrivee;
    tableaux();
    maj();
  }

  function vider() {
    cotes = [];
    contacts = [];
    tableaux();
    maj();
  }

  function utiliser() {
    if (!courant || !courant.utilisable) return;
    const reglages = App.analyser.probleme().reglages; // réglages gardés, comme sur le bureau
    App.afficherPage("analyser");
    App.analyser.charger({ condition: courant.condition, reglages, maillons: courant.maillons });
    window.scrollTo(0, 0);
  }

  async function apres(p) {
    pont = p;
    $("as-exemple").addEventListener("click", charger);
    $("as-vider").addEventListener("click", vider);
    $("as-ajout-cote").addEventListener("click", () => { cotes.push({ loi: "normale" }); tableaux(); differe(); });
    $("as-ajout-contact").addEventListener("click", () => { contacts.push({}); tableaux(); differe(); });
    for (const id of ["as-depart", "as-arrivee", "as-nom", "as-jmin", "as-jmax"]) $(id).addEventListener("input", () => maj());
    $("as-choix").addEventListener("change", (e) => maj(Number(e.target.value)));
    $("as-utiliser").addEventListener("click", utiliser);
    charger();
  }

  App.enregistrerPage({ id: "assistant", titre: "Assistant de chaîne", apres });
})();
