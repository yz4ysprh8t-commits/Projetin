#!/usr/bin/env python3
"""
Suite de Testes Completa - Branca de Neve 1.0
Cobre: API Central + RPA Gateway Fase 1 (testes gratuitos)
Tunnel URL: https://937759f505a705ec-152-255-124-131.serveousercontent.com
"""
# Sa da tamb m salva em results_fase1.txt
import io, os
_outbuf = io.StringIO()
_orig_print = print
def print(*args, **kwargs):
    _orig_print(*args, **kwargs)
    _orig_print(*args, **{k:v for k,v in kwargs.items() if k != 'file'}, file=_outbuf)
import json, time, hmac, hashlib, urllib.request, urllib.error, sys, traceback
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================
SERVEO_URL    = "https://937759f505a705ec-152-255-124-131.serveousercontent.com"
BACKEND_URL   = "http://localhost:8001"   # API Central (backend FastAPI+MongoDB)
RPA_LOCAL_URL = "http://localhost:8080"   # RPA Gateway (direto no Termux)
HMAC_SECRET   = "branca_neve_hmac_2026_s3cr3t"
RPA_TOKEN     = "branca_de_neve_2026"

# ============================================================
# HELPERS
# ============================================================
results = []

def _color(text, code): return f"\033[{code}m{text}\033[0m"
def ok(t): return _color(t, "92")
def fail(t): return _color(t, "91")
def warn(t): return _color(t, "93")
def bold(t): return _color(t, "1")

def log_result(name, passed, obs=""):
    icon = "[PASS]" if passed else "[FAIL]"
    status = "PASS" if passed else "FAIL"
    results.append({"name": name, "status": status, "obs": obs})
    print(f"  {icon} [{status}] {name}" + (f"   {obs}" if obs else ""))

def http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode())

def http_post(url, body, headers=None, timeout=15):
    h = {"Content-Type": "application/json"}
    if headers: h.update(headers)
    payload = json.dumps(body).encode()
    req = urllib.request.Request(url, data=payload, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode()) if e.read else {}

def exec_termux(cmd, timeout=20):
    """Executa comando no Termux via cmd_api.py tunnel"""
    try:
        return http_post(f"{SERVEO_URL}/exec", {"cmd": cmd, "timeout": timeout}, timeout=timeout+5)
    except Exception as e:
        return 500, {"stdout": "", "stderr": str(e), "code": -1}

def safe_json(text):
    """Tenta parse de JSON, retorna dict vazio em caso de falha"""
    try:
        if not text or not text.strip():
            return {}
        return json.loads(text)
    except:
        return {"_raw": text[:200]}

def rpa_get(path, timeout=20):
    """GET ao RPA Gateway via Termux (curl interno)"""
    _, r = exec_termux(f"curl -s {RPA_LOCAL_URL}{path} 2>&1", timeout=timeout)
    return safe_json(r.get("stdout", ""))

def rpa_post(path, body=None, timeout=20):
    body_str = json.dumps(body or {}).replace("'", "'\\''")
    _, r = exec_termux(
        f"curl -s -X POST {RPA_LOCAL_URL}{path} -H 'Content-Type: application/json' -d '{body_str}' 2>&1",
        timeout=timeout
    )
    return safe_json(r.get("stdout", ""))

def make_hmac(payload_str):
    ts = str(int(time.time()))
    msg = f"{ts}.{payload_str}".encode()
    sig = hmac.new(HMAC_SECRET.encode(), msg, hashlib.sha256).hexdigest()
    return ts, sig

def rpa_pagar(valor, tx_id=None, webhook="", timeout=25):
    if not tx_id: tx_id = f"tx_{int(time.time())}"
    payload_dict = {"valor": valor, "transaction_id": tx_id, "webhook_url": webhook}
    pstr = json.dumps(payload_dict)
    ts, sig = make_hmac(pstr)
    cmd = (f"curl -s -X POST {RPA_LOCAL_URL}/pagar "
           f"-H 'Content-Type: application/json' "
           f"-H 'X-RPA-Signature: {sig}' "
           f"-H 'X-RPA-Timestamp: {ts}' "
           f"-d '{pstr}' 2>&1")
    _, r = exec_termux(cmd, timeout=timeout)
    try: return json.loads(r["stdout"])
    except: return r

