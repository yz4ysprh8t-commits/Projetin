# Branca de Neve 1.0 - PRD

## Original Problem Statement
Usuário quer testar a funcionalidade RPA do projeto "Branca de Neve 1.0" - um sistema de e-commerce via Telegram com automação de pagamentos PIX via RPA. Ele tem um emulador Android (LDPlayer) com o app SatSails e Termux. O Replit usava um túnel serveo.net para conectar ao Termux e controlar o RPA remotamente. O objetivo é recriar essa funcionalidade na Emergent.

## Architecture

### Microservices Structure
| Serviço | Porta | Função |
|---------|-------|--------|
| `API Central` | 8001 (Emergent) | API central + proxy para RPA |
| `RPA Gateway` | 8080 (Termux) | Automação de pagamentos PIX via SatSails |

### Communication Flow
```
[Frontend Emergent] → [API Central :8001] → [Tunnel Serveo] → [RPA Gateway :8080 Termux]
```

### Tech Stack
- **Backend**: FastAPI, Python 3.11, MongoDB
- **Frontend**: React 18
- **RPA**: Python + ADB + uiautomator (Android)
- **Tunnel**: serveo.net (SSH reverse tunnel)

## User Personas
1. **Operador do Sistema** - Monitora o RPA via interface web, verifica logs, executa comandos
2. **Desenvolvedor** - Mantém e atualiza o código RPA remotamente

## Core Requirements (Static)
1. API Central para receber registro do RPA via tunnel
2. Proxy de comandos para o RPA
3. Interface web para monitorar status e logs
4. Download de pacote RPA standalone
5. Auto-registro e heartbeat

## What's Been Implemented
- [2026-02-23] Migração completa do projeto do Replit para Emergent
- [2026-02-23] API Central adaptada com endpoints RPA
- [2026-02-23] Frontend de monitoramento com abas (Status, Logs, Comandos, Ver Tela)
- [2026-02-23] Pacote RPA standalone pronto em `/app/rpa_standalone/`
- [2026-02-23] Script `start_rpa.sh` atualizado com URL da Emergent
- [2026-02-23] Sistema de heartbeat para verificar status do RPA

## Prioritized Backlog

### P0 - Critical (Done)
- ✅ API /rpa/register - registro do RPA
- ✅ API /rpa/status - status do RPA
- ✅ API /rpa/cmd/{path} - proxy de comandos
- ✅ API /rpa/download - download do pacote
- ✅ Frontend de monitoramento

### P1 - High Priority (Next)
- [ ] Teste end-to-end com emulador LDPlayer do usuário
- [ ] Validação do fluxo completo: Termux → Serveo → Emergent
- [ ] Verificação do RPA automação SatSails

### P2 - Medium Priority
- [ ] Logs persistentes no MongoDB
- [ ] Histórico de transações
- [ ] Alertas de RPA offline

### P3 - Low Priority
- [ ] Dashboard com métricas
- [ ] Múltiplos RPAs simultâneos
- [ ] Saque automático configurável

## Next Tasks
1. **Usuário**: Copiar pacote RPA para Termux do emulador
2. **Usuário**: Executar `./start_rpa.sh` no Termux
3. **Verificar**: RPA se registra automaticamente na Emergent
4. **Testar**: Comandos via interface web
