import { useState, useEffect } from 'react'

const INITIAL = {
  origin: '',
  destination: '',
  threshold: '',
  trip_type: 'roundtrip',
  date_from: '2026-08-01',
  date_to:   '2026-09-30',
  active: true,
}

const PRESET_ROUTES = [
  { label: 'CCS → MAD (I/V)', origin: 'CCS', destination: 'MAD', threshold: 650, trip_type: 'roundtrip' },
  { label: 'CCS → BCN (I/V)', origin: 'CCS', destination: 'BCN', threshold: 650, trip_type: 'roundtrip' },
  { label: 'BCN → Roma',      origin: 'BCN', destination: 'FCO', threshold: 80,  trip_type: 'oneway' },
  { label: 'BCN → Lisboa',    origin: 'BCN', destination: 'LIS', threshold: 60,  trip_type: 'oneway' },
  { label: 'BCN → Ámsterdam', origin: 'BCN', destination: 'AMS', threshold: 80,  trip_type: 'oneway' },
  { label: 'BCN → Berlín',    origin: 'BCN', destination: 'BER', threshold: 80,  trip_type: 'oneway' },
  { label: 'BCN → Viena',     origin: 'BCN', destination: 'VIE', threshold: 70,  trip_type: 'oneway' },
]

export default function AlertForm({ alert, onSave, onClose }) {
  const [form, setForm] = useState(INITIAL)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (alert) {
      setForm({
        origin:      alert.origin || '',
        destination: alert.destination || '',
        threshold:   alert.threshold || '',
        trip_type:   alert.trip_type || 'roundtrip',
        date_from:   alert.date_from || '2026-08-01',
        date_to:     alert.date_to   || '2026-09-30',
        active:      alert.active ?? true,
      })
    } else {
      setForm(INITIAL)
    }
  }, [alert])

  const set = (key, val) => setForm(f => ({ ...f, [key]: val }))

  const applyPreset = (preset) => {
    setForm(f => ({
      ...f,
      origin:      preset.origin,
      destination: preset.destination,
      threshold:   preset.threshold,
      trip_type:   preset.trip_type,
    }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.origin || !form.destination || !form.threshold) return
    setSaving(true)
    await onSave({
      origin:      form.origin.toUpperCase().trim(),
      destination: form.destination.toUpperCase().trim(),
      threshold:   parseFloat(form.threshold),
      trip_type:   form.trip_type,
      date_from:   form.date_from || null,
      date_to:     form.date_to   || null,
      active:      form.active,
    })
    setSaving(false)
  }

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-box">
        <div className="modal-title">
          {alert ? 'Editar alerta' : 'Nueva alerta de vuelo'}
        </div>

        {/* Presets (solo en modo crear) */}
        {!alert && (
          <div style={{ marginBottom: 20 }}>
            <div className="form-label">Rutas predefinidas</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {PRESET_ROUTES.map((p, i) => (
                <button
                  key={i}
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => applyPreset(p)}
                  style={{ fontSize: '0.75rem' }}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {/* Origen / Destino */}
          <div className="form-row">
            <div className="form-group">
              <label className="form-label" htmlFor="input-origin">Origen (IATA)</label>
              <input
                id="input-origin"
                className="form-input"
                placeholder="CCS"
                maxLength={3}
                value={form.origin}
                onChange={(e) => set('origin', e.target.value.toUpperCase())}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="input-destination">Destino (IATA)</label>
              <input
                id="input-destination"
                className="form-input"
                placeholder="MAD"
                maxLength={3}
                value={form.destination}
                onChange={(e) => set('destination', e.target.value.toUpperCase())}
                required
              />
            </div>
          </div>

          {/* Umbral / Tipo */}
          <div className="form-row">
            <div className="form-group">
              <label className="form-label" htmlFor="input-threshold">Umbral de alerta (€)</label>
              <input
                id="input-threshold"
                className="form-input"
                type="number"
                placeholder="650"
                min={1}
                value={form.threshold}
                onChange={(e) => set('threshold', e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="select-trip-type">Tipo de viaje</label>
              <select
                id="select-trip-type"
                className="form-select"
                value={form.trip_type}
                onChange={(e) => set('trip_type', e.target.value)}
              >
                <option value="roundtrip">↔ Ida y vuelta</option>
                <option value="oneway">→ Solo ida</option>
              </select>
            </div>
          </div>

          {/* Rango de fechas */}
          <div className="form-row">
            <div className="form-group">
              <label className="form-label" htmlFor="input-date-from">Fecha desde</label>
              <input
                id="input-date-from"
                className="form-input"
                type="date"
                value={form.date_from}
                onChange={(e) => set('date_from', e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="input-date-to">Fecha hasta</label>
              <input
                id="input-date-to"
                className="form-input"
                type="date"
                value={form.date_to}
                onChange={(e) => set('date_to', e.target.value)}
              />
            </div>
          </div>

          {/* Activa */}
          <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <input
              id="check-active"
              type="checkbox"
              checked={form.active}
              onChange={(e) => set('active', e.target.checked)}
              style={{ width: 16, height: 16, accentColor: 'var(--accent)', cursor: 'pointer' }}
            />
            <label htmlFor="check-active" style={{ cursor: 'pointer', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
              Alerta activa (el scheduler la procesará)
            </label>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancelar
            </button>
            <button
              type="submit"
              id="btn-save-alert"
              className="btn btn-primary"
              disabled={saving}
            >
              {saving ? 'Guardando…' : alert ? 'Guardar cambios' : 'Crear alerta'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
