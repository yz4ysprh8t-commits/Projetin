"""
Backend API Central - Branca de Neve 1.0
Versão SQLite para rodar 100% no Termux
"""
import os
import time
import json
import sqlite3
import threading
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

from fastapi import FastAPI, APIRouter, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

# Configuração
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "branca_de_neve.db"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# App
app = FastAPI(title="Branca de Neve 1.0 - API Central (SQLite)")
api_router = APIRouter(prefix="/api")

# RPA State (in-memory, persisted to SQLite)
_rpa_state = {
    "url": "",
    "last_seen": 0,
    "online": False,
    "registered_at": 0
}

RPA_REGISTER_TOKEN = os.environ.get("RPA_REGISTER_TOKEN", "branca_de_neve_2026")
ALLOWED_DOMAINS = ["ngrok.io", "ngrok-free.app", "serveo.net", "localhost", "127.0.0.1"]


# =============================================================================
# DATABASE SETUP
# =============================================================================

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables"""
    conn = get_db()
    cursor = conn.cursor()
    
    # RPA Config table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rpa_config (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at REAL
        )
    """)
    
    # Transactions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            valor_solicitado REAL,
            valor_pix REAL,
            codigo_pix TEXT,
            status TEXT DEFAULT 'pending',
            webhook_url TEXT,
            created_at REAL,
            updated_at REAL
        )
    """)
    
    # Bridge messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bridge_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_agent TEXT,
            content TEXT,
            timestamp REAL,
            read INTEGER DEFAULT 0
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")


def load_rpa_url():
    """Load RPA URL from SQLite"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM rpa_config WHERE key = 'rpa_state'")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            data = json.loads(row['value'])
            _rpa_state["url"] = data.get("url", "")
            _rpa_state["registered_at"] = data.get("registered_at", 0)
            logger.info(f"RPA URL loaded: {_rpa_state['url']}")
    except Exception as e:
        logger.error(f"Error loading RPA URL: {e}")


