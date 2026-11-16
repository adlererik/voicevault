"""Narrow, recorded PSpice-to-ngspice Boolean syntax adaptation.

PSpice's Boolean XOR '^' is arithmetic exponentiation in ngspice behavioral
expressions. Replace only the Boolean comparator expression inside the named
logic-gate subcircuit. Preserve supplier originals and verify truth tables.
"""
import hashlib
from pathlib import Path
import re


def boolean_xor_port(source:Path,destination:Path):
    original=source.read_text(errors='strict')
    edits=[]
    def block(match):
        text=match[0]
        pattern=r'V\(A\)\s*>\s*\{VTHRESH\}\s*\^\s*\n\+\s*V\(B\)\s*>\s*\{VTHRESH\}'
        result,count=re.subn(pattern,'((V(A) > {VTHRESH}) != (V(B) > {VTHRESH}))',text)
        if '^' in text and count!=1:raise ValueError('Unreviewed Boolean-gate syntax in '+source.name)
        if count:edits.append('Explicit Boolean inequality for PSpice XOR in '+text.splitlines()[0])
        return result
    adapted=re.sub(r'(?ims)^\.SUBCKT (?:XNOR2|XOR2)_BASIC_GEN\b.*?^\.ENDS[^\n]*',block,original)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(adapted)
    return dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        adapted_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),edits=edits,
        note='Numerically explicit Boolean syntax, not a new semiconductor model; supplier original unchanged')
