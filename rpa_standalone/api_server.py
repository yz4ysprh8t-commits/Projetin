import os
import sys
import json
import time
import hmac
import hashlib
import threading
import queue
from typing import Optional, Dict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import uvicorn

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from device_client import DeviceClient
from workflow_controller import WorkflowController

app = FastAPI(title="RPA Gateway v2 - Branca de Neve", version="2.0.0")

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DB_PATH = os.path.join(BASE_DIR, "rpa_transactions.db")

rpa_logs = []
job_queue = queue.Queue()
controller = None
worker_thread = None
worker_running = False

HMAC_SECRET = os.environ.get('RPA_HMAC_SECRET', 'branca_neve_hmac_2026_s3cr3t')
HMAC_MAX_AGE = 60
_used_nonces = {}


def verify_hmac_signature(request_headers: dict, payload: str = "") -> bool:
    signature = request_headers.get("x-rpa-signature", "")
    timestamp = request_headers.get("x-rpa-timestamp", "")

    if not signature or not timestamp:
        return False

    try:
        ts = int(timestamp)
        if abs(time.time() - ts) > HMAC_MAX_AGE:
            return False
    except (ValueError, TypeError):
        return False

    nonce_key = f"{timestamp}_{signature[:16]}"
    if nonce_key in _used_nonces:
        return False

    message = f"{timestamp}.{payload}".encode()
    expected = hmac.new(HMAC_SECRET.encode(), message, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, signature):
        return False

    _used_nonces[nonce_key] = time.time()

    now = time.time()
    expired = [k for k, v in _used_nonces.items() if now - v > HMAC_MAX_AGE * 2]
    for k in expired:
        del _used_nonces[k]

    return True


def add_log(msg: str):
    from datetime import datetime
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    rpa_logs.append(entry)
    if len(rpa_logs) > 100:
        rpa_logs.pop(0)
    print(entry)


def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {
        "mode": "adb",
        "adb_path": "adb",
        "device_id": "",
        "pin": "222222",
        "audit_interval": 10,
        "package": "com.satsails.Satsails"
    }


def save_config(config: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH) or ".", exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)


def init_controller():
    global controller
    config = load_config()

    client = DeviceClient(
        mode=config.get("mode", "adb"),
        adb_path=config.get("adb_path", "adb"),
        device_id=config.get("device_id") or None
    )

    controller = WorkflowController(
        client=client,
        pin=config.get("pin", "222222"),
        db_path=DB_PATH
    )

    add_log(f"Controller inicializado (mode={config.get('mode')}, device={config.get('device_id', 'default')})")
    return controller


def worker_loop():
    global worker_running
    config = load_config()
    audit_interval = config.get("audit_interval", 10)
    last_audit = 0

    add_log("Worker iniciado e aguardando pedidos...")

    while worker_running:
        try:
            now = time.time()
            if now - last_audit >= audit_interval:
                try:
                    confirmados = controller.auditar_pagamentos(usar_historico=False)
                    if confirmados:
                        add_log(f"Auditoria: {len(confirmados)} pagamentos confirmados")
                    last_audit = now
                except Exception as e:
                    add_log(f"Erro na auditoria: {e}")

            try:
                job_data = job_queue.get(timeout=2)
                if len(job_data) == 4:
                    valor, transaction_id, webhook_url, user_id = job_data
                else:
                    valor, transaction_id, webhook_url = job_data
                    user_id = ""

                add_log(f"Processando pedido {transaction_id}: R$ {valor} (user: {user_id or 'N/A'})")

                resultado = controller.gerar_pix(
                    valor=valor,
                    transaction_id=transaction_id,
                    webhook_url=webhook_url,
                    user_id=user_id
                )

                if resultado["sucesso"]:
                    add_log(f"PIX gerado: {transaction_id} -> R$ {resultado['valor_pix']}")
                else:
                    add_log(f"Falha PIX {transaction_id}: {resultado.get('erro', 'desconhecido')}")
                    for d in resultado.get("diag", []):
                        add_log(f"  [DIAG] {d}")

                job_queue.task_done()

            except queue.Empty:
                pass

            time.sleep(0.5)

        except Exception as e:
            add_log(f"Erro fatal no Worker: {e}")
            time.sleep(3)


def start_worker():
    global worker_thread, worker_running
    if worker_running:
        return

    worker_running = True
    worker_thread = threading.Thread(target=worker_loop, daemon=True)
    worker_thread.start()
    add_log("Worker thread iniciada")


def stop_worker():
    global worker_running
    worker_running = False
    add_log("Worker parado")


class PaymentRequest(BaseModel):
    valor: float
    webhook_url: Optional[str] = None
    transaction_id: Optional[str] = None
    user_id: Optional[str] = None


class StatusRequest(BaseModel):
    transaction_id: str


