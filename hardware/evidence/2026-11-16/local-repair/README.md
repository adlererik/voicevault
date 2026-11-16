# Local repair of the C0 return

The owner explicitly requested local repair on 16 November, superseding Quilter-only routing for this repair task. Work was confined to copies of retry 01 candidate 4.1. No source or live B0 board was overwritten and no purchase was made.

1. Corrected AE201's attached opposite-side exclusion from B.Cu to F.Cu to match its new B.Cu placement. Native antenna-rule and library-mismatch findings disappear.
2. Used native DRC to identify and remove **33 conflicting copper items**, retaining a geometry/reason audit in [cleanup.json](cleanup.json). Component values, pad nets and poses remain unchanged; initial KiCad serialization rounded coordinates by at most 0.5 nm. This clears the electrical shorts/clearances but increases missing connections from 30 to **63**. It does not complete those circuits.
3. Identified another format-translation problem: KiCad's DSN writer exports nonblocking `VV_REGION_*` placement guides as copper keepouts. Removed those **13 guide areas from the export copy only**. Actual copper, ground planes and all three antenna restrictions remain. Native repair CAD retains the guides.
4. Exported fixed placement to Specctra and used the **official, unmodified FreeRouting 2.5.0** with a three-minute job budget, 640 MB Java heap and a 1100 MB process-memory cap. Telemetry and network APIs were disabled. The initial configuration lacked a required local UUID; that startup failure was corrected. A first geometry export was replaced after detecting the false keepouts.
5. Imported the saved SES through KiCad's native reader on a copy, restored only DSN translation rounding (at most 50 nm), and verified that component poses/pad nets match the pre-import board. Ground-reference layers remain reserved. Native DRC was rerun after copper refill.

**Result: partial repair, routing still incomplete.** The local router closed one connection: **62 opens remain**, along with 69 dangling tracks and 49 silkscreen findings. Native KiCad finds zero shorting, clearance, hole-clearance, solder-mask, antenna-rule or library-mismatch findings. [Final DRC](routed-drc.json) · [Summary](report.json) · [Cleanup DRC](cleanup-drc.json) · [Router log](router.log).

FreeRouting also reports 153 pre-existing fixed-copper clearance findings under its DSN interpretation, despite the native clean-copper baseline. That discrepancy remains unresolved; router statistics cannot replace native verification. The saved SES is a bounded partial result. The local process was stopped after checkpoint capture to release memory; no background router is left running.

Next work is processor escape and remaining connection routing, resolving the DSN interpretation differences and, where needed, revising placement around escape vias. RF matching, clocks, converter loops, power, thermal and physical hardware gates also remain. Zero shorts does not establish a working or safe device. Preserve both cloud returns and this checked partial checkpoint.

[Open the separate native checkpoint](../../../rev-c/local-repair-01/README.md). Detailed DSN/SES files and intermediate copies are preserved in `.lab-runs/hardware/quilter/2026-11-16-local-repair-02/`.
