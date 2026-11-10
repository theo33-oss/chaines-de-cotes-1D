"""Essai du pont en Python ordinaire : tous les exemples passent par les mêmes fonctions que la page web."""

import json
import sys
import time
from pathlib import Path

racine = Path(__file__).resolve().parent
sys.path[:0] = [str(racine / "application"), str(racine / "docs")]
sys.modules["pandas"] = None  # la page web n'a pas pandas au démarrage : le pont ne doit pas en dépendre
import pont  # noqa: E402

exemples = json.loads(pont.exemples())
assert exemples, "aucun exemple"
assert len(json.loads(pont.materiaux())) > 50
for e in exemples:
    p = pont.charger(e["id"])
    t = time.time()
    ap = json.loads(pont.apercu(p))
    assert ap["erreur"] is None and ap["fig"]["layout"]["annotations"], (e["id"], ap["erreur"])  # flèches : annotations
    r = json.loads(pont.calculer(p))
    assert "erreur" not in r, (e["id"], r)
    assert r["resultats"]["verdicts"]["lignes"] and r["explications"] and r["sensibilite"]["figure"]
    assert len(r["figuresStatistiques"]) == 3 and r["figuresGraphiques"]
    # aller-retour fichier : ce que la page enregistre doit se rouvrir à l'identique
    s = json.loads(pont.sauver(p))
    o = json.loads(pont.ouvrir(s["contenu"]))
    assert o["probleme"]["maillons"] == pont._nettoyer(json.loads(p))["maillons"], e["id"]  # cases vides = champ absent
    v = r["resultats"]["verdicts"]["lignes"][0]
    print(f"{e['id']:<28} {r['niveau']:<13} pire cas {v[1]} … {v[2]} mm  ({time.time() - t:.1f} s)")
vide = json.loads(pont.calculer(json.dumps({"condition": {}, "reglages": {}, "maillons": [{"sens": "+", "cote": ""}]})))
assert "erreur" in vide, vide
ap = json.loads(pont.apercu(json.dumps({"condition": {}, "reglages": {}, "maillons": [{"sens": "+", "cote": "abc"}]})))
assert ap["erreur"] and ap["fig"], ap
mauvais = json.loads(pont.sauver(json.dumps({"condition": {}, "reglages": {"kSigma": 3, "tref": 20, "modeT": "x"}, "maillons": []})))
assert "erreur" in mauvais, mauvais
# ---- phase 2 : exemples, ISO 286, ajustements, matériaux
cartes = json.loads(pont.cartes())
assert len(cartes) == len(exemples) and all(c["maillons"]["lignes"] and (c["pireCas"] or c["erreur"]) for c in cartes)
assert json.loads(pont.schemaExemple(cartes[0]["id"]))["fig"]["layout"]["annotations"]
d = json.loads(pont.iso286Donnees())
assert len(d["it"]["plages"]) == len(d["it"]["colonnes"]["IT7"]) and "h" in d["arbre"]["colonnes"] and "H" in d["alesage"]["colonnes"]
h7 = json.loads(pont.iso286Lire("50 H7"))["valeurs"][0]["valeurs"]
assert h7 == [["ES (mm)", "0,025"], ["EI (mm)", "0"], ["IT (µm)", "25"]], h7
assert len(json.loads(pont.iso286Lire("50 js7"))["valeurs"]) == 2  # IT7 impair : valeur MATLAB et valeur normalisée
assert "erreur" in json.loads(pont.iso286Lire("40 Q7"))
fonctions = json.loads(pont.ajustementFonctions())["fonctions"]
aj = json.loads(pont.ajustement(50, "tournant", "alesage"))
assert aj["noms"][0] == "H8/f7" and aj["choisi"]["jeux"] == [["Jeu mini", "0,0250 mm"], ["Jeu maxi", "0,0890 mm"]], (aj["noms"], fonctions)
assert json.loads(pont.ajustement(50, "tournant", "alesage", "H7/g6"))["choisi"]["designation"] == "H7/g6"
assert "erreur" in json.loads(pont.ajustement(5000, "tournant", "alesage")) and json.loads(pont.ajustement(5000, "tournant", "alesage"))["erreur"]
m = json.loads(pont.maillonsAjustement("H7/g6", 50, json.dumps(["Arbre"]), 20))["maillons"]
assert [x["nom"] for x in m] == ["Alésage", "Arbre (2)"] and [x["sens"] for x in m] == ["+", "-"]
t = json.loads(pont.materiauxTableau("inox", "[]"))
assert 0 < len(t["tableau"]["lignes"]) < t["total"] and t["familles"]
dil = json.loads(pont.dilatation("Acier C45", 20, 100))
assert dil["metriques"][0][1].startswith("12,4") and dil["fig"]["data"], dil["metriques"]
assert "erreur" in json.loads(pont.dilatation("Acier C45", 20, -300))
assert json.loads(pont.materiauxSources())["sources"]["lignes"]
# ---- phase 3 : répartition et comparaison de scénarios
red = pont.charger("reducteur_jeu_axial")
n = len(json.loads(red)["maillons"])
r = json.loads(pont.repartir(red, "egale", "pire_cas", "[]", 0))
assert "erreur" not in r and r["tenue"], r
assert {ligne[4] for ligne in r["tableau"]["lignes"]} == {"0,1083"}, r["tableau"]["lignes"]  # IT égaux : 0,65 / 6
assert r["valeurs"][0] == ["Budget Jmax − Jmin", "0,6500 mm"] and len(r["ecarts"]) == n and r["explication"] and r["schema"]["fig"]
for methode in ("proportionnelle", "iso"):
    assert json.loads(pont.repartir(red, methode, "statistique", "[]", 0)).get("tenue") is not None, methode