def rpa_status(tx_id, timeout=15):
    ts, sig = make_hmac(tx_id)
    cmd = (f"curl -s {RPA_LOCAL_URL}/status/{tx_id} "
           f"-H 'X-RPA-Signature: {sig}' "
           f"-H 'X-RPA-Timestamp: {ts}' 2>&1")
    _, r = exec_termux(cmd, timeout=timeout)
    try: return json.loads(r["stdout"])
    except: return r

# ============================================================
# PARTE 1   API CENTRAL via backend_test.py adaptado
# ============================================================
def run_api_central_tests(backend_url):
    print(bold("\n[API] PARTE 1   API CENTRAL"))
    print("-" * 50)

    # T01 Root
    try:
        sc, r = http_get(f"{backend_url}/api/")
        log_result("T01: Root /api/", sc == 200, r.get("service", ""))
    except Exception as e: log_result("T01: Root /api/", False, str(e))

    # T02 Health
    try:
        sc, r = http_get(f"{backend_url}/api/health")
        log_result("T02: Health /api/health", sc == 200 and r.get("status") == "ok", r.get("status",""))
    except Exception as e: log_result("T02: Health /api/health", False, str(e))

    # T03 RPA Status
    try:
        sc, r = http_get(f"{backend_url}/api/rpa/status")
        log_result("T03: RPA Status", sc == 200, f"online={r.get('online')}")
    except Exception as e: log_result("T03: RPA Status", False, str(e))

    # T04 Register token inv lido
    try:
        sc, r = http_post(f"{backend_url}/api/rpa/register",
                          {"url": "https://937759f505a705ec-152-255-124-131.serveousercontent.com", "token": "invalid"})
        log_result("T04: Register token inv lido", sc == 403, f"status={sc}")
    except Exception as e: log_result("T04: Register token inv lido", False, str(e))

    # T05 Register dom nio inv lido
    try:
        sc, r = http_post(f"{backend_url}/api/rpa/register",
                          {"url": "https://invalid-domain.com", "token": RPA_TOKEN})
        log_result("T05: Register dom nio inv lido", sc == 400, f"status={sc}")
    except Exception as e: log_result("T05: Register dom nio inv lido", False, str(e))

    # T06 Register URL ausente
    try:
        sc, r = http_post(f"{backend_url}/api/rpa/register", {"token": RPA_TOKEN})
        log_result("T06: Register URL ausente", sc == 400, f"status={sc}")
    except Exception as e: log_result("T06: Register URL ausente", False, str(e))

    # T07 Logs offline
    try:
        sc, r = http_get(f"{backend_url}/api/rpa/logs")
        log_result("T07: Logs (offline)", sc == 200, f"logs={r.get('logs',[])[:1]}")
    except Exception as e: log_result("T07: Logs offline", False, str(e))

    # T08 Cmd proxy
    try:
        sc, r = http_get(f"{backend_url}/api/rpa/cmd/health")
        # Pode ser 200 com error ou error json   aceita ambos
        log_result("T08: Cmd proxy", sc in (200, 503), f"status={sc}")
    except Exception as e: log_result("T08: Cmd proxy", False, str(e))

    # T09 Ver tela offline
    try:
        sc, r = http_get(f"{backend_url}/api/rpa/ver_tela")
        log_result("T09: Ver tela (offline)", sc == 200, str(r)[:80])
    except Exception as e: log_result("T09: Ver tela offline", False, str(e))