def _auto_register():
    config = load_config()
    central_url = config.get("central_url", "")
    serveo_url = config.get("serveo_url", "")

    if not central_url or not serveo_url:
        return

    try:
        import httpx
        token = config.get("register_token", "branca_de_neve_2026")
        with httpx.Client(timeout=10) as client:
            r = client.post(f"{central_url}/rpa/register", json={"url": serveo_url, "token": token})
            if r.status_code == 200:
                add_log(f"Auto-registro OK em {central_url}")
            else:
                add_log(f"Auto-registro falhou: {r.status_code}")
    except Exception as e:
        add_log(f"Auto-registro erro: {e}")


def _registration_loop():
    time.sleep(5)
    while True:
        _auto_register()
        time.sleep(300)


@app.on_event("startup")
async def startup():
    init_controller()
    start_worker()

    config = load_config()
    if config.get("central_url") and config.get("serveo_url"):
        t = threading.Thread(target=_registration_loop, daemon=True)
        t.start()


@app.post("/pagar")
async def criar_pagamento(request: Request):
    if controller is None:
        raise HTTPException(status_code=503, detail="Controller nao inicializado")

    body = await request.body()
    body_str = body.decode()

    headers_dict = {k.lower(): v for k, v in request.headers.items()}
    if not verify_hmac_signature(headers_dict, body_str):
        add_log("⚠️ HMAC invalido em /pagar - requisicao rejeitada")
        raise HTTPException(status_code=403, detail="Assinatura invalida")

    try:
        data = json.loads(body_str)
    except:
        raise HTTPException(status_code=400, detail="JSON invalido")

    valor = data.get("valor", 0)
    tx_id = data.get("transaction_id") or f"tx_{int(time.time())}"
    webhook_url = data.get("webhook_url", "")
    user_id = data.get("user_id", "")

    job_queue.put((valor, tx_id, webhook_url, user_id))

    add_log(f"Pedido recebido: {tx_id} - R$ {valor} (user: {user_id or 'N/A'})")

    return {
        "transaction_id": tx_id,
        "valor": valor,
        "user_id": user_id,
        "posicao_fila": job_queue.qsize(),
        "mensagem": "Pedido recebido e adicionado a fila de processamento."
    }


@app.get("/status/{transaction_id}")
async def consultar_status(transaction_id: str, request: Request):
    if controller is None:
        raise HTTPException(status_code=503, detail="Controller nao inicializado")

    headers_dict = {k.lower(): v for k, v in request.headers.items()}
    has_hmac = headers_dict.get("x-rpa-signature", "")
    if has_hmac and not verify_hmac_signature(headers_dict, transaction_id):
        add_log(f"⚠️ HMAC invalido em /status/{transaction_id} - requisicao rejeitada")
        raise HTTPException(status_code=403, detail="Assinatura invalida")
    elif not has_hmac:
        add_log(f"⚠️ Requisicao /status/{transaction_id} sem HMAC - rejeitada")
        raise HTTPException(status_code=403, detail="Headers de seguranca ausentes")

    status = controller.get_status(transaction_id)
    if status:
        return {
            "transaction_id": transaction_id,
            "status": status["status"],
            "detalhes": status
        }

    raise HTTPException(status_code=404, detail="Transacao nao encontrada ou ja expirou")


@app.get("/pendentes")
async def listar_pendentes():
    if controller is None:
        raise HTTPException(status_code=503, detail="Controller nao inicializado")
    return {"pendentes": controller.get_pendentes()}


@app.post("/auditar")
async def forcar_auditoria():
    if controller is None:
        raise HTTPException(status_code=503, detail="Controller nao inicializado")

    try:
        confirmados = controller.auditar_pagamentos(usar_historico=True)
        return {
            "confirmados": len(confirmados),
            "detalhes": confirmados
        }
    except Exception as e:
        return {"confirmados": 0, "erro": str(e)}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "rpa_gateway_v2",
        "version": "2.0.0",
        "worker_running": worker_running,
        "fila_tamanho": job_queue.qsize(),
        "timestamp": time.time()
    }


@app.get("/logs")
async def get_logs():
    return {"logs": rpa_logs[-50:]}


@app.get("/config")
async def get_config():
    config = load_config()
    safe = {k: ("***" if "secret" in k.lower() or "pass" in k.lower() else v)
            for k, v in config.items()}
    return safe


@app.post("/config")
async def set_config(data: Dict):
    config = load_config()
    config.update(data)
    save_config(config)
    add_log(f"Config atualizada: {list(data.keys())}")
    return {"success": True}


