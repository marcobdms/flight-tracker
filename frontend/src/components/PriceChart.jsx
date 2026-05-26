import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  LineChart,
  Line,
} from 'recharts'
import { format, parseISO } from 'date-fns'
import { es } from 'date-fns/locale'

function fmtDate(dateStr) {
  try {
    return format(parseISO(dateStr), 'd MMM', { locale: es })
  } catch {
    return dateStr?.slice(5, 10) || ''
  }
}

const CustomTooltip = ({ active, payload, threshold }) => {
  if (!active || !payload?.length) return null
  const d = payload[0]
  const below = d.value < threshold
  return (
    <div style={{
      background: 'rgba(17,19,39,0.97)',
      border: '1px solid rgba(102,126,234,0.3)',
      borderRadius: 10,
      padding: '10px 14px',
      fontSize: '0.82rem',
      color: 'var(--text-secondary)',
      boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
    }}>
      <div style={{ fontWeight: 700, color: below ? 'var(--green)' : 'var(--text-primary)', fontSize: '1rem' }}>
        {d.value.toFixed(0)}€
      </div>
      <div>{d.payload.date}</div>
      <div style={{ marginTop: 4 }}>
        {below
          ? <span style={{ color: 'var(--green)', fontSize: '0.75rem' }}>✅ Bajo umbral</span>
          : <span style={{ color: 'var(--yellow)', fontSize: '0.75rem' }}>⚠ Sobre umbral ({threshold}€)</span>
        }
      </div>
    </div>
  )
}

export default function PriceChart({ records, threshold, compact = false }) {
  if (!records || records.length === 0) return null

  // Agrupar por fecha: precio mínimo del día
  const byDate = {}
  for (const r of records) {
    const key = r.found_at?.slice(0, 10) || 'unknown'
    if (!byDate[key] || r.price < byDate[key]) byDate[key] = r.price
  }

  const data = Object.entries(byDate)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, price]) => ({ date: fmtDate(date), fullDate: date, price }))

  const minPrice = Math.min(...data.map(d => d.price))
  const maxPrice = Math.max(...data.map(d => d.price))
  const yMin = Math.max(0, minPrice * 0.9)
  const yMax = maxPrice * 1.05

  const height = compact ? 90 : 260

  if (compact) {
    return (
      <div className="chart-container">
        <ResponsiveContainer width="100%" height={height}>
          <AreaChart data={data} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="priceGradientCompact" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#667eea" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#667eea" stopOpacity={0} />
              </linearGradient>
            </defs>
            <ReferenceLine y={threshold} stroke="#f59e0b" strokeDasharray="3 3" strokeOpacity={0.6} />
            <Area
              type="monotone"
              dataKey="price"
              stroke="#667eea"
              strokeWidth={2}
              fill="url(#priceGradientCompact)"
              dot={false}
              activeDot={{ r: 4, fill: '#667eea', stroke: '#fff', strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    )
  }

  return (
    <div className="chart-container card" style={{ padding: 24 }}>
      <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--text-primary)' }}>
            Histórico de precios
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 2 }}>
            Precio mínimo diario · últimos 30 días
          </div>
        </div>
        <div style={{ display: 'flex', gap: 16, fontSize: '0.78rem' }}>
          <span style={{ color: 'var(--text-muted)' }}>
            Umbral: <span style={{ color: '#f59e0b', fontWeight: 700 }}>{threshold}€</span>
          </span>
          <span style={{ color: 'var(--text-muted)' }}>
            Mínimo: <span style={{ color: 'var(--green)', fontWeight: 700 }}>{minPrice.toFixed(0)}€</span>
          </span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="priceGradientFull" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#667eea" stopOpacity={0.25} />
              <stop offset="95%" stopColor="#667eea" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis
            dataKey="date"
            tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            domain={[yMin, yMax]}
            tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={v => `${v.toFixed(0)}€`}
            width={55}
          />
          <Tooltip content={<CustomTooltip threshold={threshold} />} />
          <ReferenceLine
            y={threshold}
            stroke="#f59e0b"
            strokeDasharray="5 5"
            strokeWidth={1.5}
            label={{ value: `Umbral ${threshold}€`, fill: '#f59e0b', fontSize: 11, position: 'right' }}
          />
          <Area
            type="monotone"
            dataKey="price"
            stroke="#667eea"
            strokeWidth={2.5}
            fill="url(#priceGradientFull)"
            dot={{ r: 3, fill: '#667eea', stroke: '#667eea' }}
            activeDot={{ r: 6, fill: '#667eea', stroke: '#fff', strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
