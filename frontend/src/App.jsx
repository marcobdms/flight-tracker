import { useState, useEffect, useCallback } from 'react'
import toast from 'react-hot-toast'
import RouteCard from './components/RouteCard.jsx'
import AlertForm from './components/AlertForm.jsx'
import RunLog from './components/RunLog.jsx'

const API = import.meta.env.VITE_API_URL || '/api'

const TABS = [
  { id: 'routes',  label: 'Rutas' },
  { id: 'alerts',  label: 'Alertas' },
  { id: 'runs',    label: 'Ejecuciones' },
]

export default function App() {
  const [tab, setTab]         = useState('routes')
  const [alerts, setAlerts]   = useState([])
  const [runs, setRuns]       = useState([])
  const [history, setHistory] = useState({})   // { 'CCS-MAD': [...records] }
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [editAlert, setEditAlert] = useState(null)

  // ── Fetch alertas ──────────────────────────────────────────────
  const fetchAlerts = useCallback(async () => {
    try {
      const res = await fetch(`${API}/alerts`)
      if (!res.ok) throw new Error('No se pudo cargar las alertas')
      const data = await res.json()
      setAlerts(data)
      return data
    } catch (e) {
      toast.error(`Error cargando alertas: ${e.message}`)
      return []
    }
  }, [])

  // ── Fetch runs ─────────────────────────────────────────────────
  const fetchRuns = useCallback(async () => {
    try {
      const res = await fetch(`${API}/history/runs?limit=50`)
      if (!res.ok) throw new Error()
      const data = await res.json()
      setRuns(data)
    } catch {
      setRuns([])
    }
  }, [])

  // ── Fetch historial de precios para cada ruta ──────────────────
  const fetchHistory = useCallback(async (alertList) => {
    const results = {}
    await Promise.all(
      alertList.map(async (a) => {
        try {
          const res = await fetch(`${API}/history?route=${a.origin}-${a.destination}&days=30`)
          if (res.ok) {
            const data = await res.json()
            results[`${a.origin}-${a.destination}`] = data
          }
        } catch {
          results[`${a.origin}-${a.destination}`] = []
        }
      })
    )
    setHistory(results)
  }, [])

  // ── Carga inicial ──────────────────────────────────────────────
  useEffect(() => {
    const init = async () => {
      setLoading(true)
      const data = await fetchAlerts()
      await Promise.all([fetchRuns(), fetchHistory(data)])
      setLoading(false)
    }
    init()
  }, [fetchAlerts, fetchRuns, fetchHistory])

  // ── Búsqueda manual ────────────────────────────────────────────
  const handleManualRun = () => {
    setRunning(true)
    const tid = toast.loading('Iniciando búsqueda...')
    
    const eventSource = new EventSource(`${API}/search/stream`)
    
    eventSource.onmessage = async (event) => {
      const msg = event.data
      
      if (msg === 'DONE') {
        eventSource.close()
        toast.success('Búsqueda completada', { id: tid })
        const data = await fetchAlerts()
        await Promise.all([fetchRuns(), fetchHistory(data)])
        setRunning(false)
      } else if (msg.startsWith('ERROR:')) {
        eventSource.close()
        toast.error(msg, { id: tid })
        setRunning(false)
      } else {
        toast.loading(msg, { id: tid })
      }
    }
    
    eventSource.onerror = () => {
      eventSource.close()
      toast.error('Error de conexión con el servidor', { id: tid })
      setRunning(false)
    }
  }

  // ── Guardar alerta (crear / editar) ───────────────────────────
  const handleSaveAlert = async (payload) => {
    try {
      let res
      if (editAlert) {
        res = await fetch(`${API}/alerts/${editAlert.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })
      } else {
        res = await fetch(`${API}/alerts`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })
      }
      if (!res.ok) throw new Error(await res.text())
      toast.success(editAlert ? 'Alerta actualizada' : 'Alerta creada')
      setShowForm(false)
      setEditAlert(null)
      const data = await fetchAlerts()
      await fetchHistory(data)
    } catch (e) {
      toast.error(`Error guardando: ${e.message}`)
    }
  }

  // ── Eliminar alerta ────────────────────────────────────────────
  const handleDeleteAlert = async (id) => {
    if (!window.confirm('¿Eliminar esta alerta?')) return
    try {
      const res = await fetch(`${API}/alerts/${id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error()
      toast.success('Alerta eliminada')
      const data = await fetchAlerts()
      await fetchHistory(data)
    } catch {
      toast.error('Error al eliminar')
    }
  }

  // ── Toggle activo ──────────────────────────────────────────────
  const handleToggleActive = async (alert) => {
    try {
      const res = await fetch(`${API}/alerts/${alert.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active: !alert.active }),
      })
      if (!res.ok) throw new Error()
      toast.success(alert.active ? 'Alerta pausada' : 'Alerta activada')
      await fetchAlerts()
    } catch {
      toast.error('Error actualizando estado')
    }
  }

  // ── Stats hero ─────────────────────────────────────────────────
  const activeCount   = alerts.filter(a => a.active).length
  const alertsSent    = runs.filter(r => r.alert_sent).length
  const cheapestAll   = alerts.length > 0
    ? Math.min(...Object.values(history).flat().map(r => r.price).filter(Boolean))
    : null

  return (
    <>
      {/* NAVBAR */}
      <nav className="navbar">
        <div className="navbar-inner">
          <a href="/" className="navbar-brand">
            Flight Tracker
          </a>
          <div className="navbar-nav">
            {TABS.map(t => (
              <button
                key={t.id}
                className={`nav-btn ${tab === t.id ? 'active' : ''}`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>
          <button
            id="btn-manual-run"
            className="btn btn-primary btn-sm"
            onClick={handleManualRun}
            disabled={running || alerts.length === 0}
          >
            {running ? 'Buscando…' : 'Buscar ahora'}
          </button>
        </div>
      </nav>

      {/* HERO */}
      <div className="hero">
        <h1 className="hero-title">Tu tracker de vuelos baratos</h1>
        <p className="hero-subtitle">
          Monitoriza {alerts.length} rutas automáticamente y recibe alertas
          por email y WhatsApp cuando el precio baje del umbral.
        </p>
        <div className="hero-stats">
          <div className="hero-stat">
            <span className="hero-stat-value">{activeCount}</span>
            <span className="hero-stat-label">Rutas activas</span>
          </div>
          <div className="hero-stat">
            <span className="hero-stat-value">{runs.length}</span>
            <span className="hero-stat-label">Búsquedas realizadas</span>
          </div>
          <div className="hero-stat">
            <span className="hero-stat-value">{alertsSent}</span>
            <span className="hero-stat-label">Alertas enviadas</span>
          </div>
          {cheapestAll && isFinite(cheapestAll) && (
            <div className="hero-stat">
              <span className="hero-stat-value" style={{ color: 'var(--green)' }}>
                {cheapestAll.toFixed(0)}€
              </span>
              <span className="hero-stat-label">Mínimo histórico</span>
            </div>
          )}
        </div>
      </div>

      {/* MOBILE TABS */}
      <div className="container" style={{ marginBottom: 24 }}>
        <div className="tab-bar">
          {TABS.map(t => (
            <button
              key={t.id}
              className={`tab-btn ${tab === t.id ? 'active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* CONTENT */}
      {loading ? (
        <div className="loading-center"><div className="spinner" /></div>
      ) : (
        <div className="container">

          {/* ── TAB: RUTAS ── */}
          {tab === 'routes' && (
            <section className="section" style={{ padding: 0, paddingBottom: 64 }}>
              <div className="section-header">
                <div>
                  <h2 className="section-title">Rutas monitoreadas</h2>
                  <p className="section-subtitle">Precio mínimo de los últimos 30 días</p>
                </div>
                <button
                  id="btn-add-alert"
                  className="btn btn-secondary btn-sm"
                  onClick={() => { setEditAlert(null); setShowForm(true) }}
                >
                  + Nueva ruta
                </button>
              </div>
              {alerts.length === 0 ? (
                <div className="empty-state">
                  <h3>No hay rutas configuradas</h3>
                  <p>Añade tu primera ruta para empezar a monitorizar precios.</p>
                  <button
                    className="btn btn-primary"
                    style={{ marginTop: 16 }}
                    onClick={() => { setEditAlert(null); setShowForm(true) }}
                  >
                    + Añadir ruta
                  </button>
                </div>
              ) : (
                <div className="routes-grid">
                  {alerts.map(alert => (
                    <RouteCard
                      key={alert.id}
                      alert={alert}
                      records={history[`${alert.origin}-${alert.destination}`] || []}
                      onEdit={() => { setEditAlert(alert); setShowForm(true) }}
                      onDelete={() => handleDeleteAlert(alert.id)}
                      onToggle={() => handleToggleActive(alert)}
                    />
                  ))}
                </div>
              )}
            </section>
          )}

          {/* ── TAB: ALERTAS ── */}
          {tab === 'alerts' && (
            <section className="section" style={{ padding: 0, paddingBottom: 64 }}>
              <div className="section-header">
                <div>
                  <h2 className="section-title">Configuración de alertas</h2>
                  <p className="section-subtitle">Gestiona umbrales y canales de notificación</p>
                </div>
                <button
                  id="btn-add-alert-tab"
                  className="btn btn-primary btn-sm"
                  onClick={() => { setEditAlert(null); setShowForm(true) }}
                >
                  + Nueva alerta
                </button>
              </div>
              {alerts.length === 0 ? (
                <div className="empty-state">
                  <h3>Sin alertas configuradas</h3>
                </div>
              ) : (
                <div className="table-wrapper">
                  <table>
                    <thead>
                      <tr>
                        <th>Ruta</th>
                        <th>Tipo</th>
                        <th>Umbral</th>
                        <th>Período</th>
                        <th>Estado</th>
                        <th>Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {alerts.map(a => (
                        <tr key={a.id}>
                          <td style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
                            {a.origin} → {a.destination}
                          </td>
                          <td>
                            <span className={`badge ${a.trip_type === 'roundtrip' ? 'badge-blue' : 'badge-purple'}`}>
                              {a.trip_type === 'roundtrip' ? 'Ida/Vuelta' : 'Solo ida'}
                            </span>
                          </td>
                          <td style={{ fontWeight: 700, color: 'var(--green)' }}>
                            {a.threshold}€
                          </td>
                          <td style={{ fontSize: '0.8rem' }}>
                            {a.date_from && a.date_to
                              ? `${a.date_from} → ${a.date_to}`
                              : '—'}
                          </td>
                          <td>
                            <span className={`badge ${a.active ? 'badge-green' : 'badge-red'}`}>
                              {a.active ? '● Activa' : '○ Pausada'}
                            </span>
                          </td>
                          <td>
                            <div style={{ display: 'flex', gap: 6 }}>
                              <button
                                className="btn btn-secondary btn-sm"
                                onClick={() => { setEditAlert(a); setShowForm(true) }}
                                title="Editar"
                              >Editar</button>
                              <button
                                className="btn btn-secondary btn-sm"
                                onClick={() => handleToggleActive(a)}
                                title={a.active ? 'Pausar' : 'Activar'}
                              >
                                {a.active ? 'Pausar' : 'Activar'}
                              </button>
                              <button
                                className="btn btn-danger btn-sm"
                                onClick={() => handleDeleteAlert(a.id)}
                                title="Eliminar"
                              >Eliminar</button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}

          {/* ── TAB: EJECUCIONES ── */}
          {tab === 'runs' && (
            <section className="section" style={{ padding: 0, paddingBottom: 64 }}>
              <div className="section-header">
                <div>
                  <h2 className="section-title">Log de ejecuciones</h2>
                  <p className="section-subtitle">Historial de búsquedas automáticas del scheduler</p>
                </div>
                <button className="btn btn-secondary btn-sm" onClick={fetchRuns}>
                  🔄 Actualizar
                </button>
              </div>
              <RunLog runs={runs} />
            </section>
          )}
        </div>
      )}

      {/* MODAL FORMULARIO ALERTA */}
      {showForm && (
        <AlertForm
          alert={editAlert}
          onSave={handleSaveAlert}
          onClose={() => { setShowForm(false); setEditAlert(null) }}
        />
      )}
    </>
  )
}
