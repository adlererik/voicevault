#!/usr/bin/env python3
"""Render measured circuit results and a compact local review page."""
from pathlib import Path
import html
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT / '.lab-runs/hardware/latest'
report=json.loads((OUT / 'report.json').read_text())
plt.style.use('seaborn-v0_8-whitegrid')
fig, axes=plt.subplots(1,3,figsize=(15,4.5),layout='constrained')
a=np.loadtxt(OUT / 'mic-1/microphone-ac.txt')
m=np.loadtxt(OUT / 'mic-disconnected/microphone-ac.txt')
axes[0].semilogx(a[:,0],20*np.log10(a[:,1]),label='Mic connected')
axes[0].semilogx(m[:,0],20*np.log10(np.maximum(m[:,1],1e-15)),label='Mic disconnected')
axes[0].set(title='Microphone input model',xlabel='Frequency / Hz',ylabel='Transfer / dB',xlim=(20,20000))
axes[0].legend()
for load in (16,32,64,300):
 a=np.loadtxt(OUT / f'headphone-{load}-220u/headphone-ac.txt')
 axes[1].semilogx(a[:,0],20*np.log10(a[:,1]),label=f'{load} ohms')
axes[1].set(title='Headphone coupling model',xlabel='Frequency / Hz',ylabel='Transfer / dB',xlim=(20,20000),ylim=(-6,0.2))
axes[1].legend()
for resistance in (.1,.25,.5):
 a=np.loadtxt(OUT / f'supply-{resistance}-22u/supply-transient.txt')
 axes[2].plot(a[:,0]*1000,a[:,1],label=f'{resistance} ohms')
axes[2].set(title='5 V distribution model',xlabel='Time / ms',ylabel='Rail / V',ylim=(4.7,5.02))
axes[2].legend()
fig.suptitle('VoiceVault Rev A · ngspice linear circuit models · assumptions require bench correlation',fontsize=13)
fig.savefig(OUT / 'views/circuit-results.png',dpi=160)
plt.close(fig)
rows=''.join(f'<tr><td>{html.escape(c["name"])}</td><td class="{c["status"]}">{c["status"].upper()}</td><td>{html.escape(c["detail"])}</td></tr>' for c in report['checks'])
page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VoiceVault Hardware Review</title><style>
body{margin:0;background:#10171c;color:#e5eef3;font-family:system-ui,sans-serif}main{max-width:1400px;margin:auto;padding:28px}h1{font-size:36px;margin:4px 0}p{line-height:1.5;color:#b9cbd5}a{color:#8adaff}.banner{border-left:4px solid #efbe64;padding:12px 18px;background:#1c2931}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}section{background:#17232c;padding:18px;margin:20px 0;border-radius:10px}img{width:100%;background:white;border-radius:5px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;padding:12px;border-bottom:1px solid #30434f}th{color:#9eb6c3}.pass{color:#84dfb6}.blocked{color:#efbe64}.fail{color:#ff8c8c}.diagram{height:240px;display:flex;align-items:center;justify-content:space-around;gap:12px}.box{border:1px solid #4c6f81;border-radius:12px;padding:22px;text-align:center;background:#1c303c}.box small{display:block;color:#a5becd;max-width:140px;margin-top:8px}.radio{border-color:#dfaa65}.arrow{color:#79b2ca;font-size:30px}@media(max-width:850px){.grid{grid-template-columns:1fr}.diagram{height:auto;flex-wrap:wrap}}
</style><main><p>VOICEVAULT / HARDWARE LABORATORY</p><h1>Serviceable prototype review</h1><p id="timestamp"></p><div class="banner">Hardware qualification is blocked. The carrier is a placed, unrouted draft. STM32 peripheral behavior and physical security require board measurements.</div>
<div class="diagram"><div class="box">Wired headset<small>Physical mic disconnect<br>AC-coupled headphones</small></div><span class="arrow">↔</span><div class="box">Trusted endpoint<small>STM32U5G9J-DK2<br>Display and consent<br>Keys and audio</small></div><span class="arrow">↔</span><div class="box radio">Untrusted radio<small>nRF52840 module<br>Bounded ciphertext interface</small></div><span class="arrow">↔</span><div class="box radio">Compromised phone<small>BLE transport<br>Hostile network control</small></div></div>
<section><h2>Observed checks</h2><p>This table reads the most recently completed hardware check. It refreshes when a new report is saved.</p><table><thead><tr><th>Check</th><th>Result</th><th>Evidence and remaining work</th></tr></thead><tbody id="checks">ROWS</tbody></table><p><a href="report.json">Raw report</a> · <a href="spice.json">Circuit measurements</a> · <a href="erc.rpt">Electrical connectivity check</a> · <a href="drc.json">PCB routing and clearance report</a> · <a href="renode-negative-control.log">Actual emulator warnings</a> · <a href="cpu/platform.json">Actual Cortex-M33 CPU run</a></p></section>
<section><h2>Circuit results</h2><p>22 ngspice cases cover microphone bias, physical-mute assumptions, headphone coupling and distribution droop. The plots show selected cases from those runs.</p><a href="views/circuit-results.png"><img src="views/circuit-results.png" alt="Measured outputs of the three linear circuit models"></a></section>
<div class="grid"><section><h2>Carrier placement draft</h2><p>150 × 120 mm. Cabled module interfaces. 97 connections require routing.</p><a href="views/carrier.svg"><img src="views/carrier.png" alt="Actual KiCad placement draft"></a></section><section><h2>Interconnect schematic</h2><p>Zero connectivity-check violations. External module circuitry and electrical behavior require separate review.</p><a href="views/voicevault-reva.svg"><img src="views/schematic.png" alt="Actual native KiCad schematic"></a></section></div>
<section><h2>Nucleo module proposal</h2><p>The NUCLEO-U5A5ZJ-Q is a candidate removable compute module. It uses a different MCU and needs its own pin map, trusted display and exact board footprint. The current carrier draft uses the DK2 reference connections.</p></section></main>
<script>async function refresh(){try{const r=await fetch('report.json',{cache:'no-store'});if(!r.ok)return;const d=await r.json();document.getElementById('timestamp').textContent='Latest completed check '+new Date(d.created_utc).toLocaleString();const b=document.getElementById('checks');b.replaceChildren();for(const c of d.checks){const tr=document.createElement('tr');for(const [i,v] of [c.name,c.status.toUpperCase(),c.detail].entries()){const td=document.createElement('td');td.textContent=v;if(i===1)td.className=c.status;tr.append(td)}b.append(tr)}}catch(e){document.getElementById('timestamp').textContent='Report refresh unavailable'}}refresh();setInterval(refresh,3000)</script></html>'''
(OUT / 'index.html').write_text(page.replace('ROWS',rows))
print(OUT / 'index.html')