@app.post("/converter/depix-lbtc")
async def converter_depix_lbtc():
    if controller is None:
        raise HTTPException(status_code=503, detail="Controller nao inicializado")

    try:
        add_log("Iniciando conversao Depix -> Liquid Bitcoin")
        resultado = controller.converter_depix_lbtc()
        if resultado.get("sucesso"):
            add_log("Conversao Depix -> LBTC concluida")
        else:
            add_log(f"Conversao Depix -> LBTC falhou: {resultado.get('erro')}")
        return resultado
    except Exception as e:
        add_log(f"Erro na conversao Depix -> LBTC: {e}")
        return {"sucesso": False, "erro": str(e)}


@app.post("/converter/lbtc-btc")
async def converter_lbtc_btc():
    if controller is None:
        raise HTTPException(status_code=503, detail="Controller nao inicializado")

    try:
        add_log("Iniciando conversao Liquid Bitcoin -> Bitcoin")
        resultado = controller.converter_lbtc_btc()
        if resultado.get("sucesso"):
            add_log("Conversao LBTC -> BTC concluida")
        else:
            add_log(f"Conversao LBTC -> BTC falhou: {resultado.get('erro')}")
        return resultado
    except Exception as e:
        add_log(f"Erro na conversao LBTC -> BTC: {e}")
        return {"sucesso": False, "erro": str(e)}


@app.post("/saque")
async def executar_saque():
    if controller is None:
        raise HTTPException(status_code=503, detail="Controller nao inicializado")

    try:
        add_log("Iniciando saque automatico completo (Depix -> LBTC -> BTC)")
        resultado = controller.executar_saque()
        if resultado.get("sucesso"):
            add_log("Saque automatico concluido com sucesso!")
        else:
            add_log(f"Saque falhou: {resultado.get('erro')}")
        return resultado
    except Exception as e:
        add_log(f"Erro no saque automatico: {e}")
        return {"sucesso": False, "erro": str(e)}


@app.post("/worker/stop")
async def stop_worker_endpoint():
    stop_worker()
    return {"success": True, "message": "Worker parado"}


@app.post("/worker/restart")
async def restart_worker():
    stop_worker()
    time.sleep(1)
    init_controller()
    start_worker()
    return {"success": True, "message": "Worker reiniciado"}


@app.get("/diagnostico")
async def diagnostico():
    import subprocess
    testes = {}
    cmds = {
        "uiautomator_dump": "uiautomator dump /sdcard/view.xml 2>&1",
        "cat_xml": "cat /sdcard/view.xml 2>&1 | head -c 500",
        "am_start": f"am start -n com.satsails.Satsails/.MainActivity 2>&1",
        "whoami": "whoami 2>&1",
        "id": "id 2>&1",
        "uname": "uname -a 2>&1",
        "ls_sdcard": "ls /sdcard/ 2>&1 | head -20",
        "ps_satsails": "ps -A 2>&1 | grep -i satsail || echo 'nao encontrado'",
    }
    for nome, cmd in cmds.items():
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            testes[nome] = {"stdout": r.stdout.strip()[:500], "stderr": r.stderr.strip()[:300], "rc": r.returncode}
        except Exception as e:
            testes[nome] = {"erro": str(e)}
    return testes


@app.get("/dump_tela")
async def dump_tela(abrir_app: bool = True):
    import re
    if controller is None:
        raise HTTPException(status_code=503, detail="Controller nao inicializado")

    client = controller.client

    if abrir_app:
        config = load_config()
        pkg = config.get("package", "com.satsails.Satsails")
        client.shell(f"am start -n {pkg}/.MainActivity 2>/dev/null")
        time.sleep(5)

    xml = client.dump_xml(force=True)
    screen = client.identify_screen(xml=xml)

    texts = re.findall(r'text="([^"]+)"', xml) if xml else []
    descs = re.findall(r'content-desc="([^"]+)"', xml) if xml else []
    bounds_list = re.findall(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml) if xml else []
    classes = re.findall(r'class="([^"]+)"', xml) if xml else []

    views = []
    if xml:
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(xml)
            for i, node in enumerate(root.iter("node")):
                bounds_str = node.attrib.get("bounds", "")
                bm = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
                if bm:
                    x1, y1, x2, y2 = int(bm.group(1)), int(bm.group(2)), int(bm.group(3)), int(bm.group(4))
                    views.append({
                        "idx": i,
                        "cls": node.attrib.get("class", "").split(".")[-1],
                        "text": node.attrib.get("text", ""),
                        "desc": node.attrib.get("content-desc", ""),
                        "rid": node.attrib.get("resource-id", ""),
                        "click": node.attrib.get("clickable", "false"),
                        "bounds": f"[{x1},{y1}][{x2},{y2}]",
                        "center": f"{(x1+x2)//2},{(y1+y2)//2}",
                        "size": f"{x2-x1}x{y2-y1}",
                        "pkg": node.attrib.get("package", "")
                    })
        except ET.ParseError:
            pass

    return {
        "tela_identificada": screen,
        "xml_tamanho": len(xml) if xml else 0,
        "textos": [t for t in texts if t.strip()],
        "content_descs": [d for d in descs if d.strip()],
        "classes_unicas": list(set(classes)),
        "total_nodes": len(views),
        "views": views,
        "xml_bruto": xml[:3000] if xml else ""
    }


