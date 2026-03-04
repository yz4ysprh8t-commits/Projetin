#!/usr/bin/env python3
"""
Script para testar o RPA Gateway - gera HMAC e envia comandos.
"""
import json
import time
import hmac
import hashlib
import urllib.request
import urllib.error
import sys

BASE_URL = "https://67b479b4b200264a-152-255-124-131.serveousercontent.com"
RPA_LOCAL = "http://localhost:8080"
HMAC_SECRET = "branca_neve_hmac_2026_s3cr3t"

def exec_cmd(cmd, timeout=15):
    """Executa comando no Termux via cmd_api.py"""
    payload = json.dumps({"cmd": cmd, "timeout": timeout}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/exec", data=payload,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout + 5) as resp:
        return json.loads(resp.read().decode("utf-8"))

def rpa_get(path):
    """GET direto ao RPA via cmd_api"""
    r = exec_cmd(f"curl -s {RPA_LOCAL}{path} 2>&1", timeout=20)
    try:
        return json.loads(r["stdout"])
    except:
        return r

def make_hmac(payload_str):
    """Gera assinatura HMAC-SHA256"""
    ts = str(int(time.time()))
    message = f"{ts}.{payload_str}".encode()
    sig = hmac.new(HMAC_SECRET.encode(), message, hashlib.sha256).hexdigest()
    return ts, sig

def rpa_pagar(valor, tx_id=None, webhook=""):
    """Envia pedido de pagamento PIX ao RPA com HMAC correto"""
    if not tx_id:
        tx_id = f"test_{int(time.time())}"
    
    payload_dict = {"valor": valor, "transaction_id": tx_id, "webhook_url": webhook}
    payload_str = json.dumps(payload_dict)
    ts, sig = make_hmac(payload_str)
    
    curl_cmd = (
        f"curl -s -X POST {RPA_LOCAL}/pagar "
        f"-H 'Content-Type: application/json' "
        f"-H 'X-RPA-Signature: {sig}' "
        f"-H 'X-RPA-Timestamp: {ts}' "
        f"-d '{payload_str}' 2>&1"
    )
    r = exec_cmd(curl_cmd, timeout=15)
    try:
        return json.loads(r["stdout"])
    except:
        return r

def status_tx(tx_id):
    """Verifica status de uma transação"""
    ts, sig = make_hmac(tx_id)
    curl_cmd = (
        f"curl -s {RPA_LOCAL}/status/{tx_id} "
        f"-H 'X-RPA-Signature: {sig}' "
        f"-H 'X-RPA-Timestamp: {ts}' 2>&1"
    )
    r = exec_cmd(curl_cmd, timeout=15)
    try:
        return json.loads(r["stdout"])
    except:
        return r


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "diag"
    
    if cmd == "health":
        print("=== RPA HEALTH ===")
        print(json.dumps(rpa_get("/health"), indent=2, ensure_ascii=False))
        
    elif cmd == "logs":
        print("=== RPA LOGS ===")
        r = rpa_get("/logs")
        for log in (r.get("logs") or []):
            print(log)
            
    elif cmd == "tela":
        print("=== TELA ATUAL ===")
        print(json.dumps(rpa_get("/ver_tela"), indent=2, ensure_ascii=False))
        
    elif cmd == "pagar":
        valor = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
        tx_id = sys.argv[3] if len(sys.argv) > 3 else f"test_{int(time.time())}"
        print(f"=== SOLICITANDO PIX R$ {valor} (tx: {tx_id}) ===")
        r = rpa_pagar(valor, tx_id)
        print(json.dumps(r, indent=2, ensure_ascii=False))
        
    elif cmd == "status":
        tx_id = sys.argv[2] if len(sys.argv) > 2 else "test_001"
        print(f"=== STATUS TX: {tx_id} ===")
        print(json.dumps(status_tx(tx_id), indent=2, ensure_ascii=False))
        
    elif cmd == "pendentes":
        print("=== PENDENTES ===")
        print(json.dumps(rpa_get("/pendentes"), indent=2, ensure_ascii=False))
        
    elif cmd == "auditar":
        print("=== AUDITORIA FORÇADA ===")
        r = exec_cmd(f"curl -s -X POST {RPA_LOCAL}/auditar 2>&1", timeout=30)
        try:
            print(json.dumps(json.loads(r["stdout"]), indent=2, ensure_ascii=False))
        except:
            print(r)
    
    elif cmd == "diag":
        print("=== DIAGNÓSTICO COMPLETO ===")
        
        print("\n[1] Health:")
        print(json.dumps(rpa_get("/health"), indent=2, ensure_ascii=False))
        
        print("\n[2] Logs:")
        r = rpa_get("/logs")
        for log in (r.get("logs") or []):
            print(" ", log)
        
        print("\n[3] Tela atual:")
        tela = rpa_get("/ver_tela")
        print(f"  tela: {tela.get('tela')}")
        print(f"  descs: {tela.get('descs')}")
        
        print("\n[4] Pendentes:")
        print(json.dumps(rpa_get("/pendentes"), indent=2, ensure_ascii=False))
    
    else:
        print("Uso: python rpa_test.py [health|logs|tela|pagar [valor] [tx_id]|status [tx_id]|pendentes|auditar|diag]")
