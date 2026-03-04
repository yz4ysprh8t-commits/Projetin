#!/data/data/com.termux/files/usr/bin/bash
# =============================================================================
# BRANCA DE NEVE 1.0 - INSTALADOR TERMUX ONE-SHOT
# =============================================================================
# Uso: curl -sL <URL> | bash
# Ou:  ./install_termux.sh
# =============================================================================

set -e

echo ""
echo "=========================================="
echo "  BRANCA DE NEVE 1.0 - Instalador Termux"
echo "=========================================="
echo ""

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERRO]${NC} $1"; }

# =============================================================================
# 1. VERIFICAR TERMUX
# =============================================================================
log_info "Verificando ambiente Termux..."

if [ ! -d "/data/data/com.termux" ]; then
    log_error "Este script deve rodar no Termux!"
    exit 1
fi

# =============================================================================
# 2. ATUALIZAR PACOTES
# =============================================================================
log_info "Atualizando pacotes do Termux..."
pkg update -y
pkg upgrade -y

# =============================================================================
# 3. INSTALAR DEPENDENCIAS DO SISTEMA
# =============================================================================
log_info "Instalando dependencias do sistema..."
pkg install -y python git curl wget openssh

# =============================================================================
# 4. CONFIGURAR STORAGE (se necessario)
# =============================================================================
if [ ! -d "$HOME/storage" ]; then
    log_info "Configurando acesso ao storage..."
    termux-setup-storage || true
    sleep 2
fi

# =============================================================================
# 5. CLONAR REPOSITORIO
# =============================================================================
REPO_URL="https://github.com/yz4ysprh8t-commits/Projetin.git"
INSTALL_DIR="$HOME/branca_de_neve"

if [ -d "$INSTALL_DIR" ]; then
    log_warn "Diretorio existente, atualizando..."
    cd "$INSTALL_DIR"
    git pull || true
else
    log_info "Clonando repositorio..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR/compact/rpa_standalone"

# =============================================================================
# 6. INSTALAR DEPENDENCIAS PYTHON
# =============================================================================
log_info "Instalando dependencias Python..."

# Criar requirements combinado (RPA + Backend)
cat > requirements_full.txt << 'EOF'
fastapi>=0.100.0
uvicorn>=0.23.0
httpx>=0.24.0
aiosqlite>=0.19.0
pydantic>=2.0.0
python-dotenv>=1.0.0
EOF

pip install --upgrade pip
pip install -r requirements_full.txt

# =============================================================================
# 7. CRIAR SCRIPTS DE INICIALIZACAO
# =============================================================================
log_info "Criando scripts de inicializacao..."

# Script principal
cat > start.sh << 'SCRIPT'
#!/data/data/com.termux/files/usr/bin/bash
# Inicia Backend + RPA + ngrok

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo ""
echo "=========================================="
echo "  BRANCA DE NEVE 1.0 - Iniciando..."
echo "=========================================="
echo ""

# Matar processos anteriores
pkill -f "uvicorn" 2>/dev/null || true
pkill -f "ngrok" 2>/dev/null || true
sleep 1

# Iniciar Backend (porta 8001)
echo "[1/3] Iniciando Backend (porta 8001)..."
python backend_sqlite.py &
BACKEND_PID=$!
sleep 3

# Verificar Backend
if curl -s http://localhost:8001/api/health > /dev/null; then
    echo "      Backend OK!"
else
    echo "      Backend FALHOU!"
    exit 1
fi

# Iniciar RPA (porta 8080)
echo "[2/3] Iniciando RPA (porta 8080)..."
NON_INTERACTIVE=1 python main.py &
RPA_PID=$!
sleep 3

# Verificar RPA
if curl -s http://localhost:8080/health > /dev/null; then
    echo "      RPA OK!"
else
    echo "      RPA FALHOU!"
    exit 1
fi