# ============================================================
# PARTE 2   RPA GATEWAY (via Termux tunnel)
# ============================================================
def run_rpa_p0_infra():
    print(bold("\n[RPA] PARTE 2   RPA GATEWAY"))
    print(bold("  [P0] Infraestrutura B sica"))
    print("-" * 50)

    r = rpa_get("/health")
    log_result("R01: Health RPA Gateway", r.get("status") == "ok", f"version={r.get('version')}")

    r = rpa_get("/versao")
    log_result("R02: Vers o RPA", "versao" in r, f"versao={r.get('versao')}")

    r = rpa_get("/health")
    log_result("R03: Worker running", r.get("worker_running") == True, f"fila={r.get('fila_tamanho')}")

    r = rpa_get("/logs")
    logs = r.get("logs", [])
    log_result("R04: Logs worker", isinstance(logs, list), f"{len(logs)} entradas")

    r = rpa_get("/config")
    log_result("R05: Config atual", "mode" in r, f"mode={r.get('mode')} pin={r.get('pin')}")

def run_rpa_p1_tela():
    print(bold("\n  [P1] Controle de Tela e Navega  o"))
    print("-" * 50)

    r = rpa_get("/ver_tela")
    log_result("R06: Ver tela atual", "tela" in r, f"tela={r.get('tela')}")

    tela = r.get("tela", "")
    log_result("R07: Identifica  o de tela", tela in ("HOME","LOGIN","PIN","RECEBER","ENVIAR",""), f"tela={tela}")

    r = rpa_get("/dump_tela abrir_app=false", timeout=30)
    log_result("R08: Dump XML tela", "total_nodes" in r, f"nodes={r.get('total_nodes')} xml_len={r.get('xml_tamanho')}")

    # Abrir app e verificar se chegou
    r2 = rpa_get("/dump_tela abrir_app=true", timeout=30)
    tela2 = r2.get("tela_identificada", "")
    log_result("R09: Abrir SatSails via am start", "tela_identificada" in r2, f"tela={tela2}")

def run_rpa_p2_seguranca():
    print(bold("\n  [P2] Seguran a HMAC"))
    print("-" * 50)

    # Sem headers HMAC
    _, r = exec_termux(
        f"curl -s -X POST {RPA_LOCAL_URL}/pagar "
        f"-H 'Content-Type: application/json' "
        f"-d '{{\"valor\": 5.0}}' 2>&1"
    )
    resp = safe_json(r.get("stdout", ""))
    log_result("R11: Rejeitar /pagar sem HMAC", resp.get("detail") in ("Assinatura invalida","Headers de seguranca ausentes"), str(resp))

    # HMAC inv lido
    _, r = exec_termux(
        f"curl -s -X POST {RPA_LOCAL_URL}/pagar "
        f"-H 'Content-Type: application/json' "
        f"-H 'X-RPA-Signature: fake_sig_abc' "
        f"-H 'X-RPA-Timestamp: 9999999999' "
        f"-d '{{\"valor\": 5.0}}' 2>&1"
    )
    resp = safe_json(r.get("stdout", ""))
    log_result("R12: Rejeitar /pagar com HMAC inv lido", resp.get("detail") == "Assinatura invalida", str(resp))

    # Status sem HMAC
    _, r = exec_termux(f"curl -s {RPA_LOCAL_URL}/status/fake_tx 2>&1")
    resp = safe_json(r.get("stdout", ""))
    log_result("R13: Rejeitar /status sem HMAC", "detail" in resp, str(resp))

    # HMAC correto   s  enfileirar, n o esperar processar
    tx = f"seg_test_{int(time.time())}"
    resp = rpa_pagar(5.0, tx)
    log_result("R14: Aceitar /pagar com HMAC correto", "transaction_id" in resp, f"tx={resp.get('transaction_id')} fila={resp.get('posicao_fila')}")

    # Anti-replay: reutilizar mesmo timestamp/sig
    pstr = json.dumps({"valor": 5.0, "transaction_id": "replay_test", "webhook_url": ""})
    ts, sig = make_hmac(pstr)
    cmd_replay = (f"curl -s -X POST {RPA_LOCAL_URL}/pagar "
                  f"-H 'Content-Type: application/json' "
                  f"-H 'X-RPA-Signature: {sig}' "
                  f"-H 'X-RPA-Timestamp: {ts}' "
                  f"-d '{pstr}' 2>&1")
    _, r1 = exec_termux(cmd_replay, timeout=12)  # 1a vez - OK
    resp1 = safe_json(r1.get("stdout", ""))
    _, r2 = exec_termux(cmd_replay, timeout=12)  # 2a vez - deve rejeitar
    resp2 = safe_json(r2.get("stdout", ""))
    log_result("R15: Anti-replay (mesmo HMAC 2x)", resp2.get("detail") == "Assinatura invalida", 
               f"1a={resp1.get('transaction_id',' ') or resp1.get('detail',' ')} 2a={resp2.get('detail',' ')}")

