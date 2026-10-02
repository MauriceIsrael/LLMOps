# Plan d'implémentation — Similarité sémantique et réutilisation de la connaissance validée (LLMOps + Archinex)

Statut : plan, décisions D6 à D8 validées par le mainteneur. Complète
[`PLAN-IMPLEMENTATION-Gouvernance-KB-Archinex.md`](PLAN-IMPLEMENTATION-Gouvernance-KB-Archinex.md).
Lots LLMOps **L11 à L14**, lots Archinex **A12 à A15** (issues dans le dépôt Archinex), porte **G8**.

## État d'avancement (2 octobre 2026)

| Lot | État |
|---|---|
| L11, L12, L13, L14 (LLMOps) | **fusionnés** (contrats 1.9 à 1.12) |
| A12 à A15 (Archinex) | réalisés en partie : synchronisation, recherche, confirmation d'hypothèses, évaluation, « deuxième RFP » ; encodeur honnête et tests négatifs en revue (archinex#22, #24) |
| Porte G8 | **non franchie** : manquent un modèle d'embeddings réel mesuré sur le jeu annoté, des seuils calibrés (`status: uncalibrated`), une règle capitalisée avec assertion formelle prouvant un changement de verdict, et l'E2E API « deuxième RFP » sur le serveur réel (archinex#23) |

**Modèle candidat mesuré (2 octobre 2026)** : `bge-m3` (Ollama, dimension 1024) ; test de bon sens FR/EN : traduction 0,901 contre sujet voisin 0,530 (écart 0,372). Ce n'est pas la calibration : les seuils restent `uncalibrated` jusqu'à l'exécution du jeu annoté (A14).

Modèle d'embeddings : calculé par Archinex sur un serveur local (Ollama ou API compatible OpenAI, `EMBEDDING_OLLAMA_URL`) ; inventaire et test de bon sens FR/EN par `scripts/ollama-models.mjs` côté Archinex ; le choix se fait sur **mesure** (A14), pas sur ce test.

---

## 0. Pourquoi

Deux défauts mesurés ou constatés lors de la préparation du test de bout en bout « réglementation → RFP → décision → capitalisation » :

1. **L'appariement exigence ↔ contrôle est lexical et monolingue.** Un RFP français ne rencontre pas un texte légal anglais ([LLMOps#17](https://github.com/MauriceIsrael/LLMOps/pull/17) comble le cas des contrôles sans `terms`, en même langue seulement).
2. **Rien n'empêche de reposer une question déjà tranchée.** Un sujet issu de l'interprétation d'un RFP n'est jamais comparé aux sujets déjà validés en base. La capitalisation n'est donc jamais « rentabilisée » à l'engagement suivant.

Le second point est le but. Le premier en est une condition (même langue ou non, il faut reconnaître qu'on parle de la même chose).

### Deux niveaux à ne pas confondre

| Niveau | Question | Nature |
|---|---|---|
| **A. Exigence → contrôle** | « Quelle norme s'applique à cette exigence ? » | Recherche de similarité (texte ↔ texte légal) |
| **B. Sujet → connaissance validée** | « Ce sujet a-t-il déjà été tranché, et sous quelles hypothèses ? » | Recherche de similarité **puis confirmation humaine des hypothèses** |

### Le risque à ne pas introduire

« Même thème » n'est pas « même décision ». Une décision vaut sous des hypothèses (volumes, latence, contraintes réglementaires, état de l'existant). Réutiliser à tort une décision, silencieusement, serait pire que reposer la question : c'est exactement le défaut qu'on cherche à supprimer, déplacé.

## 1. Décisions (validées)

| # | Décision |
|---|---|
| **D6** | Les **embeddings sont acceptés dans l'architecture et calculés par Archinex** (son LLM/modèle local). LLMOps **ne contient aucun modèle** : il stocke des vecteurs fournis avec le nom et la version du modèle et calcule une similarité cosinus, de façon déterministe. La règle « pas de LLM dans le serveur » reste vraie. |
| **D7** | Langues : **français et anglais**. |
| **D8** | **Tolérance zéro** : une proposition de réutilisation n'est **jamais** appliquée automatiquement, **quel que soit le score**. Chaque réutilisation passe par une confirmation humaine tracée, qui rappelle les **hypothèses de validité** de la décision d'origine. Jamais de faux positif silencieux. |

## 2. Règles non négociables

1. **Aucune réutilisation automatique.** Les « zones » de score (§3.2) ordonnent et étiquettent ; elles ne décident rien.
2. **Les hypothèses sont rappelées.** Une réutilisation est confirmée **hypothèse par hypothèse** (`holds` / `does_not_hold` / `unknown`). Une décision sans hypothèse documentée ne peut pas être réutilisée telle quelle : l'expert doit d'abord les documenter (amendement, passant par le cycle de revue).
3. **Les règles sont appliquées par LLMOps**, pas seulement par l'interface (§3.3) : le serveur refuse une confirmation incohérente.
4. **Un modèle d'embeddings = un espace.** Des vecteurs de modèles différents ne sont jamais comparés ; changer de modèle impose de recalculer tout (le serveur le détecte et le signale).
5. **Aucun texte d'engagement n'est conservé.** On stocke une empreinte et un libellé **anonymisé** fourni par Archinex ; la comparaison porte sur la connaissance **capitalisée et anonymisée**.
6. **Ce qui est rejeté est mémorisé** : une paire (sujet, actif) déjà jugée « pas le même » est signalée la fois suivante (affichée avec sa raison, pas masquée).
7. **Tout est mesuré** sur un jeu annoté FR/EN avant de fixer des seuils (L13) ; aucun seuil n'est fixé « à l'œil ».
8. **Ce qui est proposé par un modèle est `llm-derived`** ; rien n'entre dans la doctrine sans action humaine tracée.

## 3. Conception

### 3.1 Vecteurs (L11)

- Table `embeddings` : `ref` (identifiant d'actif ou de contrôle), `kind`, `model_id`, `model_version`, `dim`, `vector`, `text_sha256`, `language`, `created_by`, `created_at`. Unique `(ref, model_id)`.
- `GET /api/knowledge/embeddings/pending?model=<id>` : liste ce qu'Archinex doit (re)calculer — actifs et contrôles **actifs** sans vecteur, ou dont `text_sha256` a changé depuis (vecteur périmé) — avec le **texte à encoder** (titre + énoncé / texte légal, déterministe) et son empreinte. Aucun modèle n'est requis côté LLMOps pour savoir ce qui manque.
- `PUT /api/knowledge/embeddings` (rôle `kb:maintain` ou jeton de service) : dépôt par lot de vecteurs. LLMOps **vérifie l'empreinte** (le vecteur correspond bien au texte courant), la dimension, et la cohérence du modèle ; refuse sinon.
- Les états « périmé » et « manquant » sont visibles dans `GET /api/knowledge/health`.

### 3.2 Recherche de similarité (L11)

`POST /api/knowledge/similar` `{model, vector, query_text?, types?, domains?, frameworks?, top_k}` renvoie les actifs classés par un score **hybride** :

`score = w_v · cosinus + w_l · score_lexical (moteur de doctrine existant, synonymes FR/EN inclus) + bonus_domaine`

Poids et seuils sont des **données** (`data/kb/taxonomy/similarity.yaml`), calibrés par L13. Chaque résultat porte : `ref`, `type`, `titre`, `scores` détaillés, `zone` (`strong` / `possible` / `weak`), `status` (les actifs `superseded` sont signalés, jamais présentés comme valides), `last_reviewed`, `validated_by` / `validated_at` (provenance), `assumptions` et `assumptions_documented`, et la **mémoire des jugements** passés (§3.4). Déterministe : mêmes entrées, même sortie.

### 3.3 Hypothèses et confirmations de réutilisation (L12)

- Nouveaux champs optionnels de front matter (décisions, principes, patterns) : `assumptions: [..]` (hypothèses de validité, une par ligne, vérifiables), `review_by` (date de réexamen). Le gabarit (`GET /templates/{type}`) et les contrôles de soumission avertissent quand une décision n'en documente aucune.
- `POST /api/knowledge/reuse-confirmations` : l'expert agissant (`X-Actor-Email`) consigne le jugement `{subject_fingerprint, subject_label (anonymisé), matched_ref, model, scores, assumptions: [{text, status, note?}], outcome, comment?}`. Résultats : `reused`, `reused_with_exception`, `rejected_not_same`, `rejected_assumption_fails`, `deferred`.
- **Règles appliquées par le serveur** (sinon `400`/`409`) :
  - `reused` exige au moins une hypothèse documentée sur l'actif **et** que **toutes** soient `holds` ;
  - une hypothèse `unknown` ou `does_not_hold` interdit `reused` (`reused_with_exception` exige un commentaire motivé, `rejected_assumption_fails` est proposé) ;
  - l'actif doit être `active` et non `superseded` ;
  - les hypothèses transmises doivent être **exactement** celles de l'actif à la date du jugement (empreinte), pour qu'on ne confirme pas des hypothèses périmées ;
  - le jugement est **ajouté seulement** (journal), attribué à la personne, jamais modifiable.
- `GET /api/knowledge/reuse-confirmations?matched_ref=&outcome=` : historique, base de calibration et jeu de test réel.

### 3.4 Mémoire des jugements

Chaque résultat de `similar` indique si la paire (empreinte du sujet, actif) a déjà été jugée, avec le dernier résultat et sa date : « déjà confirmé le … par … », « rejeté : hypothèse X fausse ». Ça n'élimine rien ; ça informe l'expert et évite la répétition.

### 3.5 Jeu d'évaluation FR/EN (L13)

Jeu `similarity_v1` (en base, annoté comme `check_option_v1`) : cas `{query_text, language, expected: [{ref, relation}]}` avec `relation` ∈ `same_subject`, `related_not_same`, `same_topic_different_assumptions`, `unrelated`. Quatre familles obligatoires : paires **FR↔EN du même sujet**, **mêmes mots / sujets différents**, **même sujet / hypothèses incompatibles**, **hors base**. Une exécution reçoit les vecteurs des cas (calculés par Archinex avec le modèle) et calcule en serveur précision/rappel par zone, **taux de proposition « strong » erronée** et taux de manques. Les seuils de `similarity.yaml` en sont déduits et ne changent que par une exécution documentée.

### 3.6 Métadonnées bilingues à l'ingestion (L14)

Les propositions envoyées à `link-proposals` (L8) acceptent aussi `terms` et `title_fr` (marqués `llm-derived`) ; ils sont appliqués au contrôle **seulement si l'expert les valide** (`accept` / `amend`). Ça complète les vecteurs pour les contrôles ingérés (affichage en français, recherche lexicale bilingue).

## 4. Lots

| Lot | Dépôt | Contenu | Dépend de |
|---|---|---|---|
| **L11** | LLMOps | Table de vecteurs, `pending`, dépôt, `similar` hybride, état dans la santé | L9 |
| **L12** | LLMOps | `assumptions`, `reuse-confirmations` avec règles, mémoire des jugements | L11 |
| **L13** | LLMOps | Jeu `similarity_v1`, exécutions, calibration des seuils | L11, L12 |
| **L14** | LLMOps | `terms` / `title_fr` dans les propositions d'ingestion | L8 |
| **A12** | Archinex | Client d'embeddings : synchronisation (`pending` → vecteurs → `PUT`), requête `similar` par sujet | L11 |
| **A13** | Archinex | Expérience de réutilisation : carte de proposition avec provenance, **liste de contrôle des hypothèses**, confirmation / rejet, aucune question sautée en silence | L12, A12 |
| **A14** | Archinex | Annotation du jeu FR/EN, exécutions, calibration (avec le modèle réel) | L13, A12 |
| **A15** | Archinex | Scénario de bout en bout « deuxième RFP » (API et navigateur) | A12, A13, A14 |

Ordre : L11 → (A12 ∥ L12) → A13 → L13 → A14 → A15 ; L14 en parallèle.

**Porte G8** — Sur un second RFP : un sujet déjà validé est **reconnu** (y compris FR ↔ EN) et présenté avec sa provenance et ses hypothèses ; la réutilisation n'est acquise qu'après confirmation humaine de **chaque** hypothèse ; une hypothèse fausse **réouvre la question** ; aucune question n'est supprimée sans trace ; la mesure sur le jeu annoté ne montre **aucune proposition `strong` erronée** au seuil retenu.

## 5. Tests exigés par lot

- **L11** : empreinte périmée refusée ; modèles différents refusés ; classement déterministe ; actif `superseded` signalé ; texte à encoder stable.
- **L12** : `reused` refusé sans hypothèses documentées, avec une hypothèse `unknown` ou `does_not_hold`, avec des hypothèses différentes de celles de l'actif ; `reused_with_exception` sans commentaire refusé ; journal en ajout seul ; mémoire des jugements restituée.
- **L13** : le jeu contient les quatre familles ; une exécution calcule le taux de « strong » erroné.
- **A13 / A15** : un sujet déjà validé n'est jamais écarté sans trace ; une hypothèse fausse réouvre la question.

## 6. Hors périmètre

- Réutilisation automatique, même au-dessus d'un score très élevé (décision D8).
- Comparaison d'engagement à engagement hors KB (seule la connaissance capitalisée et anonymisée est comparée).
- Choix du modèle d'embeddings : Archinex le choisit et l'évalue avec L13/A14 (candidats multilingues FR/EN) ; LLMOps l'enregistre, il ne l'impose pas.
- Traduction automatique de documents.

## 7. Limites assumées

- La qualité dépend du modèle choisi et du jeu annoté : tant que L13 n'a pas produit de mesure, **aucun seuil n'est garanti**.
- Les hypothèses des actifs existants ne sont pas documentées : tant qu'elles ne le sont pas, ces actifs sont proposés avec « hypothèses non documentées » et ne peuvent pas être réutilisés tels quels. C'est volontaire ; une campagne d'enrichissement (A11) peut les compléter.