cm = json.loads(pont.repartir(red, "cout_minimal", "pire_cas", "[0]", 1, json.dumps(["tournage"] * n), "{}", True))
assert cm["metriquesCout"] and cm["procedes"]["tableau"]["lignes"] and len(cm["figures"]) == 2 and cm["tenue"], cm.get("erreur")
assert "erreur" in json.loads(pont.repartir(red, "egale", "pire_cas", json.dumps(list(range(n))), 0))  # tout figé
sans_limite = json.loads(red); sans_limite["condition"]["jmax"] = None
assert "erreur" in json.loads(pont.repartir(json.dumps(sans_limite), "egale", "pire_cas", "[]", 0))
at = json.loads(pont.atelierExporter(json.dumps({"tournage": {"c": 2.0}})))
assert json.loads(pont.atelierImporter(at["contenu"]))["valeurs"] == {"tournage": {"c": 2.0}}
assert "erreur" in json.loads(pont.atelierImporter("pas du json"))
cp = json.loads(pont.comparer(red, json.dumps(r["apres"]), "B (répartition)"))
assert not cp["identiques"] and cp["phrases"] and len(cp["maillons"]["lignes"]) == n and cp["fig"]["data"], cp
assert json.loads(pont.comparer(red, red))["identiques"]
assert json.loads(pont.procedes())["procedes"]
# ---- phase 4 : mécanisme et dossier de validation
red_ch = json.loads(pont.mecaChaine(pont.charger("reducteur_jeu_axial")))["probleme"]
boi_ch = json.loads(pont.mecaChaine(pont.charger("boitier_electronique")))["probleme"]
mauvais_ch = json.loads(pont.mecaChaine(json.dumps({"condition": {}, "reglages": {}, "maillons": [{"sens": "+", "cote": "abc"}]})))
assert "erreur" in mauvais_ch
mec = {"nom": "Essai", "chaines": [red_ch, boi_ch]}
ex = json.loads(pont.mecaExporter(json.dumps(mec)))
assert json.loads(pont.mecaImporter(ex["contenu"]))["chaines"] == json.loads(json.dumps(mec["chaines"])), "aller-retour mécanisme"
assert len(json.loads(pont.mecaImporter(pont.charger("reducteur_jeu_axial") and json.dumps({"application": "chaines-de-cotes-1d", "version": 1, "probleme": red_ch})))["chaines"]) == 1  # étude simple promue
assert "erreur" in json.loads(pont.mecaImporter("pas du json"))
assert "erreur" in json.loads(pont.mecaExporter(json.dumps({"nom": "vide", "chaines": []})))
mr = json.loads(pont.mecaCalculer(json.dumps(mec), 20000, 1, 1.33))
assert mr["tableau"]["lignes"] and len(mr["tableau"]["lignes"]) == 2 and mr["fig"]["data"] and mr["csv"].count("\r\n") == 2, mr.get("erreur")
assert mr["tableau"]["classes"] == ["avertissement", "avertissement"] or set(mr["tableau"]["classes"]) <= {"succes", "avertissement", "erreur", "info"}
cas_erreur = {"nom": "E", "chaines": [red_ch, {"condition": {"nom": "X"}, "reglages": {}, "maillons": [{"sens": "+", "cote": 10}]}]}
mre = json.loads(pont.mecaCalculer(json.dumps(cas_erreur), 20000, 1, 1.33))
assert mre["enErreur"] and mre["tableau"]["classes"][1] == "info", mre["tableau"]["classes"]  # une chaîne en erreur n'empêche pas l'autre
ch = json.loads(pont.cartouche()); assert ch["statuts"] and ch["champs"][0]["cle"] == "projet"
assert len(pont.empreinteProbleme(pont.charger("reducteur_jeu_axial"))) == 16
dr = json.loads(pont.dossier(json.dumps({**json.loads(pont.charger("reducteur_jeu_axial")), "cartouche": {"projet": "Essai <b>", "statut": "Brouillon"}})))
assert dr["nTotal"] > 20 and dr["nOk"] == dr["nTotal"] and not dr["ecarts"], (dr["bilan"], dr["ecarts"][:2])
assert "Essai &lt;b&gt;" in dr["html"] and "<b>" not in dr["html"].split("Essai", 1)[1][:30], "cartouche échappé"
assert "plotly" in dr["html"].lower() and "<img" not in dr["html"].split("<figure>", 1)[1][:80]
assert "erreur" in json.loads(pont.dossier(json.dumps({"condition": {}, "reglages": {}, "maillons": [{"sens": "+", "cote": "abc"}]})))
# une étude validée sur la page doit rester « valide » quand le bureau la rouvre (même empreinte)
from chainecotes.services.cartouche import etatValidation  # noqa: E402

for ident in ("reducteur_jeu_axial", "thermique_par_cote", "ajustements_h7_h6_n7"):
    p = json.loads(pont.charger(ident))
    p["cartouche"] = {"statut": "Validé", "empreinte": pont.empreinteProbleme(json.dumps(p))}
    relu = json.loads(pont.ouvrir(json.loads(pont.sauver(json.dumps(p)))["contenu"]))["probleme"]
    assert etatValidation(relu) == "valide", (ident, etatValidation(relu))
    relu["maillons"][0]["cote"] += 1  # toute modification ensuite est signalée
    assert etatValidation(relu) == "modifie"
print("saisie invalide ->", vide["erreur"])
print("fichier invalide ->", mauvais["erreur"])
