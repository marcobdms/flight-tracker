import PriceChart from './PriceChart.jsx'

const IATA_NAMES = {
  CCS: 'Caracas', MAD: 'Madrid', BCN: 'Barcelona',
  FCO: 'Roma FCO', CIA: 'Roma CIA', LIS: 'Lisboa',
  AMS: 'Ámsterdam', BER: 'Berlín', VIE: 'Viena',
}

const city = (code) => IATA_NAMES[code] || code

function formatDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })
}

export default function RouteCard({ alert, records, onEdit, onDelete, onToggle }) {
  const cheapest = records.length > 0
    ? Math.min(...records.map(r => r.price))
    : null

  const belowThreshold = cheapest !== null && cheapest < alert.threshold
  const pctDiff = cheapest !== null
    ? (((cheapest - alert.threshold) / alert.threshold) * 100).toFixed(0)
    : null

  const latest = records[0] || null

  return (
    <div className={`card ${!alert.active ? 'card-paused' : ''}`}
      style={!alert.active ? { opacity: 0.5 } : {}}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-primary)' }}>
              {alert.origin}
            </span>
            <span style={{ color: 'var(--accent)', fontSize: '1rem' }}>-</span>
            <span style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-primary)' }}>
              {alert.destination}
            </span>
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            {city(alert.origin)} - {city(alert.destination)}
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
          <span className={`badge ${alert.active ? 'badge-green' : 'badge-red'}`}>
            {alert.active ? '● Activa' : '○ Pausada'}
          </span>
          <span className={`badge ${alert.trip_type === 'roundtrip' ? 'badge-blue' : 'badge-purple'}`}>
            {alert.trip_type === 'roundtrip' ? 'I/V' : 'Ida'}
          </span>
        </div>
      </div>

      {/* ── Precio mínimo ── */}
      <div style={{ margin: '20px 0' }}>
        {cheapest !== null ? (
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 12 }}>
            <div className={`price-big ${!belowThreshold ? 'above-threshold' : ''}`}>
              {cheapest.toFixed(0)}€
            </div>
            <div style={{ paddingBottom: 6 }}>
              {belowThreshold ? (
                <span className="badge badge-green">
                  ↓ {Math.abs(pctDiff)}% bajo umbral
                </span>
              ) : (
                <span className="badge badge-yellow">
                  ↑ {Math.abs(pctDiff)}% sobre umbral
                </span>
              )}
            </div>
          </div>
        ) : (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Sin datos aún
          </div>
        )}
        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 4 }}>
          Umbral: <span style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>
            {alert.threshold}€
          </span>
          {alert.date_from && (
            <> · {formatDate(alert.date_from)} – {formatDate(alert.date_to)}</>
          )}
        </div>
      </div>

      {/* ── Chart mini ── */}
      {records.length > 1 && (
        <div style={{ marginBottom: 16 }}>
          <PriceChart records={records} threshold={alert.threshold} compact />
        </div>
      )}

      {/* ── Último vuelo encontrado ── */}
      {latest && (
        <>
          <div className="divider" />
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between' }}>
            <span>
              Última: <span style={{ color: 'var(--text-secondary)' }}>
                {latest.airline || '—'} · {latest.agent || '—'}
              </span>
            </span>
            <span>{latest.stops === 0 ? 'Directo' : `${latest.stops} escala(s)`}</span>
          </div>
          {latest.booking_url && (
            <a
              href={latest.booking_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-primary"
              style={{ width: '100%', justifyContent: 'center', marginTop: 12 }}
            >
              Reservar →
            </a>
          )}
        </>
      )}

      {/* ── Acciones ── */}
      <div className="divider" />
      <div style={{ display: 'flex', gap: 8 }}>
        <button className="btn btn-secondary btn-sm" onClick={onEdit} title="Editar">
          Editar
        </button>
        <button className="btn btn-secondary btn-sm" onClick={onToggle} title="Pausar/Activar">
          {alert.active ? 'Pausar' : 'Activar'}
        </button>
        <button className="btn btn-danger btn-sm" onClick={onDelete} title="Eliminar"
          style={{ marginLeft: 'auto' }}>
          Eliminar
        </button>
      </div>
    </div>
  )
}
