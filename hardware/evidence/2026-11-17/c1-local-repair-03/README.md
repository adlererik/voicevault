# C1 repair 03 evidence

**17 open connections, zero native rule violations, zero schematic-parity mismatches. Not for fabrication.**

The [checkpoint](../../../rev-c1/local-repair-03/README.md) was refilled and checked with KiCad 10.0.8 using the unchanged project rules. [Native DRC](native-drc.json), [summary](report.json), [component/pin identity and negative controls](identity.json) and [artifact hashes](artifact-hashes.json) bind the findings to the published PCB.

The local routing helper now considers alternative attachment sites from KiCad’s actual connected-copper components and exports actual outside-approximated pad polygons. Endpoint-anchored grids avoid rounding legal narrow exits off the search grid. Wider, weighted searches and more escape-via candidates are proposal mechanisms only: every retained routing change still requires native DRC. Components and rules are not edited by that helper. Signal routing on ground-reference layers remains forbidden.

Critical-net repair may deliberately remove a bounded set of ordinary foreign copper and temporarily increase opens, recording each removed UUID, geometry and source hash. RF, clocks and repaired switching connections are protected; SE_SCL is protected after its repair. This exception is not the ordinary completion criterion. Ordinary completion retains a candidate only when the native open count falls and no new hard finding appears. Current/thermal suitability is a separate release gate; a connection may match an existing narrow rail exit rather than widening it into adjacent copper.

[Main-converter repair](critical-loop-repair.json), [ground restoration](after-critical-loop.json), [secure-element clock repair](se-clock-repair.json), [supply completion](supply-completion.json) and [native-reported dangling cleanup](dangling-cleanup.json) record the progression. The supplied Quilter support findings and earlier checkpoints remain preserved. A longer FreeRouting pass was rejected because its imported native count did not improve.

The final copied checkpoint was independently checked for all 216 component values/pad nets, mounting anchors, 144 MCU pins, 55 functions, 72 critical connections and seven corrupt mappings. These checks establish circuit identity, not physical operation. All hardware qualification and manufacturing gates remain open.

A subsequent [radio-link escape attempt](rejected-link-escape.json) was rejected: the fallback proposed removing 21 copper items, exceeding the six-item limit. The board hash and 17-open checkpoint remain unchanged. No routing process is left running by this attempt.
