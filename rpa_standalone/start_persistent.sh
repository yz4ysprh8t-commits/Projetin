#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# start_persistent.sh
# Inicia cmd_api + RPA Gateway + DOIS tunnels persistentes:
#   - cmd_api (porta 9000) -> porta 80 no Serveo [controle remoto]
#   - RPA gateway (porta 8080) -> porta 8080 no Serveo [testes]
#
# Uso: bash ~/branca/rpa_standalone/start_persistent.sh
# ============================================================

RPA_DIR="/data/data/com.termux/files/home/branca/rpa_standalone"
LOG_DIR="/data/data/com.termux/files/usr/tmp"
SSH_KEY="$HOME/.ssh/id_rsa"

log() { echo "[$(date '+%H:%M:%S')] $1"; }

# --- Matar tudo existente ---
pkill -f "cmd_api.py" 2>/dev/null
pkill -f "api_server.py" 2>/dev/null
pkill -f "ssh.*serveo" 2>/dev/null
sleep 2

# --- Garantir SSH key existe ---
if [ ! -f "$SSH_KEY" ]; then
    log "Gerando SSH key..."
    mkdir -p ~/.ssh
    ssh-keygen -t rsa -b 2048 -f "$SSH_KEY" -N "" -q
fi

# --- Iniciar cmd_api.py ---
log "Iniciando cmd_api.py (porta 9000)..."
nohup python "$HOME/cmd_api.py" > "$LOG_DIR/cmd_api.log" 2>&1 &
sleep 2
log "cmd_api.py PID: $(pgrep -f cmd_api.py)"

# --- Iniciar RPA Gateway ---
log "Iniciando RPA Gateway (porta 8080)..."
cd "$RPA_DIR" && nohup python api_server.py > "$LOG_DIR/rpa.log" 2>&1 &
sleep 3
HEALTH=$(curl -s http://localhost:8080/health 2>/dev/null)
log "RPA health: $HEALTH"

# --- Funcao de tunnel unico com reconexao ---
run_tunnel() {
    local LOCAL_PORT=$1
    local REMOTE_PORT=$2
    local NAME=$3
    local LOGFILE="$LOG_DIR/tunnel_${NAME}.log"

    while true; do
        log "[$NAME] Conectando Serveo $LOCAL_PORT -> :$REMOTE_PORT..."
        
        ssh -o StrictHostKeyChecking=no \
            -o ServerAliveInterval=20 \
            -o ServerAliveCountMax=3 \
            -o ConnectTimeout=15 \
            -o ExitOnForwardFailure=yes \
            -i "$SSH_KEY" \
            -R "${REMOTE_PORT}:localhost:${LOCAL_PORT}" \
            serveo.net 2>&1 | while IFS= read -r line; do
            echo "[$(date '+%H:%M:%S')] $line" | tee -a "$LOGFILE"
            
            if echo "$line" | grep -q "Forwarding HTTP traffic from"; then
                URL=$(echo "$line" | grep -oE 'https://[^ ]+')
                if [ -n "$URL" ]; then
                    log "[$NAME] URL ATIVA: $URL"
                    echo "$URL" > "$HOME/.tunnel_${NAME}_url"
                    
                    # Atualizar config.json se for o tunnel do RPA
                    if [ "$NAME" = "rpa" ]; then
                        python -c "
import json
c = json.load(open('$RPA_DIR/config.json'))
c['serveo_url'] = '$URL'
json.dump(c, open('$RPA_DIR/config.json','w'), indent=4)
print('config.json atualizado: ' + '$URL')
" 2>/dev/null
                        # Notificar RPA internamente
                        curl -s -X POST http://localhost:8080/config \
                            -H 'Content-Type: application/json' \
                            -d "{\"serveo_url\":\"$URL\"}" > /dev/null 2>&1
                    fi
                    
                    # Mostrar status completo
                    CMD_URL=$(cat "$HOME/.tunnel_cmd_url" 2>/dev/null || echo "aguardando...")
                    RPA_URL=$(cat "$HOME/.tunnel_rpa_url" 2>/dev/null || echo "aguardando...")
                    log "========================================"
                    log "CMD_API URL: $CMD_URL"
                    log "RPA URL    : $RPA_URL"
                    log "========================================"
                fi
            fi
        done

        log "[$NAME] Tunnel caiu. Reconectando em 3s..."
        sleep 3
    done
}

# --- Iniciar dois tunnels em background ---
log "Iniciando tunnel CMD_API (9000->80)..."
run_tunnel 9000 80 "cmd" &
TUNNEL_CMD_PID=$!

sleep 5  # Esperar o primeiro tunnel estabilizar

log "Iniciando tunnel RPA (8080->8080)..."
run_tunnel 8080 8080 "rpa" &
TUNNEL_RPA_PID=$!

# --- Aguardar URLs e mostrar resumo ---
sleep 8
CMD_URL=$(cat "$HOME/.tunnel_cmd_url" 2>/dev/null || echo "aguardando...")
RPA_URL=$(cat "$HOME/.tunnel_rpa_url" 2>/dev/null || echo "aguardando...")

echo ""
echo "========================================"
echo "  BRANCA DE NEVE -- SISTEMA ATIVO"
echo "========================================"
echo "  CMD_API  (controle): $CMD_URL"
echo "  RPA Gateway (testes): $RPA_URL:8080"
echo ""
echo "  Logs:"
echo "    cmd_api : tail -f $LOG_DIR/cmd_api.log"
echo "    rpa     : tail -f $LOG_DIR/rpa.log"
echo "    tunnel  : tail -f $LOG_DIR/tunnel_cmd.log"
echo "========================================"
echo ""
echo "  Cole no Windows:"
echo "    python tunnel_url.py --update <CMD_API_URL>"

# Manter processo vivo
wait $TUNNEL_CMD_PID
