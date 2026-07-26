#!/usr/bin/env bash
# ==============================================================================
# Script de Démo Collaboratif : 3 Architectes & Élicitation d'Architecture
# ==============================================================================
# Acteurs Fictifs :
#   - Alice   (role: cloud-architect)
#   - Bob     (role: storage-expert)
#   - Charlie (role: chief-architect)
# ==============================================================================

set -e

ENGAGEMENT="demo-collaborative"
echo "🚀 [Étape 0] Initialisation du scénario collaboratif pour l'engagement '$ENGAGEMENT'..."

echo ""
echo "🔍 [Étape 1] Scan déterministe des manques (Scan Flow)..."
poetry run elicit scan --engagement "$ENGAGEMENT"

echo ""
echo "💬 [Étape 2] Alice (cloud-architect) répond à la question Q-0001..."
poetry run elicit answer Q-0001 --as alice --text "SAN NVMe dual-controller tier-1 avec réplication synchrone" --engagement "$ENGAGEMENT"

echo ""
echo "▶️ [Étape 3] Validation et confirmation des énoncés d'Alice (Reprise d'interruption)..."
poetry run elicit confirm Q-0001 --accept --as alice --engagement "$ENGAGEMENT"

echo ""
echo "💬 [Étape 4] Bob (storage-expert) propose une alternative contradictoire..."
poetry run elicit answer Q-0001 --as bob --text "Ceph HCI all-flash SSD sur nœuds hyperconvergés" --engagement "$ENGAGEMENT"

echo ""
echo "▶️ [Étape 5] Validation des énoncés de Bob -> Détection déterministe du Conflit d'Architecture..."
poetry run elicit confirm Q-0001 --accept --as bob --engagement "$ENGAGEMENT"

echo ""
echo "📊 [Étape 6] Consultation du Maturity Board et détection des conflits..."
poetry run elicit conflicts --engagement "$ENGAGEMENT"
poetry run elicit subjects --engagement "$ENGAGEMENT"

echo ""
echo "📑 [Étape 7] Tentative d'assemblage du document (Devrait donner le statut PROVISIONAL car conflit ouvert)..."
poetry run elicit assemble --engagement "$ENGAGEMENT"

echo ""
echo "⚖️ [Étape 8] Charlie (chief-architect) arbitre le conflit en conservant la proposition d'Alice..."
# Récupérer le premier énoncé ou forcer l'arbitrage
poetry run elicit arbitrate C-0001 --keep S-0001 --reason "Homogénéité avec le datacenter existant et performances NVMe garanties" --as charlie || true

echo ""
echo "📑 [Étape 9] Assemblage final du document par Charlie..."
poetry run elicit assemble --engagement "$ENGAGEMENT"

echo ""
echo "✅ Scénario collaboratif terminé avec succès !"
