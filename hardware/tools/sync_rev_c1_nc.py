#!/usr/bin/env python3
"""Serialize only explicit single-pad NC net names from the native schematic.

This closes native schematic-parity warnings without joining any electrical
pins. It refuses to touch a placed or routed C1 board.
"""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from finalize_rev_c_quilter_input import parse, child, children
from prepare_rev_c_retry import spans, fp_ref

ROOT=Path(__file__).resolve().parents[2]
PATH=ROOT/'hardware/rev-c1/voicevault-standalone-c1.kicad_pcb'


def main():
    xml=ET.parse(ROOT/'.lab-runs/hardware/standalone-c1/netlist.xml').getroot()
    nc={}
    for net in xml.findall('./nets/net'):
        if not net.get('name').startswith('unconnected-'):continue
        nodes=net.findall('node')
        assert len(nodes)==1 and 'no_connect' in nodes[0].get('pintype','')
        nc[(nodes[0].get('ref'),nodes[0].get('pin'))]=net.get('name')
    text=PATH.read_text();board=parse(text)
    assert not any(children(board,k) for k in ['segment','via','arc'])
    assert all(float(child(f,'at')[1])>100 for f in children(board,'footprint') if not fp_ref(f).startswith('H'))
    updates=[];count=0
    for a,b in spans(text,'footprint'):
        fragment=text[a:b];ref=fp_ref(parse(fragment));edits=[]
        for x,y in spans(fragment,'pad'):
            pad=parse(fragment[x:y]);key=(ref,pad[1])
            if key not in nc:continue
            old=child(pad,'net')
            if old:
                assert old[1]==nc[key]
                continue
            edits.append((x,y,fragment[x:y].rstrip()[:-1]+' (net '+json.dumps(nc[key])+'))'))
            count+=1
        for x,y,value in sorted(edits,reverse=True):fragment=fragment[:x]+value+fragment[y:]
        if edits:updates.append((a,b,fragment))
    for a,b,value in sorted(updates,reverse=True):text=text[:a]+value+text[b:]
    PATH.write_text(text)
    print(f'Serialized {count} explicit single-pad no-connect names; no electrical joins or placement/routing changes.')


if __name__=='__main__':main()
