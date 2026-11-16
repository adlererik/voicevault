"""Fail closed on aborted, incomplete or non-finite ngspice results."""
import math
import re


def measurements_from_log(log, names, exit_code=0):
    if exit_code or re.search(r'(?im)timestep too small|simulation\(s\) aborted|fatal error|^\s*error\b', log):
        raise RuntimeError('Simulator failed or aborted; exit code zero alone is not success')
    values = {}
    for name in names:
        match = re.search(r'(?m)^'+re.escape(name)+r'\s*=\s*([\d.eE+-]+)', log)
        if not match or not math.isfinite(float(match[1])):
            raise RuntimeError('Missing/non-finite simulator measurement: '+name)
        values[name] = float(match[1])
    return values
