import { useState } from 'react'
import { postAgents } from '../../api'

const CAPTION_STYLES = ['tiktok', 'bold_yellow', 'minimal']

export default function Media() {
  // TTS (A35)
  const [script, setScript] = useState('')
  const [voice, setVoice] = useState('')
  const [tts, setTts] = useState(null)
  const [ttsBusy, setTtsBusy] = useState(false)
  const [ttsErr, setTtsErr] = useState('')

  // Caption (A34)
  const [videoUrl, setVideoUrl] = useState('')
  const [style, setStyle] = useState('tiktok')
  const [cap, setCap] = useState(null)
  const [capBusy, setCapBusy] = useState(false)
  const [capErr, setCapErr] = useState('')

  async function runTts() {
    if (!script.trim()) { setTtsErr('Вставь текст скрипта'); return }
    setTtsBusy(true); setTtsErr(''); setTts(null)
    try {
      const data = await postAgents('/tts', { text: script.trim(), voice: voice.trim() || undefined })
      if (data.error) setTtsErr(data.error)
      setTts(data)
    } catch (e) { setTtsErr(e.message) }
    setTtsBusy(false)
  }

  async function runCaption() {
    if (!videoUrl.trim()) { setCapErr('Укажи URL видео'); return }
    setCapBusy(true); setCapErr(''); setCap(null)
    try {
      const data = await postAgents('/caption', { video_url: videoUrl.trim(), style })
      if (data.error) setCapErr(data.error)
      setCap(data)
    } catch (e) { setCapErr(e.message) }
    setCapBusy(false)
  }

  return (
    <>
      {/* TTS Voiceover (A35) */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">🎙️ Озвучка скрипта <span className="ref-tag">A35 TTS</span></div>
        </div>
        <div className="card-body">
          <div className="note-box" style={{ marginBottom: 12 }}>
            Провайдер по приоритету: <code>TTS_SERVER_URL</code> (self-hosted Kokoro/Chatterbox) → ElevenLabs.
            Аудио грузится в Supabase Storage.
          </div>
          <label className="form-label">Скрипт</label>
          <textarea className="form-control" rows={5} value={script} onChange={e => setScript(e.target.value)}
            placeholder="Текст закадрового голоса…" />
          <div style={{ display: 'flex', gap: 8, marginTop: 10, alignItems: 'center' }}>
            <input className="form-control" style={{ maxWidth: 240 }} value={voice} onChange={e => setVoice(e.target.value)}
              placeholder="voice id (опц.)" />
            <button className="btn btn-primary" onClick={runTts} disabled={ttsBusy}>
              {ttsBusy ? 'Озвучиваю…' : 'Озвучить'}
            </button>
            {ttsErr && <span style={{ color: 'var(--red)', fontSize: 12 }}>⚠️ {ttsErr}</span>}
          </div>
          {tts && !tts.error && (
            <div style={{ marginTop: 12, fontSize: 13 }}>
              <div style={{ color: 'var(--muted)', marginBottom: 8 }}>
                Провайдер: <b>{tts.provider}</b> · символов: {tts.chars} · ≈ {tts.est_duration_sec}с
              </div>
              {tts.audio_url
                ? <audio controls src={tts.audio_url} style={{ width: '100%' }} />
                : <div className="note-box">Аудио получено, но нет URL (проверь MEDIA_BUCKET/Storage).</div>}
            </div>
          )}
        </div>
      </div>

      {/* Auto-Caption (A34) */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">💬 Авто-субтитры <span className="ref-tag">A34 Caption</span></div>
        </div>
        <div className="card-body">
          <div className="note-box" style={{ marginBottom: 12 }}>
            Word-тайминги берутся из Deepgram (<code>DEEPGRAM_API_KEY</code>). Агент отдаёт стилизованный
            ASS/SRT и ffmpeg-команду; рендер (burn) делает воркер.
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input className="form-control" style={{ flex: 1 }} value={videoUrl} onChange={e => setVideoUrl(e.target.value)}
              placeholder="https://…/video.mp4" />
            <select className="form-control" style={{ maxWidth: 150 }} value={style} onChange={e => setStyle(e.target.value)}>
              {CAPTION_STYLES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <button className="btn btn-primary" onClick={runCaption} disabled={capBusy}>
              {capBusy ? 'Строю…' : 'Сделать субтитры'}
            </button>
          </div>
          {capErr && <div style={{ color: 'var(--red)', fontSize: 12, marginTop: 8 }}>⚠️ {capErr}</div>}
          {cap && !cap.error && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 8 }}>
                Сегментов: <b>{cap.segment_count}</b>{cap.burned_url ? ' · burned ✅' : ''}
              </div>
              <label className="form-label">ffmpeg команда</label>
              <input className="form-control mono" style={{ fontSize: 11 }} readOnly value={cap.ffmpeg_cmd} onFocus={e => e.target.select()} />
              <label className="form-label" style={{ marginTop: 10 }}>SRT (превью)</label>
              <textarea className="form-control mono" style={{ fontSize: 11 }} rows={6} readOnly value={cap.srt} />
            </div>
          )}
        </div>
      </div>
    </>
  )
}
