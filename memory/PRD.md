# Branca de Neve 1.0 - PRD

## Data: 23/02/2026 02:30 UTC

## Status Atual
- **RPA**: ✅ Online e funcionando
- **API Central**: ✅ Rodando no Emergent
- **Bot Telegram**: ✅ Pronto para conectar
- **Documentação**: ✅ Completa (1790 linhas)

## Configuração para Conectar o Bot

```bash
export API_CENTRAL_URL="https://project-staging.preview.emergentagent.com/api"
export RPA_HMAC_SECRET="branca_neve_hmac_2026_s3cr3t"
```

## URLs Importantes

| Serviço | URL |
|---------|-----|
| API Central | https://project-staging.preview.emergentagent.com/api |
| Frontend | https://project-staging.preview.emergentagent.com |
| RPA Status | https://project-staging.preview.emergentagent.com/api/rpa/status |

## Documentação Completa

Arquivo: `/replit_project/Iconeszip/HISTORICO_DESENVOLVIMENTO.md`

### Conteúdo (1790 linhas):
1. Visão Geral do Sistema
2. Arquitetura Completa
3. API Central - Todos os Endpoints
4. RPA Gateway - Endpoints Completos (15+)
5. Bot Telegram - Comandos e Funcionalidades
6. Fluxo de Pagamento PIX
7. Configurações e Variáveis de Ambiente
8. Segurança e Autenticação HMAC
9. Deploy e Operação
10. Troubleshooting

## Limites Implementados (Avisos)

- Primeira compra por CPF: máx R$ 100
- Por QR Code: máx R$ 3.000  
- Por dia (CPF/CNPJ): máx R$ 6.000

## Arquitetura

```
[Bot Telegram] → [API Central Emergent] → [Túnel Serveo] → [RPA Termux] → [SatSails]
```

## Changelog

### v2.0.0-emergent (23/02/2026)
- Migração para Emergent Platform
- Frontend de monitoramento React
- Sistema de Bridge
- Documentação completa (962 linhas novas)