def save_rpa_url():
    """Save RPA URL to SQLite"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        data = json.dumps({
            "url": _rpa_state["url"],
            "registered_at": _rpa_state["registered_at"]
        })
        cursor.execute("""
            INSERT OR REPLACE INTO rpa_config (key, value, updated_at)
            VALUES ('rpa_state', ?, ?)
        """, (data, time.time()))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error saving RPA URL: {e}")


# =============================================================================
# HEARTBEAT
# =============================================================================

def _heartbeat_loop():
    """Background thread to check RPA health"""
    while True:
        if _rpa_state["url"]:
            try:
                with httpx.Client(timeout=10) as client:
                    r = client.get(f"{_rpa_state['url']}/health")
                    if r.status_code == 200:
                        _rpa_state["online"] = True
                        _rpa_state["last_seen"] = time.time()
                    else:
                        _rpa_state["online"] = False
            except Exception:
                _rpa_state["online"] = False
        time.sleep(30)


# =============================================================================
# STARTUP / SHUTDOWN
# =============================================================================

@app.on_event("startup")
async def startup():
    init_db()
    load_rpa_url()
    t = threading.Thread(target=_heartbeat_loop, daemon=True)
    t.start()
    logger.info("API Central started - Branca de Neve 1.0 (SQLite)")


# =============================================================================
# MAIN ROUTES
# =============================================================================

@api_router.get("/")
async def root():
    return {
        "service": "Branca de Neve 1.0 - API Central",
        "version": "2.0.0-sqlite",
        "rpa_online": _rpa_state["online"],
        "rpa_url": _rpa_state["url"] or "not registered"
    }


@api_router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "api_central",
        "database": "sqlite",
        "timestamp": time.time(),
        "rpa_online": _rpa_state["online"]
    }


# =============================================================================
# RPA MANAGEMENT
# =============================================================================

@api_router.post("/rpa/register")
async def rpa_register(request: Request):
    """Register RPA Gateway URL"""
    data = await request.json()
    url = data.get("url", "").rstrip("/")
    token = data.get("token", "")

    if not url:
        raise HTTPException(status_code=400, detail="URL obrigatoria")

    if token != RPA_REGISTER_TOKEN:
        logger.warning(f"RPA register with invalid token: {url}")
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
    save_rpa_url()

    logger.info(f"RPA registered: {url}")
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
        return {"error": "RPA nao registrado"}

    target_url = f"{_rpa_state['url']}/{path}"

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            if request.method == "GET":
                params = dict(request.query_params)
                r = await client.get(target_url, params=params)
            else:
                body = await request.body()
                r = await client.post(target_url, content=body, 
                                     headers={"Content-Type": "application/json"})

            _rpa_state["online"] = True
            _rpa_state["last_seen"] = time.time()

            try:
                return r.json()
            except:
                return {"raw": r.text}
    except httpx.TimeoutException:
        _rpa_state["online"] = False
        raise HTTPException(status_code=504, detail="RPA timeout")
    except httpx.ConnectError:
        _rpa_state["online"] = False
        raise HTTPException(status_code=502, detail="RPA offline")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/rpa/logs")
async def rpa_logs():
    """Get RPA logs via proxy"""
    if not _rpa_state["url"]:
        return {"logs": [], "error": "RPA nao registrado"}
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{_rpa_state['url']}/logs")
            return r.json()
    except Exception as e:
        return {"logs": [], "error": str(e)}


@api_router.get("/rpa/ver_tela")
async def rpa_ver_tela():
    """Get current screen info"""
    if not _rpa_state["url"]:
        return {"error": "RPA nao registrado"}
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{_rpa_state['url']}/ver_tela")
            return r.json()
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# BRIDGE - AGENT COMMUNICATION
# =============================================================================

_message_queue = []

class BridgeMessage(BaseModel):
    from_agent: str
    content: str

@api_router.get("/bridge/health")
async def bridge_health():
    return {"status": "online", "queue_size": len(_message_queue)}

@api_router.post("/bridge/msg")
async def bridge_send(msg: BridgeMessage):
    message = {"from": msg.from_agent, "content": msg.content, "timestamp": time.time()}
    _message_queue.append(message)
    
    # Also save to DB
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO bridge_messages (from_agent, content, timestamp)
            VALUES (?, ?, ?)
        """, (msg.from_agent, msg.content, time.time()))
        conn.commit()
        conn.close()
    except:
        pass
    
    return {"success": True, "queued": len(_message_queue)}

@api_router.get("/bridge/msg")
async def bridge_receive():
    if _message_queue:
        return _message_queue.pop(0)
    return {"empty": True}

@api_router.get("/bridge/all")
async def bridge_all():
    return {"messages": _message_queue[-50:]}

@api_router.delete("/bridge/clear")
async def bridge_clear():
    _message_queue.clear()
    return {"success": True}


# =============================================================================
# TRANSACTIONS (for tracking)
# =============================================================================

@api_router.get("/transactions")
async def list_transactions(status: Optional[str] = None, limit: int = 50):
    """List transactions"""
    conn = get_db()
    cursor = conn.cursor()
    
    if status:
        cursor.execute("""
            SELECT * FROM transactions 
            WHERE status = ? 
            ORDER BY created_at DESC LIMIT ?
        """, (status, limit))
    else:
        cursor.execute("""
            SELECT * FROM transactions 
            ORDER BY created_at DESC LIMIT ?
        """, (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return {"transactions": [dict(row) for row in rows]}


@api_router.post("/transactions")
async def create_transaction(request: Request):
    """Create/update transaction record"""
    data = await request.json()
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO transactions 
        (id, user_id, valor_solicitado, valor_pix, codigo_pix, status, webhook_url, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("id", f"tx_{int(time.time())}"),
        data.get("user_id", ""),
        data.get("valor_solicitado", 0),
        data.get("valor_pix", 0),
        data.get("codigo_pix", ""),
        data.get("status", "pending"),
        data.get("webhook_url", ""),
        data.get("created_at", time.time()),
        time.time()
    ))
    
    conn.commit()
    conn.close()
    
    return {"success": True}


# =============================================================================
# SETUP
# =============================================================================

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("BACKEND_PORT", "8001"))
    print(f"Starting Backend on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