@app.get("/ver_tela")
async def ver_tela():
    import re
    if controller is None:
        raise HTTPException(status_code=503, detail="Controller nao inicializado")
    client = controller.client
    xml = client.dump_xml(force=True)
    screen = client.identify_screen(xml=xml)
    texts = [t for t in re.findall(r'text="([^"]+)"', xml) if t.strip()] if xml else []
    descs = [t for t in re.findall(r'content-desc="([^"]+)"', xml) if t.strip()] if xml else []
    clipboard = ""
    try:
        clipboard = client.shell("service call clipboard 2 i32 1 2>/dev/null", timeout=3)
    except:
        pass
    return {
        "tela": screen,
        "textos": texts,
        "descs": descs,
        "clipboard": clipboard,
        "xml_len": len(xml) if xml else 0
    }


@app.get("/debug_clipboard")
async def debug_clipboard():
    import subprocess
    results = {}
    try:
        r1 = controller.client.shell("am broadcast -a clipper.get 2>/dev/null")
        results["clipper_get"] = r1
    except Exception as e:
        results["clipper_get"] = str(e)
    try:
        r2 = controller.client.shell("service call clipboard 2 i32 1 i32 0 2>/dev/null")
        results["service_call_clipboard"] = r2
    except Exception as e:
        results["service_call_clipboard"] = str(e)
    try:
        r3 = subprocess.run(["termux-clipboard-get"], capture_output=True, text=True, timeout=5)
        results["termux_clipboard_get"] = {"stdout": r3.stdout, "stderr": r3.stderr, "rc": r3.returncode}
    except Exception as e:
        results["termux_clipboard_get"] = str(e)
    try:
        r4 = controller.client.shell("content call --uri content://com.termux.contentprovider/clipboard/get --method get 2>/dev/null")
        results["termux_content_provider"] = r4
    except Exception as e:
        results["termux_content_provider"] = str(e)
    try:
        controller.client.shell("am broadcast -a clipper.set -e text 'TESTE_CLIPBOARD_123' 2>/dev/null")
        time.sleep(1)
        r5 = controller.client.shell("am broadcast -a clipper.get 2>/dev/null")
        results["clipper_roundtrip"] = r5
    except Exception as e:
        results["clipper_roundtrip"] = str(e)
    return results


@app.post("/atualizar")
async def atualizar(request: Request):
    data = {}
    try:
        data = await request.json()
    except:
        pass
    token = data.get("token", "")
    config = load_config()
    expected_token = config.get("register_token", "branca_de_neve_2026")
    if token != expected_token:
        raise HTTPException(status_code=403, detail="Token invalido")

    central_url = config.get("central_url", "")
    if not central_url:
        raise HTTPException(status_code=400, detail="central_url nao configurada")

    add_log("Iniciando auto-atualizacao remota...")

    try:
        import subprocess as sp
        import tarfile
        import io
        import httpx

        with httpx.Client(timeout=30) as client:
            r = client.get(f"{central_url}/rpa/download")
            if r.status_code != 200:
                add_log(f"Download falhou: {r.status_code}")
                return {"sucesso": False, "erro": f"Download falhou: {r.status_code}"}

        backup_config = load_config()

        buf = io.BytesIO(r.content)
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            members = tar.getnames()
            safe_members = [m for m in tar.getmembers() if not m.name.startswith("/") and ".." not in m.name]
            tar.extractall(path=BASE_DIR, members=safe_members)

        save_config(backup_config)

        add_log(f"Atualizacao concluida! Arquivos: {members}")
        add_log("Reiniciando em 2 segundos...")

        def _restart():
            time.sleep(2)
            os.execv(sys.executable, [sys.executable, os.path.join(BASE_DIR, "main.py")])

        t = threading.Thread(target=_restart, daemon=True)
        t.start()

        return {"sucesso": True, "arquivos": members, "mensagem": "Atualizado! Reiniciando..."}

    except Exception as e:
        add_log(f"Erro na atualizacao: {e}")
        return {"sucesso": False, "erro": str(e)}


@app.get("/versao")
async def versao():
    version_file = os.path.join(BASE_DIR, ".version")
    version = "desconhecida"
    if os.path.exists(version_file):
        with open(version_file) as f:
            version = f.read().strip()
    return {"versao": version, "timestamp": time.time()}


if __name__ == "__main__":
    port = int(os.environ.get("RPA_PORT", "8080"))
    print(f"🚀 RPA Gateway v2 iniciando na porta {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
