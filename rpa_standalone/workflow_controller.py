import time
import httpx
from typing import Optional, List, Dict

from device_client import DeviceClient
from auth_manager import AuthManager
from navigation_manager import NavigationManager
from payment_manager import PaymentManager
from identification_manager import IdentificationManager
from conversion_manager import ConversionManager


class WorkflowController:

    def __init__(self, client: DeviceClient, pin: str = "222222",
                 db_path: str = "rpa_transactions.db"):
        self.client = client
        self.auth = AuthManager(client, pin=pin)
        self.nav = NavigationManager(client)
        self.pay = PaymentManager(client)
        self.ident = IdentificationManager(client, db_path=db_path)
        self.conv = ConversionManager(client)

    def preparar_terreno(self) -> bool:
        status = self.auth.garantir_app_aberto()

        if status == "LOGIN":
            if not self.auth.fazer_login():
                print("❌ Falha no login")
                return False
            return True
        elif status in ("OK", "HOME"):
            return True
        elif status == "ERRO":
            print("❌ Erro critico ao abrir app")
            return False
        else:
            print(f"   App na tela '{status}', navegando para Home...")
            if self.nav.ir_para_home():
                return True
            screen = self.client.identify_screen()
            if screen == "LOGIN":
                if not self.auth.fazer_login():
                    print("❌ Falha no login apos navegacao")
                    return False
                return True
            return False

    def gerar_pix(self, valor: float, transaction_id: str = None,
                  webhook_url: str = None, user_id: str = None) -> Dict:
        resultado = {
            "sucesso": False,
            "transaction_id": transaction_id or f"tx_{int(time.time())}",
            "valor_solicitado": valor,
            "valor_pix": None,
            "codigo_pix": "",
            "user_id": user_id or "",
            "erro": ""
        }

        if not self.preparar_terreno():
            resultado["erro"] = "Falha ao preparar terreno (login/app)"
            return resultado

        valor_unico = self.ident.gerar_valor_unico(
            valor_base=valor,
            transaction_id=resultado["transaction_id"],
            usuario_id=user_id or resultado["transaction_id"],
            webhook_url=webhook_url
        )

        if not valor_unico:
            resultado["erro"] = "Sem slots de valor disponiveis"
            return resultado

        resultado["valor_pix"] = valor_unico

        nav_status = self.nav.garantir_posicionamento_deposito()
        if nav_status == "LOGIN_NEEDED":
            if not self.auth.fazer_login():
                resultado["erro"] = "Falha no login"
                return resultado
            nav_status = self.nav.garantir_posicionamento_deposito()

        if nav_status != "OK":
            resultado["erro"] = "Falha na navegacao ate deposito PIX"
            return resultado

        pix_resultado = self.pay.gerar_pix_completo(valor_unico)

        if pix_resultado.get("diag"):
            for d in pix_resultado["diag"]:
                print(f"   [DIAG] {d}")

        if not pix_resultado["sucesso"]:
            resultado["erro"] = pix_resultado.get("erro", "Falha ao gerar PIX")
            resultado["diag"] = pix_resultado.get("diag", [])
            self.nav.ir_para_home()
            return resultado

        resultado["sucesso"] = True
        resultado["codigo_pix"] = pix_resultado["codigo_pix"]
        resultado["info"] = pix_resultado.get("info", {})

        self.ident.atualizar_codigo_pix(resultado["transaction_id"], resultado["codigo_pix"])

        self.nav.voltar()
        self.nav.ir_para_home()

        return resultado

    def auditar_pagamentos(self, usar_historico: bool = False) -> List[Dict]:
        if not self.preparar_terreno():
            return []

        if not self.nav.ir_para_home():
            return []

        xml = self.client.dump_xml(force=True)
        confirmados = self.ident.verificar_pagamentos_home(xml=xml)

        if not confirmados and usar_historico:
            if self.nav.ir_para_historico():
                confirmados = self.ident.verificar_pagamentos_historico()
                self.nav.sair_do_historico()

        for pagamento in confirmados:
            webhook_url = pagamento.get("webhook_url")
            if webhook_url:
                self._enviar_webhook(webhook_url, pagamento)

        return confirmados

    def _enviar_webhook(self, url: str, dados: Dict):
        try:
            print(f"   📡 Enviando webhook para {url}")
            payload = {
                "event": "payment_confirmed",
                "transaction_id": dados.get("transaction_id"),
                "valor_brl": dados.get("valor_brl"),
                "depix": dados.get("depix"),
                "timestamp": time.time()
            }
            with httpx.Client(timeout=10) as client:
                response = client.post(url, json=payload)
                if response.status_code == 200:
                    print(f"   ✅ Webhook enviado com sucesso")
                else:
                    print(f"   ⚠️ Webhook respondeu {response.status_code}")
        except Exception as e:
            print(f"   ❌ Erro ao enviar webhook: {e}")

    def ciclo_completo(self, valor: float, transaction_id: str = None,
                       webhook_url: str = None) -> Dict:
        resultado = self.gerar_pix(valor, transaction_id, webhook_url)

        if resultado["sucesso"]:
            time.sleep(0.5)
            confirmados = self.auditar_pagamentos()
            resultado["pagamentos_confirmados"] = len(confirmados)

        return resultado

    def executar_saque(self) -> Dict:
        print("💸 === INICIANDO SAQUE AUTOMATICO ===")
        resultado = {
            "sucesso": False,
            "etapa1": None,
            "etapa2": None,
            "erro": ""
        }

        if not self.preparar_terreno():
            resultado["erro"] = "Falha ao preparar terreno (login/app)"
            return resultado

        if not self.nav.ir_para_converter():
            resultado["erro"] = "Nao conseguiu navegar para tela Converter"
            return resultado

        etapa1 = self.conv.converter_depix_para_lbtc()
        resultado["etapa1"] = etapa1

        if not etapa1["sucesso"]:
            resultado["erro"] = f"Etapa 1 falhou: {etapa1.get('erro', 'desconhecido')}"
            self.nav.ir_para_home()
            return resultado

        print("   Aguardando entre conversoes...")
        time.sleep(1.5)

        screen = self.client.identify_screen()
        if screen != "CONVERTER":
            if not self.nav.ir_para_converter():
                resultado["erro"] = "Nao conseguiu voltar para Converter apos etapa 1"
                self.nav.ir_para_home()
                return resultado

        etapa2 = self.conv.converter_lbtc_para_btc()
        resultado["etapa2"] = etapa2

        if not etapa2["sucesso"]:
            resultado["erro"] = f"Etapa 2 falhou: {etapa2.get('erro', 'desconhecido')}"
            self.nav.ir_para_home()
            return resultado

        resultado["sucesso"] = True
        print("✅ === SAQUE AUTOMATICO CONCLUIDO COM SUCESSO ===")
        self.nav.ir_para_home()

        return resultado

    def converter_depix_lbtc(self) -> Dict:
        if not self.preparar_terreno():
            return {"sucesso": False, "erro": "Falha ao preparar terreno"}

        if not self.nav.ir_para_converter():
            return {"sucesso": False, "erro": "Nao conseguiu navegar para Converter"}

        result = self.conv.converter_depix_para_lbtc()
        self.nav.ir_para_home()
        return result

    def converter_lbtc_btc(self) -> Dict:
        if not self.preparar_terreno():
            return {"sucesso": False, "erro": "Falha ao preparar terreno"}

        if not self.nav.ir_para_converter():
            return {"sucesso": False, "erro": "Nao conseguiu navegar para Converter"}

        result = self.conv.converter_lbtc_para_btc()
        self.nav.ir_para_home()
        return result

    def get_status(self, transaction_id: str) -> Optional[Dict]:
        return self.ident.get_status(transaction_id)

    def get_pendentes(self) -> List[Dict]:
        return self.ident.get_pendentes()
