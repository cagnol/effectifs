# Effectifs
Distribution du nombre d'eleves par classe dans le premier degre.

## Objet :
Produit deux graphiques a partir du fichier open data de la DEPP
"Effectifs d'eleves par niveau et nombre de classes par ecole"
(jeu de donnees fr-en-ecoles-effectifs-nb_classes) :

  1. distribution_dept_vs_france.png
     Distribution des classes du secteur public, departement vs France.

  2. distribution_par_secteur.png
     Distribution du departement decomposee en REP/REP+, autre public
     et prive sous contrat.

## Fichier source à récupérer
fr-en-ecoles-effectifs-nb_classes
https://data.education.gouv.fr/explore/assets/fr-en-ecoles-effectifs-nb_classes/export/


## Methodo : 
le fichier ne descend pas au niveau de la classe.
Il donne, par ecole, un effectif total et un nombre total de classes. On en
tire donc un E/C par ECOLE, ULIS incluses.
Les histogrammes sont ponderes par le nombre de classes de chaque
ecole, de facon a decrire une classe tiree au hasard plutot qu'une ecole
tiree au hasard. Ces valeurs sont legerement superieures a l'indicateur
officiel de la DEPP, qui exclut les ULIS et scinde les classes multiniveaux
au prorata (Note d'Information n° 26-01).

## Usage :
    python graphes_classes.py fr-en-ecoles-effectifs-nb_classes.xlsx
    python graphes_classes.py fichier.xlsx --annee 2024 --departement YVELINES
    python graphes_classes.py fichier.xlsx --cache  # relectures instantanees

## Dependances : 
pandas, numpy, matplotlib, et openpyxl ou python-calamine (plus rapide).
