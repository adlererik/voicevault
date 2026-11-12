#!/usr/bin/env python3
"""Plot actual saved B0 measurements and native KiCad placement exports."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'.lab-runs/hardware/standalone-b0'
OUT=ROOT/'hardware/evidence/2026-11-12'
OUT.mkdir(parents=True,exist_ok=True)
data=json.loads((RUN/'spice-audio-backlight/summary.json').read_text())
plt.style.use('seaborn-v0_8-whitegrid')
fig,axes=plt.subplots(2,2,figsize=(14,8.6),layout='constrained')
for load,color in [(16,'#21799b'),(32,'#29946b'),(300,'#bb7932')]:
    curves=[np.loadtxt(RUN/f'spice-audio-backlight/headphone/{c["case"]}/headphone-ac.txt')
            for c in data['headphone'] if c['load_ohm']==load]
    y=np.stack([a[:,1] for a in curves]);x=curves[0][:,0]
    axes[0,0].fill_between(x,y.min(axis=0),y.max(axis=0),alpha=.35,color=color,label=f'{load} Ω load')
axes[0,0].set(xscale='log',xlim=(20,20000),ylim=(-15,1),title='Headphone passive response · 36 cases',xlabel='Frequency / Hz',ylabel='Transfer / dB')
axes[0,0].legend()
for mute,color,label in [(False,'#29946b','Connected'),(True,'#d07a32','Muted, assumed parasitics')]:
    curves=[np.loadtxt(RUN/f'spice-audio-backlight/microphone/{c["case"]}/microphone-ac.txt')
            for c in data['microphone'] if c['mute']==mute]
    x=curves[0][:,0];y=np.stack([a[:,1] for a in curves])
    axes[0,1].fill_between(x,y.min(axis=0),y.max(axis=0),alpha=.4,color=color,label=label)
axes[0,1].axhline(-100,color='#888',linestyle=':',label='Chosen modeled mute target')
axes[0,1].set(xscale='log',xlim=(20,20000),title='Microphone/contact model · 32 cases',xlabel='Frequency / Hz',ylabel='Transfer / dB')
axes[0,1].legend(fontsize=8)
for n in range(27):
    a=np.loadtxt(RUN/f'spice-core/{n}/core-transient.txt')
    axes[1,0].plot(a[:,0]*1000,a[:,1],color='#347997',alpha=.22,linewidth=.8)
axes[1,0].axhline(1.1,color='#555',linestyle=':',label='Ideal source: 1.1 V')
axes[1,0].set(title='Passive core load-step sensitivity · 27 cases',xlabel='Time / ms',ylabel='Modeled core node / V')
axes[1,0].legend(fontsize=8)
heights=[]
for opened in range(4):
    heights.append(max(c[f'i(vmon{i+1})']*1000 for c in data['backlight']
       if c['open_mask'].bit_count()==opened for i in range(4) if not c['open_mask']&(1<<i)))
axes[1,1].bar(range(4),heights,color=['#367b96','#468f9b','#b99246','#bd7946'])
axes[1,1].axhline(25,color='#aa493e',linestyle='--',label='Chosen 25 mA branch limit')
axes[1,1].set(title='Static backlight envelope · 704 cases',xlabel='Open LED branches',ylabel='Worst healthy-branch current / mA',xticks=range(4),ylim=(0,28))
axes[1,1].legend(fontsize=8)
fig.suptitle('VoiceVault B0 · actual ngspice 47 outputs from 799 model cases',fontsize=17)
fig.supxlabel('Ideal sources, assumed impedances and static LED/clamp envelopes. No silicon, charging, RF or physical-device qualification.',fontsize=10)
fig.savefig(OUT/'circuit-results.png',dpi=160);plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(14,6.6),layout='constrained')
parts={p['reference']:p for p in json.loads((RUN/'board-pads.json').read_text())['parts']}
labels={'front':[('U6','BLE radio',.25,1.05),('U1','Trusted MCU',.57,1.05),
                 ('J701','Display / touch',.86,1.05),('U601','Audio codec',.15,-.08),
                 ('U3','Power / charger',.48,-.08),('J401','Offline microSD',.84,-.08)],
        'back':[('U11','Secure elements',.2,1.05),('U201','Radio isolation',.75,1.05),
                ('U7','NFC',.12,-.08),('J101','Main debug',.4,-.08),
                ('U5','Qi receiver',.64,-.08),('J502','Battery',.87,-.08)]}
for ax,side,title in zip(axes,['front','back'],['Front','Rear · mirrored viewing direction']):
    pixels=plt.imread(RUN/f'views/{side}.png');ax.imshow(pixels);ax.axis('off');ax.set_title(title,fontsize=14,pad=44)
    for ref,label,tx,ty in labels[side]:
        p=parts[ref];x=(p['x_mm']-25)/70 if side=='front' else (95-p['x_mm'])/70
        y=(p['y_mm']-25)/45
        ax.annotate(label,xy=(x*pixels.shape[1],y*pixels.shape[0]),xycoords='data',
            xytext=(tx,ty),textcoords='axes fraction',ha='center',fontsize=9,
            bbox=dict(boxstyle='round,pad=.3',fc='white',ec='#9baeb8'),
            arrowprops=dict(arrowstyle='-',color='#607d8b',lw=.8),annotation_clip=False)
fig.suptitle('VoiceVault B0 · 70 × 45 mm component placement proposal',fontsize=18)
fig.supxlabel('Native KiCad exports · 296 electrical components + 14 probe pads + 4 holes · NO ROUTED COPPER · NOT FOR FABRICATION',fontsize=10)
fig.savefig(OUT/'placement.png',dpi=180);plt.close(fig)
(OUT/'plot-tools.json').write_text(json.dumps(dict(matplotlib=matplotlib.__version__,numpy=np.__version__,source='Saved ngspice case outputs and native KiCad exports'),indent=2)+'\n')
print('Saved actual circuit-model plots and native placement image:',OUT)
