# Log de Sessão - Branca de Neve 1.0

## Data: 03/03/2026 - Horário: ~17:00 - 19:30 UTC

---

## Objetivo da Sessão
Separar o projeto Branca de Neve para torná-lo independente do Emergent e configurar acesso remoto ao Termux para diagnóstico e controle via API.

---

## Resumo das Atividades

### 1. Clonagem e Análise do Projeto
- Repositório clonado de: `https://github.com/yz4ysprh8t-commits/Projetin.git`
- Branch utilizado: `new`
- Estrutura identificada: Backend FastAPI + Frontend React + RPA Standalone

### 2. Adaptação para SQLite
- Removida dependência do MongoDB (incompatível com Termux)
- Criado `backend_sqlite.py` com SQLite embutido
- Criado `start_all.py` para inicialização one-shot

### 3. Configuração do Termux no LDPlayer
- Instalação de dependências: Python, OpenSSH
- Problema identificado: Pydantic 2 requer Rust (não disponível no Termux)
- Solução: Usar versões antigas `pydantic<2` e `fastapi<0.100`

### 4. Diagnóstico do UIAutomator
- Problema: UIAutomator retornava "XML vazio"
- Causa: Falta de permissão root no Termux
- Solução: Usar `/system/xbin/su -c "comando"` para executar com root

### 5. Configuração de Acesso Remoto
- Criada API de comandos (`cmd_api.py`) na porta 9000
- Túnel via Serveo: `ssh -R 80:localhost:9000 serveo.net`
- Permissão de root concedida via popup do LDPlayer

### 6. Teste de Funcionamento
- UIAutomator funcionando com root
- Login automático no SatSails testado com sucesso (PIN 222222)
- Tela Home identificada corretamente

---

## Comandos Executados e Respostas

### Teste 1: Verificar UIAutomator sem root
```bash
# Comando
/system/bin/uiautomator dump /sdcard/test.xml

# Resposta
mkdir: cannot create directory '/data/local/tmp/dalvik-cache': Permission denied
app_process: not found
```

### Teste 2: Verificar disponibilidade do root
```bash
# Comando
ls -la /system/xbin/su

# Resposta
-rwxr-xr-x. 1 root shell 1489736 Aug 21 2025 /system/xbin/su
```

### Teste 3: Testar UIAutomator com root
```bash
# Comando
/system/xbin/su -c "uiautomator dump /sdcard/view.xml && cat /sdcard/view.xml"

# Resposta (primeira vez)
# Popup de permissão apareceu no LDPlayer - usuário clicou "Permitir"

# Resposta (após permissão)
UI hierchary dumped to: /sdcard/view.xml
<?xml version='1.0' encoding='UTF-8' standalone='yes' ?><hierarchy rotation="0">...
```

### Teste 4: Identificar tela de senha do SatSails
```bash
# Comando
/system/xbin/su -c "uiautomator dump /sdcard/view.xml && cat /sdcard/view.xml" | grep content-desc

# Resposta
content-desc="Bem-vindo de volta"
content-desc="1" bounds="[36,252][157,373]"
content-desc="2" bounds="[179,252][301,373]"
content-desc="3" bounds="[323,252][444,373]"
# ... (teclado numérico completo)
```

### Teste 5: Digitar PIN automaticamente
```bash
# Comando (PIN 222222 - tecla 2 em [179,252][301,373], centro: 240,312)
/system/xbin/su -c "input tap 240 312 && sleep 0.3 && input tap 240 312 && sleep 0.3 && input tap 240 312 && sleep 0.3 && input tap 240 312 && sleep 0.3 && input tap 240 312 && sleep 0.3 && input tap 240 312"

# Resposta
(vazio - sucesso)
```

### Teste 6: Verificar tela após login
```bash
# Comando
/system/xbin/su -c "uiautomator dump /sdcard/view.xml && cat /sdcard/view.xml" | grep content-desc

# Resposta
content-desc="C&#10;Conta"
content-desc="Bitcoin&#10;Ver Saldos"
content-desc="0&#10;$ 0"
content-desc="Receber"
content-desc="Enviar"
content-desc="Transações"
content-desc="Compra"
content-desc="Depix&#10;9 jan., 01:23&#10;4.60"
content-desc="Depix&#10;7 jan., 20:54&#10;3.86"
content-desc="Ver todas as transações"
```