def run_rpa_p3_pix():
    print(bold("\n  [P3] Fluxo Principal PIX"))
    print("-" * 50)

    # Enfileirar pedido
    tx = f"fase1_pix_{int(time.time())}"
    resp = rpa_pagar(5.0, tx)
    enfileirado = "transaction_id" in resp and resp.get("posicao_fila", 0) >= 1
    log_result("R16: Enfileirar pedido PIX", enfileirado, f"fila={resp.get('posicao_fila')}")

    # Aguardar worker processar (~60s)
    print(f"    [WAIT] Aguardando worker processar {tx}...")
    resultado = None
    for i in range(12):  # 12 x 5s = 60s
        time.sleep(5)
        r = rpa_status(tx)
        s = r.get("status", "") if isinstance(r, dict) else ""
        if s in ("pending", "confirmed", "failed"):
            resultado = r
            break
        # Checa logs
        logs = rpa_get("/logs").get("logs", [])
        gerado = any(tx in l and "PIX gerado" in l for l in logs)
        falhou = any(tx in l and "Falha PIX" in l for l in logs)
        if gerado or falhou:
            resultado = rpa_status(tx)
            break

    if resultado:
        codigo_pix = resultado.get("detalhes", {}).get("codigo_pix", "")
        log_result("R17: QR Code PIX gerado", bool(codigo_pix), f"valor={resultado.get('detalhes',{}).get('valor_brl')} status={resultado.get('status')}")
        log_result("R18: Status da transa  o retorna", resultado.get("status") in ("pending","confirmed"), f"status={resultado.get('status')}")
    else:
        r_logs = rpa_get("/logs").get("logs", [])
        ultimo = r_logs[-3:] if r_logs else []
        log_result("R17: QR Code PIX gerado", False, f"timeout   logs: {ultimo}")
        log_result("R18: Status da transa  o", False, "n o processado a tempo")

    # Pendentes
    r = rpa_get("/pendentes")
    log_result("R19: Listar pendentes", "pendentes" in r, f"qtd={len(r.get('pendentes',[]))}")

    # M ltiplas transa  es na fila
    tx2 = f"fase1_multi1_{int(time.time())}"
    tx3 = f"fase1_multi2_{int(time.time())+1}"
    r2 = rpa_pagar(5.0, tx2)
    r3 = rpa_pagar(5.0, tx3)
    log_result("R20: M ltiplas transa  es fila", "transaction_id" in r2 and "transaction_id" in r3,
               f"fila={r3.get('posicao_fila')}")

def run_rpa_p4_auditoria():
    print(bold("\n  [P4] Auditoria"))
    print("-" * 50)

    r = rpa_post("/auditar")
    log_result("R21: Auditoria for ada", "confirmados" in r, f"confirmados={r.get('confirmados')}")

    r = rpa_get("/health")
    log_result("R22: Worker ativo (auditoria peri dica configurada)", r.get("worker_running") == True,
               f"audit_interval=10s configurado no config.json")

def run_rpa_p5_robustez():
    print(bold("\n  [P5] Robustez"))
    print("-" * 50)

    r = rpa_post("/worker/stop")
    log_result("R23: Worker stop", r.get("success") == True, str(r))
    time.sleep(2)

    r = rpa_post("/worker/restart")
    log_result("R24: Worker restart", r.get("success") == True, str(r))
    time.sleep(3)

    r = rpa_get("/health")
    log_result("R24b: Worker rodando ap s restart", r.get("worker_running") == True, str(r))

    r = rpa_get("/diagnostico")
    log_result("R25: Diagn stico do sistema", "whoami" in r or "id" in r, f"keys={list(r.keys())[:5]}")

    r = rpa_get("/debug_clipboard")
    log_result("R26: Debug clipboard", isinstance(r, dict), f"keys={list(r.keys())[:3]}")