# Iniciar ngrok
echo "[3/3] Iniciando ngrok..."
if command -v ngrok &> /dev/null; then
    ngrok http 8001 --log=stdout > ngrok.log 2>&1 &
    NGROK_PID=$!
    sleep 5
    
    # Pegar URL do ngrok
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | grep -o '"public_url":"[^"]*' | head -1 | cut -d'"' -f4)
    
    if [ -n "$NGROK_URL" ]; then
        echo ""
        echo "=========================================="
        echo "  SISTEMA INICIADO COM SUCESSO!"
        echo "=========================================="
        echo ""
        echo "  Backend Local:  http://localhost:8001"
        echo "  RPA Local:      http://localhost:8080"
        echo "  URL Externa:    $NGROK_URL"
        echo ""
        echo "  Para testar:"
        echo "  curl $NGROK_URL/api/health"
        echo ""
        echo "  PIDs: Backend=$BACKEND_PID RPA=$RPA_PID ngrok=$NGROK_PID"
        echo "=========================================="
    else
        echo "      ngrok iniciou mas URL nao disponivel"
        echo "      Verifique: curl http://localhost:4040/api/tunnels"
    fi
else
    echo ""
    echo "=========================================="
    echo "  SISTEMA INICIADO (SEM NGROK)"
    echo "=========================================="
    echo ""
    echo "  Backend: http://localhost:8001"
    echo "  RPA:     http://localhost:8080"
    echo ""
    echo "  ngrok nao instalado. Para acesso externo:"
    echo "  pkg install ngrok"
    echo "  ngrok authtoken SEU_TOKEN"
    echo "=========================================="
fi

# Manter rodando
echo ""
echo "Pressione Ctrl+C para parar..."
wait
SCRIPT

chmod +x start.sh

# Script para parar
cat > stop.sh << 'SCRIPT'
#!/data/data/com.termux/files/usr/bin/bash
echo "Parando servicos..."
pkill -f "uvicorn" 2>/dev/null || true
pkill -f "python main.py" 2>/dev/null || true
pkill -f "ngrok" 2>/dev/null || true
echo "Servicos parados!"
SCRIPT

chmod +x stop.sh

# Script de status
cat > status.sh << 'SCRIPT'
#!/data/data/com.termux/files/usr/bin/bash
echo ""
echo "=== STATUS DOS SERVICOS ==="
echo ""

echo -n "Backend (8001): "
if curl -s http://localhost:8001/api/health > /dev/null 2>&1; then
    echo "ONLINE"
else
    echo "OFFLINE"
fi

echo -n "RPA (8080):     "
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo "ONLINE"
else
    echo "OFFLINE"
fi

echo -n "ngrok:          "
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | grep -o '"public_url":"[^"]*' | head -1 | cut -d'"' -f4)
if [ -n "$NGROK_URL" ]; then
    echo "$NGROK_URL"
else
    echo "OFFLINE"
fi
echo ""
SCRIPT

chmod +x status.sh

# =============================================================================
# 8. CRIAR CONFIG PADRAO
# =============================================================================
if [ ! -f "config.json" ]; then
    log_info "Criando configuracao padrao..."
    cat > config.json << 'EOF'
{
    "mode": "termux",
    "adb_path": "",
    "device_id": "",
    "pin": "222222",
    "audit_interval": 10,
    "package": "com.satsails.Satsails"
}
EOF
fi

# =============================================================================
# 9. INSTRUCOES FINAIS
# =============================================================================
echo ""
echo "=========================================="
echo -e "${GREEN}  INSTALACAO CONCLUIDA!${NC}"
echo "=========================================="
echo ""
echo "  Diretorio: $INSTALL_DIR/compact/rpa_standalone"
echo ""
echo "  Comandos disponiveis:"
echo "    ./start.sh   - Iniciar tudo"
echo "    ./stop.sh    - Parar tudo"
echo "    ./status.sh  - Ver status"
echo ""
echo "  Antes de iniciar:"
echo "    1. Configure o PIN em config.json"
echo "    2. Certifique que SatSails esta instalado"
echo "    3. (Opcional) Configure ngrok: ngrok authtoken SEU_TOKEN"
echo ""
echo "  Para iniciar agora:"
echo "    cd $INSTALL_DIR/compact/rpa_standalone"
echo "    ./start.sh"
echo ""
echo "=========================================="
