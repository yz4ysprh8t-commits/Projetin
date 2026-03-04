import time
import re
import xml.etree.ElementTree as ET
from device_client import DeviceClient


class NavigationManager:

    PACKAGE_NAME = "com.satsails.Satsails"

    def __init__(self, client: DeviceClient):
        self.client = client

    def _wait_screen(self, target: str, timeout: int = 6) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            screen = self.client.identify_screen()
            if screen == target:
                return True
            time.sleep(0.5)
        return False

    def _wait_any_screen(self, targets: list, timeout: int = 6) -> str:
        start = time.time()
        while time.time() - start < timeout:
            screen = self.client.identify_screen()
            if screen in targets:
                return screen
            time.sleep(0.5)
        return ""

    def voltar(self):
        xml = self.client.dump_xml(force=True)
        if self._tap_seta_voltar(xml):
            self._wait_any_screen(["HOME", "TIPO_DEPOSITO"], timeout=3)
            return

        self.client.key_back()
        time.sleep(0.3)

    def _tap_seta_voltar(self, xml: str = None) -> bool:
        if xml is None:
            xml = self.client.dump_xml(force=True)
        if not xml:
            return False

        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return False

        for node in root.iter("node"):
            desc = (node.attrib.get("content-desc", "") or "").lower()
            text = (node.attrib.get("text", "") or "").lower()
            cls = node.attrib.get("class", "")

            is_back = False
            if "voltar" in desc or "back" in desc or "navigate up" in desc:
                is_back = True
            if "voltar" in text or "back" in text:
                is_back = True

            if not is_back:
                bounds_str = node.attrib.get("bounds", "")
                bounds_match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
                if bounds_match:
                    x1, y1 = int(bounds_match.group(1)), int(bounds_match.group(2))
                    x2, y2 = int(bounds_match.group(3)), int(bounds_match.group(4))
                    w, h = x2 - x1, y2 - y1
                    clickable = node.attrib.get("clickable", "false") == "true"
                    if (clickable or "Image" in cls or "Button" in cls) and x1 < 100 and y1 < 200 and w < 120 and h < 120:
                        is_back = True

            if is_back:
                bounds_str = node.attrib.get("bounds", "")
                bounds_match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
                if bounds_match:
                    x1, y1 = int(bounds_match.group(1)), int(bounds_match.group(2))
                    x2, y2 = int(bounds_match.group(3)), int(bounds_match.group(4))
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                    print(f"   [Nav] Seta voltar encontrada em ({cx}, {cy})")
                    self.client.tap(cx, cy)
                    return True

        return False

    def ir_para_home(self, max_tentativas: int = 5) -> bool:
        for tentativa in range(max_tentativas):
            xml = self.client.dump_xml(force=True)
            screen = self.client.identify_screen(xml=xml)

            if screen == "HOME":
                print("[Nav] Home confirmada")
                return True

            if screen == "LOGIN":
                print("   Detectada tela de login (precisa autenticar)")
                return False

            print(f"   Tentativa {tentativa+1}: tela '{screen}', voltando...")

            if not self._tap_seta_voltar(xml):
                self.client.key_back()
            time.sleep(0.5)

        self.client.key_home()
        if self._wait_screen("HOME", timeout=3):
            print("[Nav] Home via tecla Home do Android")
            return True

        print("[Nav] Nao conseguiu voltar para Home. Reiniciando app...")
        self._reiniciar_app()

        xml = self.client.dump_xml(force=True)
        screen = self.client.identify_screen(xml=xml)

        if screen == "LOGIN":
            print("   App reiniciou na tela de login")
            return False

        if screen == "HOME":
            return True

        for tentativa in range(3):
            print(f"   Pos-reinicio tentativa {tentativa+1}: tela '{screen}'")
            if not self._tap_seta_voltar():
                self.client.key_back()
            time.sleep(1)
            screen = self.client.identify_screen()
            if screen in ("HOME", "LOGIN"):
                return screen == "HOME"

        return False

    def _reiniciar_app(self):
        print("   Tentando force-stop...")
        self.client.force_stop(self.PACKAGE_NAME)
        time.sleep(0.5)

        result = self.client.shell("pidof " + self.PACKAGE_NAME)
        if result.strip():
            print("   force-stop nao funcionou, tentando kill...")
            self.client.shell(f"kill {result.strip()} 2>/dev/null")
            time.sleep(0.3)
            self.client.shell(f"run-as {self.PACKAGE_NAME} kill {result.strip()} 2>/dev/null")
            time.sleep(0.3)

        print("   Abrindo app...")
        self.client.shell(f"am start -n {self.PACKAGE_NAME}/.MainActivity 2>/dev/null")

        loaded = self._wait_any_screen(["HOME", "LOGIN", "TIPO_DEPOSITO"], timeout=10)
        if loaded:
            print(f"   App abriu na tela: {loaded}")
            return

        self.client.open_app(self.PACKAGE_NAME)
        self._wait_any_screen(["HOME", "LOGIN"], timeout=8)

    def ir_para_compra(self) -> bool:
        print("[Nav] Indo para Compra...")
        xml = self.client.dump_xml(force=True)
        screen = self.client.identify_screen(xml=xml)

        if screen != "HOME":
            print(f"   Nao esta na Home (tela: {screen}), tentando voltar...")
            if not self.ir_para_home():
                return False

        if not self.client.wait_and_tap(text="Compra", timeout=6):
            print("   Botao 'Compra' nao encontrado na Home")
            texts = self.client.get_all_texts()
            print(f"   [DIAG] Textos na tela: {texts[:15]}")
            return False

        loaded = self._wait_any_screen(["TIPO_DEPOSITO", "DEPOSITO_PIX"], timeout=8)
        if loaded:
            print(f"   Tela apos Compra: {loaded}")
            return True

        elem = self.client.wait_for_element(text="Tipo de Dep", timeout=3)
        if elem:
            print("   Tela Tipo de Deposito carregada")
            return True

        screen = self.client.identify_screen()
        print(f"   [DIAG] Tela apos clicar Compra: {screen}")
        texts = self.client.get_all_texts()
        print(f"   [DIAG] Textos: {texts[:15]}")

        if screen not in ("HOME", "LOGIN", "DESCONHECIDO"):
            return True

        return False

    def ir_para_deposito_pix(self) -> bool:
        print("[Nav] Indo para Deposito via PIX...")
        xml = self.client.dump_xml(force=True)
        screen = self.client.identify_screen(xml=xml)

        if screen == "DEPOSITO_PIX":
            print("   Ja esta na tela de Deposito PIX")
            return True

        if screen != "TIPO_DEPOSITO":
            if not self.ir_para_compra():
                return False
            screen = self.client.identify_screen()

        if screen == "DEPOSITO_PIX":
            return True

        if not self.client.wait_and_tap(text="Comprar", timeout=6):
            texts = self.client.get_all_texts()
            print(f"   [DIAG] Botao Comprar nao encontrado. Textos: {texts[:15]}")

            for candidate in ["Bitcoin", "BTC", "Pix", "PIX", "Depósito", "Deposito"]:
                if self.client.tap_element(text=candidate):
                    print(f"   Tentou clicar em '{candidate}' como alternativa")
                    break
            else:
                print("   Nenhum botao alternativo encontrado")
                return False

        if self._wait_screen("DEPOSITO_PIX", timeout=10):
            print("   Tela Deposito via PIX carregada")
            return True

        screen = self.client.identify_screen()
        if screen == "DEPOSITO_PIX":
            return True

        print(f"   [DIAG] Tela apos clicar Comprar: {screen}")
        texts = self.client.get_all_texts()
        print(f"   [DIAG] Textos: {texts[:15]}")

        return False

    def ir_para_historico(self) -> bool:
        print("[Nav] Indo para Historico...")
        xml = self.client.dump_xml(force=True)
        screen = self.client.identify_screen(xml=xml)

        if screen == "HISTORICO":
            print("   Ja esta no Historico")
            return True

        if screen != "HOME":
            if not self.ir_para_home():
                return False

        if not self.client.wait_and_tap(text="Ver todas as transa", timeout=6):
            if not self.client.wait_and_tap(text="Ver todas", timeout=3):
                print("   Botao 'Ver todas as transacoes' nao encontrado")
                return False

        if self._wait_screen("HISTORICO", timeout=8):
            print("   Tela Historico carregada")
            return True

        screen = self.client.identify_screen()
        if screen == "HISTORICO":
            return True

        print("   Historico nao carregou")
        return False

    def sair_do_historico(self) -> bool:
        self.voltar()
        screen = self.client.identify_screen()
        if screen == "HOME":
            return True
        self.voltar()
        return self.client.identify_screen() == "HOME"

    def ir_para_converter(self) -> bool:
        print("[Nav] Indo para tela Converter...")
        xml = self.client.dump_xml(force=True)
        screen = self.client.identify_screen(xml=xml)

        if screen == "CONVERTER":
            print("   Ja esta na tela Converter")
            return True

        if screen != "HOME":
            print(f"   Tela atual: {screen}, voltando para Home...")
            if not self.ir_para_home():
                return False

        if self.client.tap_element(content_desc="Converter"):
            if self._wait_screen("CONVERTER", timeout=5):
                print("   Tela Converter carregada")
                return True

        xml = self.client.dump_xml(force=True)
        bottom_icons = []
        try:
            root = ET.fromstring(xml)
            for node in root.iter("node"):
                bounds_str = node.attrib.get("bounds", "")
                bounds_match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
                if bounds_match:
                    y1 = int(bounds_match.group(2))
                    y2 = int(bounds_match.group(4))
                    x1 = int(bounds_match.group(1))
                    x2 = int(bounds_match.group(3))
                    if y1 > 800 and (y2 - y1) < 120:
                        clickable = node.attrib.get("clickable", "false") == "true"
                        cls = node.attrib.get("class", "")
                        if clickable or "Image" in cls or "Button" in cls:
                            bottom_icons.append({
                                "x": (x1 + x2) // 2,
                                "y": (y1 + y2) // 2,
                                "bounds": (x1, y1, x2, y2)
                            })
        except Exception:
            pass

        if bottom_icons:
            bottom_icons.sort(key=lambda e: e["x"])
            unique_icons = []
            for icon in bottom_icons:
                if not unique_icons or abs(icon["x"] - unique_icons[-1]["x"]) > 40:
                    unique_icons.append(icon)

            if len(unique_icons) >= 3:
                target = unique_icons[2]
                print(f"   Clicando 3o icone navbar ({target['x']}, {target['y']})")
                self.client.tap(target["x"], target["y"])
                if self._wait_screen("CONVERTER", timeout=5):
                    print("   Tela Converter carregada via navbar")
                    return True

        print("   Nao conseguiu abrir tela Converter")
        return False

    def garantir_posicionamento_deposito(self) -> str:
        xml = self.client.dump_xml(force=True)
        screen = self.client.identify_screen(xml=xml)

        if screen == "DEPOSITO_PIX":
            return "OK"

        if screen == "TIPO_DEPOSITO":
            if self.ir_para_deposito_pix():
                return "OK"
            return "ERRO"

        if screen == "HOME":
            if self.ir_para_deposito_pix():
                return "OK"
            return "ERRO"

        if screen == "LOGIN":
            return "LOGIN_NEEDED"

        if not self.ir_para_home():
            return "ERRO"

        if self.ir_para_deposito_pix():
            return "OK"

        return "ERRO"
