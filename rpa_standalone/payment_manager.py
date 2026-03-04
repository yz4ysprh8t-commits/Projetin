import time
import re
from device_client import DeviceClient


class PaymentManager:

    def __init__(self, client: DeviceClient):
        self.client = client

    def digitar_valor_e_gerar(self, valor: str) -> bool:
        valor_formatado = str(valor).replace(",", ".").strip()
        print(f"[Pay] Digitando valor R$ {valor_formatado} e gerando pagamento...")

        xml = self.client.dump_xml(force=True)
        screen = self.client.identify_screen(xml=xml)

        if screen != "DEPOSITO_PIX":
            print(f"   Tela errada: {screen} (esperado DEPOSITO_PIX)")
            return False

        input_elem = self.client.find_element(class_name="android.widget.EditText", xml=xml)
        if input_elem:
            cx, cy = input_elem["center"]
            print(f"   Campo de valor encontrado em ({cx}, {cy})")
            self.client.tap(cx, cy)
            time.sleep(0.2)
        else:
            texts = self.client.get_all_texts(xml=xml)
            print(f"   Campo EditText nao encontrado. Textos na tela: {texts[:10]}")
            return False

        self.client.key_delete(times=15)
        time.sleep(0.1)

        print(f"   Digitando {valor_formatado}...")
        self.client.input_text(valor_formatado)
        time.sleep(0.3)

        print("   Ocultando teclado...")
        self.client.key_back()
        time.sleep(0.3)

        if not self.client.wait_and_tap(text="Gerar Pagamento", timeout=6, interval=0.5):
            if not self.client.wait_and_tap(text="Gerar", timeout=4, interval=0.5):
                print("   Botao 'Gerar Pagamento' nao encontrado")
                return False

        print("   Aguardando QR Code carregar...")
        time.sleep(3)

        copiar = self.client.wait_for_element(text="Copiar", timeout=25, interval=0.5)
        if copiar:
            print("   QR Code carregado com sucesso!")
            return True

        screen = self.client.identify_screen()
        if screen == "QR_CODE":
            return True

        print("   QR Code nao carregou no tempo esperado")
        return False

    def copiar_codigo_pix(self) -> str:
        print("[Pay] Extraindo codigo PIX da tela...")

        xml = self.client.dump_xml(force=True)
        screen = self.client.identify_screen(xml=xml)

        if screen != "QR_CODE":
            print(f"   [DIAG] Tela atual: {screen} (esperado QR_CODE)")
            codigo = self._buscar_pix_no_xml(xml)
            if codigo:
                return codigo
            return ""

        codigo = self._extrair_pix_expandido(xml)
        if codigo:
            return codigo

        print("   Codigo truncado, clicando para expandir...")
        pix_elem = self.client.find_element(content_desc="0002", xml=xml)
        if pix_elem:
            cx, cy = pix_elem["center"]
            print(f"   Clicando no codigo truncado em ({cx}, {cy})")
            self.client.tap(cx, cy)
            time.sleep(0.5)

            xml2 = self.client.dump_xml(force=True)
            codigo = self._extrair_pix_expandido(xml2)
            if codigo:
                return codigo

        print("   Tentando buscar via scroll/descs...")
        xml3 = self.client.dump_xml(force=True)
        all_descs = re.findall(r'content-desc="([^"]+)"', xml3)
        for desc in all_descs:
            limpo = desc.replace("&#10;", "").replace("\n", "").strip()
            if len(limpo) > 50 and limpo.startswith("0002"):
                print(f"   Codigo PIX encontrado em desc ({len(limpo)} chars)")
                return limpo

        print("   Nao foi possivel capturar o codigo PIX")
        return ""

    def _extrair_pix_expandido(self, xml: str) -> str:
        all_descs = re.findall(r'content-desc="([^"]+)"', xml)
        for desc in all_descs:
            limpo = desc.replace("&#10;", "").replace("\n", "").strip()
            if len(limpo) > 100 and limpo.startswith("0002"):
                print(f"   Codigo PIX completo extraido do XML ({len(limpo)} chars)")
                return limpo

        all_texts = self.client.get_all_texts(xml=xml)
        for texto in all_texts:
            limpo = texto.replace("\n", "").strip()
            if len(limpo) > 100 and limpo.startswith("0002"):
                print(f"   Codigo PIX completo extraido de text ({len(limpo)} chars)")
                return limpo

        return ""

    def _buscar_pix_no_xml(self, xml: str) -> str:
        all_texts = self.client.get_all_texts(xml=xml)
        for texto in all_texts:
            if len(texto) > 50 and (texto.startswith("00020126") or "pix" in texto.lower()):
                print(f"   Codigo encontrado em text ({len(texto)} chars)")
                return texto

        all_descs = re.findall(r'content-desc="([^"]+)"', xml)
        for desc in all_descs:
            if len(desc) > 50 and (desc.startswith("00020126") or "pix" in desc.lower()):
                print(f"   Codigo encontrado em content-desc ({len(desc)} chars)")
                return desc

        for desc in all_descs:
            if len(desc) > 100:
                print(f"   [DIAG] content-desc longo encontrado ({len(desc)} chars): {desc[:80]}...")
                if any(c.isdigit() for c in desc[:10]):
                    print(f"   Possivel codigo PIX em content-desc longo")
                    return desc

        return ""

    def extrair_info_qr(self, xml: str = None) -> dict:
        if xml is None:
            xml = self.client.dump_xml(force=True)

        info = {
            "valor_depix": None,
            "valor_brl": None,
            "taxa_fixa": None,
            "taxa_pct": None,
            "status": None
        }

        all_texts = self.client.get_all_texts(xml=xml)

        for texto in all_texts:
            texto_lower = texto.lower()

            if "depix" in texto_lower or "de pix" in texto_lower:
                match = re.search(r'(\d+[.,]\d{2})', texto)
                if match:
                    info["valor_depix"] = match.group(1)

            if "0,99" in texto or "0.99" in texto:
                info["taxa_fixa"] = "0.99"

            if "3%" in texto:
                info["taxa_pct"] = "3"

            if "pago" in texto_lower or "confirmado" in texto_lower or "aprovado" in texto_lower:
                info["status"] = "pago"
            elif "pendente" in texto_lower or "aguardando" in texto_lower:
                info["status"] = "pendente"

        return info

    def gerar_pix_completo(self, valor: str) -> dict:
        resultado = {
            "sucesso": False,
            "codigo_pix": "",
            "valor": valor,
            "info": {},
            "diag": []
        }

        if not self.digitar_valor_e_gerar(valor):
            resultado["erro"] = "Falha ao gerar pagamento"
            resultado["diag"].append("digitar_valor_e_gerar retornou False")
            return resultado

        resultado["diag"].append("QR gerado OK, tentando copiar...")

        xml = self.client.dump_xml(force=True)
        screen = self.client.identify_screen(xml=xml)
        resultado["diag"].append(f"Tela detectada: {screen}")

        all_texts = self.client.get_all_texts(xml=xml)
        resultado["diag"].append(f"Textos: {all_texts[:20]}")

        all_descs = re.findall(r'content-desc="([^"]+)"', xml)
        descs_filtrados = [d for d in all_descs if d][:20]
        resultado["diag"].append(f"Descs: {descs_filtrados}")

        resultado["diag"].append(f"XML length: {len(xml)}")

        codigo = self.copiar_codigo_pix()
        if not codigo:
            resultado["erro"] = "Falha ao copiar codigo PIX"
            resultado["diag"].append("copiar_codigo_pix retornou vazio")
            try:
                with open("last_fail_xml.txt", "w") as f:
                    f.write(xml)
                resultado["diag"].append("XML salvo em last_fail_xml.txt")
            except:
                pass
            return resultado

        info = self.extrair_info_qr()

        resultado["sucesso"] = True
        resultado["codigo_pix"] = codigo
        resultado["info"] = info

        return resultado
