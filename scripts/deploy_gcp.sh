#!/usr/bin/env bash
# ==============================================================================
# Script de Publication & Déploiement GCP Cloud Run — Serveur FastMCP LLMOps
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_ID="canvas-eye-403415"
REGION="europe-west1"
SERVICE_NAME="llmops-mcp-server"
SERVICE_URL="https://llmops-mcp-server-344571265365.europe-west1.run.app"

echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE}  🚀 LLMOps FastMCP — Publication sur GCP Cloud Run  ${NC}"
echo -e "${BLUE}======================================================${NC}"

# 1. Vérification des prérequis CLI
echo -e "\n${YELLOW}[1/5] Vérification de l'environnement GCP...${NC}"
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ Erreur : gcloud CLI n'est pas installé.${NC}"
    exit 1
fi

CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
if [ "$CURRENT_PROJECT" != "$PROJECT_ID" ]; then
    echo -e "${YELLOW}ℹ️  Bascule vers le projet GCP ${PROJECT_ID}...${NC}"
    gcloud config set project "$PROJECT_ID"
fi
echo -e "${GREEN}✅ Projet GCP actif : ${PROJECT_ID}${NC}"

# 2. Vérification de l'état Git
echo -e "\n${YELLOW}[2/5] Vérification du statut Git...${NC}"
if [ -n "$(git status --porcelain)" ]; then
    echo -e "${YELLOW}⚠️  Attention : Des modifications non commitées sont présentes dans le working tree :${NC}"
    git status --short
else
    echo -e "${GREEN}✅ Working tree Git propre (commit: $(git rev-parse --short HEAD)).${NC}"
fi

# 3. Contrôles Qualité Locaux (Pre-flight checks)
echo -e "\n${YELLOW}[3/5] Exécution des vérifications de pré-vol (Ruff & Contrats)...${NC}"
poetry run ruff check .
poetry run pytest tests/contract -q
echo -e "${GREEN}✅ Pré-vol réussi avec succès.${NC}"

# 4. Déclenchement de Google Cloud Build
echo -e "\n${YELLOW}[4/5] Soumission du build et déploiement via Cloud Build...${NC}"
START_TIME=$(date +%s)
gcloud builds submit --config=cloudbuild.yaml --project="$PROJECT_ID"
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
echo -e "${GREEN}✅ Build et déploiement terminés en ${DURATION}s.${NC}"

# 5. Vérification Live de Santé (Post-flight Health Check)
echo -e "\n${YELLOW}[5/5] Vérification de l'endpoint live en production...${NC}"
HEALTH_RESPONSE=$(curl -sf "${SERVICE_URL}/health" || echo "")

if [ -n "$HEALTH_RESPONSE" ]; then
    echo -e "${GREEN}✅ Service en ligne et opérationnel !${NC}"
    echo -e "   Réponse : ${HEALTH_RESPONSE}"
else
    echo -e "${RED}❌ Erreur : Impossible de joindre ${SERVICE_URL}/health${NC}"
    exit 1
fi

echo -e "\n${BLUE}======================================================${NC}"
echo -e "${GREEN}🎉 Publication GCP Réussie !${NC}"
echo -e "   - Service : ${SERVICE_NAME}"
echo -e "   - Région  : ${REGION}"
echo -e "   - URL     : ${SERVICE_URL}"
echo -e "   - Health  : ${SERVICE_URL}/health"
echo -e "${BLUE}======================================================${NC}"
