#!/usr/bin/env python3
"""
Script para executar comandos no Termux via API remota (Serveo tunnel)
Uso: python termux_exec.py "comando aqui"
"""
import sys
import json
import urllib.request
import urllib.error

BASE_URL = "https://67b479b4b200264a-152-255-124-131.serveousercontent.com"

def exec_cmd(cmd, timeout=20):
    """Executa um comando no Termux via POST /exec"""
    payload = json.dumps({"cmd": cmd, "timeout": timeout}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/exec",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout + 5) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result
    except urllib.error.HTTPError as e:
        return {"stdout": "", "stderr": f"HTTP {e.code}: {e.reason}", "code": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "code": -1}

def run(cmd, label=None, timeout=20):
    if label:
        print(f"\n{'='*50}")
        print(f">>> {label}")
        print(f"CMD: {cmd}")
        print('='*50)
    result = exec_cmd(cmd, timeout)
    if result.get("stdout"):
        print("STDOUT:", result["stdout"])
    if result.get("stderr"):
        print("STDERR:", result["stderr"])
    print(f"CODE: {result.get('code', '?')}")
    return result

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Modo direto: python termux_exec.py "comando"
        cmd = " ".join(sys.argv[1:])
        run(cmd)
    else:
        # Modo diagnóstico completo
        print("=== DIAGNÓSTICO COMPLETO DO TERMUX ===")
        
        run("echo $HOME && whoami && id",
            label="1. Usuário atual")
        
        run("ls /data/data/com.termux/files/home/branca/rpa_standalone/ 2>&1",
            label="2. Arquivos do RPA")
        
        run("ls /system/xbin/su 2>&1",
            label="3. Binário su disponível")
        
        run("ps -A 2>/dev/null | grep -E 'python|satsail' | grep -v grep",
            label="4. Processos Python/SatSails rodando")
        
        run("cat /data/data/com.termux/files/home/branca/rpa_standalone/config.json 2>&1",
            label="5. config.json do RPA")
        
        run("/system/xbin/su -c 'pm list packages | grep satsail' 2>&1",
            label="6. SatSails instalado (com root)",
            timeout=15)
