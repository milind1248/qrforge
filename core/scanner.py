"""Live QR scanner for the entrance (Streamlit Custom Component v2, runs in the browser) + a print button.
The browser reads the camera. Where the BarcodeDetector API exists (Chrome/Android) the QR is decoded on the phone itself; elsewhere
(iPhone Safari, desktop Firefox) small JPEG frames are sent to the server and decoded there with OpenCV. Results come back to Python
via triggers: `code` (decoded text) and `frame` (data-URL image). Python answers through `data` so the page can beep/vibrate."""
import base64

import streamlit as st

_HTML = """
<div class="gs">
  <div class="stage">
    <video class="vid" playsinline muted></video>
    <div class="reticle"></div>
    <div class="flash"></div>
    <div class="idle"><div class="ico">&#128247;</div><div class="t">Tap Start camera to scan passes</div></div>
  </div>
  <div class="bar">
    <button type="button" class="btn start">Start camera</button>
    <button type="button" class="btn ghost flip" style="display:none">Switch camera</button>
    <span class="msg"></span>
  </div>
</div>
"""

_CSS = """
.gs { max-width: 560px; margin: 0 auto; font-family: var(--st-font, sans-serif); color: var(--st-text-color, #0f172a); }
.stage { position: relative; width: 100%; aspect-ratio: 4 / 3; background: #0b1020; border-radius: 18px; overflow: hidden; }
.vid { width: 100%; height: 100%; object-fit: cover; display: none; }
.reticle { position: absolute; inset: 14% 18%; border: 3px solid rgba(255,255,255,.85); border-radius: 18px; box-shadow: 0 0 0 999px rgba(0,0,0,.28); display: none; pointer-events: none; }
.flash { position: absolute; inset: 0; opacity: 0; pointer-events: none; transition: opacity .35s ease-out; }
.idle { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #cbd5e1; gap: 8px; }
.idle .ico { font-size: 44px; } .idle .t { font-size: 15px; }
.bar { display: flex; gap: 10px; align-items: center; margin-top: 10px; flex-wrap: wrap; }
.btn { background: linear-gradient(90deg, #4f46e5, #7c3aed); color: #fff; border: 0; padding: 10px 18px; border-radius: 12px; font-weight: 700; font-size: 15px; cursor: pointer; }
.btn.ghost { background: transparent; color: var(--st-primary-color, #4f46e5); border: 1px solid #c7d2fe; }
.msg { font-size: 13px; color: #64748b; }
"""

_JS = """
export default function (component) {
  const { data, parentElement, setTriggerValue } = component
  const root = parentElement.querySelector('.gs')
  if (!root) return
  let S = parentElement.__gate
  if (!S) {
    S = parentElement.__gate = { running: false, stream: null, facing: 'environment', pauseUntil: 0, lastCode: '', lastCodeAt: 0, lastUpload: 0,
                                 lastTick: 0, det: null, lastNonce: 0, audio: null, frames: 0 }
    S.video = root.querySelector('.vid'); S.reticle = root.querySelector('.reticle'); S.idle = root.querySelector('.idle')
    S.flash = root.querySelector('.flash'); S.msg = root.querySelector('.msg'); S.start = root.querySelector('.start'); S.flip = root.querySelector('.flip')
    S.canvas = document.createElement('canvas')
    try { if ('BarcodeDetector' in window) S.det = new BarcodeDetector({ formats: ['qr_code'] }) } catch (e) { S.det = null }

    const stop = () => {
      S.running = false
      if (S.stream) { S.stream.getTracks().forEach(t => t.stop()); S.stream = null }
      S.video.style.display = 'none'; S.reticle.style.display = 'none'; S.idle.style.display = 'flex'
      S.start.textContent = 'Start camera'; S.flip.style.display = 'none'
    }
    S.stop = stop
    const emit = (text) => {
      const now = performance.now()
      if (!text || (text === S.lastCode && now - S.lastCodeAt < 4000)) return
      S.lastCode = text; S.lastCodeAt = now; S.pauseUntil = now + 1500
      S.msg.textContent = 'Checking...'
      setTriggerValue('code', text)
    }
    const loop = async () => {
      if (!S.running) return
      const now = performance.now()
      if (now > S.pauseUntil && S.video.readyState >= 2 && now - S.lastTick > 110) {
        S.lastTick = now
        try {
          if (S.det) {
            const codes = await S.det.detect(S.video)
            if (codes.length) emit(codes[0].rawValue)
          } else if (now - S.lastUpload > 850) {
            S.lastUpload = now
            const w = Math.min(640, S.video.videoWidth || 640), h = Math.round(w * (S.video.videoHeight || 480) / (S.video.videoWidth || 640))
            S.canvas.width = w; S.canvas.height = h
            S.canvas.getContext('2d').drawImage(S.video, 0, 0, w, h)
            S.frames += 1
            setTriggerValue('frame', S.canvas.toDataURL('image/jpeg', 0.7))
          }
        } catch (e) { /* keep scanning */ }
      }
      requestAnimationFrame(loop)
    }
    const startCam = async () => {
      try {
        if (!S.audio) { const AC = window.AudioContext || window.webkitAudioContext; if (AC) S.audio = new AC() }
        if (S.audio && S.audio.state === 'suspended') S.audio.resume()
        if (S.stream) S.stream.getTracks().forEach(t => t.stop())
        S.stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: S.facing }, width: { ideal: 1280 } }, audio: false })
        S.video.srcObject = S.stream; await S.video.play()
        S.video.style.display = 'block'; S.reticle.style.display = 'block'; S.idle.style.display = 'none'
        S.start.textContent = 'Stop camera'; S.flip.style.display = ''
        S.msg.textContent = S.det ? 'Scanning... hold the pass inside the frame' : 'Scanning (server mode)... hold the pass inside the frame'
        if (!S.running) { S.running = true; requestAnimationFrame(loop) }
      } catch (e) {
        S.msg.textContent = 'Camera unavailable: ' + (e && e.name === 'NotAllowedError' ? 'permission was denied. Allow camera access in the browser.' : (e && e.message) || e)
      }
    }
    S.start.onclick = () => { if (S.running) stop(); else startCam() }
    S.flip.onclick = () => { S.facing = S.facing === 'environment' ? 'user' : 'environment'; startCam() }
    S.beep = (freqs, dur) => {
      if (!S.audio) return
      let t = S.audio.currentTime
      freqs.forEach(f => { const o = S.audio.createOscillator(), g = S.audio.createGain(); o.frequency.value = f; o.type = 'sine'
        g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.35, t + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t + dur)
        o.connect(g); g.connect(S.audio.destination); o.start(t); o.stop(t + dur + 0.02); t += dur + 0.04 })
    }
  }
  // Python -> JS: feedback for the last scan (beep + vibrate + colour flash). `nonce` makes each result fire once.
  if (data && data.nonce && data.nonce !== S.lastNonce) {
    S.lastNonce = data.nonce
    const r = data.result || ''
    const good = r === 'valid'
    S.flash.style.background = good ? 'rgba(16,185,129,.55)' : (r === 'already_used' ? 'rgba(245,158,11,.55)' : 'rgba(239,68,68,.55)')
    S.flash.style.opacity = '1'; setTimeout(() => { S.flash.style.opacity = '0' }, 450)
    S.beep(good ? [880, 1320] : (r === 'already_used' ? [440, 440] : [300, 220, 300]), good ? 0.11 : 0.16)
    if (navigator.vibrate) navigator.vibrate(good ? 80 : [120, 60, 120])
    S.msg.textContent = good ? 'Checked in. Next pass...' : 'Result shown below. Next pass...'
  }
}
"""

