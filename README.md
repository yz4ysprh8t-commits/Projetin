# Branca de Neve 1.0

Sistema de automação RPA para pagamentos PIX e conversão BTC.

## Quick Start

```bash
# Com Docker (recomendado)
./start.sh

# Ou manualmente - veja SETUP_INDEPENDENTE.md
```

## Acessos

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs

## Documentação

- [Setup Independente](SETUP_INDEPENDENTE.md) - Guia completo de instalação
- [PRD](memory/PRD.md) - Documentação do projeto

## Estrutura

```
├── backend/           # API FastAPI + MongoDB
├── frontend/          # Interface React
├── rpa_standalone/    # RPA para Termux/Android
├── docker-compose.yml # Orquestração
└── SETUP_INDEPENDENTE.md
```

## Licença

Proprietário - Todos os direitos reservados
