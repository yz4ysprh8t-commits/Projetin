# Guia de Acesso Remoto ao Termux

Este documento explica como configurar o acesso remoto ao Termux para permitir que um assistente AI (ou você mesmo) execute comandos remotamente.

---

## Pré-requisitos

1. **LDPlayer** (ou outro emulador Android) com ROOT habilitado
2. **Termux** instalado (de preferência do F-Droid)
3. **Python** instalado no Termux
4. **FastAPI e dependências** instaladas

---

## Passo 1: Instalar Dependências no Termux

```bash
pkg update -y && pkg install -y python openssh
pip install 'pydantic<2' 'fastapi<0.100' uvicorn httpx
```

---

## Passo 2: Criar a API de Comandos

Execute este comando para criar o arquivo:

```bash
cat > ~/cmd_api.py << 'EOF'
from fastapi import FastAPI
from pydantic import BaseModel
import subprocess
import os

app = FastAPI()

class Cmd(BaseModel):
    cmd: str
    timeout: int = 30

@app.post("/exec")
def execute(c: Cmd):
    try:
        r = subprocess.run(c.cmd, shell=True, capture_output=True, text=True, timeout=c.timeout, cwd=os.path.expanduser("~"))
        return {"stdout": r.stdout, "stderr": r.stderr, "code": r.returncode}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "timeout", "code": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "code": -1}

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
EOF
```

---

## Passo 3: Iniciar a API

**Sessão 1 do Termux:**
```bash
python ~/cmd_api.py
```

Deve aparecer:
```
INFO:     Uvicorn running on http://0.0.0.0:9000 (Press CTRL+C to quit)
```

---

## Passo 4: Criar o Túnel Serveo

**Abra uma nova sessão do Termux** (deslize da esquerda → New Session)

```bash
ssh -R 80:localhost:9000 serveo.net
```

Você verá algo como:
```
Forwarding HTTP traffic from https://XXXXXX.serveousercontent.com
```

**Copie essa URL** - ela será usada para acesso remoto.

---

## Passo 5: Dar Permissão de Root

Na primeira vez que um comando com `su` for executado, o LDPlayer mostrará um popup pedindo permissão. **Clique em "Permitir/Allow"**.

---

## Passo 6: Testar Acesso Remoto

De qualquer lugar, você pode executar:

```bash
# Testar conexão
curl -s "https://XXXXXX.serveousercontent.com/health"

# Executar comando
curl -s -X POST "https://XXXXXX.serveousercontent.com/exec" \
  -H "Content-Type: application/json" \
  -d '{"cmd": "echo Hello World", "timeout": 10}'

# Comando com root
curl -s -X POST "https://XXXXXX.serveousercontent.com/exec" \
  -H "Content-Type: application/json" \
  -d '{"cmd": "/system/xbin/su -c \"id\"", "timeout": 10}'
```

---

## Resumo dos Comandos (Início Rápido)

Toda vez que precisar reconectar:

**Sessão 1:**
```bash
pkill -9 python ; sleep 2 ; python ~/cmd_api.py
```

**Sessão 2:**
```bash
ssh -R 80:localhost:9000 serveo.net
```

---

## Endpoints Disponíveis

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/health` | Verificar se API está online |
| POST | `/exec` | Executar comando |

### Formato do POST /exec

```json
{
  "cmd": "comando a executar",
  "timeout": 30
}
```

### Resposta

```json
{
  "stdout": "saída do comando",
  "stderr": "erros",
  "code": 0
}
```

---

## Troubleshooting

### Porta em uso
```bash
pkill -9 python ; pkill -9 uvicorn ; sleep 2 ; python ~/cmd_api.py
```

### Serveo desconecta frequentemente
- É normal, basta reconectar: `ssh -R 80:localhost:9000 serveo.net`
- Alternativa: usar ngrok (requer conta)

### Comando com root não funciona
- Verifique se ROOT está habilitado no LDPlayer
- Na primeira vez, aceite o popup de permissão
- Use o caminho completo: `/system/xbin/su -c "comando"`

### UIAutomator não funciona
- Precisa de root: `/system/xbin/su -c "uiautomator dump /sdcard/view.xml"`

---

## Notas de Segurança

⚠️ **ATENÇÃO**: Esta API permite execução de qualquer comando no dispositivo!

- Use apenas em ambientes de teste/desenvolvimento
- A URL do serveo é pública - qualquer pessoa com ela pode executar comandos
- Para produção, implemente autenticação

---

## Integração com AI/Assistente

Forneça a URL do serveo ao assistente e ele poderá:

1. Executar comandos no Termux
2. Ler/escrever arquivos
3. Controlar o RPA
4. Diagnosticar problemas

Exemplo de prompt:
```
A URL de acesso ao Termux é: https://XXXXXX.serveousercontent.com
Por favor, verifique o status do sistema e corrija qualquer problema.
```