_SCANNER = st.components.v2.component("qrforge_gate_scanner", html=_HTML, css=_CSS, js=_JS)

_PRINT = st.components.v2.component(
    "qrforge_print_button",
    html="<button type='button' class='pb'>Print this pass</button>",
    css=".pb{background:#fff;color:#4f46e5;border:1px solid #c7d2fe;padding:9px 16px;border-radius:12px;font-weight:700;font-size:14px;cursor:pointer;width:100%}"
        ".pb:hover{background:#eef2ff}",
    js="""
export default function (component) {
  const { data, parentElement } = component
  const b = parentElement.querySelector('.pb')
  if (!b) return
  if (data && data.label) b.textContent = data.label
  b.onclick = () => {
    // print ONLY this attendee's pass card in a clean window (the rest of the app page is left out)
    const doc = parentElement.ownerDocument
    const card = doc.querySelector('.pass-print[data-ref="' + ((data && data.ref) || '') + '"]')
    if (!card) { window.print(); return }
    const w = window.open('', '_blank', 'width=520,height=800')
    if (!w) { window.print(); return }
    w.document.write('<!doctype html><html><head><meta charset="utf-8"><title>Event pass</title>'
      + '<style>body{margin:24px;font-family:Arial,sans-serif;background:#fff}@page{margin:12mm}</style></head><body>' + card.outerHTML + '</body></html>')
    w.document.close()
    w.focus()
    setTimeout(() => { w.print() }, 400)
  }
}
""",
)


def live_scanner(key: str, result: str = "", nonce: int = 0):
    """Mounts the scanner. Returns (code_text_or_None, frame_data_url_or_None) for this run."""
    res = _SCANNER(key=key, data={"result": result, "nonce": nonce}, on_code_change=lambda: None, on_frame_change=lambda: None)
    return res.code, res.frame


def print_button(key: str, ref: str = ""):
    from core.i18n import _
    _PRINT(key=key, data={"ref": ref, "label": _("Print this pass")})


def frame_to_bytes(data_url: str, max_bytes: int = 600_000) -> bytes | None:
    """Camera frame sent by the browser -> JPEG bytes (size-capped so nobody can push huge payloads)."""
    if not data_url or not data_url.startswith("data:image/") or "," not in data_url or len(data_url) > max_bytes * 1.4:
        return None
    try:
        raw = base64.b64decode(data_url.split(",", 1)[1])
    except Exception:  # noqa: BLE001
        return None
    return raw if len(raw) <= max_bytes else None
