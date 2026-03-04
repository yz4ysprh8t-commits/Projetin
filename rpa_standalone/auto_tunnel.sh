#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# auto_tunnel.sh — Tunnel Serveo persistente com auto-registro
# Instalar: chmod +x auto_tunnel.sh
# Executar: bash auto_tunnel.sh
# ============================================================

LOG_FILE="/data/data/com.termux/files/usr/tmp/tunnel.log"
CONFIG_FILE="$HOME/branca/rpa_standalone/config.json"
RPA_PORT=8080
TUNNEL_PORT=9000   # porta do cmd_api.py (controle remoto)
RPA_TUNNEL_PORT=8080  # porta do RPA gateway

log() {
    echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

notify_backend() {
    local serveo_url="$1"
    
    # Atualizar config.json com a nova URL do tunnel
    if command -v python3 &>/dev/null || command -v python &>/dev/null; then
        PY=$(command -v python3 || command -v python)
        $PY - <<PYEOF
import json, os

config_path = "$CONFIG_FILE"
serveo_url = "$serveo_url"

# Ler config atual
with open(config_path, "r") as f:
    config = json.load(f)

# Atualizar URL do serveo
config["serveo_url"] = serveo_url

# Salvar
with open(config_path, "w") as f:
    json.dump(config, f, indent=4)

print(f"[CONFIG] serveo_url atualizado: {serveo_url}")

# Se central_url configurada, auto-registrar
central_url = config.get("central_url", "")
token = config.get("register_token", "branca_de_neve_2026")
if central_url:
    import urllib.request, json as j
    try:
        payload = j.dumps({"url": serveo_url, "token": token}).encode()
        req = urllib.request.Request(
            f"{central_url}/rpa/register",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            print(f"[AUTO-REGISTRO] OK: {r.read().decode()}")
    except Exception as e:
        print(f"[AUTO-REGISTRO] Falhou: {e}")
PYEOF
    fi
    
    # Notificar localmente via RPA (atualiza estado interno)
    curl -s -X POST http://localhost:$RPA_PORT/config \
        -H "Content-Type: application/json" \
        -d "{\"serveo_url\": \"$serveo_url\"}" \
        > /dev/null 2>&1 && log "[RPA] URL atualizada internamente"
}

# ============================================================
# MAIN LOOP
# ============================================================
log "=== AUTO TUNNEL INICIADO ==="
log "Portas: cmd_api=$TUNNEL_PORT | rpa=$RPA_PORT"

RETRY=0
while true; do
    RETRY=$((RETRY + 1))
    log "Tentativa $RETRY — conectando ao Serveo..."
    
    # Criar pipe temporário para capturar URL
    TMPFILE=$(mktemp)
    
    # Iniciar SSH em background capturando output
    ssh -o StrictHostKeyChecking=no \
        -o ServerAliveInterval=30 \
        -o ServerAliveCountMax=3 \
        -o ConnectTimeout=15 \
        -R "80:localhost:$TUNNEL_PORT" \
        serveo.net 2>&1 | while IFS= read -r line; do
        echo "$line" >> "$LOG_FILE"
        echo "$line"
        
        # Capturar URL do Serveo
        if echo "$line" | grep -q "Forwarding HTTP traffic from"; then
            URL=$(echo "$line" | grep -oE 'https://[^ ]+')
            if [ -n "$URL" ]; then
                log "=== TUNNEL ATIVO: $URL ==="
                notify_backend "$URL"
                
                # Salvar URL em arquivo simples para consulta
                echo "$URL" > "$HOME/.tunnel_url"
                log "URL salva em ~/.tunnel_url"
            fi
        fi
    done
    
    log "Tunnel desconectado. Aguardando 5s antes de reconectar..."
    sleep 5
done
