"""Animated home-page demo: a link is typed, the QR builds, a phone scans it and the page opens. Pure CSS/JS in a CCv2 component (no media files)."""
import streamlit as st

_HTML = """
<div class="hd">
  <div class="hd-steps"><span>1 Type a link</span><span>2 QR builds</span><span>3 Phone scans it</span></div>
  <div class="hd-row">
    <svg class="hd-qr" width="104" height="104" viewBox="0 0 10 10" role="img" aria-label="QR code being built"></svg>
    <div class="hd-phone">
      <div class="hd-notch"></div>
      <div class="hd-cam">
        <div class="hd-frame"></div>
        <svg class="hd-qr2" width="44" height="44" viewBox="0 0 10 10" aria-hidden="true"></svg>
        <div class="hd-beam"></div>
      </div>
      <div class="hd-ok"><div class="hd-tick">&#10003;</div><b>Menu opened</b><span>shop.in/menu</span></div>
      <div class="hd-hint">Point camera at the code</div>
    </div>
    <div class="hd-count"><i>Scans today</i><b>0</b></div>
  </div>
</div>
"""

_CSS = """
.hd { font-family: var(--st-font, sans-serif); background: linear-gradient(135deg,#EEF2FF,#F5F3FF); border: 1px solid #C7D2FE; border-radius: 20px; padding: 12px 14px; max-width: 480px; margin: 0 auto; }
.hd-steps { display: flex; gap: 6px; margin-bottom: 8px; }
.hd-steps span { flex: 1; text-align: center; font-size: 11.5px; font-weight: 600; padding: 5px 4px; border-radius: 999px; border: 1px solid #C7D2FE; color: #64748B; background: #fff; transition: all .3s; white-space: nowrap; }
.hd-steps span.on { background: #4F46E5; color: #fff; border-color: #4F46E5; }
.hd-link { display: flex; align-items: center; gap: 8px; background: #fff; border: 1px solid #C7D2FE; border-radius: 10px; padding: 7px 10px; margin-bottom: 10px; }
.hd-link i { font-style: normal; font-size: 11px; color: #94A3B8; }
.hd-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.hd-qr { background: #fff; padding: 6px; border-radius: 10px; border: 1px solid #E2E8F0; box-shadow: 0 6px 18px rgba(79,70,229,.15); }
.hd-phone { position: relative; width: 90px; height: 150px; border: 3px solid #1E1B4B; border-radius: 18px; background: #0B1020; overflow: hidden; flex: none; }
.hd-notch { position: absolute; top: 4px; left: 50%; width: 28px; height: 4px; margin-left: -14px; border-radius: 3px; background: #475569; z-index: 2; }
.hd-cam { position: absolute; inset: 16px 5px 26px 5px; border-radius: 8px; background: #1E293B; overflow: hidden; }
.hd-frame { position: absolute; left: 50%; top: 50%; width: 58px; height: 68px; margin: -34px 0 0 -29px; border: 2px solid #fff; border-radius: 9px; opacity: .9; }
.hd-qr2 { position: absolute; left: 50%; top: 50%; width: 44px; height: 44px; margin: -25px 0 0 -25px; background: #fff; padding: 3px; border-radius: 4px; opacity: 0; transform: scale(.5); transition: transform .8s ease, opacity .4s; }
.hd-beam { position: absolute; left: 50%; width: 52px; margin-left: -26px; height: 2px; top: 16px; background: #38BDF8; box-shadow: 0 0 8px #38BDF8; opacity: 0; }
.hd-ok { position: absolute; inset: 0; background: #fff; opacity: 0; transition: opacity .4s; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; z-index: 3; }
.hd-tick { width: 34px; height: 34px; border-radius: 50%; background: #D1FAE5; color: #047857; font-size: 20px; font-weight: 800; display: flex; align-items: center; justify-content: center; }
.hd-ok b { font-size: 12.5px; color: #0F172A; } .hd-ok span { font-size: 10.5px; color: #64748B; }
.hd-hint { position: absolute; bottom: 7px; left: 0; right: 0; text-align: center; font-size: 9.5px; color: #94A3B8; }
.hd-count { text-align: center; min-width: 64px; }
.hd-count i { display: block; font-style: normal; font-size: 11px; color: #64748B; }
.hd-count b { font-size: 28px; color: #4F46E5; font-weight: 800; }
@media (max-width: 900px) { .hd { display: none; } }
"""

