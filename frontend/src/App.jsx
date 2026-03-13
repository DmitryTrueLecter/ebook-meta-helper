import { useState, useEffect } from 'react'

const API_BASE = '/api'

export default function App() {
  const [books, setBooks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetch(`${API_BASE}/books`)
      .then(async (r) => {
        if (!r.ok) {
          let detail = r.statusText
          try {
            const body = await r.json()
            detail = body.detail || JSON.stringify(body)
          } catch {
            try {
              detail = await r.text()
            } catch {}
          }
          throw new Error(`${r.status} ${r.statusText}: ${detail}`)
        }
        return r.json()
      })
      .then((data) => {
        if (!cancelled) {
          setBooks(data.items ?? [])
        }
      })
      .catch((e) => {
        if (!cancelled) {
          console.error('[API Error]', e)
          setError(e.message || 'Неизвестная ошибка')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  return (
    <div style={{ padding: '2rem', maxWidth: 960, margin: '0 auto' }}>
      <h1 style={{ marginTop: 0 }}>Ebook Meta Helper</h1>
      {loading && <p>Загрузка…</p>}
      {error && (
        <div style={{ background: '#451a1a', border: '1px solid #f87171', borderRadius: 8, padding: '1rem', marginBottom: '1rem' }}>
          <p style={{ color: '#f87171', margin: 0, fontWeight: 600 }}>Ошибка загрузки</p>
          <pre style={{ color: '#fca5a5', margin: '0.5rem 0 0', whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: '0.875rem' }}>{error}</pre>
          <p style={{ color: '#a1a1aa', margin: '0.75rem 0 0', fontSize: '0.875rem' }}>
            Убедитесь, что API сервер запущен: <code style={{ background: '#27272a', padding: '2px 6px', borderRadius: 4 }}>python run_api.py</code>
          </p>
        </div>
      )}
      {!loading && !error && (
        <section>
          <h2>Книги</h2>
          {books.length === 0 ? (
            <p>Пока нет книг. Запустите пайплайн или подключите БД.</p>
          ) : (
            <ul style={{ listStyle: 'none', padding: 0 }}>
              {books.map((b) => (
                <li key={b.id} style={{ padding: '0.5rem 0', borderBottom: '1px solid #3f3f46' }}>
                  {b.title || b.original_filename || b.path}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  )
}
