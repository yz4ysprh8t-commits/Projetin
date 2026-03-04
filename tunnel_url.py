#!/usr/bin/env python3
"""
tunnel_url.py — Descobre a URL atual do tunnel Serveo no Termux
Uso: python tunnel_url.py
     python tunnel_url.py --set  (atualiza SERVEO_URL em rpa_test.py e run_tests.py)

A URL é lida do arquivo ~/.tunnel_url no Termux via cmd_api.py.
A última URL conhecida é salva em .tunnel_url_cache para uso offline.
"""
import json, sys, os, urllib.request, urllib.error

LAST_KNOWN_URLS = [
    "https://67b479b4b200264a-152-255-124-131.serveousercontent.com",  # última sessão conhecida
]
CACHE_FILE = os.path.join(os.path.dirname(__file__), ".tunnel_url_cache")

def try_health(url):
    """Testa se a URL está respondendo"""
    try:
        req = urllib.request.Request(f"{url}/health", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
            return data.get("status") == "ok", data
    except:
        return False, {}

def get_tunnel_url_from_termux(base_url):
    """Pergunta ao cmd_api.py qual é a URL do tunnel atual"""
    try:
        payload = json.dumps({"cmd": "cat ~/.tunnel_url 2>/dev/null || echo 'NOT_FOUND'", "timeout": 5}).encode()
        req = urllib.request.Request(
            f"{base_url}/exec", data=payload,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
            url = data.get("stdout", "").strip()
            if url and url != "NOT_FOUND" and url.startswith("https://"):
                return url
    except:
        pass
    return None

def discover():
    """Descobre a URL ativa atual"""
    # 1. Tentar URL do cache
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            cached = f.read().strip()
        if cached:
            ok, data = try_health(cached)
            if ok:
                print(f"✅ URL ativa (cache): {cached}")
                # Buscar URL atual do tunnel
                tunnel_url = get_tunnel_url_from_termux(cached)
                if tunnel_url and tunnel_url != cached:
                    print(f"ℹ️  URL do tunnel atual: {tunnel_url}")
                    return tunnel_url
                return cached

    # 2. Tentar URLs conhecidas
    for url in LAST_KNOWN_URLS:
        ok, data = try_health(url)
        if ok:
            print(f"✅ URL ativa (conhecida): {url}")
            # Salvar no cache
            with open(CACHE_FILE, "w") as f:
                f.write(url)
            # Buscar URL do tunnel
            tunnel_url = get_tunnel_url_from_termux(url)
            if tunnel_url and tunnel_url != url:
                print(f"ℹ️  URL do tunnel atual: {tunnel_url}")
                # Atualizar cache com a URL do cmd_api (que pode ser diferente)
                with open(CACHE_FILE, "w") as f:
                    f.write(url)  # mantém a do cmd_api pois é quem responde
                return tunnel_url
            return url

    print("❌ Nenhuma URL ativa encontrada.")
    print("\nAção necessária:")
    print("1. No Termux, execute: bash ~/branca/rpa_standalone/auto_start.sh")
    print("2. Copie a URL exibida (https://XXXXX.serveousercontent.com)")
    print("3. Execute: python tunnel_url.py --update https://SUA-URL-AQUI")
    return None

def update_url_in_files(new_url):
    """Atualiza a SERVEO_URL nos scripts Python"""
    files = ["rpa_test.py", "run_tests.py", "termux_exec.py"]
    base_dir = os.path.dirname(__file__)
    updated = []
    
    for fname in files:
        fpath = os.path.join(base_dir, fname)
        if not os.path.exists(fpath):
            continue
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Substituir qualquer URL do Serveo
        import re
        new_content = re.sub(
            r'https://[a-z0-9\-]+\.serveousercontent\.com',
            new_url, content
        )
        if new_content != content:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(new_content)
            updated.append(fname)
            print(f"  ✅ {fname} atualizado")
    
    # Salvar cache
    with open(CACHE_FILE, "w") as f:
        f.write(new_url)
    
    if not updated:
        print("  ℹ️  Nenhum arquivo precisou ser atualizado")
    return updated

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        if sys.argv[1] == "--update" and len(sys.argv) >= 3:
            new_url = sys.argv[2].rstrip("/")
            print(f"\n🔄 Atualizando URL para: {new_url}")
            ok, data = try_health(new_url)
            if ok:
                print(f"✅ URL respondendo: {data}")
                update_url_in_files(new_url)
            else:
                print(f"⚠️  URL não respondendo, mas atualizando mesmo assim...")
                update_url_in_files(new_url)
        elif sys.argv[1] == "--set":
            url = discover()
            if url:
                print(f"\n🔄 Atualizando scripts com: {url}")
                update_url_in_files(url)
        else:
            print(f"Uso: python tunnel_url.py [--set | --update URL]")
    else:
        url = discover()
        if url:
            print(f"\nPara atualizar todos os scripts: python tunnel_url.py --update {url}")
