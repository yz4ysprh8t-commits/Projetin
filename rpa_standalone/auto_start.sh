#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# auto_start.sh — Inicialização completa do sistema Branca de Neve
# Sobe: cmd_api (controle remoto) + RPA Gateway + Tunnel persistente
# 
# Uso: bash ~/branca/auto_start.sh
# Atalho: echo 'bash ~/branca/auto_start.sh' >> ~/.bashrc
# ============================================================

RPA_DIR="$HOME/branca/rpa_standalone"
LOG_DIR="/data/data/com.termux/files/usr/tmp"
CMD_API_PORT=9000
RPA_PORT=8080

log() { echo "[$(date '+%H:%M:%S')] $1"; }

kill_existing() {
    pkill -f "cmd_api.py" 2>/dev/null
    pkill -f "api_server.py" 2>/dev/null
    pkill -f "auto_tunnel.sh" 2>/dev/null
    pkill -f "ssh.*serveo" 2>/dev/null
    sleep 2
}

start_cmd_api() {
    log "Iniciando cmd_api.py (porta $CMD_API_PORT)..."
    
    # Criar cmd_api.py se nao existir
    if [ ! -f "$HOME/cmd_api.py" ]; then
        cat > "$HOME/cmd_api.py" << 'PYEOF'
from fastapi import FastAPI
from pydantic import BaseModel
import subprocess, os

app = FastAPI()

class Cmd(BaseModel):
    cmd: str
    timeout: int = 30

@app.post("/exec")
def execute(c: Cmd):
    try:
        r = subprocess.run(c.cmd, shell=True, capture_output=True, text=True,
                          timeout=c.timeout, cwd=os.path.expanduser("~"))
        return {"stdout": r.stdout, "stderr": r.stderr, "code": r.returncode}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "timeout", "code": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "code": -1}

@app.get("/health")
def health():
    url = ""
    try:
        with open(os.path.expanduser("~/.tunnel_url")) as f:
            url = f.read().strip()
    except: pass
    return {"status": "ok", "tunnel_url": url}

import uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)
PYEOF
        log "cmd_api.py criado"
    fi
    
    nohup python "$HOME/cmd_api.py" > "$LOG_DIR/cmd_api.log" 2>&1 &
    CMD_API_PID=$!
    sleep 2
    
    if kill -0 $CMD_API_PID 2>/dev/null; then
        log "cmd_api.py rodando (PID: $CMD_API_PID)"
        echo $CMD_API_PID > "$LOG_DIR/cmd_api.pid"
    else
        log "ERRO: cmd_api.py falhou ao iniciar"
        cat "$LOG_DIR/cmd_api.log"
    fi
}

start_rpa() {
    log "Iniciando RPA Gateway (porta $RPA_PORT)..."
    cd "$RPA_DIR" || { log "ERRO: pasta RPA não encontrada"; return 1; }
    
    nohup python api_server.py > "$LOG_DIR/rpa.log" 2>&1 &
    RPA_PID=$!
    sleep 3
    
    if kill -0 $RPA_PID 2>/dev/null; then
        log "RPA Gateway rodando (PID: $RPA_PID)"
        echo $RPA_PID > "$LOG_DIR/rpa.pid"
        
        # Verificar health
        HEALTH=$(curl -s http://localhost:$RPA_PORT/health 2>/dev/null)
        log "RPA Health: $HEALTH"
    else
        log "ERRO: RPA Gateway falhou"
        cat "$LOG_DIR/rpa.log" | tail -20
    fi
}

start_tunnel() {
    log "Iniciando tunnel persistente (auto_tunnel.sh)..."
    chmod +x "$RPA_DIR/auto_tunnel.sh"
    nohup bash "$RPA_DIR/auto_tunnel.sh" > "$LOG_DIR/tunnel.log" 2>&1 &
    TUNNEL_PID=$!
    echo $TUNNEL_PID > "$LOG_DIR/tunnel.pid"
    
    log "Aguardando URL do tunnel (até 20s)..."
    for i in $(seq 1 20); do
        sleep 1
        if [ -f "$HOME/.tunnel_url" ]; then
            URL=$(cat "$HOME/.tunnel_url")
            log "=== TUNNEL URL: $URL ==="
            break
        fi
    done
    
    if [ ! -f "$HOME/.tunnel_url" ]; then
        log "AVISO: URL do tunnel não capturada ainda. Verifique: tail -f $LOG_DIR/tunnel.log"
    fi
}

show_status() {
    log ""
    log "======================================="
    log "   BRANCA DE NEVE — STATUS FINAL"
    log "======================================="
    
    # cmd_api
    if pgrep -f "cmd_api.py" > /dev/null; then
        log "✅ cmd_api.py  → porta $CMD_API_PORT [RUNNING]"
    else
        log "❌ cmd_api.py  → STOPPED"
    fi
    
    # RPA
    if pgrep -f "api_server.py" > /dev/null; then
        log "✅ RPA Gateway → porta $RPA_PORT [RUNNING]"
    else
        log "❌ RPA Gateway → STOPPED"
    fi
    
    # Tunnel
    if pgrep -f "auto_tunnel.sh" > /dev/null || pgrep -f "ssh.*serveo" > /dev/null; then
        log "✅ Tunnel Serveo → [RUNNING]"
    else
        log "❌ Tunnel → STOPPED"
    fi
    
    # URL
    if [ -f "$HOME/.tunnel_url" ]; then
        log "🌐 URL: $(cat $HOME/.tunnel_url)"
    else
        log "⚠️  URL: aguardando..."
    fi
    
    log "======================================="
    log "Logs:"
    log "  cmd_api : tail -f $LOG_DIR/cmd_api.log"
    log "  RPA     : tail -f $LOG_DIR/rpa.log"
    log "  Tunnel  : tail -f $LOG_DIR/tunnel.log"
}

# ============================================================
# EXECUÇÃO
# ============================================================
log "=== INICIANDO BRANCA DE NEVE ==="
kill_existing
start_cmd_api
start_rpa
start_tunnel
show_status
