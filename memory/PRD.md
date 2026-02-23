# Branca de Neve 1.0 - PRD

## Status Atual
- **RPA**: ✅ Online e funcionando
- **API Central**: ✅ Rodando no Emergent
- **Bot Telegram**: ✅ Pronto para conectar

## Configuração para o Bot

O bot precisa apenas desta variável de ambiente para conectar ao RPA:
```
API_CENTRAL_URL=https://project-staging.preview.emergentagent.com/api
```

## Limites Implementados (AVISOS)
Os avisos de limite foram adicionados em `/services/bot_telegram/cogs/add_credits.py`:
- Primeira compra por CPF: máx R$ 100
- Por QR Code: máx R$ 3.000
- Por dia (CPF/CNPJ): máx R$ 6.000

**NOTA**: Apenas avisos foram implementados, não validação real.

## Arquitetura de Conexão
```
[Bot Telegram] 
    ↓ (API_CENTRAL_URL)
[API Central - Emergent]
    ↓ (proxy)
[RPA Gateway - Termux/Emulador]
    ↓ (ADB)
[SatSails App]
```

## Endpoints Principais

### API Central (Emergent)
- `GET /api/rpa/status` - Status do RPA
- `POST /api/rpa/register` - Registrar RPA
- `GET /api/rpa/cmd/{path}` - Proxy para RPA
- `GET /api/bridge/*` - Ponte de comunicação

### RPA Gateway (Termux)
- `POST /pagar` - Criar pagamento PIX
- `GET /status/{id}` - Consultar status
- `GET /pendentes` - Listar pendentes
- `GET /health` - Health check

## Próximos Passos
1. [ ] Implementar validação real dos limites
2. [ ] Adicionar tracking de CPF/CNPJ
3. [ ] Sistema de alertas quando limite atingido
