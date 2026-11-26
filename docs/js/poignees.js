"use strict";
// Poignées de redimensionnement (même geste partout : souris, doigt, flèches, Début ou double-clic pour revenir) et
// taille des graphiques et des tableaux. Les graphiques suivent leur cadre pendant qu'on tire ; au relâchement,
// l'événement « taillechange » laisse les pages redessiner ce qui dépend de la taille. Tailles gardées dans ce navigateur.

const Poignees = (() => {
  const lire = (cle) => { try { return Number(localStorage.getItem(cle)) || 0; } catch (e) { return 0; } };
  const ecrire = (cle, v) => { try { if (v) localStorage.setItem(cle, String(v)); else localStorage.removeItem(cle); } catch (e) { /* sans mémoire */ } };
  const borner = (v, mini, maxi) => Math.max(mini, Math.min(maxi, Math.round(v)));
  const relacher = () => document.dispatchEvent(new Event("taillechange"));

  // Branche les gestes sur une poignée. o : axe (« x » largeur, « y » hauteur), valeur() actuelle, depuis(événement, départ)
  // → valeur visée, poser(v) pendant le geste, garder() à la fin, auto() taille de départ, pas(touche) → écart ou undefined.
  function brancher(el, o) {
    const classe = o.axe === "y" ? "glisse-haut" : "glisse";
    let depart = null, vise = null, image = 0;
    const appliquer = () => { image = 0; if (vise !== null) o.poser(vise); };
    const valider = () => { o.garder(); relacher(); };
    el.addEventListener("pointerdown", (e) => {
      if (e.button) return;
      e.preventDefault();
      el.setPointerCapture(e.pointerId);
      depart = { x: e.pageX, y: e.pageY, v: o.valeur() };
      vise = null;
      document.body.classList.add(classe);
    });
    el.addEventListener("pointermove", (e) => {
      if (!depart || (vise === null && e.pageX === depart.x && e.pageY === depart.y)) return; // simple clic : rien ne change
      vise = o.depuis(e, depart);
      if (!image) image = requestAnimationFrame(appliquer); // une mise à jour par image affichée
    });
    const finir = () => {
      if (!depart) return;
      depart = null;
      document.body.classList.remove(classe);
      if (image) cancelAnimationFrame(image);
      if (vise === null) return;
      appliquer();
      vise = null;
      valider();
    };
    el.addEventListener("pointerup", finir);
    el.addEventListener("pointercancel", finir);
    el.addEventListener("lostpointercapture", finir);
    el.addEventListener("keydown", (e) => {
      const pas = o.pas(e.key);
      if (pas !== undefined) { e.preventDefault(); o.poser(o.valeur() + pas); valider(); }
      else if (e.key === "Home") { e.preventDefault(); o.auto(); relacher(); }
    });
    el.addEventListener("dblclick", () => { o.auto(); relacher(); });
  }

  // Poignée « ⋯ » posée sous un graphique ou un tableau.
  function poigneeBasse(quoi) {
    const p = document.createElement("div");
    p.className = "poignee-hauteur";
    p.setAttribute("role", "separator");
    p.setAttribute("aria-orientation", "horizontal");
    p.setAttribute("aria-label", `Hauteur ${quoi} : glisser, ou flèches haut et bas ; double-clic ou touche Début pour la hauteur automatique`);
    p.tabIndex = 0;
    p.title = `Tirer pour changer la hauteur ${quoi} (double-clic : hauteur automatique)`;
    p.innerHTML = '<span aria-hidden="true">⋯</span>';
    return p;
  }
  const PAS_HAUTEUR = (touche) => ({ ArrowDown: 40, ArrowUp: -40 }[touche]);

  // ---------- graphiques Plotly ----------

  const FIG_MINI = 200, FIG_MAXI = 1400;
  // Graphiques d'une même clé (attribut data-cle, sinon l'identifiant) : une seule hauteur pour eux tous.
  const cleFigure = (div) => div.dataset.cle || div.id || "figure";
  const memoire = (cle) => (cle === "schema" ? "chainecotes.schemaHauteur" : "chainecotes.hauteur." + cle);
  const zone = (div, h) => Math.max(h - div._marges.t - div._marges.b, 50); // hauteur du tracé, sans les marges
  // La légende, placée sous le tracé en proportion de sa hauteur, garde ainsi la même distance en pixels.
  const yLegende = (div, h) => (-0.28 * zone(div, div._naturelle)) / zone(div, h);

  // Mise en page prête à dessiner : hauteur choisie, sinon celle prévue par le calcul. La largeur suit le cadre.
  function preparerFigure(div, layout) {
    div._naturelle = layout.height || 450;
    div._marges = layout.showlegend !== false ? { t: layout.margin?.t ?? 100, b: layout.margin?.b ?? 80 } : null;
    div._choisie = lire(memoire(cleFigure(div)));
    const h = div._choisie || div._naturelle;
    const legende = div._marges ? { legend: { ...layout.legend, y: yLegende(div, h) } } : {};
    // largeur du cadre sans ses bords (Plotly les compterait) ; figure cachée : ajustée quand elle apparaît
    return { ...layout, ...legende, height: h, ...(div.clientWidth ? { width: div.clientWidth } : {}) };
  }

  function ajuster(div) {
    if (!div._fullLayout || !div.clientWidth) return; // pas encore dessiné, ou caché : fait quand il apparaît
    const largeur = div.clientWidth, hauteur = div._choisie || div._naturelle;
    if (Math.abs(div._fullLayout.width - largeur) < 1 && Math.abs(div._fullLayout.height - hauteur) < 1) return;
    const maj = { width: largeur, height: hauteur };
    if (div._marges) maj["legend.y"] = yLegende(div, hauteur);
    Plotly.relayout(div, maj);
  }

  const observateur = new ResizeObserver((entrees) => {
    for (const { target } of entrees) {
      if (!target._image) target._image = requestAnimationFrame(() => { target._image = 0; ajuster(target); });
      // largeur changée sans poignée (fenêtre, disposition) : redessin une fois la taille stable
      if (target._redessiner && target.clientWidth && Math.abs(target.clientWidth - target._largeurDessin) > 1) {
        clearTimeout(target._minuterie);
        target._minuterie = setTimeout(() => { if (!document.body.matches(".glisse, .glisse-haut")) target._redessiner(); }, 200);
      }
    }
  });

  function poserHauteur(cle, h) {
    for (const d of document.querySelectorAll(".js-plotly-plot")) if (cleFigure(d) === cle) { d._choisie = h; ajuster(d); }
  }

  // Après chaque tracé : le graphique est suivi (largeur) et reçoit sa poignée de hauteur.
  function suivreFigure(div) {
    div._largeurDessin = div.clientWidth;
    observateur.observe(div);
    ajuster(div); // la barre de défilement de la page a pu apparaître avec le tracé
    if (div._poignee || !div.parentNode) return;
    const p = (div._poignee = poigneeBasse("du graphique"));
    p.setAttribute("aria-valuemin", String(FIG_MINI));
    p.setAttribute("aria-valuemax", String(FIG_MAXI));
    div.after(p);
    let h = 0;
    brancher(p, {
      axe: "y",
      valeur: () => div._choisie || div._naturelle,
      depuis: (e, d) => d.v + e.pageY - d.y,
      poser: (v) => { h = borner(v, FIG_MINI, FIG_MAXI); p.setAttribute("aria-valuenow", String(h)); poserHauteur(cleFigure(div), h); },
      garder: () => ecrire(memoire(cleFigure(div)), h),
      auto: () => { ecrire(memoire(cleFigure(div)), 0); p.removeAttribute("aria-valuenow"); poserHauteur(cleFigure(div), 0); },
      pas: PAS_HAUTEUR,
    });
  }

  document.addEventListener("taillechange", () => {
    for (const d of document.querySelectorAll(".js-plotly-plot")) {
      ajuster(d);
      if (d._redessiner && d.clientWidth) { clearTimeout(d._minuterie); d._redessiner(); }
    }
  });

  // ---------- tableaux ----------

  const TAB_MINI = 160, TAB_SEUIL = 320; // pas de poignée pour un tableau court : elle ne servirait à rien

  // Boîte qui contient un tableau : hauteur réglable (le tableau défile dedans, titres de colonnes fixes).
  function tableau(boite, cle) {
    if (boite._poignee) return;
    const nom = "chainecotes.hauteur.tableau." + cle;
    const p = (boite._poignee = poigneeBasse("du tableau"));
    p.hidden = true;
    p.setAttribute("aria-valuemin", String(TAB_MINI));
    boite.after(p);
    let h = lire(nom);
    const contenu = () => boite.scrollHeight + boite.offsetHeight - boite.clientHeight;
    const montrer = () => {
      if (!boite.offsetHeight) return; // boîte cachée
      p.hidden = !(contenu() > TAB_SEUIL || contenu() > boite.offsetHeight + 1); // un tableau rogné garde sa poignée
      p.setAttribute("aria-valuemax", String(contenu()));
      p.setAttribute("aria-valuenow", String(boite.offsetHeight));
    };
    const appliquer = () => { boite.style.maxHeight = h ? h + "px" : ""; montrer(); };
    brancher(p, {
      axe: "y",
      valeur: () => boite.offsetHeight,
      depuis: (e, d) => d.v + e.pageY - d.y,
      poser: (v) => { h = borner(v, TAB_MINI, Math.max(contenu(), TAB_MINI)); appliquer(); },
      garder: () => ecrire(nom, h),
      auto: () => { h = 0; ecrire(nom, 0); appliquer(); },
      pas: PAS_HAUTEUR,
    });
    boite.classList.add("hauteur-reglable");
    new ResizeObserver(() => requestAnimationFrame(montrer)).observe(boite);
    new MutationObserver(montrer).observe(boite, { childList: true, subtree: true }); // lignes ajoutées, tableau remplacé
    appliquer();
  }

  return { brancher, preparerFigure, suivreFigure, ajuster, tableau };
})();
