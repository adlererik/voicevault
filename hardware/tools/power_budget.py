#!/usr/bin/env python3
"""Evaluate explicit B0 allocations, not measured silicon current or battery life."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '.lab-runs/hardware/standalone-b0/power-budget.json'


def main():
    # Engineering allocations, not datasheet maxima or observed consumption.
    main_ma = 120 + 12 + 23 + 10 + 10  # MCU, LCD, touch, codec I/O, bridges/misc.
    aux_ma = 25 + 40 + 5  # Radio, secure elements, other loads.
    assert main_ma <= 180 and aux_ma <= 180  # Leave room on both 200mA bucks.
    media = json.loads((OUT.parent / 'spice-audio-backlight/summary.json').read_text())
    worst_led_w = max(c['v(anode)'] * c['reference_v']/c['sense_ohm'] for c in media['backlight'])
    rows = []
    modes = [('call', 200, 0, 0, 0), ('call+haptic-burst', 200, 0, 0, 150),
             ('offline-update', 0, 250, 0, 0), ('NFC-enrollment', 0, 0, 150, 0),
             ('all-features-at-allocation', 200, 250, 150, 150)]
    for voltage in [3.6, 3.7, 4.2, 4.7]:
        for mode, audio, card, nfc, haptic in modes:
            # Deliberately pessimistic assumptions: both bucks loaded in every
            # mode, 80% buck efficiency, 75% backlight efficiency, 10mA overhead.
            current = (main_ma+aux_ma)*3.3/(voltage*.8) + worst_led_w/(voltage*.75)*1000
            current += audio+card+nfc+haptic+10
            fits = current <= 1200*.8
            if mode != 'all-features-at-allocation' and not fits:
                raise RuntimeError('Planned mode exceeds 80% of candidate battery current rating')
            rows.append(dict(vsys_v=voltage, mode=mode, modeled_input_ma=current,
                             fits_960ma_design_allocation=fits))
    thermal=[]
    for name, current in [('audio',.2),('microSD',.25),('NFC',.15)]:
        power=(5.2-3.3)*current
        thermal.append(dict(load=name,current_a=current,assumed_input_v=5.2,
                            dissipation_w=power,reference_theta_ja_c_per_w=100.2,
                            estimated_junction_at_50c=50+power*100.2))
    report=dict(status='ALLOCATION STUDY; NOT HARDWARE QUALIFICATION',
        rail_allocations_ma=dict(VDD_3V3=main_ma,AUX_3V3=aux_ma,AUD_LDOIN_3V3=200,SD_3V3=250,NFC_3V3=150),
        backlight_worst_modeled_output_w=worst_led_w,
        battery_candidate='Adafruit 258 / 1200mAh protected pack; exact delivered pack must be checked',
        battery_rating_ma=1200, battery_design_allocation_ma=960,
        full_operation_minimum_vsys_v=3.6,
        modes=rows, thermal_reference_estimates=thermal,
        limitations=['MCU/codec/radio/secure-element current allocations are not measurements or proven maxima',
            'Efficiencies, load steps and wiring losses require bench correlation',
            'Reject all-features concurrency; offline updates and NFC enrollment exclude active audio',
            '500mAh candidate lacks worst-case call headroom; 100mA USB cannot independently sustain a full call',
            'The 500mA USB resettable fuse and source/CC limit remain binding; battery supplementation is required at modeled peak call load',
            'Charge current must yield to system budget; NTC/current/temperature configuration is not implemented device firmware',
            'JEDEC thermal resistance is a reference, not a measured temperature in this enclosure',
            'Below 3.6V, suspend full operation until dropout behavior and supply margins are measured; battery PCM cutoff is not the operational threshold'])
    OUT.write_text(json.dumps(report,indent=2)+'\n')
    print(f'Allocations: MCU rail {main_ma}/200mA, AUX {aux_ma}/200mA. See {OUT}.')
    print('Mode/current and thermal assumptions remain unqualified; no battery-life claim.')


if __name__=='__main__':main()
