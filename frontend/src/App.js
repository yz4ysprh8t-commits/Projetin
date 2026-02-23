import React, { useState, useEffect, useCallback } from 'react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

function App() {
  const [rpaStatus, setRpaStatus] = useState(null);
  const [logs, setLogs] = useState([]);
  const [telaInfo, setTelaInfo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('status');

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/rpa/status`);
      const data = await res.json();
      setRpaStatus(data);
    } catch (err) {
      console.error('Error fetching status:', err);
    }
  }, []);

  const fetchLogs = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/rpa/logs`);
      const data = await res.json();
      setLogs(data.logs || []);
    } catch (err) {
      console.error('Error fetching logs:', err);
    }
  }, []);

  const fetchTelaInfo = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/rpa/ver_tela`);
      const data = await res.json();
      setTelaInfo(data);
    } catch (err) {
      console.error('Error fetching tela info:', err);
    } finally {
      setLoading(false);
    }
  };

  const executeCommand = async (endpoint) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/rpa/cmd/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      alert(JSON.stringify(data, null, 2));
      fetchLogs();
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchLogs();
    const interval = setInterval(() => {
      fetchStatus();
      if (activeTab === 'logs') {
        fetchLogs();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchStatus, fetchLogs, activeTab]);

  return (
    <div className="app-container">
      <header className="header">
        <h1>Branca de Neve 1.0</h1>
        <p className="subtitle">RPA Gateway Monitor</p>
      </header>

      <div className="status-card">
        <div className="status-indicator">
          <span className={`dot ${rpaStatus?.online ? 'online' : 'offline'}`}></span>
          <span className="status-text">
            RPA {rpaStatus?.online ? 'Online' : 'Offline'}
          </span>
        </div>
        {rpaStatus?.url && (
          <p className="status-url">{rpaStatus.url}</p>
        )}
        {rpaStatus?.last_seen_seconds_ago !== null && rpaStatus?.last_seen_seconds_ago >= 0 && (
          <p className="last-seen">
            Última comunicação: {Math.round(rpaStatus.last_seen_seconds_ago)}s atrás
          </p>
        )}
        {!rpaStatus?.url && (
          <div className="setup-instructions">
            <p><strong>RPA não registrado.</strong> Execute no Termux do emulador:</p>
            <code>./start_rpa.sh</code>
          </div>
        )}
      </div>

      <nav className="tabs">
        <button 
          className={activeTab === 'status' ? 'active' : ''} 
          onClick={() => setActiveTab('status')}
          data-testid="tab-status"
        >
          Status
        </button>
        <button 
          className={activeTab === 'logs' ? 'active' : ''} 
          onClick={() => setActiveTab('logs')}
          data-testid="tab-logs"
        >
          Logs
        </button>
        <button 
          className={activeTab === 'commands' ? 'active' : ''} 
          onClick={() => setActiveTab('commands')}
          data-testid="tab-commands"
        >
          Comandos
        </button>
        <button 
          className={activeTab === 'tela' ? 'active' : ''} 
          onClick={() => setActiveTab('tela')}
          data-testid="tab-tela"
        >
          Ver Tela
        </button>
      </nav>

      <main className="content">
        {activeTab === 'status' && (
          <div className="panel" data-testid="panel-status">
            <h2>Status do Sistema</h2>
            <div className="info-grid">
              <div className="info-item">
                <label>URL do RPA:</label>
                <span>{rpaStatus?.url || 'Não registrado'}</span>
              </div>
              <div className="info-item">
                <label>Status:</label>
                <span className={rpaStatus?.online ? 'text-green' : 'text-red'}>
                  {rpaStatus?.online ? 'Online' : 'Offline'}
                </span>
              </div>
              <div className="info-item">
                <label>Registrado em:</label>
                <span>
                  {rpaStatus?.registered_at 
                    ? new Date(rpaStatus.registered_at * 1000).toLocaleString() 
                    : '-'}
                </span>
              </div>
            </div>

            <div className="instructions-panel">
              <h3>Como conectar o RPA</h3>
              <ol>
                <li>Abra o <strong>Termux</strong> no emulador (LDPlayer ou celular)</li>
                <li>Navegue até a pasta do RPA: <code>cd ~/rpa_standalone</code></li>
                <li>Execute: <code>./start_rpa.sh</code></li>
                <li>Aguarde o tunnel serveo conectar</li>
                <li>O RPA se registrará automaticamente aqui</li>
              </ol>
              <p className="note">
                <strong>Primeira vez?</strong> Execute <code>./setup_termux.sh</code> primeiro para instalar dependências.
              </p>
            </div>
          </div>
        )}

        {activeTab === 'logs' && (
          <div className="panel" data-testid="panel-logs">
            <h2>Logs do RPA</h2>
            <button className="btn-refresh" onClick={fetchLogs} disabled={loading}>
              {loading ? 'Carregando...' : 'Atualizar Logs'}
            </button>
            <div className="logs-container">
              {logs.length === 0 ? (
                <p className="no-logs">Nenhum log disponível. RPA precisa estar online.</p>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className="log-entry">{log}</div>
                ))
              )}
            </div>
          </div>
        )}

        {activeTab === 'commands' && (
          <div className="panel" data-testid="panel-commands">
            <h2>Comandos RPA</h2>
            {!rpaStatus?.online ? (
              <p className="warning">RPA offline. Conecte o RPA primeiro.</p>
            ) : (
              <div className="commands-grid">
                <div className="command-group">
                  <h3>Health & Status</h3>
                  <button 
                    className="btn-cmd" 
                    onClick={() => executeCommand('health')}
                    disabled={loading}
                    data-testid="cmd-health"
                  >
                    Health Check
                  </button>
                  <button 
                    className="btn-cmd" 
                    onClick={() => executeCommand('pendentes')}
                    disabled={loading}
                    data-testid="cmd-pendentes"
                  >
                    Ver Pendentes
                  </button>
                  <button 
                    className="btn-cmd" 
                    onClick={() => executeCommand('config')}
                    disabled={loading}
                    data-testid="cmd-config"
                  >
                    Ver Config
                  </button>
                </div>

                <div className="command-group">
                  <h3>Auditoria</h3>
                  <button 
                    className="btn-cmd btn-warning" 
                    onClick={() => executeCommand('auditar')}
                    disabled={loading}
                    data-testid="cmd-auditar"
                  >
                    Forçar Auditoria
                  </button>
                </div>

                <div className="command-group">
                  <h3>Worker</h3>
                  <button 
                    className="btn-cmd btn-danger" 
                    onClick={() => executeCommand('worker/restart')}
                    disabled={loading}
                    data-testid="cmd-worker-restart"
                  >
                    Reiniciar Worker
                  </button>
                </div>

                <div className="command-group">
                  <h3>Diagnóstico</h3>
                  <button 
                    className="btn-cmd" 
                    onClick={() => executeCommand('diagnostico')}
                    disabled={loading}
                    data-testid="cmd-diagnostico"
                  >
                    Diagnóstico Completo
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'tela' && (
          <div className="panel" data-testid="panel-tela">
            <h2>Ver Tela do App</h2>
            {!rpaStatus?.online ? (
              <p className="warning">RPA offline. Conecte o RPA primeiro.</p>
            ) : (
              <>
                <button 
                  className="btn-primary" 
                  onClick={fetchTelaInfo}
                  disabled={loading}
                  data-testid="btn-ver-tela"
                >
                  {loading ? 'Carregando...' : 'Capturar Tela Atual'}
                </button>

                {telaInfo && (
                  <div className="tela-info">
                    <div className="tela-header">
                      <h3>Tela Identificada: <span className="tela-name">{telaInfo.tela || 'DESCONHECIDO'}</span></h3>
                    </div>
                    
                    {telaInfo.textos && telaInfo.textos.length > 0 && (
                      <div className="tela-section">
                        <h4>Textos na Tela ({telaInfo.textos.length})</h4>
                        <div className="text-list">
                          {telaInfo.textos.map((t, i) => (
                            <span key={i} className="text-item">{t}</span>
                          ))}
                        </div>
                      </div>
                    )}

                    {telaInfo.descs && telaInfo.descs.length > 0 && (
                      <div className="tela-section">
                        <h4>Content Descriptions ({telaInfo.descs.length})</h4>
                        <div className="text-list">
                          {telaInfo.descs.map((d, i) => (
                            <span key={i} className="text-item desc">{d}</span>
                          ))}
                        </div>
                      </div>
                    )}

                    {telaInfo.error && (
                      <p className="error">{telaInfo.error}</p>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </main>

      <footer className="footer">
        <p>Branca de Neve 1.0 — Sistema de Automação RPA</p>
      </footer>
    </div>
  );
}

export default App;
