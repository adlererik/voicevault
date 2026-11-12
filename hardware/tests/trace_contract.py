#!/usr/bin/env python3
"""Validate observations, and prevent unqualified peripheral models passing gates."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = json.loads((ROOT / 'hardware/reference/target.json').read_text())


def observation_errors(trace):
    errors = []
    if not isinstance(trace, dict):
        return ["Trace must be a JSON object"]
    if trace.get('target') != TARGET['mcu']:
        errors.append('Wrong MCU target')
    if trace.get('revision') != TARGET['silicon_revision']:
        errors.append('Wrong silicon revision')
    if trace.get('rev_id') != TARGET['expected_rev_id']:
        errors.append('DBGMCU revision observation missing or mismatched')
    if trace.get('timed_out') is not False:
        errors.append('Execution timed out or timeout state missing')
    if trace.get('unexpected_register_accesses') != []:
        errors.append('Unexpected register access or access log missing')
    if trace.get('emulator_warnings') != []:
        errors.append('Emulator warning or warning log missing')
    digest = trace.get('image_sha256')
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        errors.append('Test image digest missing')
    expected = [((index * 257) % 65536) - 32768 for index in range(320)]
    audio = trace.get('audio', {})
    if not isinstance(audio, dict):
        audio = {}
    if audio.get('tx_samples') != expected or audio.get('rx_samples') != expected:
        errors.append('Expected 320 audio samples were not observed in both DMA buffers')
    if audio.get('dma_irqs') != [29, 30, 29, 30]:
        errors.append('Expected DMA completion interrupt sequence missing')
    if audio.get('guard_words_intact') is not True:
        errors.append('DMA buffer boundary guards changed or missing')
    if audio.get('underrun_recovered') is not True:
        errors.append('Audio underrun recovery missing')
    isolation = trace.get('isolation', {})
    if not isinstance(isolation, dict):
        isolation = {}
    for key in ('cpu_denied', 'dma_denied', 'trusted_memory_unchanged', 'allowed_transfer_completed'):
        if isolation.get(key) is not True:
            errors.append('Missing isolation observation ' + key)
    if isolation.get('fault_irq') != 8:
        errors.append('GTZC denial interrupt missing')
    return errors


def qualify(trace):
    errors = observation_errors(trace)
    profile = trace.get('qualified_profile') if isinstance(trace, dict) else None
    if profile not in TARGET['qualified_peripheral_models']:
        errors.append('Peripheral model has no STM32U5G9 revision-Z bench qualification')
    return {'status': 'fail' if errors else 'pass', 'errors': errors}


if __name__ == '__main__':
    import sys
    try:
        trace = json.loads(Path(sys.argv[1]).read_text())
        report = qualify(trace)
    except (IndexError, OSError, ValueError, TypeError) as error:
        report = {'status': 'fail', 'errors': [str(error)]}
    print(json.dumps(report, indent=2))
    sys.exit(0 if report['status'] == 'pass' else 1)
