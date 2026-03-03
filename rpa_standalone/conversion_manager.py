import time
import re
from typing import Optional, Dict

from device_client import DeviceClient


class ConversionManager:

    MIN_BTC_AMOUNT = 0.00025000
    DEPIX_TO_LBTC = "depix_to_lbtc"
    LBTC_TO_BTC = "lbtc_to_btc"

    def __init__(self, client: DeviceClient):
        self.client = client

    def selecionar_moeda_de(self, moeda: str) -> bool:
        print(f"   Selecionando moeda DE: {moeda}")
        xml = self.client.dump_xml(force=True)

        de_section = self.client.find_element(text="De", xml=xml)
        if not de_section:
            de_section = self.client.find_element(text="Dé", xml=xml)

        dropdown_found = False
        if self.client.has_text("Depix", xml) and moeda.lower() == "depix":
            print("   Depix ja selecionado como moeda DE")
            return True
        if self.client.has_text("Liquid Bitcoin", xml) and moeda.lower() in ("liquid bitcoin", "lbtc", "liquid"):
            print("   Liquid Bitcoin ja selecionado como moeda DE")
            return True

        elems_de = self.client.find_all_elements(text="", xml=xml)
        for elem in elems_de:
            txt = elem.get("text", "").lower()
            if txt in ("depix", "liquid bitcoin", "bitcoin"):
                cx, cy = elem["center"]
                if de_section and cy > de_section["center"][1]:
                    print(f"   Clicando no seletor DE em ({cx}, {cy})")
                    self.client.tap(cx, cy)
                    dropdown_found = True
                    break

        if not dropdown_found:
            if de_section:
                cx, cy = de_section["center"]
                self.client.tap(cx, cy + 40)
                dropdown_found = True

        if dropdown_found:
            time.sleep(1.5)
            xml = self.client.dump_xml(force=True)

            if self.client.wait_and_tap(text=moeda, timeout=5):
                print(f"   Moeda '{moeda}' selecionada")
                time.sleep(1)
                return True

        print(f"   Nao conseguiu selecionar moeda DE: {moeda}")
        return False

    def selecionar_moeda_para(self, moeda: str) -> bool:
        print(f"   Selecionando moeda PARA: {moeda}")
        xml = self.client.dump_xml(force=True)

        para_section = self.client.find_element(text="Para", xml=xml)

        if para_section:
            cx, cy = para_section["center"]
            below_para = []
            try:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(xml)
                for node in root.iter("node"):
                    node_text = node.attrib.get("text", "")
                    bounds_str = node.attrib.get("bounds", "")
                    bounds_match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
                    if bounds_match:
                        ny = int(bounds_match.group(2))
                        if ny > cy and node_text:
                            below_para.append({
                                "text": node_text,
                                "center": ((int(bounds_match.group(1)) + int(bounds_match.group(3))) // 2,
                                          (ny + int(bounds_match.group(4))) // 2)
                            })
            except Exception:
                pass

            currency_below = [e for e in below_para if e["text"].lower() in
                            ("depix", "liquid bitcoin", "bitcoin", "btc")]

            if currency_below:
                target = currency_below[0]
                if target["text"].lower() == moeda.lower():
                    print(f"   '{moeda}' ja selecionado como PARA")
                    return True
                print(f"   Clicando no seletor PARA: {target['text']}")
                self.client.tap(target["center"][0], target["center"][1])
            else:
                self.client.tap(cx, cy + 40)

            time.sleep(1.5)

            if self.client.wait_and_tap(text=moeda, timeout=5):
                print(f"   Moeda PARA '{moeda}' selecionada")
                time.sleep(1)
                return True

        print(f"   Nao conseguiu selecionar moeda PARA: {moeda}")
        return False

    def clicar_max(self) -> bool:
        print("   Clicando em Max...")
        if self.client.wait_and_tap(text="Max", timeout=5):
            print("   Max clicado")
            time.sleep(1)
            return True
        print("   Botao Max nao encontrado")
        return False

    def ler_saldo_disponivel(self, xml: str = None) -> Optional[str]:
        if xml is None:
            xml = self.client.dump_xml(force=True)

        all_texts = self.client.get_all_texts(xml=xml)

        for i, texto in enumerate(all_texts):
            if "Saldo Dispon" in texto:
                if i + 1 < len(all_texts):
                    saldo = all_texts[i + 1]
                    match = re.search(r'[\d.,]+', saldo)
                    if match:
                        return match.group(0)

        for texto in all_texts:
            match = re.match(r'^[\d]+[.,][\d]+$', texto.strip())
            if match and texto.strip() != "0":
                return texto.strip()

        return None

    def ajustar_taxa_minima(self) -> bool:
        print("💰 Ajustando taxa para minimo (Lento)...")

        if not self.client.wait_and_tap(text="Taxas e limites", timeout=5):
            if not self.client.wait_and_tap(text="taxas e limites", timeout=3):
                print("   Link 'Taxas e limites' nao encontrado, pode ja estar aberto")

        time.sleep(1.5)
        xml = self.client.dump_xml(force=True)

        lento = self.client.find_element(text="Lento", xml=xml)
        rapido = self.client.find_element(text="Rápido", xml=xml)

        if not rapido:
            rapido = self.client.find_element(text="Rapido", xml=xml)

        if lento and rapido:
            lento_x = lento["center"][0]

            slider_y = (lento["bounds"][1] + rapido["bounds"][1]) // 2
            if lento["bounds"][1] > 0:
                slider_y = lento["bounds"][1] - 30

            seekbar = self.client.find_element(class_name="android.widget.SeekBar", xml=xml)
            if seekbar:
                sx1, sy1, sx2, sy2 = seekbar["bounds"]
                slider_start_x = sx1 + 10
                slider_y = (sy1 + sy2) // 2
                print(f"   SeekBar encontrado: arrastando para esquerda ({slider_start_x}, {slider_y})")
                self.client.swipe(sx2 - 20, slider_y, sx1 + 10, slider_y, duration=500)
            else:
                print(f"   Arrastando slider para 'Lento' em x={lento_x}")
                self.client.swipe(rapido["center"][0], slider_y, lento_x, slider_y, duration=500)

            time.sleep(1)
            print("✅ Taxa ajustada para minimo")
            return True

        seekbar = self.client.find_element(class_name="android.widget.SeekBar", xml=xml)
        if seekbar:
            sx1, sy1, sx2, sy2 = seekbar["bounds"]
            slider_y = (sy1 + sy2) // 2
            print(f"   SeekBar encontrado sem labels: arrastando para esquerda")
            self.client.swipe(sx2 - 20, slider_y, sx1 + 10, slider_y, duration=500)
            time.sleep(1)
            print("✅ Taxa ajustada para minimo via SeekBar")
            return True

        print("   Nao encontrou slider de taxa")
        return False

    def arrastar_para_confirmar(self) -> bool:
        print("➡️ Arrastando slider para confirmar conversao...")
        xml = self.client.dump_xml(force=True)

        slide_elem = self.client.find_element(text="Arrastar", xml=xml)
        if not slide_elem:
            slide_elem = self.client.find_element(text="Deslize", xml=xml)
        if not slide_elem:
            slide_elem = self.client.find_element(text="Slide", xml=xml)
        if not slide_elem:
            slide_elem = self.client.find_element(content_desc="Slide", xml=xml)
        if not slide_elem:
            slide_elem = self.client.find_element(content_desc="Arrastar", xml=xml)

        if slide_elem:
            x1, y1, x2, y2 = slide_elem["bounds"]
            start_x = x1 + 30
            end_x = x2 - 10
            cy = (y1 + y2) // 2
            print(f"   Arrastando de ({start_x}, {cy}) ate ({end_x}, {cy})")
            self.client.swipe(start_x, cy, end_x, cy, duration=800)
            time.sleep(3)
            return True

        all_elems = []
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml)
            for node in root.iter("node"):
                bounds_str = node.attrib.get("bounds", "")
                bounds_match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
                if bounds_match:
                    y1 = int(bounds_match.group(2))
                    y2 = int(bounds_match.group(4))
                    x1 = int(bounds_match.group(1))
                    x2 = int(bounds_match.group(3))
                    width = x2 - x1
                    height = y2 - y1
                    if width > 200 and 30 < height < 100 and y1 > 600:
                        all_elems.append({
                            "bounds": (x1, y1, x2, y2),
                            "center": ((x1 + x2) // 2, (y1 + y2) // 2),
                            "width": width,
                            "height": height,
                            "y": y1
                        })
        except Exception:
            pass

        if all_elems:
            all_elems.sort(key=lambda e: e["y"], reverse=True)
            slider = all_elems[0]
            x1, y1, x2, y2 = slider["bounds"]
            start_x = x1 + 30
            end_x = x2 - 10
            cy = (y1 + y2) // 2
            print(f"   Slider detectado por heuristica: arrastando ({start_x}, {cy}) -> ({end_x}, {cy})")
            self.client.swipe(start_x, cy, end_x, cy, duration=800)
            time.sleep(3)
            return True

        print("   Slider de confirmacao nao encontrado")
        return False

    def aguardar_conversao_concluida(self, timeout: int = 30) -> bool:
        print("⏳ Aguardando conversao ser processada...")
        start = time.time()
        while time.time() - start < timeout:
            xml = self.client.dump_xml(force=True)
            all_texts = self.client.get_all_texts(xml=xml)

            for texto in all_texts:
                texto_lower = texto.lower()
                if any(word in texto_lower for word in ["sucesso", "conclu", "realizada", "convertido", "completa"]):
                    print(f"✅ Conversao concluida: '{texto}'")
                    return True

            screen = self.client.identify_screen(xml=xml)
            if screen == "HOME":
                print("✅ Voltou para Home (conversao provavelmente concluida)")
                return True

            time.sleep(2)

        print("   Timeout aguardando conclusao da conversao")
        return False

    def converter_depix_para_lbtc(self) -> Dict:
        print("🔄 === CONVERSAO: Depix → Liquid Bitcoin ===")
        resultado = {
            "sucesso": False,
            "tipo": self.DEPIX_TO_LBTC,
            "saldo_antes": None,
            "erro": ""
        }

        xml = self.client.dump_xml(force=True)
        screen = self.client.identify_screen(xml=xml)

        if screen != "CONVERTER":
            resultado["erro"] = f"Tela errada: {screen} (esperado CONVERTER)"
            return resultado

        resultado["saldo_antes"] = self.ler_saldo_disponivel(xml=xml)

        if not self.selecionar_moeda_de("Depix"):
            resultado["erro"] = "Nao conseguiu selecionar Depix como moeda DE"
            return resultado

        if not self.selecionar_moeda_para("Liquid Bitcoin"):
            resultado["erro"] = "Nao conseguiu selecionar Liquid Bitcoin como moeda PARA"
            return resultado

        if not self.clicar_max():
            resultado["erro"] = "Nao conseguiu clicar em Max"
            return resultado

        time.sleep(1)

        if not self.arrastar_para_confirmar():
            resultado["erro"] = "Nao conseguiu arrastar slider de confirmacao"
            return resultado

        if self.aguardar_conversao_concluida(timeout=30):
            resultado["sucesso"] = True
            print("✅ Depix → Liquid Bitcoin concluido!")
        else:
            resultado["erro"] = "Timeout aguardando conversao Depix→LBTC"

        return resultado

    def converter_lbtc_para_btc(self) -> Dict:
        print("🔄 === CONVERSAO: Liquid Bitcoin → Bitcoin ===")
        resultado = {
            "sucesso": False,
            "tipo": self.LBTC_TO_BTC,
            "saldo_antes": None,
            "erro": ""
        }

        xml = self.client.dump_xml(force=True)
        screen = self.client.identify_screen(xml=xml)

        if screen != "CONVERTER":
            resultado["erro"] = f"Tela errada: {screen} (esperado CONVERTER)"
            return resultado

        resultado["saldo_antes"] = self.ler_saldo_disponivel(xml=xml)

        if not self.selecionar_moeda_de("Liquid Bitcoin"):
            resultado["erro"] = "Nao conseguiu selecionar Liquid Bitcoin como moeda DE"
            return resultado

        if not self.selecionar_moeda_para("Bitcoin"):
            resultado["erro"] = "Nao conseguiu selecionar Bitcoin como moeda PARA"
            return resultado

        if not self.clicar_max():
            resultado["erro"] = "Nao conseguiu clicar em Max"
            return resultado

        time.sleep(1)

        saldo_str = self.ler_saldo_disponivel()
        if saldo_str:
            try:
                saldo_float = float(saldo_str.replace(",", "."))
                if saldo_float < self.MIN_BTC_AMOUNT:
                    resultado["erro"] = f"Saldo insuficiente: {saldo_str} < {self.MIN_BTC_AMOUNT} BTC (minimo)"
                    return resultado
            except ValueError:
                pass

        self.ajustar_taxa_minima()
        time.sleep(1)

        self.client.key_back()
        time.sleep(1)

        if not self.arrastar_para_confirmar():
            resultado["erro"] = "Nao conseguiu arrastar slider de confirmacao"
            return resultado

        if self.aguardar_conversao_concluida(timeout=60):
            resultado["sucesso"] = True
            print("✅ Liquid Bitcoin → Bitcoin concluido!")
        else:
            resultado["erro"] = "Timeout aguardando conversao LBTC→BTC"

        return resultado

    def saque_completo(self) -> Dict:
        print("💸 === SAQUE AUTOMATICO COMPLETO ===")
        print("   Etapa 1: Depix → Liquid Bitcoin")
        print("   Etapa 2: Liquid Bitcoin → Bitcoin")

        resultado = {
            "sucesso": False,
            "etapa1": None,
            "etapa2": None,
            "erro": ""
        }

        etapa1 = self.converter_depix_para_lbtc()
        resultado["etapa1"] = etapa1

        if not etapa1["sucesso"]:
            resultado["erro"] = f"Etapa 1 falhou: {etapa1.get('erro', 'desconhecido')}"
            return resultado

        print("   Aguardando 5s entre conversoes...")
        time.sleep(5)

        xml = self.client.dump_xml(force=True)
        screen = self.client.identify_screen(xml=xml)

        if screen != "CONVERTER":
            resultado["erro"] = f"Nao esta na tela Converter apos etapa 1 (tela: {screen}). Navegacao externa necessaria."
            return resultado

        etapa2 = self.converter_lbtc_para_btc()
        resultado["etapa2"] = etapa2

        if not etapa2["sucesso"]:
            resultado["erro"] = f"Etapa 2 falhou: {etapa2.get('erro', 'desconhecido')}"
            return resultado

        resultado["sucesso"] = True
        print("✅ === SAQUE AUTOMATICO CONCLUIDO COM SUCESSO ===")
        return resultado
