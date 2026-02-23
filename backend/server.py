from fastapi import FastAPI, APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, PlainTextResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import time
import json
import threading
import tarfile
import io
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import httpx

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI(title="Branca de Neve 1.0 - API Central")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# RPA State
_rpa_state = {
    "url": "",
    "last_seen": 0,
    "online": False,
    "registered_at": 0
}

RPA_REGISTER_TOKEN = os.environ.get("RPA_REGISTER_TOKEN", "branca_de_neve_2026")
ALLOWED_DOMAINS = ["serveousercontent.com", "serveo.net", "localhost", "127.0.0.1", "ngrok.io", "ngrok-free.app"]

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# RPA STATE MANAGEMENT
# =============================================================================

async def load_rpa_url():
    """Load RPA URL from MongoDB"""
    doc = await db.rpa_config.find_one({"_id": "rpa_state"})
    if doc:
        _rpa_state["url"] = doc.get("url", "")
        _rpa_state["registered_at"] = doc.get("registered_at", 0)
        logger.info(f"RPA URL loaded from DB: {_rpa_state['url']}")


async def save_rpa_url():
    """Save RPA URL to MongoDB"""
    await db.rpa_config.update_one(
        {"_id": "rpa_state"},
        {"$set": {
            "url": _rpa_state["url"],
            "registered_at": _rpa_state["registered_at"]
        }},
        upsert=True
    )


def _heartbeat_loop():
    """Background thread to check RPA health"""
    import asyncio
    while True:
        if _rpa_state["url"]:
            try:
                with httpx.Client(timeout=10) as http_client:
                    r = http_client.get(f"{_rpa_state['url']}/health")
                    if r.status_code == 200:
                        _rpa_state["online"] = True
                        _rpa_state["last_seen"] = time.time()
                        logger.info(f"RPA heartbeat OK: {_rpa_state['url']}")
                    else:
                        _rpa_state["online"] = False
                        logger.warning(f"RPA heartbeat failed: status {r.status_code}")
            except Exception as e:
                _rpa_state["online"] = False
                logger.warning(f"RPA heartbeat error: {e}")
        time.sleep(30)


# =============================================================================
# STARTUP EVENT
# =============================================================================

@app.on_event("startup")
async def startup():
    await load_rpa_url()
    # Start heartbeat thread
    t = threading.Thread(target=_heartbeat_loop, daemon=True)
    t.start()
    logger.info("API Central started - Branca de Neve 1.0")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()


# =============================================================================
# MAIN ROUTES
# =============================================================================

@api_router.get("/")
async def root():
    return {
        "service": "Branca de Neve 1.0 - API Central",
        "version": "2.0.0",
        "rpa_online": _rpa_state["online"],
        "rpa_url": _rpa_state["url"] or "not registered"
    }


@api_router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "api_central",
        "timestamp": time.time(),
        "rpa_online": _rpa_state["online"]
    }


# =============================================================================
# RPA MANAGEMENT ROUTES
# =============================================================================

@api_router.post("/rpa/register")
async def rpa_register(request: Request):
    """Register RPA Gateway URL (called from Termux via tunnel)"""
    data = await request.json()
    url = data.get("url", "").rstrip("/")
    token = data.get("token", "")

    if not url:
        raise HTTPException(status_code=400, detail="URL obrigatoria")

    if token != RPA_REGISTER_TOKEN:
        logger.warning(f"RPA register attempt with invalid token from: {url}")
        raise HTTPException(status_code=403, detail="Token invalido")

    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.hostname or ""
    domain_ok = any(domain.endswith(d) for d in ALLOWED_DOMAINS)
    if not domain_ok:
        raise HTTPException(status_code=400, detail=f"Dominio nao permitido: {domain}")

    _rpa_state["url"] = url
    _rpa_state["registered_at"] = time.time()
    _rpa_state["online"] = True
    _rpa_state["last_seen"] = time.time()
    await save_rpa_url()

    logger.info(f"RPA registered successfully: {url}")
    return {"success": True, "message": f"RPA registrado: {url}"}


@api_router.get("/rpa/status")
async def rpa_status():
    """Get RPA Gateway status"""
    ago = time.time() - _rpa_state["last_seen"] if _rpa_state["last_seen"] else -1
    return {
        "url": _rpa_state["url"],
        "online": _rpa_state["online"],
        "last_seen_seconds_ago": round(ago, 1) if ago >= 0 else None,
        "registered_at": _rpa_state["registered_at"]
    }