_JS = """
export default function (component) {
  const { parentElement } = component
  const root = parentElement.querySelector('.hd')
  if (!root) return
  const NS = 'http://www.w3.org/2000/svg'
  const mk = (svg) => { const a = []
    for (let y = 0; y < 10; y++) for (let x = 0; x < 10; x++) {
      const f = (x < 3 && y < 3) || (x > 6 && y < 3) || (x < 3 && y > 6)
      const on = f || ((x * 7 + y * 13 + x * y) % 3 === 0)
      if (!on) continue
      const r = document.createElementNS(NS, 'rect')
      r.setAttribute('x', x); r.setAttribute('y', y); r.setAttribute('width', .92); r.setAttribute('height', .92); r.setAttribute('rx', .15)
      r.setAttribute('fill', f ? '#4F46E5' : '#0F172A'); svg.appendChild(r); a.push(r) }
    return a }
  const q1 = root.querySelector('.hd-qr'), q2 = root.querySelector('.hd-qr2')
  q1.replaceChildren(); q2.replaceChildren()
  const cells = mk(q1); mk(q2)
  const $ = (s) => root.querySelector(s)
  const steps = [...root.querySelectorAll('.hd-steps span')], typed = steps[0], beam = $('.hd-beam'), ok = $('.hd-ok'), hint = $('.hd-hint'), cnt = $('.hd-count b')
  const text = 'shop.in/menu'
  const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  let timers = [], alive = true, n = 0
  const at = (fn, ms) => { const t = setTimeout(() => { if (alive) fn() }, ms); timers.push(t) }
  const mark = (i) => steps.forEach((s, j) => s.classList.toggle('on', j === i))
  function run() {
    cells.forEach(c => { c.style.opacity = 0; c.style.transition = 'opacity .25s' })
    typed.textContent = '1 Type a link'; ok.style.opacity = 0; q2.style.opacity = 0; q2.style.transform = 'scale(.5)'; beam.style.opacity = 0
    hint.textContent = 'Point camera at the code'; mark(0)
    for (let i = 1; i <= text.length; i++) at(() => { typed.textContent = '1 ' + text.slice(0, i) + '|' }, 90 * i)
    const t1 = 90 * text.length + 200
    at(() => { typed.textContent = '1 ' + text; mark(1) }, t1)
    const per = 5, nsteps = Math.ceil(cells.length / per)
    for (let k = 0; k < nsteps; k++) at(() => cells.slice(k * per, k * per + per).forEach(c => { c.style.opacity = 1 }), t1 + 40 * k)
    const t2 = t1 + 40 * nsteps + 300
    at(() => { mark(2); q2.style.opacity = 1 }, t2)
    at(() => { q2.style.transform = 'scale(1)'; hint.textContent = 'Scanning...'; beam.style.opacity = 1 }, t2 + 300)
    let y = 16, d = 1.5
    for (let f = 0; f < 90; f++) at(() => { y += d; if (y > 80) d = -2; if (y < 16) d = 2; beam.style.top = y + 'px' }, t2 + 300 + 16 * f)
    at(() => { beam.style.opacity = 0; hint.textContent = 'Got it' }, t2 + 1800)
    at(() => { ok.style.opacity = 1; cnt.textContent = ++n }, t2 + 2200)
    at(() => { timers = []; run() }, t2 + 5200)
  }
  if (reduce) { cells.forEach(c => { c.style.opacity = 1 }); typed.textContent = '1 ' + text; mark(2); q2.style.opacity = 1; q2.style.transform = 'scale(1)'; hint.textContent = 'Scan and go' }
  else run()
  return () => { alive = false; timers.forEach(clearTimeout) }
}
"""

_DEMO = st.components.v2.component("qrforge_hero_demo", html=_HTML, css=_CSS, js=_JS)


def hero_demo(key: str = "hero_demo"):
    _DEMO(key=key)
