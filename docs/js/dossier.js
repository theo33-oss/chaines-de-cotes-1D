"use strict";
// Page « Dossier de validation » : cartouche, puis dossier HTML qui refait les calculs sans le solveur (services/validation.py).

(() => {
  const { $ } = App;
  let pont = null;
  let champs = []; // [{ cle, libelle }]
  let html = ""; // dernier dossier généré

  function cartoucheSaisi() {
    const c = { ...(App.analyser.cartouche() || {}) };
    for (const { cle } of champs) {
      const v = $("dos-" + cle).value.trim();
      v ? (c[cle] = v) : delete c[cle];
    }
    return c;
  }

  function lireCartouche() {
    const c = App.analyser.cartouche() || {};
    for (const { cle } of champs) $("dos-" + cle).value = c[cle] || "";
  }

  // Statut « Validé » : l'empreinte du problème est enregistrée (le bureau la compare à l'ouverture) ; sinon elle est retirée.
  function majStatut() {
    const c = cartoucheSaisi();
    if (c.statut === "Validé") {
      const p = App.analyser.probleme();
      delete p.cartouche;
      c.empreinte = pont.empreinteProbleme(JSON.stringify(p));
    } else delete c.empreinte;
    App.analyser.poserCartouche(c);
  }

  async function generer() {
    App.message($("dos-erreur"), "erreur", "");
    $("dos-resultat").hidden = true;
    $("dos-generer").disabled = true;
    $("etat").textContent = "Dossier en cours : chargement de jinja2 et refonte des calculs…";
    try {
      await App.paquets(["jinja2"]); // gabarit du dossier, chargé à la première utilisation seulement
      App.analyser.poserCartouche(cartoucheSaisi());
      const probleme = App.analyser.probleme();
      const revisions = App.analyser.revisions();
      if (probleme.cartouche && !probleme.cartouche.revisions && revisions.length) {
        probleme.cartouche = { ...probleme.cartouche, revisions: revisions.map(({ indice, date, auteur, objet }) => ({ indice, date, auteur, objet })) };
      }
      await new Promise((r) => setTimeout(r, 30)); // laisse afficher le message avant le calcul
      const r = JSON.parse(pont.dossier(JSON.stringify(probleme)));
      if (r.erreur) return App.message($("dos-erreur"), "erreur", r.erreur);
      html = r.html;
      $("dos-resultat").hidden = false;
      App.message($("dos-bilan"), r.nOk === r.nTotal ? "succes" : "erreur", r.bilan + (r.nOk === r.nTotal ? "." : " : les écarts sont listés ci-dessous et dans le dossier."));
      $("dos-ecarts").replaceChildren(...(r.ecarts.length ? [App.tableau({ entetes: ["Contrôle", "Attendu (refait à la main)", "Obtenu (solveur)"], lignes: r.ecarts.map((e) => [e.nom, e.attendu, e.obtenu]) })] : []));
    } catch (e) {
      App.message($("dos-erreur"), "erreur", "Dossier impossible : " + e);
    } finally {
      $("dos-generer").disabled = false;
      $("etat").textContent = $("dos-erreur").hidden ? "Dossier prêt." : "Dossier impossible : voir le message d'erreur.";
    }
  }

  async function apres(p) {
    pont = p;
    const c = JSON.parse(pont.cartouche());
    champs = c.champs;
    $("dos-champs").replaceChildren(...champs.map(({ cle, libelle }) => {
      const l = document.createElement("label");
      l.textContent = libelle;
      let champ;
      if (cle === "statut") {
        champ = App.remplir(document.createElement("select"), [["", "(aucun)"], ...c.statuts.map((s) => [s, s])]);
        champ.addEventListener("change", majStatut);
      } else {
        champ = Object.assign(document.createElement("input"), { type: "text", maxLength: 200 });
        champ.addEventListener("change", () => App.analyser.poserCartouche(cartoucheSaisi()));
      }
      champ.id = "dos-" + cle;
      l.append(champ);
      return l;
    }));
    $("dos-generer").addEventListener("click", generer);
    $("dos-telecharger").addEventListener("click", () => App.telecharger("dossier_de_validation.html", html, "text/html;charset=utf-8"));
    $("dos-imprimer").addEventListener("click", () => window.open(URL.createObjectURL(new Blob([html], { type: "text/html;charset=utf-8" })), "_blank"));
  }

  App.enregistrerPage({ id: "dossier", titre: "Dossier", apres, afficher: () => { if (pont) lireCartouche(); } });
})();