@api_router.api_route("/rpa/cmd/{path:path}", methods=["GET", "POST"])
async def rpa_proxy(path: str, request: Request):
    """Proxy commands to RPA Gateway"""
    if not _rpa_state["url"]:
        raise HTTPException(status_code=503, detail="RPA nao registrado. Aguardando registro do Termux.")

    target_url = f"{_rpa_state['url']}/{path}"

    try:
        async with httpx.AsyncClient(timeout=60) as http_client:
            forward_headers = {}
            for h in ("X-RPA-Signature", "X-RPA-Timestamp", "Content-Type"):
                if h.lower() in [k.lower() for k in request.headers.keys()]:
                    forward_headers[h] = request.headers.get(h)

            if request.method == "GET":
                params = dict(request.query_params)
                r = await http_client.get(target_url, params=params, headers=forward_headers)
            else:
                body = await request.body()
                content_type = request.headers.get("content-type", "application/json")
                forward_headers["Content-Type"] = content_type
                r = await http_client.post(target_url, content=body, headers=forward_headers)

            _rpa_state["online"] = True
            _rpa_state["last_seen"] = time.time()

            try:
                return json.loads(r.text)
            except (json.JSONDecodeError, ValueError):
                from fastapi.responses import Response
                return Response(content=r.content, status_code=r.status_code,
                               media_type=r.headers.get("content-type", "text/plain"))
    except httpx.TimeoutException:
        _rpa_state["online"] = False
        raise HTTPException(status_code=504, detail="RPA timeout - servidor nao respondeu")
    except httpx.ConnectError:
        _rpa_state["online"] = False
        raise HTTPException(status_code=502, detail="RPA offline - nao foi possivel conectar")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao conectar ao RPA: {str(e)}")


@api_router.get("/rpa/download")
async def rpa_download():
    """Download RPA standalone package as tar.gz"""
    rpa_dir = ROOT_DIR.parent / "rpa_standalone"
    
    if not rpa_dir.exists():
        raise HTTPException(status_code=404, detail="RPA standalone nao encontrado")
    
    files_to_send = [
        "api_server.py", "auth_manager.py", "conversion_manager.py",
        "device_client.py", "identification_manager.py", "main.py",
        "navigation_manager.py", "payment_manager.py", "workflow_controller.py",
        "config.json", "requirements.txt",
        "start_rpa.sh", "setup_termux.sh"
    ]
    
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for fname in files_to_send:
            fpath = rpa_dir / fname
            if fpath.exists():
                tar.add(str(fpath), arcname=fname)
    
    buf.seek(0)
    return StreamingResponse(
        buf, 
        media_type="application/gzip", 
        headers={"Content-Disposition": "attachment; filename=rpa_update.tar.gz"}
    )


@api_router.post("/rpa/atualizar")
async def rpa_atualizar():
    """Send update command to RPA"""
    if not _rpa_state["url"]:
        raise HTTPException(status_code=404, detail="RPA nao registrado")

    try:
        async with httpx.AsyncClient(timeout=60) as http_client:
            r = await http_client.post(
                f"{_rpa_state['url']}/atualizar",
                json={"token": RPA_REGISTER_TOKEN}
            )
            return r.json()
    except Exception as e:
        return {"info": "RPA antigo sem /atualizar. Reinicie start_rpa.sh no Termux para atualizar.", "erro": str(e)}


# =============================================================================
# LOGS AND DEBUG
# =============================================================================

@api_router.get("/rpa/logs")
async def rpa_logs():
    """Get RPA logs via proxy"""
    if not _rpa_state["url"]:
        return {"logs": [], "error": "RPA nao registrado"}
    
    try:
        async with httpx.AsyncClient(timeout=10) as http_client:
            r = await http_client.get(f"{_rpa_state['url']}/logs")
            return r.json()
    except Exception as e:
        return {"logs": [], "error": str(e)}


@api_router.get("/rpa/ver_tela")
async def rpa_ver_tela():
    """Get current screen info from RPA"""
    if not _rpa_state["url"]:
        return {"error": "RPA nao registrado"}
    
    try:
        async with httpx.AsyncClient(timeout=30) as http_client:
            r = await http_client.get(f"{_rpa_state['url']}/ver_tela")
            return r.json()
    except Exception as e:
        return {"error": str(e)}


@api_router.get("/rpa/dump_tela")
async def rpa_dump_tela():
    """Get full screen dump from RPA"""
    if not _rpa_state["url"]:
        return {"error": "RPA nao registrado"}
    
    try:
        async with httpx.AsyncClient(timeout=60) as http_client:
            r = await http_client.get(f"{_rpa_state['url']}/dump_tela?abrir_app=true")
            return r.json()
    except Exception as e:
        return {"error": str(e)}


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