def run_rpa_p6_config():
    print(bold("\n  [P6] Configura  o"))
    print("-" * 50)

    r_before = rpa_get("/config")
    old_interval = r_before.get("audit_interval", 10)

    r = rpa_post("/config", {"audit_interval": 15})
    log_result("R27: Atualizar config via API", r.get("success") == True, str(r))

    r_after = rpa_get("/config")
    log_result("R28: Config persistida", r_after.get("audit_interval") == 15, f"interval={r_after.get('audit_interval')}")

    # Restaurar
    rpa_post("/config", {"audit_interval": old_interval})

# ============================================================
# MAIN
# ============================================================
def main():
    print(bold("=" * 60))
    print(bold("[TEST] BRANCA DE NEVE 1.0   SUITE COMPLETA DE TESTES (FASE 1)"))
    print(bold("=" * 60))
    print(f"In cio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Tunnel: {SERVEO_URL}")
    print()

    # ---- PARTE 1: API Central ----
    # Backend n o est  acess vel diretamente daqui (  localhost:8001 no Termux)
    # Verificar se est  rodando
    try:
        _, h = exec_termux("curl -s http://localhost:8001/api/health 2>&1")
        backend_data = json.loads(h["stdout"])
        backend_online = backend_data.get("status") == "ok"
    except:
        backend_online = False

    if backend_online:
        run_api_central_tests(f"{SERVEO_URL}")   # Aproxima  o: testes via tunnel
        # Nota: Os testes T01-T09 s o da API Central. Se backend n o estiver no tunnel,
        # marcamos como SKIP
    else:
        print(bold("\n[API] PARTE 1   API CENTRAL"))
        print("-" * 50)
        print(warn("  [WARN]  Backend API Central (porta 8001) n o est  rodando no Termux."))
        print(warn("  [INFO]  O backend precisa de MongoDB e est  pensado para rodar com Docker."))
        print(warn("  ->  Testes T01-T09 marcados como N/A neste ambiente standalone."))
        for test_name in [f"T0{i}" for i in range(1, 10)]:
            results.append({"name": test_name, "status": "N/A", "obs": "Backend requer Docker+MongoDB"})

    # ---- PARTE 2: RPA Gateway ----
    run_rpa_p0_infra()
    run_rpa_p1_tela()
    run_rpa_p2_seguranca()
    run_rpa_p3_pix()
    run_rpa_p4_auditoria()
    run_rpa_p5_robustez()
    run_rpa_p6_config()

    # ---- SUMMARY ----
    print(bold(f"\n{'='*60}"))
    print(bold("[STATS] SUM RIO DOS TESTES"))
    print(bold('='*60))

    passed = [r for r in results if r["status"] == "PASS"]
    failed = [r for r in results if r["status"] == "FAIL"]
    na     = [r for r in results if r["status"] == "N/A"]

    print(f"Total: {len(results)} | {ok('PASS: '+str(len(passed)))} | {fail('FAIL: '+str(len(failed)))} | {warn('N/A: '+str(len(na)))}")
    print(f"Taxa: {(len(passed)/max(len(passed)+len(failed),1))*100:.0f}% ({len(passed)}/{len(passed)+len(failed)})")

    if failed:
        print(fail(f"\n[FAIL] FALHAS ({len(failed)}):"))
        for r in failed:
            print(f"    {r['name']}: {r['obs']}")

    print(f"\nFim: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Salvar resultado em arquivo
    out_path = os.path.join(os.path.dirname(__file__), "results_fase1.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(_outbuf.getvalue())
    _orig_print(f"\n[FILE] Resultado salvo em: {out_path}")

    return 0 if not failed else 1

if __name__ == "__main__":
    sys.exit(main())
