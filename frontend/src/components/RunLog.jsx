function fmtDateTime(dt) {
  if (!dt) return '—'
  try {
    return new Date(dt).toLocaleString('es-ES', {
      day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return dt
  }
}

const STATUS_CONFIG = {
  ok:         { badge: 'badge-green',  label: 'OK' },
  error:      { badge: 'badge-red',    label: 'Error' },
  no_results: { badge: 'badge-yellow', label: 'Sin datos' },
}

export default function RunLog({ runs }) {
  if (!runs || runs.length === 0) {
    return (
      <div className="empty-state">
        <h3>Sin ejecuciones aún</h3>
        <p>Los logs aparecerán aquí después de la primera búsqueda automática (08:00, 14:00 o 20:00) o al pulsar "Buscar ahora".</p>
      </div>
    )
  }

  return (
    <div className="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>Ruta</th>
            <th>Cuándo</th>
            <th>Resultados</th>
            <th>Mejor precio</th>
            <th>Estado</th>
            <th>Alerta enviada</th>
            <th>Error</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => {
            const config = STATUS_CONFIG[r.status] || { badge: 'badge-blue', label: r.status }
            return (
              <tr key={r.id}>
                <td style={{ fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '0.03em' }}>
                  {r.route}
                </td>
                <td style={{ fontSize: '0.82rem' }}>{fmtDateTime(r.ran_at)}</td>
                <td style={{ textAlign: 'center' }}>
                  <span style={{ fontWeight: 600, color: r.results_count > 0 ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                    {r.results_count}
                  </span>
                </td>
                <td>
                  {r.cheapest_price != null ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <span style={{ fontWeight: 700, color: 'var(--green)' }}>
                        {r.cheapest_price.toFixed(0)}€
                      </span>
                      {r.cheapest_date_out && (
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          {new Date(r.cheapest_date_out).toLocaleDateString('es-ES', { day: '2-digit', month: 'short' })}
                          {r.cheapest_date_back && ` - ${new Date(r.cheapest_date_back).toLocaleDateString('es-ES', { day: '2-digit', month: 'short' })}`}
                        </span>
                      )}
                      {r.cheapest_airline && (
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-primary)' }}>
                          {r.cheapest_airline} {r.cheapest_agent && r.cheapest_agent !== r.cheapest_airline ? `(vía ${r.cheapest_agent})` : ''}
                        </span>
                      )}
                      {r.cheapest_booking_url && (
                        <a href={r.cheapest_booking_url} target="_blank" rel="noreferrer" style={{ fontSize: '0.75rem', color: '#3B82F6', textDecoration: 'none', fontWeight: 600 }}>
                          Ver vuelo ↗
                        </a>
                      )}
                    </div>
                  ) : '—'}
                </td>
                <td>
                  <span className={`badge ${config.badge}`}>{config.label}</span>
                </td>
                <td style={{ textAlign: 'center' }}>
                  {r.alert_sent ? (
                    <span className="badge badge-purple">Sí</span>
                  ) : (
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>—</span>
                  )}
                </td>
                <td style={{ fontSize: '0.78rem', color: 'var(--red)', maxWidth: 200 }}>
                  {r.error_msg ? (
                    <span title={r.error_msg}>
                      {r.error_msg.length > 60 ? r.error_msg.slice(0, 60) + '…' : r.error_msg}
                    </span>
                  ) : '—'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
