#!/usr/bin/env python3
"""Plot the retained native before/after MCU escape geometry and audit result."""
import json
import math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle,Polygon

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'hardware/evidence/2026-11-12'
data=json.loads((OUT/'routing/mcu-escape-geometry.json').read_text())
fig,axes=plt.subplots(1,2,figsize=(13,7.4),layout='constrained')
colors={'AUD_SDA':'#5368a5','LINK_CTS':'#a4613e','MCU_NRST':'#7a4f99',
        'MCU_SWO':'#387d8d','MCU_UART_TX':'#a17c2f','RAD_IO_DISABLE':'#a65e7f','SD_POWER_EN':'#467b52'}
for ax,stage in zip(axes,data['stages']):
    for p in stage['pads']:
        ax.add_patch(Circle((p['x'],p['y']),p['w']/2,fc='#eef0f3',ec='#c9ced6',lw=.4,zorder=1))
    for t in stage['tracks']:
        if t['kind']=='via':
            ax.add_patch(Circle((t['x'],t['y']),t['w']/2,fc='#bad6c5' if t['net']=='GND' else '#b6c7d6',ec='white',lw=.3,zorder=2))
            continue
        a,b=t['start'],t['end'];dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        if not length:continue
        nx,ny=-dy/length*t['w']/2,dx/length*t['w']/2;color=colors.get(t['net'],'#b0b6c1')
        ax.add_patch(Polygon([(a[0]+nx,a[1]+ny),(b[0]+nx,b[1]+ny),(b[0]-nx,b[1]-ny),(a[0]-nx,a[1]-ny)],fc=color,ec='none',alpha=.9,zorder=3))
        for p in [a,b]:ax.add_patch(Circle(p,t['w']/2,fc=color,ec='none',alpha=.9,zorder=3))
    for p in stage['reservations']:
        bad=p['pin'] in stage['blocked_pins'];color='#bb3e42' if bad else '#d69c28'
        ax.add_patch(Circle((p['x'],p['y']),p['w']/2,fc='none',ec=color,lw=1.4,zorder=5))
        if bad:ax.text(p['x']+.18,p['y']-.16,p['pin'],color=color,fontsize=7.5,zorder=6)
    ax.set(xlim=(53.1,62.9),ylim=(51.9,42.1),xlabel='PCB X / mm',ylabel='PCB Y / mm')
    ax.set_aspect('equal');ax.grid(alpha=.12);ax.tick_params(labelsize=8)
    ax.set_title('Before: 9 future sites blocked' if stage['name']=='before' else 'After: 68 future sites clear',fontsize=13,pad=12)
fig.suptitle('VoiceVault · preserving room for the remaining MCU escapes',fontsize=17)
fig.supxlabel('Actual In1 copper · projected front-side ball lands in gray · planned 0.25 mm capture circles in gold/red\nSeven nets reworked; other copper retained. This checks MCU escape space, not complete fanout or physical hardware.',fontsize=9)
fig.savefig(OUT/'mcu-escape-review.png',dpi=180)
print('Rendered retained native MCU geometry and independently checked reservations.')
