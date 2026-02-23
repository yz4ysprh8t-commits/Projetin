#!/bin/bash
# Script para rodar o Bot Telegram do Branca de Neve

export API_CENTRAL_URL="https://project-staging.preview.emergentagent.com/api"
export RPA_HMAC_SECRET="branca_neve_hmac_2026_s3cr3t"

cd /app/replit_project/Iconeszip/services/bot_telegram

# Adicionar paths necessários
export PYTHONPATH="/app/replit_project/Iconeszip/services/bot_telegram:/app/replit_project/Iconeszip/services/bot_telegram/cogs:/app/replit_project/Iconeszip/services/bot_telegram/cogs/modules:/app/replit_project/Iconeszip/services/shared:$PYTHONPATH"

echo "=== Branca de Neve 1.0 - Bot Telegram ==="
echo "API Central: $API_CENTRAL_URL"
echo ""

python engine_v20.py
