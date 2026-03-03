#!/usr/bin/env python3
"""
BRANCA DE NEVE 1.0 - Iniciador Completo
Inicia Backend + RPA em um único comando
"""
import subprocess
import sys
import os
import time
import threading
import signal

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REQUIREMENTS = [
    "fastapi>=0.100.0",
    "uvicorn>=0.23.0", 
    "httpx>=0.24.0",
    "pydantic>=2.0.0"
]

def print_banner():
    print()
    print("=" * 60)
    print("   BRANCA DE NEVE 1.0 - Sistema Completo")
    print("   Backend + RPA Gateway")
    print("=" * 60)
    print()


def install_dependencies():
    """Instala dependências se necessário"""
    marker = os.path.join(BASE_DIR, ".deps_ok")
    
    if os.path.exists(marker):
        print("[OK] Dependencias ja instaladas")
        return True
    
    print("[SETUP] Instalando dependencias...")
    
    for pkg in REQUIREMENTS:
        print(f"   Instalando {pkg}...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg, "-q"],
            capture_output=True
        )
        if result.returncode != 0:
            print(f"   [ERRO] Falha ao instalar {pkg}")
            return False
    
    with open(marker, "w") as f:
        f.write("ok")
    
    print("[OK] Dependencias instaladas!")
    return True


def check_config():
    """Verifica/cria config.json"""
    import json
    config_path = os.path.join(BASE_DIR, "config.json")
    
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)
        print(f"[CONFIG] PIN: {'*' * len(config.get('pin', ''))}")
        print(f"[CONFIG] Modo: {config.get('mode', 'termux')}")
        return config
    
    # Criar config padrão para Termux
    config = {
        "mode": "termux",
        "adb_path": "",
        "device_id": "",
        "pin": "222222",
        "audit_interval": 10,
        "package": "com.satsails.Satsails"
    }
    
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)
    
    print("[CONFIG] Arquivo criado com PIN padrao: 222222")
    print("[CONFIG] Edite config.json para alterar o PIN")
    return config


class ServiceRunner:
    def __init__(self):
        self.backend_proc = None
        self.rpa_proc = None
        self.running = True
    
    def start_backend(self):
        """Inicia o Backend SQLite na porta 8001"""
        print("[1/2] Iniciando Backend (porta 8001)...")
        
        backend_script = os.path.join(BASE_DIR, "backend_sqlite.py")
        
        self.backend_proc = subprocess.Popen(
            [sys.executable, backend_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=BASE_DIR
        )
        
        # Aguardar inicialização
        time.sleep(3)
        
        # Verificar
        try:
            import httpx
            r = httpx.get("http://localhost:8001/api/health", timeout=5)
            if r.status_code == 200:
                print("      Backend: OK")
                return True
        except:
            pass
        
        print("      Backend: FALHOU")
        return False
    
    def start_rpa(self):
        """Inicia o RPA Gateway na porta 8080"""
        print("[2/2] Iniciando RPA (porta 8080)...")
        
        env = os.environ.copy()
        env["NON_INTERACTIVE"] = "1"
        
        rpa_script = os.path.join(BASE_DIR, "main.py")
        
        self.rpa_proc = subprocess.Popen(
            [sys.executable, rpa_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=BASE_DIR
        )
        
        # Aguardar inicialização
        time.sleep(4)
        
        # Verificar
        try:
            import httpx
            r = httpx.get("http://localhost:8080/health", timeout=5)
            if r.status_code == 200:
                print("      RPA: OK")
                return True
        except:
            pass
        
        print("      RPA: FALHOU")
        return False
    
    def print_status(self):
        """Mostra URLs e status"""
        print()
        print("=" * 60)
        print("   SISTEMA INICIADO COM SUCESSO!")
        print("=" * 60)
        print()
        print("   Endpoints locais:")
        print("   - Backend:  http://localhost:8001/api")
        print("   - RPA:      http://localhost:8080")
        print()
        print("   Para acesso externo, inicie ngrok:")
        print("   ngrok http 8001")
        print()
        print("   Testes rapidos:")
        print("   curl http://localhost:8001/api/health")
        print("   curl http://localhost:8080/health")
        print("   curl http://localhost:8080/ver_tela")
        print()
        print("=" * 60)
        print("   Pressione Ctrl+C para parar")
        print("=" * 60)
        print()
    
    def stop(self):
        """Para todos os serviços"""
        self.running = False
        print()
        print("[STOP] Parando servicos...")
        
        if self.backend_proc:
            self.backend_proc.terminate()
            self.backend_proc.wait(timeout=5)
        
        if self.rpa_proc:
            self.rpa_proc.terminate()
            self.rpa_proc.wait(timeout=5)
        
        print("[STOP] Servicos parados!")
    
    def wait(self):
        """Aguarda até Ctrl+C"""
        try:
            while self.running:
                time.sleep(1)
                
                # Verificar se processos ainda estão rodando
                if self.backend_proc and self.backend_proc.poll() is not None:
                    print("[WARN] Backend parou inesperadamente!")
                    self.running = False
                
                if self.rpa_proc and self.rpa_proc.poll() is not None:
                    print("[WARN] RPA parou inesperadamente!")
                    self.running = False
                    
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()


def main():
    print_banner()
    
    # 1. Instalar dependências
    if not install_dependencies():
        print("[FATAL] Falha nas dependencias")
        sys.exit(1)
    
    # 2. Verificar config
    check_config()
    print()
    
    # 3. Iniciar serviços
    runner = ServiceRunner()
    
    # Handler para Ctrl+C
    def signal_handler(sig, frame):
        runner.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Iniciar Backend
    if not runner.start_backend():
        print("[FATAL] Backend falhou ao iniciar")
        sys.exit(1)
    
    # Iniciar RPA
    if not runner.start_rpa():
        print("[FATAL] RPA falhou ao iniciar")
        runner.stop()
        sys.exit(1)
    
    # Mostrar status
    runner.print_status()
    
    # Aguardar
    runner.wait()


if __name__ == "__main__":
    main()
