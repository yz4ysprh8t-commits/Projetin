#!/usr/bin/env python3
import subprocess
import sys
import os
import json
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
REQUIREMENTS_PATH = os.path.join(BASE_DIR, "requirements.txt")
INSTALL_MARKER = os.path.join(BASE_DIR, ".deps_installed")


def print_banner():
    print()
    print("=" * 55)
    print("   BRANCA DE NEVE 1.0 - RPA Gateway Standalone")
    print("   Automacao SatSails - PIX + Conversao BTC")
    print("=" * 55)
    print()


def install_dependencies():
    if os.path.exists(INSTALL_MARKER):
        return True

    print("[SETUP] Instalando dependencias automaticamente...")
    print()

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS_PATH, "--quiet"],
            capture_output=True, text=True, timeout=120
        )

        if result.returncode != 0:
            print("[ERRO] Falha ao instalar dependencias:")
            print(result.stderr)
            print()
            print("Tente manualmente: pip install -r requirements.txt")
            return False

        with open(INSTALL_MARKER, "w") as f:
            f.write("ok")

        print("[OK] Dependencias instaladas com sucesso!")
        print()
        return True

    except subprocess.TimeoutExpired:
        print("[ERRO] Timeout na instalacao. Verifique sua conexao.")
        return False
    except Exception as e:
        print(f"[ERRO] {e}")
        return False


def detect_mode():
    adb_path = shutil.which("adb")
    if adb_path:
        try:
            result = subprocess.run(
                [adb_path, "devices"], capture_output=True, text=True, timeout=5
            )
            lines = [l for l in result.stdout.strip().split("\n")[1:] if l.strip() and "device" in l]
            if lines:
                device_id = lines[0].split("\t")[0]
                return "adb", adb_path, device_id
        except Exception:
            pass
        return "adb", adb_path, ""

    if os.path.exists("/data/data/com.termux"):
        return "termux"

    return "adb", "adb", ""


def setup_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
        print(f"[CONFIG] Configuracao encontrada:")
        print(f"   Modo: {config.get('mode', 'adb')}")
        print(f"   Device: {config.get('device_id', '(vazio)')}")
        print(f"   PIN: {'*' * len(config.get('pin', ''))}")
        print(f"   Auditoria: a cada {config.get('audit_interval', 10)}s")
        print()
        is_interactive = sys.stdin.isatty() and os.environ.get("NON_INTERACTIVE") != "1"
        if not is_interactive:
            print("[CONFIG] Modo nao-interativo, usando config existente.")
            return config
        try:
            resp = input("Manter configuracao atual? (S/n): ").strip().lower()
            if resp not in ("n", "nao", "no"):
                return config
        except (EOFError, OSError):
            return config

    print()
    print("[CONFIG] Configuracao inicial do RPA")
    print("-" * 40)

    detection = detect_mode()

    if detection == "termux":
        mode = "termux"
        adb_path = ""
        device_id = ""
        print("   Detectado: Termux (Android local)")
    else:
        _, adb_path, device_id = detection
        if device_id:
            print(f"   Detectado: Emulador ADB (device: {device_id})")
        else:
            print("   Detectado: Modo ADB (nenhum device conectado)")

        mode_input = input("   Modo [adb/termux] (adb): ").strip().lower()
        mode = mode_input if mode_input in ("adb", "termux") else "adb"

        if mode == "adb":
            adb_input = input(f"   Caminho do ADB ({adb_path or 'adb'}): ").strip()
            adb_path = adb_input or adb_path or "adb"

            device_input = input(f"   Device ID ({device_id or 'auto'}): ").strip()
            device_id = device_input or device_id

    pin = input("   PIN do SatSails (222222): ").strip() or "222222"

    audit_input = input("   Intervalo auditoria segundos (10): ").strip()
    try:
        audit_interval = int(audit_input) if audit_input else 10
    except ValueError:
        audit_interval = 10

    config = {
        "mode": mode,
        "adb_path": adb_path if mode == "adb" else "",
        "device_id": device_id if mode == "adb" else "",
        "pin": pin,
        "audit_interval": audit_interval,
        "package": "com.satsails.Satsails"
    }

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)

    print()
    print("[OK] Configuracao salva!")
    print()
    return config


def check_adb_connection(config):
    if config.get("mode") != "adb":
        return True

    adb = config.get("adb_path", "adb")
    device = config.get("device_id", "")

    print("[CHECK] Verificando conexao ADB...")

    if device:
        print(f"[ADB] Conectando a {device}...")
        try:
            result = subprocess.run(
                [adb, "connect", device],
                capture_output=True, text=True, timeout=10
            )
            print(f"   {result.stdout.strip()}")
        except Exception as e:
            print(f"   [AVISO] Erro ao conectar: {e}")

    cmd = [adb, "devices"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        lines = [l for l in result.stdout.strip().split("\n")[1:] if l.strip() and "device" in l]

        if not lines:
            print("[AVISO] Nenhum dispositivo ADB conectado!")
            print("   O servidor vai iniciar mesmo assim.")
            print()
            return True

        if device:
            found = any(device in l for l in lines)
            if found:
                print(f"[OK] Dispositivo {device} conectado!")
            else:
                print(f"[AVISO] Dispositivo {device} nao encontrado, mas ha outros:")
                for l in lines:
                    print(f"   {l}")
        else:
            print(f"[OK] {len(lines)} dispositivo(s) conectado(s):")
            for l in lines:
                print(f"   {l}")

        print()
        return True

    except FileNotFoundError:
        print(f"[ERRO] ADB nao encontrado em '{adb}'")
        print()
        return True
    except Exception as e:
        print(f"[AVISO] Erro ao verificar ADB: {e}")
        print()
        return True


def start_server(config):
    port = int(os.environ.get("RPA_PORT", "8080"))

    print("=" * 55)
    print(f"   Servidor RPA iniciando na porta {port}")
    print(f"   Modo: {config.get('mode', 'adb')}")
    print(f"   Acesse: http://localhost:{port}/health")
    print(f"   Docs:   http://localhost:{port}/docs")
    print("=" * 55)
    print()
    print("   Endpoints disponiveis:")
    print(f"   POST /pagar            - Criar pagamento PIX")
    print(f"   GET  /status/{{id}}      - Consultar status")
    print(f"   GET  /pendentes        - Listar pendentes")
    print(f"   POST /auditar          - Forcar auditoria")
    print(f"   POST /converter/depix-lbtc - Converter Depix -> LBTC")
    print(f"   POST /converter/lbtc-btc   - Converter LBTC -> BTC")
    print(f"   POST /saque            - Saque automatico completo")
    print(f"   GET  /health           - Health check")
    print(f"   GET  /logs             - Ver logs recentes")
    print(f"   GET  /config           - Ver configuracao")
    print(f"   POST /config           - Atualizar configuracao")
    print(f"   POST /worker/restart   - Reiniciar worker")
    print()
    print("   Pressione Ctrl+C para parar")
    print()

    sys.path.insert(0, BASE_DIR)
    from api_server import app
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)


def main():
    print_banner()

    if not install_dependencies():
        print("[FATAL] Nao foi possivel instalar dependencias. Abortando.")
        sys.exit(1)

    config = setup_config()

    check_adb_connection(config)

    start_server(config)


if __name__ == "__main__":
    main()
