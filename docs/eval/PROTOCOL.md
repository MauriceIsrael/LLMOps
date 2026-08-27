# 3GPP Elicitation Benchmark Evaluation Protocol & Frozen Metrics (v2)

> **Protocol Status:** FROZEN  
> **Freeze Date:** 2026-08-27  
> **Workorder:** v2 Anti-Fabrication Protocol  

---

## 1. Définition d'un Point de Décision Architectural (§5.1)

Un **point de décision** est une question d'architecture ouverte à la lecture de l'étape 1, tranchée explicitement en étape 2, portant sur un choix entre au moins deux possibilités défendables, et ayant un effet sur la structure du système (entité, interface, procédure, ou répartition de responsabilité).

### Exclusions
- Reformulations purement textuelles des exigences d'étape 1.
- Détails de protocole de niveau 3 (champs de paquets, encodage binaire TS 24.380).
- Choix de nommage ou d'étiquettes.

---

## 2. Accord Inter-Annotateurs & Intervalle de Confiance (§5.3)

> **Variante retenue : à confirmer par l'humain avant exécution**

### Variante A — Second Annotateur Humain Indépendant
- **Fichiers lus :** `annotation/annotator1.csv` et `annotation/annotator2.csv`.
- **Rapport :** Accord inter-annotateurs ($\kappa$ de Cohen).
- **Évaluation du critère d'arrêt 1 :** Évalué directement sur $\kappa$.

### Variante B — Test-Retest à 15 Jours d'Intervalle (Même Annotateur)
- **Fichiers lus :** `annotation/annotator1.csv` et `annotation/annotator1_retest.csv`.
- **Rapport :** Stabilité intra-annotateur (et non accord inter-annotateurs).
- **Évaluation du critère d'arrêt 1 :** Marqué **« non évaluable »** (plutôt que « passé »).

### Calcul de l'Intervalle de Confiance à 95 %
Pour le coefficient $\kappa$ calculé sur $N$ items avec une erreur type $SE(\kappa) = \sqrt{\frac{p_o(1-p_o)}{N(1-p_e)^2}}$, l'intervalle de confiance à 95 % est :
$$IC_{95\%}(\kappa) = \kappa \pm 1,96 \times SE(\kappa)$$

> **Règle absolue :** Si la borne basse de l'intervalle de confiance à 95 % est inférieure à 0,50 ($IC_{95\%\_lower} < 0,50$), le résultat est **non concluant** (ni succès ni échec).

---

## 3. Critères d'Arrêt Pré-Définis (§0.2)

1. **Critère d'Arrêt 1 — Tâche mal définie :** $\kappa < 0,60$ (ou $IC_{95\%\_lower} < 0,50$). Si la variante test-retest est choisie, ce critère est noté **« non évaluable »**.
2. **Critère d'Arrêt 2 — Absence d'écart :** Rappel du bras B ne dépasse pas celui du bras A d'au moins 10 points en valeur absolue ($\Delta \text{Rappel} < 10\%$).

---

## 4. Métriques du Banc

1. **Rappel des points de décision ($R$) :** La précision est strictement interdite (l'étape 2 ne répond pas à tout).
2. **Mean Reciprocal Rank (MRR) :** Rang du premier appariement correct.
3. **Classification des non-appariés :** Échantillon de 20 questions non appariées classées en 3 catégories (traitée ailleurs, légitimement ouverte, hors sujet).
