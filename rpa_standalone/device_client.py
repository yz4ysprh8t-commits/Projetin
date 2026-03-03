import subprocess
import re
import time
import os
import xml.etree.ElementTree as ET
from typing import Optional, Tuple, List, Dict


class DeviceClient:
    MODE_ADB = "adb"
    MODE_LOCAL = "local"
    MODE_TERMUX = "termux"

    def __init__(self, mode: str = "adb", adb_path: str = "adb", device_id: str = None):
        self.mode = mode
        self.adb_path = adb_path
        self.device_id = device_id
        self.xml_dump_path = "/sdcard/view.xml"
        self._last_xml = ""
        self._last_xml_time = 0
        self._xml_cache_ttl = 0.3
        self._connected = False
        self._su_path = "/system/xbin/su"  # Path to su binary for root commands

    def _ensure_connected(self):
        if self._connected:
            return
        if self.mode == self.MODE_ADB and self.device_id and ":" in self.device_id:
            try:
                cmd = f"{self.adb_path} connect {self.device_id}"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                                       encoding='utf-8', errors='ignore', timeout=10)
                if "connected" in result.stdout.lower() or "already" in result.stdout.lower():
                    print(f"   [ADB] Conectado a {self.device_id}")
                else:
                    print(f"   [ADB] Tentativa de conexao: {result.stdout.strip()}")
            except Exception as e:
                print(f"   [ADB] Erro ao conectar: {e}")
        self._connected = True

    def _run(self, cmd: str, timeout: int = 10) -> subprocess.CompletedProcess:
        if self.mode == self.MODE_ADB:
            self._ensure_connected()
            if self.device_id:
                full_cmd = f'{self.adb_path} -s {self.device_id} {cmd}'
            else:
                full_cmd = f'{self.adb_path} {cmd}'
        else:
            full_cmd = cmd

        try:
            return subprocess.run(
                full_cmd,
                shell=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=timeout
            )
        except subprocess.TimeoutExpired:
            print(f"   [DeviceClient] Timeout: {full_cmd[:80]}")
            return subprocess.CompletedProcess(full_cmd, 1, stdout="", stderr="timeout")
        except Exception as e:
            print(f"   [DeviceClient] Erro: {e}")
            return subprocess.CompletedProcess(full_cmd, 1, stdout="", stderr=str(e))

    def shell(self, cmd: str, timeout: int = 10, use_root: bool = False) -> str:
        if self.mode == self.MODE_ADB:
            res = self._run(f"shell {cmd}", timeout=timeout)
        elif self.mode == self.MODE_TERMUX or self.mode == "termux":
            # In Termux, use su for root commands
            if use_root:
                full_cmd = f'{self._su_path} -c "{cmd}"'
            else:
                full_cmd = cmd
            res = self._run(full_cmd, timeout=timeout)
        else:
            res = self._run(cmd, timeout=timeout)
        return res.stdout.strip()

    def tap(self, x: int, y: int):
        self.shell(f"input tap {x} {y}")
        time.sleep(0.15)

    def tap_coord_string(self, coord: str):
        self.shell(f"input tap {coord}")
        time.sleep(0.15)

    def input_text(self, text: str):
        self.shell(f"input text {text}")

    def keyevent(self, key: int):
        self.shell(f"input keyevent {key}")

    def key_back(self):
        self.keyevent(4)

    def key_home(self):
        self.keyevent(3)

    def key_delete(self, times: int = 15):
        if times <= 3:
            for _ in range(times):
                self.keyevent(67)
        else:
            keys = " ".join(["67"] * times)
            self.shell(f"input keyevent {keys}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300):
        self.shell(f"input swipe {x1} {y1} {x2} {y2} {duration}")

    def open_app(self, package: str):
        self.shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")

    def force_stop(self, package: str):
        self.shell(f"am force-stop {package}")

    def screencap(self, local_path: str) -> bool:
        remote_path = "/sdcard/screen_rpa.png"
        self.shell(f"screencap -p {remote_path}")
        if self.mode == self.MODE_ADB:
            res = self._run(f"pull {remote_path} {local_path}")
            return res.returncode == 0
        else:
            res = self._run(f"cp {remote_path} {local_path}")
            return res.returncode == 0

    def pull_file(self, remote_path: str, local_path: str) -> bool:
        if self.mode == self.MODE_ADB:
            res = self._run(f'pull "{remote_path}" "{local_path}"')
            return res.returncode == 0
        else:
            res = self._run(f'cp "{remote_path}" "{local_path}"')
            return res.returncode == 0

    def get_clipboard(self) -> str:
        print("   [Clip] Tentando metodos de clipboard...")

        result = self.shell("am broadcast -a clipper.get 2>/dev/null")
        match = re.search(r'data="(.+?)"', result)
        if match:
            val = match.group(1)
            print(f"   [Clip] clipper.get OK ({len(val)} chars)")
            return val

        result2 = self.shell("content call --uri content://com.termux.contentprovider/clipboard/get --method get 2>/dev/null")
        if result2 and "result" in result2:
            match2 = re.search(r'result=(.+?)(?:\}|$)', result2)
            if match2:
                val = match2.group(1).strip()
                if val and len(val) > 10:
                    print(f"   [Clip] termux content provider OK ({len(val)} chars)")
                    return val

        result3 = self.shell("su -c 'service call clipboard 2 i32 1 i32 0' 2>/dev/null")
        if not result3 or "not found" in result3.lower():
            result3 = self.shell("service call clipboard 2 i32 1 i32 0 2>/dev/null")
        if result3 and "Result" in result3:
            hex_parts = re.findall(r"'(.+?)'", result3)
            if hex_parts:
                text = "".join(hex_parts).replace(".", "").replace("\n", "").strip()
                if text and len(text) > 10:
                    print(f"   [Clip] service call clipboard OK ({len(text)} chars)")
                    return text

        try:
            import subprocess
            r = subprocess.run(["termux-clipboard-get"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                val = r.stdout.strip()
                print(f"   [Clip] termux-clipboard-get OK ({len(val)} chars)")
                return val
        except Exception:
            pass

        try:
            import pyperclip
            texto = pyperclip.paste()
            if texto and texto.strip():
                print(f"   [Clip] pyperclip OK ({len(texto.strip())} chars)")
                return texto.strip()
        except (ImportError, Exception):
            pass

        print("   [Clip] Todos os metodos falharam")
        return ""

    def set_clipboard(self, text: str):
        self.shell(f"am broadcast -a clipper.set -e text '{text}' 2>/dev/null")

    def dump_xml(self, force: bool = False) -> str:
        now = time.time()
        if not force and self._last_xml and (now - self._last_xml_time) < self._xml_cache_ttl:
            return self._last_xml

        try:
            self.shell("uiautomator dump --compressed /sdcard/view.xml", timeout=8)
            xml_content = self.shell("cat /sdcard/view.xml", timeout=5)

            if xml_content and len(xml_content) > 50:
                self._last_xml = xml_content
                self._last_xml_time = now
                return xml_content
            else:
                self.shell("uiautomator dump /sdcard/view.xml", timeout=8)
                xml_content = self.shell("cat /sdcard/view.xml", timeout=5)
                if xml_content and len(xml_content) > 50:
                    self._last_xml = xml_content
                    self._last_xml_time = now
                    return xml_content

                print("   [DeviceClient] XML vazio ou muito curto")
                return self._last_xml or ""
        except Exception as e:
            print(f"   [DeviceClient] Erro ao ler XML: {e}")
            self.shell("pkill uiautomator 2>/dev/null")
            return self._last_xml or ""

    def find_element(self, text: str = None, content_desc: str = None,
                     resource_id: str = None, class_name: str = None,
                     xml: str = None) -> Optional[Dict]:
        if xml is None:
            xml = self.dump_xml(force=True)
        if not xml:
            return None

        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            pattern = self._build_search_pattern(text, content_desc, resource_id, class_name)
            match = re.search(pattern, xml)
            if match:
                bounds = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', match.group(0))
                if bounds:
                    x1, y1, x2, y2 = int(bounds.group(1)), int(bounds.group(2)), int(bounds.group(3)), int(bounds.group(4))
                    return {
                        "text": text or "",
                        "bounds": (x1, y1, x2, y2),
                        "center": ((x1 + x2) // 2, (y1 + y2) // 2)
                    }
            return None

        for node in root.iter("node"):
            node_text = node.attrib.get("text", "") or ""
            node_desc = node.attrib.get("content-desc", "") or ""
            node_rid = node.attrib.get("resource-id", "") or ""
            node_cls = node.attrib.get("class", "") or ""

            matched = False
            if text and (text in node_text or text in node_desc):
                matched = True
            elif content_desc and content_desc in node_desc:
                matched = True
            elif resource_id and resource_id in node_rid:
                matched = True
            elif class_name and class_name == node_cls:
                matched = True

            if not matched:
                continue

            bounds_str = node.attrib.get("bounds", "")
            bounds_match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
            if bounds_match:
                x1, y1 = int(bounds_match.group(1)), int(bounds_match.group(2))
                x2, y2 = int(bounds_match.group(3)), int(bounds_match.group(4))
                return {
                    "text": node_text,
                    "content_desc": node_desc,
                    "resource_id": node_rid,
                    "class": node_cls,
                    "bounds": (x1, y1, x2, y2),
                    "center": ((x1 + x2) // 2, (y1 + y2) // 2),
                    "clickable": node.attrib.get("clickable", "false") == "true"
                }
        return None

    def find_all_elements(self, text: str = None, content_desc: str = None,
                          resource_id: str = None, xml: str = None) -> List[Dict]:
        if xml is None:
            xml = self.dump_xml(force=True)
        if not xml:
            return []

        results = []
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return results

        for node in root.iter("node"):
            node_text = node.attrib.get("text", "") or ""
            node_desc = node.attrib.get("content-desc", "") or ""
            node_rid = node.attrib.get("resource-id", "") or ""

            matched = False
            if text and (text in node_text or text in node_desc):
                matched = True
            if content_desc and content_desc in node_desc:
                matched = True
            if resource_id and resource_id in node_rid:
                matched = True

            if not matched:
                continue

            bounds_str = node.attrib.get("bounds", "")
            bounds_match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
            if bounds_match:
                x1, y1 = int(bounds_match.group(1)), int(bounds_match.group(2))
                x2, y2 = int(bounds_match.group(3)), int(bounds_match.group(4))
                results.append({
                    "text": node_text,
                    "content_desc": node_desc,
                    "resource_id": node_rid,
                    "class": node.attrib.get("class", ""),
                    "bounds": (x1, y1, x2, y2),
                    "center": ((x1 + x2) // 2, (y1 + y2) // 2)
                })
        return results

    def tap_element(self, text: str = None, content_desc: str = None,
                    resource_id: str = None, xml: str = None) -> bool:
        elem = self.find_element(text=text, content_desc=content_desc,
                                 resource_id=resource_id, xml=xml)
        if elem:
            cx, cy = elem["center"]
            print(f"   [Tap] '{text or content_desc or resource_id}' em ({cx}, {cy})")
            self.tap(cx, cy)
            return True
        else:
            print(f"   [Tap] Elemento nao encontrado: '{text or content_desc or resource_id}'")
            return False

    def wait_for_element(self, text: str = None, content_desc: str = None,
                         resource_id: str = None, timeout: int = 15,
                         interval: float = 1.0) -> Optional[Dict]:
        start = time.time()
        attempts = 0
        while time.time() - start < timeout:
            attempts += 1
            xml = self.dump_xml(force=True)
            elem = self.find_element(text=text, content_desc=content_desc,
                                     resource_id=resource_id, xml=xml)
            if elem:
                print(f"   [Wait] '{text or content_desc or resource_id}' encontrado ({attempts} tentativas, {time.time()-start:.1f}s)")
                return elem
            time.sleep(interval)

        print(f"   [Wait] Timeout ({timeout}s): '{text or content_desc or resource_id}' nao encontrado")
        return None

    def wait_and_tap(self, text: str = None, content_desc: str = None,
                     resource_id: str = None, timeout: int = 15,
                     interval: float = 1.0) -> bool:
        elem = self.wait_for_element(text=text, content_desc=content_desc,
                                     resource_id=resource_id, timeout=timeout,
                                     interval=interval)
        if elem:
            cx, cy = elem["center"]
            print(f"   [WaitTap] '{text or content_desc or resource_id}' em ({cx}, {cy})")
            self.tap(cx, cy)
            return True
        return False

    def has_text(self, text: str, xml: str = None) -> bool:
        if xml is None:
            xml = self.dump_xml(force=True)
        return text in xml if xml else False

    def get_all_texts(self, xml: str = None) -> List[str]:
        if xml is None:
            xml = self.dump_xml(force=True)
        if not xml:
            return []
        texts = re.findall(r'text="([^"]+)"', xml)
        descs = re.findall(r'content-desc="([^"]+)"', xml)
        all_items = [t for t in texts if t.strip()] + [d for d in descs if d.strip()]
        seen = set()
        unique = []
        for item in all_items:
            if item not in seen:
                seen.add(item)
                unique.append(item)
        return unique

    def identify_screen(self, xml: str = None) -> str:
        if xml is None:
            xml = self.dump_xml(force=True)
        if not xml:
            return "DESCONHECIDO"

        if "Bem-vindo" in xml or "Bem-vindo de volta" in xml:
            return "LOGIN"

        if "Bitcoin" in xml and ("Transações" in xml or "Transaç" in xml):
            return "HOME"

        if "Receber" in xml and "Enviar" in xml:
            return "HOME"

        if "Tipo de Depósito" in xml or "Tipo de Dep" in xml:
            return "TIPO_DEPOSITO"

        if "Copiar" in xml and ("Compartilhar" in xml or "QR" in xml.upper() or "Depósito" in xml or "sito via Pix" in xml):
            return "QR_CODE"

        if "Depósito via Pix" in xml or "sito via Pix" in xml:
            return "DEPOSITO_PIX"

        if "Redefinir" in xml or "Filtro" in xml:
            return "HISTORICO"

        if "Converter" in xml and ("Saldo Dispon" in xml or "Max" in xml):
            return "CONVERTER"

        if "Taxas e limites" in xml and ("Lento" in xml or "Rápido" in xml or "Rapido" in xml):
            return "CONVERTER_TAXAS"

        if "Conta" in xml and "Compra" in xml:
            return "HOME"

        pkg_match = re.search(r'package="([^"]+)"', xml)
        pkg = pkg_match.group(1) if pkg_match else ""

        if pkg != "com.satsails.Satsails":
            return "DESCONHECIDO"

        view_count = xml.count('class="android.view.View"')
        has_scroll = "ScrollView" in xml
        clickable_count = xml.count('clickable="true"')

        if view_count <= 5:
            return "SPLASH"

        if not has_scroll and clickable_count >= 10:
            return "LOGIN"

        if has_scroll and view_count > 15:
            return "HOME"

        if has_scroll:
            return "HOME"

        return "APP_ABERTO"

    def _build_search_pattern(self, text=None, content_desc=None, resource_id=None, class_name=None) -> str:
        parts = []
        if text:
            parts.append(f'text="{re.escape(text)}"')
        if content_desc:
            parts.append(f'content-desc="{re.escape(content_desc)}"')
        if resource_id:
            parts.append(f'resource-id="{re.escape(resource_id)}"')
        if class_name:
            parts.append(f'class="{re.escape(class_name)}"')

        pattern = r'<node[^>]*' + r'[^>]*'.join(parts) + r'[^>]*>'
        return pattern