**Resultado: Login automático bem-sucedido! Tela Home identificada.**

---

## Problemas Encontrados e Soluções

### Problema 1: Pydantic 2 não instala no Termux
```
ERROR: Failed to build 'pydantic-core' when installing build dependencies
Rust not found, installing into a temporary directory
```

**Solução:**
```bash
pip install 'pydantic<2' 'fastapi<0.100' uvicorn httpx
```

### Problema 2: ngrok não disponível no Termux
```
E: Unable to locate package ngrok
```

**Solução:**
```bash
ssh -R 80:localhost:9000 serveo.net
```

### Problema 3: UIAutomator sem permissão
```
mkdir: cannot create directory '/data/local/tmp/dalvik-cache': Permission denied
```

**Solução:**
- Usar root: `/system/xbin/su -c "uiautomator dump ..."`
- Aceitar popup de permissão no LDPlayer

### Problema 4: Porta 9000 em uso
```
ERROR: [Errno 98] error while attempting to bind on address ('0.0.0.0', 9000): address already in use
```

**Solução:**
```bash
pkill -9 python ; sleep 2 ; python ~/cmd_api.py
```

---

## Arquivos Criados/Modificados

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `/app/rpa_standalone/backend_sqlite.py` | Criado | Backend com SQLite |
| `/app/rpa_standalone/start_all.py` | Criado | Iniciador one-shot |
| `/app/rpa_standalone/install_termux.sh` | Criado | Script de instalação |
| `/app/rpa_standalone/device_client.py` | Modificado | Adicionado suporte a root no Termux |
| `/app/docs/ACESSO_REMOTO_TERMUX.md` | Criado | Documentação de acesso remoto |
| `/app/rpa_standalone/config.json` | Criado | Configuração padrão |

---

## Modificações no device_client.py

### Antes (não funcionava no Termux):
```python
def shell(self, cmd: str, timeout: int = 10) -> str:
    if self.mode == self.MODE_ADB:
        res = self._run(f"shell {cmd}", timeout=timeout)
    else:
        res = self._run(cmd, timeout=timeout)
    return res.stdout.strip()
```

### Depois (funciona com root no Termux):
```python
def shell(self, cmd: str, timeout: int = 10, use_root: bool = False) -> str:
    if self.mode == self.MODE_ADB:
        res = self._run(f"shell {cmd}", timeout=timeout)
    elif self.mode == self.MODE_TERMUX or self.mode == "termux":
        if use_root:
            full_cmd = f'{self._su_path} -c "{cmd}"'
        else:
            full_cmd = cmd
        res = self._run(full_cmd, timeout=timeout)
    else:
        res = self._run(cmd, timeout=timeout)
    return res.stdout.strip()
```

---

## Configuração Final do Ambiente

### Termux
- Python 3.12
- FastAPI 0.99.1
- Pydantic 1.10.26
- Uvicorn 0.41.0

### LDPlayer
- Root habilitado
- Permissão de root concedida ao Termux

### Túnel
- Serveo: `ssh -R 80:localhost:9000 serveo.net`
- URL dinâmica (muda a cada conexão)

---

## Próximos Passos

1. [ ] Testar RPA completo com `python start_all.py`
2. [ ] Executar Fase 1 dos testes (32 testes gratuitos)
3. [ ] Validar geração de QR Code PIX
4. [ ] Testar auditoria de pagamentos
5. [ ] Executar Fase 2 dos testes (com depósitos reais)

---

## URLs de Referência

- Repositório: https://github.com/yz4ysprh8t-commits/Projetin
- Branch: `new`
- Documentação de Acesso Remoto: `/docs/ACESSO_REMOTO_TERMUX.md`

---

## Observações

- O túnel Serveo desconecta frequentemente - reconectar com `ssh -R 80:localhost:9000 serveo.net`
- Para nomes persistentes no Serveo, é necessário gerar chave SSH e registrar
- O PIN padrão configurado é `222222` - alterar em `config.json` se necessário
- Resolução do emulador: 480x800 pixels
