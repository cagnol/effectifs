"""
Distribution du nombre d'eleves par classe dans le premier degré. 

Produit deux graphiques a partir du fichier open data de la DEPP
"Effectifs d'eleves par niveau et nombre de classes par ecole"
(jeu de donnees fr-en-ecoles-effectifs-nb_classes) :

  1. distribution_dept_vs_france.png
     Distribution des classes du secteur public, departement vs France.

  2. distribution_par_secteur.png
     Distribution du departement decomposee en REP/REP+, autre public
     et prive sous contrat.

Methodo : le fichier ne descend pas au niveau de la classe.
Il donne, par ecole, un effectif total et un nombre total de classes. On en
tire donc un E/C par ECOLE, ULIS incluses.
Les histogrammes sont ponderes par le nombre de classes de chaque
ecole, de facon a decrire une classe tiree au hasard plutot qu'une ecole
tiree au hasard. Ces valeurs sont legerement superieures a l'indicateur
officiel de la DEPP, qui exclut les ULIS et scinde les classes multiniveaux
au prorata (Note d'Information n° 26-01).

Usage :
    python graphes_classes.py fr-en-ecoles-effectifs-nb_classes.xlsx
    python graphes_classes.py fichier.xlsx --annee 2024 --departement YVELINES
    python graphes_classes.py fichier.xlsx --cache  # relectures instantanees

Dependances : pandas, numpy, matplotlib, et openpyxl ou python-calamine (plus rapide).
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")  # backend fichier, pas de fenetre
import matplotlib.pyplot as plt  # noqa: E402

# --------------------------------------------------------------------------
# Colonnes du jeu de donnees
# --------------------------------------------------------------------------
COL_ANNEE = "Rentrée scolaire"
COL_DEPT = "Département"
COL_SECTEUR = "Secteur"
COL_REP = "REP"
COL_REPP = "REP +"
COL_CLASSES = "Nombre total de classes"
COL_ELEVES = "Nombre total d'élèves"

SECTEUR_PUBLIC = "PUBLIC"

# Bornes de l'histogramme : un palier de 1 eleve, de 12 a 30.
# Les valeurs hors bornes sont ecretees pour ne pas perdre les queues.
BIN_MIN, BIN_MAX = 12, 30


# --------------------------------------------------------------------------
# Lecture
# --------------------------------------------------------------------------
def strip_accents(text: str) -> str:
    """Retire les accents, pour comparer 'Département' et 'DEPARTEMENT'."""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def load(path: Path, cache: bool, outdir: Path) -> pd.DataFrame:
    """Charge le classeur, avec cache pickle optionnel.

    Le cache va dans le dossier de sortie et non a cote du fichier source :
    celui-ci est souvent monte en lecture seule.
    """
    cache_path = outdir / (path.stem + ".cache.pkl")
    if cache and cache_path.exists():
        print(f"Lecture du cache {cache_path.name}")
        return pd.read_pickle(cache_path)

    print(f"Lecture de {path.name} (peut prendre une minute)...")
    try:
        df = pd.read_excel(path, engine="calamine")
    except (ImportError, ValueError):
        print("  python-calamine indisponible, bascule sur openpyxl (plus lent)")
        df = pd.read_excel(path)

    missing = [
        c
        for c in (COL_ANNEE, COL_DEPT, COL_SECTEUR, COL_REP, COL_REPP,
                  COL_CLASSES, COL_ELEVES)
        if c not in df.columns
    ]
    if missing:
        sys.exit(f"Colonnes absentes du fichier : {missing}")

    for col in (COL_CLASSES, COL_ELEVES, COL_REP, COL_REPP):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df[COL_ANNEE] = df[COL_ANNEE].astype(str).str.strip()

    if cache:
        try:
            df.to_pickle(cache_path)
            print(f"  cache ecrit dans {cache_path}")
        except OSError as exc:
            print(f"  cache non ecrit ({exc})")
    return df


def prepare(df: pd.DataFrame, annee: str) -> pd.DataFrame:
    """Filtre l'annee, calcule le E/C par ecole et le groupe d'appartenance."""
    d = df[df[COL_ANNEE] == annee].copy()
    if d.empty:
        annees = sorted(df[COL_ANNEE].dropna().unique())
        sys.exit(f"Aucune ligne pour la rentree {annee}. Disponibles : {annees}")

    # Une ecole sans classe ou sans effectif ne peut pas produire de ratio.
    d = d.dropna(subset=[COL_CLASSES, COL_ELEVES])
    d = d[d[COL_CLASSES] > 0]

    d["ec"] = d[COL_ELEVES] / d[COL_CLASSES]

    est_public = d[COL_SECTEUR] == SECTEUR_PUBLIC
    est_ep = (d[COL_REP] == 1) | (d[COL_REPP] == 1)
    d["groupe"] = np.select(
        [~est_public, est_public & est_ep],
        ["Privé sous contrat", "REP / REP+"],
        default="Autre public",
    )
    return d


def subset_departement(d: pd.DataFrame, departement: str) -> pd.DataFrame:
    """Selectionne un departement sans se soucier des accents ni de la casse."""
    cible = strip_accents(departement).upper()
    dept_norm = d[COL_DEPT].map(lambda v: strip_accents(v).upper())
    sub = d[dept_norm == cible]
    if sub.empty:
        proches = sorted({v for v in dept_norm.unique() if cible[:4] in v})
        sys.exit(f"Departement '{departement}' introuvable. Proches : {proches}")
    return sub


# --------------------------------------------------------------------------
# Histogramme pondere
# --------------------------------------------------------------------------
def distribution(sub: pd.DataFrame) -> np.ndarray:
    """Part des classes (%) par palier de taille, ponderee par le nb de classes.

    Chaque ecole pese son nombre de classes : on decrit ainsi la classe
    moyenne et non l'ecole moyenne. Les E/C hors [BIN_MIN, BIN_MAX] sont
    ecretes sur la borne, pour que les paliers extremes contiennent les
    queues de distribution au lieu de les perdre.
    """
    if sub.empty:
        return np.zeros(BIN_MAX - BIN_MIN + 1)
    x = np.clip(sub["ec"].to_numpy(float), BIN_MIN, BIN_MAX)
    poids = sub[COL_CLASSES].to_numpy(float)
    bornes = np.arange(BIN_MIN - 0.5, BIN_MAX + 0.6, 1.0)
    effectifs, _ = np.histogram(x, bins=bornes, weights=poids)
    return effectifs / poids.sum() * 100


def moyenne_ponderee(sub: pd.DataFrame) -> float:
    """E/C agrege : total des eleves / total des classes."""
    if sub.empty:
        return float("nan")
    return sub[COL_ELEVES].sum() / sub[COL_CLASSES].sum()


# --------------------------------------------------------------------------
# Graphiques
# --------------------------------------------------------------------------
PALIERS = np.arange(BIN_MIN, BIN_MAX + 1)


def _habiller(ax, titre: str, sous_titre: str) -> None:
    ax.set_xlabel("Élèves par classe (moyenne de l'école)")
    ax.set_ylabel("% des classes")
    ax.set_xticks(PALIERS)
    ax.set_xlim(BIN_MIN - 0.5, BIN_MAX + 0.5)
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", alpha=0.3, linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    # pad reserve la place du sous-titre, sinon les deux se superposent
    ax.set_title(titre, fontsize=13, fontweight="bold", loc="left", pad=30)
    ax.text(0, 1.015, sous_titre, transform=ax.transAxes, fontsize=9,
            color="#555555", va="bottom")
    ax.legend(frameon=False)


def graphe_comparaison(dept_pub, france_pub, departement, annee, out: Path):
    """Graphe 1 : departement vs France, secteur public."""
    fig, ax = plt.subplots(figsize=(11, 6))
    series = [
        (departement.capitalize(), dept_pub, "#c0392b"),
        ("France", france_pub, "#2c3e50"),
    ]
    for nom, sub, couleur in series:
        y = distribution(sub)
        moy = moyenne_ponderee(sub)
        ax.plot(PALIERS, y, marker="o", markersize=4, linewidth=2,
                color=couleur, label=f"{nom} (moyenne {moy:.2f})")
        ax.fill_between(PALIERS, y, alpha=0.08, color=couleur)
        ax.axvline(moy, color=couleur, linestyle=":", linewidth=1.2, alpha=0.8)

    _habiller(
        ax,
        f"Distribution des classes du public selon la taille moyenne de l'école",
        f"Rentrée {annee} — pondéré par le nombre de classes — "
        f"lignes pointillées : moyennes agrégées",
    )
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  ecrit : {out}")


def graphe_secteurs(dept, departement, annee, out: Path):
    """Graphe 2 : decomposition du departement par groupe."""
    fig, ax = plt.subplots(figsize=(11, 6))
    couleurs = {
        "REP / REP+": "#27ae60",
        "Autre public": "#c0392b",
        "Privé sous contrat": "#8e44ad",
    }
    for nom, couleur in couleurs.items():
        sub = dept[dept["groupe"] == nom]
        if sub.empty:
            continue
        y = distribution(sub)
        moy = moyenne_ponderee(sub)
        n_cl = int(sub[COL_CLASSES].sum())
        ax.plot(PALIERS, y, marker="o", markersize=4, linewidth=2,
                color=couleur,
                label=f"{nom} — {moy:.2f} él./classe, {n_cl:,} classes"
                      .replace(",", " "))
        ax.fill_between(PALIERS, y, alpha=0.08, color=couleur)

    ax.set_ylabel("% des classes du groupe")
    _habiller(
        ax,
        f"{departement.capitalize()} : distribution par secteur",
        f"Rentrée {annee} — chaque courbe somme à 100 % sur son propre groupe",
    )
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  ecrit : {out}")


# --------------------------------------------------------------------------
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("fichier", type=Path,
                   help="fr-en-ecoles-effectifs-nb_classes.xlsx")
    p.add_argument("--annee", default="2025",
                   help="rentree scolaire, defaut 2025 (annee 2025-2026)")
    p.add_argument("--departement", default="ESSONNE",
                   help="libelle du departement, defaut ESSONNE")
    p.add_argument("--outdir", type=Path, default=Path("."),
                   help="dossier de sortie des PNG")
    p.add_argument("--cache", action="store_true",
                   help="ecrit/relit un cache pickle dans --outdir")
    args = p.parse_args()

    if not args.fichier.exists():
        sys.exit(f"Fichier introuvable : {args.fichier}")
    args.outdir.mkdir(parents=True, exist_ok=True)

    d = prepare(load(args.fichier, args.cache, args.outdir), args.annee)
    dept = subset_departement(d, args.departement)
    dept_pub = dept[dept[COL_SECTEUR] == SECTEUR_PUBLIC]
    france_pub = d[d[COL_SECTEUR] == SECTEUR_PUBLIC]

    # Recapitulatif chiffre, utile pour verifier les graphes
    print(f"\nRentree {args.annee} — {args.departement.upper()}")
    print(f"{'groupe':<22}{'écoles':>8}{'classes':>9}{'élèves':>9}{'E/C':>7}{'σ':>7}")
    lignes = [(g, dept[dept["groupe"] == g]) for g in
              ("REP / REP+", "Autre public", "Privé sous contrat")]
    lignes += [("Total public", dept_pub), ("Ensemble", dept),
               ("France, public", france_pub)]
    for nom, sub in lignes:
        if sub.empty:
            continue
        moy = moyenne_ponderee(sub)
        poids = sub[COL_CLASSES].to_numpy(float)
        sigma = np.sqrt(np.average((sub["ec"] - moy) ** 2, weights=poids))
        print(f"{nom:<22}{len(sub):>8}{int(poids.sum()):>9}"
              f"{int(sub[COL_ELEVES].sum()):>9}{moy:>7.2f}{sigma:>7.2f}")

    print("\nGraphiques :")
    graphe_comparaison(dept_pub, france_pub, args.departement, args.annee,
                       args.outdir / "distribution_dept_vs_france.png")
    graphe_secteurs(dept, args.departement, args.annee,
                    args.outdir / "distribution_par_secteur.png")


if __name__ == "__main__":
    main()
