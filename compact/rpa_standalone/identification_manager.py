import json
import time
import re
import sqlite3
import os
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict

from device_client import DeviceClient

MESES_PT = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4,
    "mai": 5, "jun": 6, "jul": 7, "ago": 8,
    "set": 9, "out": 10, "nov": 11, "dez": 12
}


class IdentificationManager:

    TAXA_FIXA = Decimal("0.99")
    TAXA_VARIAVEL_PCT = Decimal("0.03")
    TIMEOUT_PIX = 300

    def __init__(self, client: DeviceClient, db_path: str = "rpa_transactions.db"):
        self.client = client
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pendentes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                valor_brl TEXT NOT NULL,
                valor_original REAL NOT NULL,
                depix_esperado TEXT NOT NULL,
                usuario_id TEXT,
                transaction_id TEXT UNIQUE,
                codigo_pix TEXT,
                webhook_url TEXT,
                status TEXT DEFAULT 'pending',
                created_at REAL NOT NULL,
                confirmed_at REAL,
                texto_confirmacao TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS historico (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                valor_brl TEXT NOT NULL,
                valor_original REAL NOT NULL,
                depix_esperado TEXT NOT NULL,
                usuario_id TEXT,
                transaction_id TEXT,
                codigo_pix TEXT,
                webhook_url TEXT,
                status TEXT NOT NULL,
                created_at REAL NOT NULL,
                confirmed_at REAL,
                texto_confirmacao TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def calcular_depix_esperado(self, valor_brl: float) -> str:
        v = Decimal(str(valor_brl))
        resultado = (v - self.TAXA_FIXA) - (v * self.TAXA_VARIAVEL_PCT)
        return f"{resultado:.2f}"

    def gerar_valor_unico(self, valor_base: float, transaction_id: str = None,
                          usuario_id: str = None, webhook_url: str = None,
                          codigo_pix: str = None) -> Optional[str]:
        if transaction_id is None:
            transaction_id = f"tx_{int(time.time())}"
        if usuario_id is None:
            usuario_id = transaction_id

        valor_base_dec = Decimal(str(valor_base))
        conn = self._get_conn()

        try:
            cursor = conn.execute("SELECT valor_brl FROM pendentes WHERE status = 'pending'")
            valores_ocupados = {row[0] for row in cursor.fetchall()}

            for centavo in range(1, 100):
                acrescimo = Decimal(centavo) / Decimal(100)
                valor_candidato = valor_base_dec + acrescimo
                valor_final_str = f"{valor_candidato:.2f}"

                if valor_final_str not in valores_ocupados:
                    depix_alvo = self.calcular_depix_esperado(float(valor_final_str))

                    conn.execute("""
                        INSERT INTO pendentes
                        (valor_brl, valor_original, depix_esperado, usuario_id, transaction_id,
                         codigo_pix, webhook_url, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                    """, (
                        valor_final_str, float(valor_base), depix_alvo,
                        usuario_id, transaction_id, codigo_pix or "",
                        webhook_url or "", time.time()
                    ))
                    conn.commit()
                    print(f"   [ID] Valor unico gerado: R$ {valor_final_str} (DePix esperado: {depix_alvo})")
                    return valor_final_str

            print("   [ID] Sem slots disponiveis (0.01 a 0.99)")
            return None
        finally:
            conn.close()

    def atualizar_codigo_pix(self, transaction_id: str, codigo_pix: str):
        conn = self._get_conn()
        conn.execute("UPDATE pendentes SET codigo_pix = ? WHERE transaction_id = ?",
                      (codigo_pix, transaction_id))
        conn.commit()
        conn.close()

    def limpar_expirados(self) -> int:
        agora = time.time()
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT id, valor_brl, depix_esperado, created_at FROM pendentes WHERE status = 'pending'"
        )
        removidos = 0
        for row in cursor.fetchall():
            pid, valor, depix, created = row
            idade = agora - created
            if idade > self.TIMEOUT_PIX:
                print(f"   🗑️ PIX Expirado (>{self.TIMEOUT_PIX//60}min): R$ {valor} (DePix: {depix})")
                conn.execute("UPDATE pendentes SET status = 'expired' WHERE id = ?", (pid,))

                conn.execute("""
                    INSERT INTO historico
                    (valor_brl, valor_original, depix_esperado, usuario_id, transaction_id,
                     codigo_pix, webhook_url, status, created_at, confirmed_at, texto_confirmacao)
                    SELECT valor_brl, valor_original, depix_esperado, usuario_id, transaction_id,
                           codigo_pix, webhook_url, 'expired', created_at, ?, 'Expirado automaticamente'
                    FROM pendentes WHERE id = ?
                """, (agora, pid))

                conn.execute("DELETE FROM pendentes WHERE id = ?", (pid,))
                removidos += 1

        if removidos > 0:
            conn.commit()
            print(f"   🗑️ {removidos} pagamentos expirados removidos")
        conn.close()
        return removidos

    def _parse_transaction_entry(self, desc_text: str) -> dict:
        parts = desc_text.replace("&#10;", "\n").split("\n")
        result = {"tipo": "", "data_str": "", "valor": "", "is_recent": False}

        if len(parts) >= 3:
            result["tipo"] = parts[0].strip()
            result["data_str"] = parts[1].strip()
            result["valor"] = parts[2].strip()
        elif len(parts) == 2:
            result["tipo"] = parts[0].strip()
            result["valor"] = parts[1].strip()

        if result["data_str"]:
            try:
                match = re.match(r'(\d{1,2})\s+de\s+(\w{3})\.?,?\s*(\d{1,2}):(\d{2})', result["data_str"])
                if not match:
                    match = re.match(r'(\d{1,2})\s+(\w{3})\.?,?\s*(\d{1,2}):(\d{2})', result["data_str"])

                if match:
                    dia = int(match.group(1))
                    mes_str = match.group(2).lower()[:3]
                    hora = int(match.group(3))
                    minuto = int(match.group(4))
                    mes = MESES_PT.get(mes_str, 0)

                    if mes > 0:
                        agora = datetime.now()
                        ano = agora.year
                        try:
                            tx_time = datetime(ano, mes, dia, hora, minuto)
                            diff_seconds = (agora - tx_time).total_seconds()
                            result["is_recent"] = 0 <= diff_seconds <= self.TIMEOUT_PIX
                            result["diff_seconds"] = diff_seconds
                        except ValueError:
                            pass
            except Exception as e:
                print(f"   [ID] Erro ao parsear data '{result['data_str']}': {e}")

        return result

    def verificar_pagamentos_home(self, xml: str = None) -> List[Dict]:
        self.limpar_expirados()

        if xml is None:
            xml = self.client.dump_xml(force=True)
        if not xml:
            return []

        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT id, valor_brl, depix_esperado, transaction_id, webhook_url FROM pendentes WHERE status = 'pending'"
        )
        pendentes = cursor.fetchall()

        if not pendentes:
            conn.close()
            return []

        all_descs = re.findall(r'content-desc="([^"]+)"', xml)

        transactions = []
        for desc in all_descs:
            parsed = self._parse_transaction_entry(desc)
            if parsed["tipo"].lower() == "depix" and parsed["valor"]:
                transactions.append(parsed)

        confirmados = []

        for pid, valor_brl, depix_esperado, tx_id, webhook_url in pendentes:
            for tx in transactions:
                if tx["valor"] == depix_esperado and tx["is_recent"]:
                    diff_str = f"{tx.get('diff_seconds', 0):.0f}s"
                    print(f"   💰 PAGAMENTO CONFIRMADO: R$ {valor_brl} -> DePix: {depix_esperado} (tx: {tx_id}) [data: {tx['data_str']}, diff: {diff_str}]")

                    agora = time.time()
                    texto = f"Depix {tx['data_str']} {tx['valor']}"
                    conn.execute(
                        "UPDATE pendentes SET status = 'confirmed', confirmed_at = ?, texto_confirmacao = ? WHERE id = ?",
                        (agora, texto, pid)
                    )

                    conn.execute("""
                        INSERT INTO historico
                        (valor_brl, valor_original, depix_esperado, usuario_id, transaction_id,
                         codigo_pix, webhook_url, status, created_at, confirmed_at, texto_confirmacao)
                        SELECT valor_brl, valor_original, depix_esperado, usuario_id, transaction_id,
                               codigo_pix, webhook_url, 'confirmed', created_at, ?, ?
                        FROM pendentes WHERE id = ?
                    """, (agora, texto, pid))

                    conn.execute("DELETE FROM pendentes WHERE id = ?", (pid,))

                    confirmados.append({
                        "transaction_id": tx_id,
                        "valor_brl": valor_brl,
                        "depix": depix_esperado,
                        "webhook_url": webhook_url,
                        "texto_lido": texto,
                        "data_transacao": tx["data_str"]
                    })
                    break
                elif tx["valor"] == depix_esperado and not tx["is_recent"]:
                    print(f"   ⚠️ DePix {depix_esperado} encontrado mas transacao antiga: {tx['data_str']} (diff: {tx.get('diff_seconds', 0):.0f}s)")

        if confirmados:
            conn.commit()
            print(f"   ✅ {len(confirmados)} pagamentos confirmados!")
        conn.close()
        return confirmados

    def verificar_pagamentos_historico(self) -> List[Dict]:
        xml = self.client.dump_xml(force=True)
        return self.verificar_pagamentos_home(xml=xml)

    def get_pendentes(self) -> List[Dict]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT transaction_id, valor_brl, depix_esperado, codigo_pix, status, created_at FROM pendentes WHERE status = 'pending'"
        )
        resultado = []
        for row in cursor.fetchall():
            resultado.append({
                "transaction_id": row[0],
                "valor_brl": row[1],
                "depix_esperado": row[2],
                "codigo_pix": row[3],
                "status": row[4],
                "created_at": row[5]
            })
        conn.close()
        return resultado

    def get_status(self, transaction_id: str) -> Optional[Dict]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT transaction_id, valor_brl, depix_esperado, codigo_pix, status, created_at, confirmed_at "
            "FROM pendentes WHERE transaction_id = ?", (transaction_id,)
        )
        row = cursor.fetchone()
        if row:
            conn.close()
            return {
                "transaction_id": row[0], "valor_brl": row[1], "depix_esperado": row[2],
                "codigo_pix": row[3], "status": row[4], "created_at": row[5], "confirmed_at": row[6]
            }

        cursor = conn.execute(
            "SELECT transaction_id, valor_brl, depix_esperado, codigo_pix, status, created_at, confirmed_at "
            "FROM historico WHERE transaction_id = ?", (transaction_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "transaction_id": row[0], "valor_brl": row[1], "depix_esperado": row[2],
                "codigo_pix": row[3], "status": row[4], "created_at": row[5], "confirmed_at": row[6]
            }
        return None
