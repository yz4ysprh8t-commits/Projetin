#!/bin/bash
# =============================================================================
# BRANCA DE NEVE 1.0 - RPA Startup com NGROK
# =============================================================================

CENTRAL_URL="https://project-staging.preview.emergentagent.com/api"
RPA_PORT=8080
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== BRANCA DE NEVE 1.0 - Startup com NGROK ==="
echo ""

# ===== ADB =====
echo "[1/3] Garantindo conexao ADB local..."
adb start-server 2>/dev/null
adb connect 127.0.0.1:5555 2>/dev/null
echo "   ADB OK"

# ===== SERVIDOR RPA =====
echo ""
echo "[2/3] Iniciando servidor RPA na porta $RPA_PORT..."

pkill -f "uvicorn.*$RPA_PORT" 2>/dev/null
pkill -f "python.*main.py" 2>/dev/null
pkill -f ngrok 2>/dev/null
sleep 1

NON_INTERACTIVE=1 python main.py > rpa.log 2>&1 &
RPA_PID=$!

echo "   Aguardando servidor (PID: $RPA_PID)..."
TRIES=0
while [ $TRIES -lt 30 ]; do
    if curl -s "http://localhost:$RPA_PORT/health" > /dev/null 2>&1; then
        echo "   [OK] Servidor RPA ativo!"
        break
    fi
    if ! kill -0 $RPA_PID 2>/dev/null; then
        echo "   [ERRO] Servidor morreu. Log:"
        tail -20 rpa.log
        exit 1
    fi
    TRIES=$((TRIES + 1))
    sleep 2
done

if [ $TRIES -eq 30 ]; then
    echo "   [ERRO] Timeout"
    exit 1
fi

# ===== NGROK =====
echo ""
echo "[3/3] Iniciando tunnel NGROK..."

ngrok http $RPA_PORT --log=stdout > ngrok.log 2>&1 &
NGROK_PID=$!
sleep 5

# Pegar URL do ngrok
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['tunnels'][0]['public_url'] if d.get('tunnels') else '')" 2>/dev/null)

if [ -z "$NGROK_URL" ]; then
    echo "   [ERRO] Ngrok nao iniciou. Verifique se esta autenticado:"
    echo "   ngrok config add-authtoken SEU_TOKEN"
    cat ngrok.log
    exit 1
fi

echo ""
echo "============================================"
echo "  TUNNEL ATIVO!"
echo "  URL: $NGROK_URL"
echo "============================================"

# Registrar na Emergent
echo ""
echo "Registrando na API Central..."
REGISTER=$(curl -s -X POST "$CENTRAL_URL/rpa/register" \
    -H "Content-Type: application/json" \
    -d "{\"url\": \"$NGROK_URL\", \"token\": \"branca_de_neve_2026\"}" 2>&1)
echo "Resultado: $REGISTER"

# Salvar config
python3 -c "
import json
c = {}
try:
    with open('config.json') as f: c = json.load(f)
except: pass
c['ngrok_url'] = '$NGROK_URL'
c['central_url'] = '$CENTRAL_URL'
with open('config.json', 'w') as f: json.dump(c, f, indent=4)
"

echo ""
echo "============================================"
echo "  SISTEMA ATIVO!"
echo "  RPA: http://localhost:$RPA_PORT"
echo "  Tunnel: $NGROK_URL"
echo "  Central: $CENTRAL_URL"
echo "============================================"
echo ""
echo "Pressione Ctrl+C para parar"

cleanup() {
    echo "Parando..."
    kill $RPA_PID 2>/dev/null
    kill $NGROK_PID 2>/dev/null
}
trap cleanup INT TERM

wait
