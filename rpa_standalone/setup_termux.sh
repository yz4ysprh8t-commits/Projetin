#!/bin/bash
echo "=== Setup RPA Standalone no Termux (Emulador LDPlayer) ==="
echo ""

pkg update -y && pkg upgrade -y
pkg install -y python git wget openssh android-tools

echo ""
echo "[1/3] Instalando dependencias Python..."
pip install fastapi uvicorn httpx aiosqlite

echo ""
echo "[2/3] Configurando ADB local..."
adb start-server
adb connect 127.0.0.1:5555
adb devices

echo ""
echo "[3/3] Baixando ngrok..."
ARCH=$(uname -m)
if [ "$ARCH" = "aarch64" ]; then
    wget -q https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm64.tgz -O ngrok.tgz
elif [ "$ARCH" = "armv7l" ] || [ "$ARCH" = "armv8l" ]; then
    wget -q https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm.tgz -O ngrok.tgz
elif [ "$ARCH" = "x86_64" ]; then
    wget -q https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz -O ngrok.tgz
elif [ "$ARCH" = "i686" ]; then
    wget -q https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-386.tgz -O ngrok.tgz
else
    echo "Arquitetura desconhecida: $ARCH"
    echo "Tente baixar manualmente em ngrok.com"
fi

if [ -f "ngrok.tgz" ]; then
    tar xf ngrok.tgz
    rm ngrok.tgz
    chmod +x ngrok
    echo "ngrok instalado!"
fi

echo ""
echo "============================================"
echo "  SETUP CONCLUIDO!"
echo "============================================"
echo ""
echo "PROXIMOS PASSOS:"
echo ""
echo "1. Configurar ngrok (uma vez so):"
echo "   - Crie conta em ngrok.com"
echo "   - Copie seu Authtoken do dashboard"
echo "   - ./ngrok config add-authtoken SEU_TOKEN"
echo ""
echo "2. Iniciar o RPA + tunel:"
echo "   bash start_rpa.sh"
echo ""
echo "IMPORTANTE: O RPA usa modo ADB conectando em"
echo "127.0.0.1:5555 (ADB local do emulador)."
echo "Isso resolve o problema de permissoes do Termux"
echo "para executar uiautomator e outros comandos."
echo ""
