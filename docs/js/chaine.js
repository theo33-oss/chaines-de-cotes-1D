"use strict";
// Page « Analyser » : saisie de la chaîne, aperçu en direct, calcul complet, enregistrement et ouverture d'une étude.
// Aucun calcul ici : tout vient de pont.py (le Python de l'application de bureau).

(() => {
  const { $, nombre } = App;
  let pont = null;
  let etude = { cartouche: null, revisions: [] }; // reportés tels quels dans le fichier enregistré (cartouche, révisions)
  let materiaux = [];
  let ongletActif = "resultats";

  const CHAMPS_CONNUS = ["nom", "sens", "cote", "iso", "es", "ei", "loi", "materiau", "alpha", "tservice"];
  const MAILLON_VIDE = { nom: "", sens: "+", cote: "", iso: "", es: "", ei: "", loi: "normale", materiau: "", alpha: "", tservice: "" };

  // Étude affichée à l'ouverture : 6 cotes (4 dans un sens, 2 dans l'autre) ; les cotes C et F ont une grande tolérance
  // (± 0,1 mm), les autres une tolérance fine. Jeu de 0,25 à 0,90 mm pour 0,20 à 1,00 demandé : conforme au pire des cas.
  const CAS_DE_BASE = {
    condition: { nom: "Jeu J", jmin: 0.2, jmax: 1 },
    maillons: [
      { nom: "Pièce A", sens: "+", cote: 20, es: 0.05, ei: 0 },
      { nom: "Pièce B", sens: "+", cote: 15, es: 0.05, ei: 0 },
      { nom: "Pièce C (grande tolérance)", sens: "+", cote: 30, es: 0.1, ei: -0.1 },
      { nom: "Pièce D", sens: "+", cote: 25, es: 0.05, ei: 0 },
      { nom: "Carter E", sens: "-", cote: 50, es: 0.05, ei: -0.05 },
      { nom: "Carter F (grande tolérance)", sens: "-", cote: 39.5, es: 0.1, ei: -0.1 },
    ],
  };

  // ---------- tableau des maillons ----------

  function champ(valeur, classe, numerique) {
    const el = document.createElement("input");
    el.type = "text";
    el.value = valeur ?? "";
    el.className = classe;
    if (numerique) el.inputMode = "decimal";
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
    tr._extra = m.extra || {}; // champs que la page ne saisit pas (facteur, angle, mesures de l'atelier…) : gardés intacts
    const cellules = [
      ["Nom", champ(m.nom, "m-nom")],
      ["Sens", liste("m-sens", [["+", "+ (agrandit)"], ["-", "− (réduit)"]], m.sens === "-" ? "-" : "+")],
      ["Cote nominale", champ(m.cote, "m-cote", true)],
      ["Désignation ISO 286", champ(m.iso, "m-iso")],
      ["Écart supérieur ES", champ(m.es, "m-es", true)],
      ["Écart inférieur EI", champ(m.ei, "m-ei", true)],
      ["Loi", liste("m-loi", [["normale", "normale"], ["uniforme", "uniforme"], ["triangulaire", "triangulaire"]], m.loi || "normale")],
      ["Matériau", liste("m-mat", [["", "(aucun)"], ...materiaux.map((n) => [n, n])], materiaux.includes(m.materiau) ? m.materiau : "")],
      ["Coefficient de dilatation α", champ(m.alpha, "m-alpha", true)],
      ["Température de service", champ(m.tservice, "m-tserv", true)],
    ];
    cellules.forEach(([nom, el], i) => {
      el.setAttribute("aria-label", `${nom}, maillon ${numero}`);
      const td = document.createElement("td");
      if (i >= 7) td.className = "td-therm" + (i === 9 ? " td-tcote" : "");
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
      apercuDiffere();
    });
    const td = document.createElement("td");
    td.append(sup);
    tr.append(td);
    return tr;
  }

  function afficherMaillons(maillons) {
    document.querySelector("#maillons tbody").replaceChildren(...maillons.map((m, i) => ligneMaillon(m, i + 1)));
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
      materiau: tr.querySelector(".m-mat").value,
      alpha: tr.querySelector(".m-alpha").value,
      tservice: tr.querySelector(".m-tserv").value,
      extra: tr._extra,
    }));
  }

  // ---------- problème ↔ saisie ----------

  function lireProbleme() {
    const therm = $("thermique").checked;
    const maillons = lireMaillons().map((m) => ({
      ...m.extra,
      nom: m.nom, sens: m.sens, loi: m.loi, iso: m.iso.trim(),
      cote: nombre(m.cote), es: nombre(m.es), ei: nombre(m.ei),
      ...(therm ? { materiau: m.materiau, alpha: nombre(m.alpha), tservice: nombre(m.tservice) } : {}),
    }));
    const probleme = {
      condition: { nom: $("c-nom").value, jmin: nombre($("c-jmin").value), jmax: nombre($("c-jmax").value) },
      reglages: {
        kSigma: nombre($("r-k").value), tref: nombre($("r-tref").value), tservice: nombre($("r-tserv").value),
        modeT: $("r-mode").value, decentrage: nombre($("r-dec").value), tolGenerale: $("r-tolgen").value,
      },
      maillons,
    };
    if (etude.cartouche) probleme.cartouche = etude.cartouche;
    return probleme;
  }

  // Maillon d'un problème (champs absents ou null possibles) → ligne du tableau ; les champs non saisis vont dans extra.
  function versLigne(m) {
    return {
      ...MAILLON_VIDE, ...Object.fromEntries(CHAMPS_CONNUS.filter((k) => m[k] != null).map((k) => [k, m[k]])),
      extra: Object.fromEntries(Object.entries(m).filter(([k]) => !CHAMPS_CONNUS.includes(k))),
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
    $("r-mode").value = r.modeT ?? "uniforme";
    $("r-dec").value = r.decentrage ?? 0;
    $("r-tolgen").value = r.tolGenerale ?? "";
    const maillons = (p.maillons || []).map(versLigne);
    afficherMaillons(maillons);
    // la température de chaque maillon (20 °C dans les fichiers du bureau) ne compte pas : seuls un matériau, un α,
    // le mode « par cote » ou une température de service différente de la référence activent l'effet thermique
    const avecThermique = maillons.some((m) => m.materiau || m.alpha !== "")
      || r.modeT === "par_cote" || (r.tservice != null && r.tservice !== (r.tref ?? 20));
    $("thermique").checked = avecThermique;
    colonnesThermiques();
  }

  function colonnesThermiques() {
    const t = $("maillons");
    t.classList.toggle("therm", $("thermique").checked);
    t.classList.toggle("tcote", $("thermique").checked && $("r-mode").value === "par_cote");
  }

  // ---------- aperçu en direct ----------

  let minuterie = null;
  function apercuDiffere() {
    clearTimeout(minuterie);
    minuterie = setTimeout(apercu, 350);
  }

  function apercu() {
    let r;
    try {
      r = JSON.parse(pont.apercu(JSON.stringify(lireProbleme())));
    } catch (e) {
      App.message($("apercu-verdict"), "erreur", "Aperçu impossible : " + e);
      return;
    }
    if (r.erreur) App.message($("apercu-verdict"), "avertissement", "Saisie à compléter : " + r.erreur);
    else App.message($("apercu-verdict"), r.pireCas.niveau, r.pireCas.texte);
    App.tracer($("apercu-fig"), r.fig);
    $("apercu-legende").textContent = r.erreur ? "" : r.legende;
    $("controles").replaceChildren(...r.controles.map((c) => {
      const li = document.createElement("li");
      li.className = c.niveau;
      li.textContent = ({ erreur: "Erreur : ", avertissement: "Attention : ", info: "À noter : " }[c.niveau] || "") + c.message;
      return li;
    }));
  }

  // ---------- résultats ----------

  function figures(panneau, liste) {
    for (const f of liste) {
      const d = document.createElement("div");
      d.className = "figure";
      panneau.append(d);
      App.tracer(d, f.fig);
      panneau.append(App.legende(f.legende));
    }
  }

  function onglets(r) {
    const res = r.resultats, st = r.statistiques;
    return [
      {
        id: "resultats", titre: "Résultats",
        rendu(p) {
          p.append(App.metriques(res.metriques));
          if (r.details.length) {
            const ul = document.createElement("ul");
            ul.className = "details";
            for (const d of r.details) ul.append(Object.assign(document.createElement("li"), { textContent: d }));
            p.append(ul);
          }
          p.append(App.titre("Verdicts"), App.legende(res.limites), App.tableau(res.verdicts));
          p.append(App.titre("Maillons"), App.tableau(res.maillons), App.legende(res.legendeMaillons));
          if (res.capabilite) p.append(App.titre("Capabilité de chaque cote"), App.tableau(res.capabilite));
        },
      },
      {
        id: "statistiques", titre: "Statistiques",
        rendu(p) {
          if (st.monteCarlo) p.append(App.legende(st.monteCarlo.texte), App.tableau(st.monteCarlo.table));
          else p.append(App.legende("Pas de tirage Monte-Carlo : l'écart-type du jeu est nul, il n'y a rien à simuler."));
          p.append(App.titre("Tolérancement inertiel (Pillet)"), App.metriques(st.inertiel.metriques));
          if (st.inertiel.table) {
            p.append(App.tableau(st.inertiel.table), App.legende(
              "L'inertie d'une cote mêle sa dispersion et son décentrage. Répartir l'inertie maxi du jeu également autorise des IT "
              + "environ √n fois plus larges que la répartition égale au pire des cas, à condition que chaque cote soit produite "
              + "avec cette inertie. Ordres de grandeur pour discuter d'une cotation, pas une cotation."));
          } else p.append(App.legende(st.inertiel.info));
          figures(p, r.figuresStatistiques);
        },
      },
      { id: "graphiques", titre: "Graphiques", rendu: (p) => figures(p, r.figuresGraphiques) },
      {
        id: "sensibilite", titre: "Sensibilité",
        rendu(p) {
          p.append(App.legende("L'indice de Sobol d'un maillon est la part de la variance du jeu qu'il explique (somme = 100 %). "
            + "Resserrer la tolérance du maillon au plus fort indice est le levier le plus efficace."));
          figures(p, [r.sensibilite.figure]);
          if (r.sensibilite.table) {
            p.append(App.tableau(r.sensibilite.table), App.legende(
              "Colonnes « si resserré » : un seul maillon est ramené à 50 % de son IT, les autres gardent leur tolérance ; moyenne du procédé et limites inchangées."));
          }
        },
      },
      {
        id: "explications", titre: "Explications du calcul",
        rendu(p) {
          for (const s of r.explications) {
            p.append(App.titre(s.titre));
            const texte = document.createElement("div");
            texte.innerHTML = App.markdown(s.texte); // texte échappé par App.markdown
            p.append(texte);
            for (const f of s.formules) {
              const d = document.createElement("div");
              d.className = "formule";
              d.innerHTML = f; // HTML produit par core/formules.texVersHtml, qui échappe le texte
              p.append(d);
            }
          }
        },
      },
    ];
  }

  function afficherResultats(r) {
    $("resultats").hidden = false;
    App.message($("verdict"), r.niveau, r.titre);
    $("conseil").textContent = r.conseil ? "À faire : " + r.conseil : "";
    // mode guidé : le verdict en langage courant (chiffres, puis conseils)
    const puces = (liste) => liste.map((t) => Object.assign(document.createElement("li"), { textContent: t }));
    $("plain-details").replaceChildren(...puces(r.details));
    const ul = Object.assign(document.createElement("ul"), { className: "details" });
    ul.append(...puces(r.conseils));
    $("plain-conseils").replaceChildren(...(r.conseils.length ? [App.titre("Que faire ?"), ul] : []));
    $("avertissements").replaceChildren(...r.avertissements.map((t) => Object.assign(document.createElement("li"), { textContent: t })));
    App.onglets($("onglets"), $("panneau"), onglets(r).map((o) => ({ ...o, rendu: (p) => { ongletActif = o.id; o.rendu(p); } })), ongletActif);
  }

  function calculer() {
    App.message($("erreur"), "erreur", "");
    $("calculer").disabled = true;
    $("calculer").textContent = "Calcul en cours…";
    // laisse le navigateur afficher le message avant le calcul, qui occupe le processeur quelques secondes
    setTimeout(() => {
      let r = null;
      try {
        r = JSON.parse(pont.calculer(JSON.stringify(lireProbleme())));
        if (r.erreur) {
          $("resultats").hidden = true;
          App.message($("erreur"), "erreur", r.erreur);
        } else {
          afficherResultats(r);
          // mode expert : le verdict est sous le tableau des maillons, on y amène l'utilisateur
          if (!guide.actif && !$("page-analyser").hidden) $("resultats").scrollIntoView({ behavior: "smooth", block: "start" });
        }
      } catch (e) {
        App.message($("erreur"), "erreur", "Erreur inattendue : " + e);
      } finally {
        $("calculer").disabled = false;
        $("calculer").textContent = "Calculer";
      }
    }, 30);
  }

  // ---------- exemples, fichiers ----------

  function messageFichier(niveau, texte) {
    App.message($("message-fichier"), niveau, texte);
  }

  // ---------- parcours guidé : les mêmes sections, montrées une étape à la fois ----------

  const ETAPES = [
    ["Point de départ", "Une chaîne de cotes répond à une question : <strong>le jeu entre deux pièces reste-t-il dans ses limites ?</strong> Partez d'un exemple, d'une étude déjà enregistrée, ou de la chaîne en cours."],
    ["Cote condition", "La <strong>cote condition</strong> est le jeu (ou le serrage, le dépassement) à garantir. Donnez-lui un nom et ses limites : <strong>Jmin</strong> est le plus petit jeu acceptable, <strong>Jmax</strong> le plus grand."],
    ["Maillons", "Ajoutez une ligne par cote de la chaîne : son <strong>sens</strong> (« + » si elle agrandit le jeu, « − » si elle le réduit), sa <strong>cote nominale</strong> et sa <strong>tolérance</strong> (désignation ISO comme H7, ou écarts ES / EI)."],
    ["Calcul et verdict", "Le calcul est lancé à l'ouverture de cette étape. Lisez le verdict : il dit si le jeu tient et sur quelle cote agir. Après une modification, cliquez sur <strong>Calculer</strong>."],
    ["Dossier", "Complétez le cartouche, gardez une révision, puis enregistrez le dossier et l'étude."],
  ];
  const guide = { actif: false, etape: 0 };

  function majGuide() {
    const page = $("page-analyser");
    page.classList.toggle("guidee", guide.actif);
    for (const el of page.querySelectorAll("[data-etape]")) el.classList.toggle("etape-courante", Number(el.dataset.etape) === guide.etape + 1);
    $("guide-etapes").replaceChildren(...ETAPES.map(([titre], i) => {
      const li = document.createElement("li");
      const b = Object.assign(document.createElement("button"), { type: "button", textContent: `${i + 1}. ${titre}` });
      b.setAttribute("aria-current", String(i === guide.etape ? "step" : "false"));
      b.addEventListener("click", () => allerEtape(i));
      li.append(b);
      return li;
    }));
    $("guide-titre").textContent = `Étape ${guide.etape + 1} sur ${ETAPES.length} : ${ETAPES[guide.etape][0]}`;
    $("guide-texte").innerHTML = ETAPES[guide.etape][1]; // textes écrits ici, sans donnée de l'utilisateur
    for (const b of page.querySelectorAll(".js-precedent")) b.disabled = guide.etape === 0;
    for (const b of page.querySelectorAll(".js-suivant")) b.disabled = guide.etape === ETAPES.length - 1;
  }

  function allerEtape(i) {
    guide.etape = Math.min(Math.max(i, 0), ETAPES.length - 1);
    majGuide();
    window.scrollTo(0, 0);
    if (guide.etape === 3) calculer(); // étape « Calcul et verdict » : pas de clic de plus
  }

  function modeGuide(actif, etape = 0) {
    guide.actif = actif;
    guide.etape = etape;
    majGuide();
  }

  async function ouvrirFichier(fichier) {
    if (!fichier) return;
    let o;
    try {
      o = JSON.parse(pont.ouvrir(await fichier.text()));
    } catch (e) {
      messageFichier("erreur", "Lecture impossible : " + e);
      return;
    }
    if (o.erreur) {
      messageFichier("erreur", o.erreur);
      return;
    }
    etude = { cartouche: o.probleme.cartouche || null, revisions: o.revisions || [] };
    poserProbleme(o.probleme);
    $("resultats").hidden = true;
    App.message($("erreur"), "erreur", "");
    messageFichier("succes", `Étude « ${fichier.name} » ouverte : ${o.probleme.maillons.length} maillon(s). Cliquez sur Calculer.`);
    apercu();
  }

  function enregistrer() {
    const r = JSON.parse(pont.sauver(JSON.stringify(lireProbleme()), JSON.stringify(etude.revisions)));
    if (r.erreur) {
      messageFichier("erreur", "Enregistrement impossible : " + r.erreur);
      return;
    }
    App.telecharger("chaine_de_cotes.json", r.contenu);
    messageFichier("succes", "Étude enregistrée : chaine_de_cotes.json (dossier des téléchargements).");
  }

  async function apres(p) {
    pont = p;
    materiaux = JSON.parse(pont.materiaux());
    const exemples = JSON.parse(pont.exemples());
    const choix = $("exemple");
    choix.replaceChildren(...exemples.map((e) => Object.assign(document.createElement("option"), { value: e.id, textContent: e.titre })));
    choix.prepend(Object.assign(document.createElement("option"), { value: "", textContent: "Cas de base : 6 cotes (modifiable)" }));
    choix.value = "";
    const decrire = () => {
      $("description").textContent = (exemples.find((e) => e.id === choix.value) || {}).description
        || "Cas de base affiché ci-dessous : 6 cotes (4 « + », 2 « − »), dont deux (C et F) à grande tolérance. Modifiez-le, ou choisissez un exemple.";
    };
    choix.addEventListener("change", decrire);
    decrire();
    $("charger").addEventListener("click", () => {
      if (!choix.value) return poserProbleme(CAS_DE_BASE), $("resultats").hidden = true, apercu(); // retour au cas de base
      etude = { cartouche: null, revisions: [] };
      poserProbleme(JSON.parse(pont.charger(choix.value)));
      $("resultats").hidden = true;
      App.message($("erreur"), "erreur", "");
      messageFichier("info", "");
      calculer();
      apercu();
    });
    $("ouvrir").addEventListener("click", () => $("fichier").click());
    $("fichier").addEventListener("change", async (e) => { await ouvrirFichier(e.target.files[0]); e.target.value = ""; });
    $("enregistrer").addEventListener("click", enregistrer);
    $("ajouter").addEventListener("click", () => { afficherMaillons([...lireMaillons(), { ...MAILLON_VIDE }]); apercuDiffere(); });
    $("calculer").addEventListener("click", calculer);
    $("guide-ouvrir").addEventListener("click", () => modeGuide(true, 0));
    $("guide-quitter").addEventListener("click", () => modeGuide(false));
    for (const b of document.querySelectorAll("#page-analyser .js-precedent")) b.addEventListener("click", () => allerEtape(guide.etape - 1));
    for (const b of document.querySelectorAll("#page-analyser .js-suivant")) b.addEventListener("click", () => allerEtape(guide.etape + 1));
    $("guide-vers-dossier").addEventListener("click", () => App.afficherPage("dossier"));
    $("guide-enregistrer").addEventListener("click", enregistrer);
    majGuide();
    $("thermique").addEventListener("change", () => { colonnesThermiques(); apercuDiffere(); });
    $("r-mode").addEventListener("change", colonnesThermiques);
    $("page-analyser").addEventListener("input", apercuDiffere);
    $("page-analyser").addEventListener("change", apercuDiffere);
    poserProbleme(CAS_DE_BASE);
    colonnesThermiques();
    apercu();
  }

  // Points d'entrée pour les autres pages (exemples, assistant d'ajustement) : elles alimentent la chaîne de cette page.
  App.analyser = {
    guide: modeGuide, // modeGuide(true, 0) : parcours guidé à l'étape 1 ; modeGuide(false) : mode expert
    ouvrirFichier: () => $("fichier").click(),
    // Remplace l'étude par un problème (dict du pont) et lance le calcul.
    charger(probleme) {
      etude = { cartouche: null, revisions: [] };
      poserProbleme(probleme);
      $("resultats").hidden = true;
      App.message($("erreur"), "erreur", "");
      messageFichier("info", "");
      apercu();
      calculer();
    },
    // Ajoute des maillons (dicts du pont) à la suite de ceux de la chaîne.
    ajouterMaillons(liste) {
      afficherMaillons([...lireMaillons(), ...liste.map(versLigne)]);
      $("resultats").hidden = true;
      apercu();
    },
    noms: () => lireMaillons().map((m) => m.nom),
    tref: () => nombre($("r-tref").value) || 20,
    probleme: lireProbleme,
    // cartouche et révisions de l'étude (reportés dans le fichier enregistré et dans le dossier de validation)
    cartouche: () => etude.cartouche,
    poserCartouche(c) { etude.cartouche = c && Object.keys(c).length ? c : null; },
    revisions: () => etude.revisions,
    limites: () => [$("c-jmin").value, $("c-jmax").value],
    poserLimites(jmin, jmax) {
      $("c-jmin").value = jmin;
      $("c-jmax").value = jmax;
      $("resultats").hidden = true;
      apercu();
    },
    // « Appliquer à l'étude » : remplace les écarts de chaque maillon (la désignation ISO est vidée).
    appliquerEcarts(ecarts) {
      document.querySelectorAll("#maillons tbody tr").forEach((tr, i) => {
        if (!ecarts[i]) return;
        tr.querySelector(".m-iso").value = "";
        // valeurs exactes, sans arrondi : un jeu qui tombe pile sur une limite deviendrait « non conforme » d'un millionième
        tr.querySelector(".m-es").value = String(ecarts[i].es);
        tr.querySelector(".m-ei").value = String(ecarts[i].ei);
      });
      $("resultats").hidden = true;
      apercu();
    },
  };

  App.enregistrerPage({ id: "analyser", titre: "Analyser", apres });
})();
