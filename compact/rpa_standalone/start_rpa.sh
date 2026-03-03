#!/bin/bash
# =============================================================================
# BRANCA DE NEVE 1.0 - RPA Startup Script
# Adaptado para Emergent Platform
# =============================================================================

# URL da API Central no Emergent (ALTERE SE NECESSÁRIO)
CENTRAL_URL="https://project-staging.preview.emergentagent.com/api"
RPA_PORT=8080
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== BRANCA DE NEVE 1.0 - Startup Automatico ==="
echo ""
echo "CENTRAL_URL: $CENTRAL_URL"
echo ""

# ===== AUTO-UPDATE =====
echo "[0/3] Verificando atualizacoes..."
CONFIG_BACKUP=""
if [ -f "config.json" ]; then
    CONFIG_BACKUP=$(cat config.json)
fi

UPDATE_OK=false
curl -sL --max-time 15 "$CENTRAL_URL/rpa/download" -o /tmp/rpa_update.tar.gz 2>/dev/null
if [ $? -eq 0 ] && [ -f /tmp/rpa_update.tar.gz ]; then
    SIZE=$(stat -c%s /tmp/rpa_update.tar.gz 2>/dev/null || stat -f%z /tmp/rpa_update.tar.gz 2>/dev/null)
    if [ "$SIZE" -gt 1000 ] 2>/dev/null; then
        tar xzf /tmp/rpa_update.tar.gz -C "$SCRIPT_DIR" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "   [OK] Codigo atualizado!"
            UPDATE_OK=true
        else
            echo "   [AVISO] Falha ao extrair atualizacao"
        fi
    else
        echo "   [AVISO] Download muito pequeno, ignorando"
    fi
    rm -f /tmp/rpa_update.tar.gz
else
    echo "   [AVISO] Sem conexao com Central, usando codigo local"
fi

if [ -n "$CONFIG_BACKUP" ]; then
    echo "$CONFIG_BACKUP" > config.json
    echo "   [OK] Configuracao preservada"
fi

chmod +x start_rpa.sh 2>/dev/null

if [ -f ".version" ]; then
    echo "   Versao: $(cat .version)"
fi
echo ""

# ===== ADB =====
echo "[1/3] Garantindo conexao ADB local..."
adb start-server 2>/dev/null
adb connect 127.0.0.1:5555 2>/dev/null
DEVICES=$(adb devices 2>/dev/null | grep -c "device$")
echo "   Devices: $DEVICES conectado(s)"

# ===== SERVIDOR RPA =====
echo ""
echo "[2/3] Iniciando servidor RPA na porta $RPA_PORT..."

pkill -f "uvicorn.*$RPA_PORT" 2>/dev/null
pkill -f "python.*main.py" 2>/dev/null
sleep 1

NON_INTERACTIVE=1 python main.py &
RPA_PID=$!

echo "   Aguardando servidor iniciar (PID: $RPA_PID)..."
TRIES=0
MAX_TRIES=30
while [ $TRIES -lt $MAX_TRIES ]; do
    if curl -s "http://localhost:$RPA_PORT/health" > /dev/null 2>&1; then
        echo "   [OK] Servidor RPA ativo na porta $RPA_PORT!"
        break
    fi

    if ! kill -0 $RPA_PID 2>/dev/null; then
        echo "   [ERRO] Processo RPA morreu. Verifique os erros acima."
        echo "   Dica: Execute 'python main.py' sozinho para ver o erro."
        exit 1
    fi

    TRIES=$((TRIES + 1))
    sleep 2
done

if [ $TRIES -eq $MAX_TRIES ]; then
    echo "   [ERRO] Timeout - servidor nao respondeu em 60s"
    kill $RPA_PID 2>/dev/null
    exit 1
fi

# ===== TUNNEL SERVEO =====
echo ""
echo "[3/3] Iniciando tunnel serveo com auto-registro..."

start_serveo() {
    while true; do
        echo "[SERVEO] Conectando tunnel..."
        SERVEO_LOG=$(mktemp)

        ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 \
            -R 80:localhost:$RPA_PORT serveo.net 2>&1 | tee "$SERVEO_LOG" &
        SSH_PID=$!

        SERVEO_URL=""
        WAIT=0
        while [ $WAIT -lt 20 ] && [ -z "$SERVEO_URL" ]; do
            sleep 2
            SERVEO_URL=$(grep -oP 'https://[a-z0-9-]+\.serveousercontent\.com' "$SERVEO_LOG" | head -1)
            WAIT=$((WAIT + 2))
        done

        if [ -n "$SERVEO_URL" ]; then
            echo ""
            echo "============================================"
            echo "  TUNNEL ATIVO!"
            echo "  URL: $SERVEO_URL"
            echo "============================================"

            python3 -c "
import json
try:
    with open('config.json', 'r') as f:
        c = json.load(f)
except:
    c = {}
c['serveo_url'] = '$SERVEO_URL'
c['central_url'] = '$CENTRAL_URL'
with open('config.json', 'w') as f:
    json.dump(c, f, indent=4)
print('[CONFIG] URLs salvas')
"

            REGISTER_RESULT=$(curl -s -X POST "$CENTRAL_URL/rpa/register" \
                -H "Content-Type: application/json" \
                -d "{\"url\": \"$SERVEO_URL\", \"token\": \"branca_de_neve_2026\"}" 2>&1)
            echo "[REGISTRO] $REGISTER_RESULT"
            echo ""
            echo "  Sistema 100% automatico!"
            echo "  Nenhuma acao manual necessaria."
            echo ""
            echo "  Acesse a API Central para ver logs e status:"
            echo "  $CENTRAL_URL/rpa/status"
            echo ""
        else
            echo "[SERVEO] URL nao detectada apos 20s. Reconectando..."
        fi

        wait $SSH_PID
        echo "[SERVEO] Desconectado. Reconectando em 3s..."
        rm -f "$SERVEO_LOG"
        sleep 3
    done
}

start_serveo &
SERVEO_PID=$!

echo ""
echo "  Tudo rodando! Sistema autonomo ativo."
echo "  Atualizacoes remotas disponiveis via /atualizar"
echo ""

cleanup() {
    echo ""
    echo "Parando servicos..."
    kill $RPA_PID 2>/dev/null
    kill $SERVEO_PID 2>/dev/null
    pkill -P $SERVEO_PID 2>/dev/null
    wait
}
trap cleanup INT TERM

wait
