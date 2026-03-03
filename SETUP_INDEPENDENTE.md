# Branca de Neve 1.0 - Setup Independente

## Visão Geral
Este projeto foi preparado para rodar **totalmente independente** do Emergent Platform.

---

## Opção 1: Docker (Recomendado)

### Pré-requisitos
- Docker e Docker Compose instalados

### Executar
```bash
# Clone ou baixe o projeto
cd branca_de_neve

# Inicie todos os serviços
docker-compose up -d

# Verifique os logs
docker-compose logs -f
```

### Acessar
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs

### Parar
```bash
docker-compose down
```

---

## Opção 2: Setup Manual

### Pré-requisitos
- Python 3.10+
- Node.js 18+ (com yarn)
- MongoDB 6+

### Backend
```bash
cd backend

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis
cp .env.example .env
# Edite .env conforme necessário

# Iniciar servidor
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend
```bash
cd frontend

# Instalar dependências
yarn install

# Configurar variáveis
cp .env.example .env
# Edite REACT_APP_BACKEND_URL se necessário

# Iniciar servidor
yarn start
```

### MongoDB
```bash
# Docker (mais fácil)
docker run -d -p 27017:27017 --name mongodb mongo:7

# Ou instale localmente: https://www.mongodb.com/docs/manual/installation/
```

---

## Estrutura do Projeto

```
branca_de_neve/
├── backend/               # API FastAPI
│   ├── server.py          # Servidor principal
│   ├── requirements.txt   # Dependências Python
│   ├── Dockerfile         # Container backend
│   └── .env.example       # Template de configuração
│
├── frontend/              # Interface React
│   ├── src/               # Código fonte
│   ├── package.json       # Dependências Node
│   ├── Dockerfile         # Container frontend
│   └── .env.example       # Template de configuração
│
├── rpa_standalone/        # RPA para Termux/Android
│   ├── main.py            # Entrada principal
│   ├── api_server.py      # Servidor do RPA
│   ├── start_rpa.sh       # Script de inicialização
│   └── setup_termux.sh    # Setup no Termux
│
├── docker-compose.yml     # Orquestração de containers
└── SETUP_INDEPENDENTE.md  # Este arquivo
```

---

## Variáveis de Ambiente

### Backend (.env)
| Variável | Descrição | Padrão |
|----------|-----------|--------|
| MONGO_URL | URL do MongoDB | mongodb://localhost:27017 |
| DB_NAME | Nome do banco | branca_de_neve |
| CORS_ORIGINS | Origens permitidas | * |
| RPA_REGISTER_TOKEN | Token para RPA | branca_de_neve_2026 |

### Frontend (.env)
| Variável | Descrição | Padrão |
|----------|-----------|--------|
| REACT_APP_BACKEND_URL | URL da API | http://localhost:8001 |

---

## RPA Standalone (Termux/Android)

### Setup no Termux
```bash
# Copie a pasta rpa_standalone para o Termux
cd rpa_standalone

# Execute o setup (primeira vez)
chmod +x setup_termux.sh
./setup_termux.sh

# Inicie o RPA
chmod +x start_rpa.sh
./start_rpa.sh
```

### Configurar conexão com Backend
Edite `rpa_standalone/config.json`:
```json
{
  "central_url": "http://SEU_SERVIDOR:8001/api",
  "register_token": "branca_de_neve_2026"
}
```

---

## Deploy em Produção

### Opções de Hospedagem

1. **VPS (DigitalOcean, Linode, AWS EC2)**
   - Use Docker Compose
   - Configure Nginx como reverse proxy
   - Adicione SSL com Let's Encrypt

2. **Railway**
   ```bash
   railway login
   railway init
   railway up
   ```

3. **Render**
   - Crie serviços separados para backend e frontend
   - Use MongoDB Atlas para o banco

4. **Vercel (Frontend) + Railway (Backend)**
   - Frontend: Deploy direto do GitHub
   - Backend: Railway ou Render

---

## Troubleshooting

### MongoDB não conecta
```bash
# Verifique se está rodando
docker ps | grep mongo

# Ou teste conexão
mongosh mongodb://localhost:27017
```

### Frontend não conecta ao Backend
- Verifique se `REACT_APP_BACKEND_URL` está correto
- Confirme que o backend está rodando na porta 8001
- Verifique CORS no backend

### RPA não registra
- Confirme que o tunnel está funcionando
- Verifique o token no config.json
- Veja logs: `tail -f /tmp/rpa.log`

---

## Suporte

Este projeto foi desenvolvido na plataforma Emergent e exportado para uso independente.

Para mais informações sobre o sistema Branca de Neve, consulte o arquivo `memory/PRD.md`.
