#!/usr/bin/env python3
"""Rev C scoped circuit experiments and separately labeled datasheet calculations.

No MCU/secure-element/charger emulation. Supplier-model parser/solver errors and
missing measurements cannot count as successful device simulations.
"""
from datetime import datetime,timezone
import hashlib
import itertools
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from spice_executable import ngspice
from spice_model_port import boolean_xor_port
from spice_results import measurements_from_log

ROOT=Path(__file__).resolve().parents[2]
DESIGN=ROOT/'hardware/rev-c'
OUT=ROOT/'.lab-runs/hardware/standalone-c0'
CACHE=ROOT/'.lab-cache/hardware-research/2026-11-15/revc'


def simulate(directory,source,measurements,timeout=20,pspice=False):
    directory.mkdir(parents=True,exist_ok=True)
    (directory/'input.cir').write_text(source)
    (directory/'.spiceinit').write_text(('set ngbehavior=ps\n' if pspice else 'unset ngbehavior\n')+'set num_threads=1\n')
    with (directory/'ngspice.log').open('w') as log:
        try:r=subprocess.run([ngspice(),'-b','input.cir'],cwd=directory,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
        except subprocess.TimeoutExpired:raise RuntimeError('Simulator timeout: '+str(directory))
    text=(directory/'ngspice.log').read_text()
    return measurements_from_log(text,measurements,r.returncode)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={'checked_utc':datetime.now(timezone.utc).isoformat(),'scope':'Scoped models, not complete-device qualification',
            'simulator':subprocess.check_output([ngspice(),'--version'],text=True).strip(),
            'circuits_sha256':hashlib.sha256((DESIGN/'circuits.json').read_bytes()).hexdigest(),
            'groups':[],'full_device':'BLOCKED'}
    if 'ngspice-47' not in report['simulator']:raise RuntimeError('Review changed simulator version')
    tree=ET.parse(OUT/'netlist.xml').getroot()
    native={x.get('ref'):x.findtext('value') for x in tree.findall('./components/comp')}
    required={'R1101':'4.7k','R1102':'4.7k','R504':'4.42k','R505':'68.1k','R1201':'312k',
              'R1202':'100k','R1203':'180k','R1204':'100k','R1209':'100k','R1205':'232k',
              'R1211':'3.3k','C208':'4.7u','C205':'100n','C214':'100n','C216':'100n'}
    for ref,value in required.items():
        if not native.get(ref,'').startswith(value):raise RuntimeError('Native value differs from model: '+ref)
    rc=[]
    try:
        for i,(vdd,r,c) in enumerate(itertools.product([3.25,3.35],[4653,4747],[20e-12,50e-12,100e-12,200e-12])):
            source=f'''Rev C secure-bus RC sensitivity; ideal worst-resistance sink, not NXP silicon
Vdd supply 0 {vdd}
Rpull supply sda {r}
Cbus sda 0 {c}
Vcontrol control 0 PWL(0 1 10u 1 10.001u 0)
Ssink sda 0 control 0 open_drain
.model open_drain SW(Ron=1000 Roff=1e12 Vt=0.5 Vh=0)
.save v(sda)
.control
tran 2n 30u
meas tran low_v FIND v(sda) AT=9u
meas tran rise_s TRIG v(sda) VAL={.3*vdd} RISE=1 TARG v(sda) VAL={.7*vdd} RISE=1
set wr_vecnames
wrdata waveform.txt v(sda)
quit
.endc
.end
'''
            values=simulate(OUT/'spice-secure-bus'/str(i),source,['low_v','rise_s'])
            if values['rise_s']>1e-6 or values['low_v']>.3*vdd:raise RuntimeError('100kHz bus model exceeds rise/low thresholds')
            rc.append(dict(vdd_v=vdd,pullup_ohm=r,assumed_bus_cap_f=c,**values))
        report['groups'].append(dict(name='Secure-bus RC sensitivity',status='PASS',cases=rc,
            limitation='1kOhm sink is a datasheet-based conservative assumption, not a transistor model; actual routed bus capacitance unmeasured'))
    except Exception as e:report['groups'].append(dict(name='Secure-bus RC sensitivity',status='FAIL',error=str(e)))

    # These are explicit arithmetic corners, NOT additional SPICE device tests.
    feedback=[v*(1+r1/r2) for v,r1,r2 in itertools.product([.792,.808],[311688,312312],[99900,100100])]
    uvlo={}
    for label,thresholds in [('rise',[.77,.83]),('fall',[.67,.73])]:
        values=[v*(1+r1*(1/r2+1/r3))+leak*r1 for v,r1,r2,r3,leak in itertools.product(
            thresholds,[179820,180180],[99900,100100],[99900,100100],[-1e-7,1e-7])]
        uvlo[label]=[min(values),max(values)]
    charge=[k/r for k,r in itertools.product([797,975],[4420*.99,4420*1.01])]
    timer=[10*r*k/3600 for r,k in itertools.product([68.1*.99,68.1*1.01],[36,60])]
    radio_min=25230/(232*1.01)**1.016
    radio_max=22980/(232*.99)**.94
    calculations=dict(name='Native-value / datasheet arithmetic',status='PASS',not_spice=True,
        main_feedback_v=[min(feedback),max(feedback)],uvlo_v=uvlo,
        charge_current_a=[min(charge),max(charge)],charge_timer_h=[min(timer),max(timer)],
        radio_limit_ma=[radio_min,radio_max],
        audio_headroom_v=min(feedback)-2.8*1.02,audio_ldo_max_dropout_v=.14,
        limitations=['Charger current/timer and NTC network still require exact battery acceptance',
            'Feedback DC accuracy excludes switching ripple and transient behavior',
            'No charger silicon, thermal loop, cell chemistry or NXP RNG simulation'])
    if min(feedback)<3.2 or max(feedback)>3.4 or uvlo['fall'][0]<3.0 or uvlo['rise'][1]>4.2:
        calculations.update(status='FAIL',error='Supply/UVLO allocation thresholds exceeded')
    if calculations['audio_headroom_v']<.14 or max(charge)>.25 or radio_max>160:
        calculations.update(status='FAIL',error='Audio/charge/radio design allocation exceeded')
    report['groups'].append(calculations)

    try:
        reference=next(x for x in json.loads((DESIGN/'references.json').read_text())['sources']
                       if x['cache_file']=='tps2553-model.zip')
        model=CACHE/reference['model_cache_directory']/reference['model_member']
        if hashlib.sha256(model.read_bytes()).hexdigest()!=reference['model_sha256']:
            raise RuntimeError('Supplier radio model changed: review its revision before running')
        supplier=model
        model=OUT/'model-ports/tps2553-ngspice.lib'
        port=boolean_xor_port(supplier,model)
        lines=[f'.include "{model.resolve()}"','Vzero zero 0 0','Vone one 0 1']
        expectations={}
        for a,b in itertools.product([0,1],repeat=2):
            for gate,expected in [('XNOR2',int(a==b)),('AND2',a&b),('OR2',a|b)]:
                node=gate.lower()+str(a)+str(b)
                lines.append(f'X{node} '+('one' if a else 'zero')+' '+('one' if b else 'zero')+f' {node} {gate}_BASIC_GEN')
                expectations['v('+node+')']=expected
        truth='PSpice Boolean-port truth table\n'+'\n'.join(lines)+'\n.control\nop\nprint '+' '.join(expectations)+'\nquit\n.endc\n.end\n'
        observed=simulate(OUT/'spice-model-logic',truth,list(expectations),pspice=True)
        if any(abs(observed[k]-v)>1e-6 for k,v in expectations.items()):
            raise AssertionError('Supplier logic syntax port failed its independent truth table')
        report['groups'].append(dict(name='PSpice Boolean-port truth table',status='PASS',outputs=len(expectations),port=port))
        source=f'''Rev C current-limited radio switch; supplier PSpice model portability experiment
.include "{model.resolve()}"
Vsource supply 0 3.296
Vmonitor supply vin 0
Venable enable 0 PWL(0 0 100u 0 101u 3.296 30m 3.296 30.001m 0)
Xswitch vin 0 enable 0 fault ilim radio TPS2553_TRANS
Rilim ilim 0 232k
Rfault supply fault 47k
Cin vin 0 100n
Cout radio 0 6.9u
Rbleed radio 0 3.3k
* 6.9u is above the 5.1u nominal external capacitance on RADIO_3V3.
* Disconnect the nominal load on disable: passive discharge must work unloaded.
Sload radio normal_load enable 0 load_switch
Rnormal normal_load 0 100
.model load_switch SW(Ron=0.01 Roff=1e12 Vt=1 Vh=0)
Vshort control 0 PWL(0 0 6m 0 6.001m 1 21m 1 21.001m 0)
Sshort radio rs control 0 short_switch
Rshort rs 0 5
.model short_switch SW(Ron=0.01 Roff=1e12 Vt=0.5 Vh=0)
.save v(radio) v(fault) i(Vmonitor)
.options reltol=0.003 method=gear
.control
tran 2u 140m
meas tran default_off_v MAX v(radio) FROM=0 TO=80u
* The datasheet allows up to 3ms turn-on at its specified load; do not sample
* startup at 1ms and mistake the intentional soft-start for a failed switch.
meas tran normal_v MIN v(radio) FROM=4m TO=5m
meas tran limited_a MAX i(Vmonitor) FROM=7m TO=19m
meas tran transient_peak_a MAX i(Vmonitor) FROM=6m TO=7m
meas tran fault_v FIND v(fault) AT=20m
meas tran recovered_v FIND v(radio) AT=27m
* TPS2553 has no quick-output-discharge. 3.3k x 6.9u = 22.77ms;
* allow 100ms after disable, independent of any helpful radio load.
meas tran disabled_v FIND v(radio) AT=130m
set wr_vecnames
wrdata waveform.txt v(radio) v(fault) i(Vmonitor)
quit
.endc
.end
'''
        values=simulate(OUT/'spice-radio-switch',source,['default_off_v','normal_v','limited_a','transient_peak_a',
            'fault_v','recovered_v','disabled_v'],timeout=60,pspice=True)
        if not (values['default_off_v']<.1 and values['normal_v']>3.1 and .08<values['limited_a']<.16
                and values['fault_v']<.4 and values['recovered_v']>3.1 and values['disabled_v']<.1):
            raise AssertionError('Supplier switch-model behavior missed the declared thresholds: '+str(values))
        report['groups'].append(dict(name='Supplier radio-switch model',status='PASS',measurements=values,
            model_port=port,
            schedule=dict(on_ms=.101,steady_window_ms=[4,5],short_ms=[6,21],disable_ms=30.001,
                          unloaded_discharge_check_ms=130,output_cap_f=6.9e-6,bleed_ohm=3300),
            limitation='Supplier PSpice model under ngspice compatibility; steady current limit is not the transient peak. Temperature, main regulator coupling and malicious electrical/RF faults not qualified'))
    except AssertionError as e:report['groups'].append(dict(name='Supplier radio-switch model',status='FAIL',error=str(e)))
    except Exception as e:report['groups'].append(dict(name='Supplier radio-switch model',status='BLOCKED',error=str(e)))

    for script_name in ['spice_audio_backlight.py']:
        with (OUT/(script_name+'.log')).open('w') as log:
            result=subprocess.run([sys.executable,ROOT/'hardware/tools'/script_name,
                '--design-dir',DESIGN,'--out',OUT/'spice-audio-backlight','--project-name','voicevault-standalone-c0'],
                cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        report['groups'].append(dict(name='Retained passive audio/backlight sensitivity',
            status='PASS' if result.returncode==0 else 'FAIL',cases=772 if result.returncode==0 else 0,
            limitation='Ideal sources/static networks; not codec or converter silicon/acoustic qualification'))

    diagnostic=CACHE/'converter-compatibility'
    converter=dict(name='Supplier main-converter model',status='BLOCKED',
        reason='3ms run exceeded the bounded CPU budget; shorter PSpice port hit timestep-too-small near the load step. No complete converter result claimed.')
    if (diagnostic/'ngspice-short.log').exists():
        converter['raw_log_sha256']=hashlib.sha256((diagnostic/'ngspice-short.log').read_bytes()).hexdigest()
        converter['exit_zero_is_not_pass']=True
    report['groups'].append(converter)
    report['available_model_checks']='FAIL' if any(x['status']=='FAIL' for x in report['groups']) else 'PASS'
    report['silicon_and_system_simulation']='BLOCKED'
    (OUT/'spice-summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['simulator','groups']},indent=2))
    for x in report['groups']:print(x['name'],x['status'],x.get('error',''))
    return 1 if report['available_model_checks']=='FAIL' else 0


if __name__=='__main__':sys.exit(main())
