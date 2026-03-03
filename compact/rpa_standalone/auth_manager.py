import time
import re
from device_client import DeviceClient


class AuthManager:

    PACKAGE_NAME = "com.satsails.Satsails"

    FALLBACK_COORDS = {
        "1": (96, 312), "2": (240, 312), "3": (383, 312),
        "4": (96, 451), "5": (240, 451), "6": (383, 451),
        "7": (96, 589), "8": (240, 589), "9": (383, 589),
        "0": (240, 728),
    }

    def __init__(self, client: DeviceClient, pin: str = "222222"):
        self.client = client
        self.pin = pin
        self.pin_coords = None

    def _detectar_coords_pin(self, xml: str) -> dict:
        coords = {}
        if not xml:
            return coords
        pattern = r'content-desc="(\d)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
        for match in re.finditer(pattern, xml):
            digito = match.group(1)
            x1, y1, x2, y2 = int(match.group(2)), int(match.group(3)), int(match.group(4)), int(match.group(5))
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            coords[digito] = (cx, cy)

        if not coords:
            pattern2 = r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*content-desc="(\d)"'
            for match in re.finditer(pattern2, xml):
                x1, y1, x2, y2 = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
                digito = match.group(5)
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                coords[digito] = (cx, cy)

        return coords

    def fazer_login(self) -> bool:
        print("Iniciando login...")

        xml = self.client.dump_xml(force=True)
        screen = self.client.identify_screen(xml=xml)

        if screen == "HOME":
            print("   Ja esta logado (Home detectada)")
            return True

        detected = self._detectar_coords_pin(xml)
        if len(detected) >= 9:
            self.pin_coords = detected
            print(f"   Coordenadas detectadas automaticamente para {len(detected)} digitos")
        else:
            self.pin_coords = self.FALLBACK_COORDS
            print(f"   Usando coordenadas fallback (detectadas: {len(detected)})")

        print(f"   Digitando PIN ({len(self.pin)} digitos)...")
        for digito in self.pin:
            coord = self.pin_coords.get(digito, self.FALLBACK_COORDS.get(digito, (240, 400)))
            self.client.tap(coord[0], coord[1])
            time.sleep(0.2)

        print("   PIN digitado. Aguardando Home...")

        home = self.client.wait_for_element(text="Compra", timeout=8, interval=0.5)
        if home:
            print("Login concluido com sucesso!")
            return True

        xml = self.client.dump_xml(force=True)
        screen = self.client.identify_screen(xml=xml)
        if screen == "HOME":
            print("Login concluido com sucesso!")
            return True

        node_count = xml.count('class="android.view.View"') if xml else 0
        has_scroll = "ScrollView" in xml if xml else False
        if has_scroll or node_count > 15:
            print(f"Login provavelmente OK (nodes={node_count}, scroll={has_scroll})")
            return True

        print("Login falhou - Home nao carregou apos PIN")
        return False

    def garantir_app_aberto(self) -> str:
        xml = self.client.dump_xml(force=True)
        pkg = self._get_package(xml)
        screen = self.client.identify_screen(xml=xml)

        if screen == "HOME":
            return "OK"
        if screen == "LOGIN":
            return "LOGIN"

        if screen in ("TIPO_DEPOSITO", "DEPOSITO_PIX", "QR_CODE", "HISTORICO", "CONVERTER", "CONVERTER_TAXAS"):
            print(f"   App aberto na tela {screen}, precisa navegar para Home")
            return screen

        if pkg == self.PACKAGE_NAME:
            print(f"   App aberto mas tela desconhecida, tentando login")
            return "LOGIN"

        print("Abrindo SatSails...")
        self.client.shell(f"am start -n {self.PACKAGE_NAME}/.MainActivity 2>/dev/null")

        elem = self.client.wait_for_element(text="Bem-vindo", timeout=6, interval=0.5)
        if not elem:
            elem = self.client.wait_for_element(text="Compra", timeout=4, interval=0.5)

        xml = self.client.dump_xml(force=True)
        pkg = self._get_package(xml)
        screen = self.client.identify_screen(xml=xml)

        if screen == "HOME":
            return "OK"
        if screen == "LOGIN":
            return "LOGIN"
        if pkg == self.PACKAGE_NAME:
            return "LOGIN"

        self.client.open_app(self.PACKAGE_NAME)

        for _ in range(5):
            time.sleep(1)
            xml = self.client.dump_xml(force=True)
            pkg = self._get_package(xml)
            screen = self.client.identify_screen(xml=xml)
            if screen == "HOME":
                return "OK"
            if screen == "LOGIN" or pkg == self.PACKAGE_NAME:
                return "LOGIN"

        print("App nao abriu. Forcando reinicio...")
        self.client.force_stop(self.PACKAGE_NAME)
        time.sleep(0.3)
        self.client.open_app(self.PACKAGE_NAME)

        for _ in range(5):
            time.sleep(1)
            xml = self.client.dump_xml(force=True)
            pkg = self._get_package(xml)
            screen = self.client.identify_screen(xml=xml)
            if screen == "HOME":
                return "OK"
            if screen == "LOGIN" or pkg == self.PACKAGE_NAME:
                return "LOGIN"

        return "ERRO"

    def _get_package(self, xml: str) -> str:
        if not xml:
            return ""
        m = re.search(r'package="([^"]+)"', xml)
        return m.group(1) if m else ""
