# Quilter support findings supplied by the owner

On 17 November 2026 the owner supplied a reply from Quilter support to the previously authorized C0 reproduction packet. This is a summary of that supplied correspondence, not a claim of independent access to the owner's email. Quilter reported that engineering reproduced both issues, attributed them to its own limitations, and provided no fix schedule.

## Earlier C0 BGA fanout shorts

Quilter confirmed roughly 33 copper overlaps in candidate 4, including the GND via at (65.408, 48.971) touching C107 pad 1. It attributed the cases to a difference between via-span collision checking and export: full F.Cu–B.Cu through vias intersect top-side passives or inner-layer tracks. Candidate 1 had similar problems.

Its suggested precautions are native KiCad DRC on every return, locking the BGA MCU on the chosen face and forbidding opposite-face components over its fanout, and local KiCad correction of remaining inner-layer collisions. The opposite-face exclusion prevents putting bypass capacitors directly under that BGA. Support supplied no reliable input-side workaround for the inner-layer failures.

C1 uses LQFP144 and does not use that BGA escape layout. This does not make a cloud return automatically safe: actual via spans, pad nets, planes and all native clearances still require checking. The reviewed C1 return and accepted local repair checkpoints have no native copper shorts.

## Antenna rule-area layer transformation

Quilter confirmed that moving AE201 to B.Cu flips its pads and graphics but leaves footprint keepout layer sets unchanged. The opposite-side exclusion then blocks B.Cu and omits F.Cu. Support recommends restricting or locking the antenna to F.Cu for future cloud jobs.

The current local C1 repair preserves its returned B.Cu pose, corrects the opposite-side exclusion to F.Cu plus the four inner layers, and retains the all-layer copper/feed-corridor restrictions. Five isolated native controls test the actual corrected back-side policy. This is a checked local repair, not evidence that Quilter's export bug has been fixed.

The converter/inductor placement corrections in C1 are a separate finding. This reply does not diagnose those placements or qualify power integrity, RF performance, assembly or hardware security. No new cloud run, support message or manufacturing submission is made by recording this information.
