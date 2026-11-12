# Four assembled VoiceVault prototypes delivered to Sweden

Research date: **12 November 2026**. Target: **four populated 70 × 45 mm boards**,
with the selected Safe 7 core ICs. No order, paid quote, account checkout,
supplier message or design upload was made for this comparison.

**A cheapest supplier has not been established.** None of the public headline
prices is a delivered quotation for this fine-pitch board. The economical design
direction is to minimize HDI process complexity, retain standard materials and
consolidate genuinely interchangeable parts. Routing can proceed against the
provisional rules below while the owner defers supplier quotations.

## What determines the price

The 0.4 mm WLCSPs, 0201 passives and assembly on both sides put B0 outside
JLCPCB's Economic assembly service. Its published limits are 0402 and 0.5 mm BGA
pitch for Economic; Standard supports smaller packages and two-sided assembly.
Removing a few rear components would not qualify this board for Economic.
The current footprint envelopes also exceed the available area of one side.
[Assembly capabilities](https://jlcpcb.com/capabilities/pcb-assembly-capabilities)

The provisional routing target is **six layers, first-order 1+4+1 HDI**: signal
and components outside; ground references on In1 and In4, with only localized
escape corridors if needed; signal/power distribution on In2 and In3. Avoid
stacked microvias, skip vias, mechanically buried vias and additional sequential
lamination cycles unless routing demonstrates a need. This is a cost-directed
candidate, **not an accepted factory stackup or a proof that six layers suffice**.
HDI cost depends on laser/drilling and lamination operations as well as layer
count. [HDI service](https://jlcpcb.com/pcb-fabrication/hdi-pcb)

Use green mask, standard FR-4, ordinary lead time and no decorative finishes.
Request a flat finish suitable for these packages, provisionally ENIG. Keep the
chosen core chips. Select common passive order codes only when voltage, effective
capacitance, tolerance, temperature, RF Q/SRF and other requirements really match;
equal printed values alone are insufficient. Feeder setup and part procurement
can outweigh placement labor in a four-board run.

## Supplier comparison

| Supplier | Relevant public offering | What remains unknown for these four boards |
|---|---|---|
| JLCPCB | Standard two-sided small-package assembly; HDI fabrication; itemized assembly fees | Exact HDI construction/land acceptance, complete sourced BOM, inspection scope, shipping and delivered price |
| PCBWay | Advanced fabrication with fine traces, 0.4 mm BGA design capability and HDI; turnkey assembly | Their published advanced minima differ from JLC's; our smallest lands and full BOM need review. An advertised assembly starting price excludes the PCB and components. |
| NextPCB | HDI, filled/capped vias, fine-pitch turnkey assembly; assembly stencils included | Applicable process, final component sourcing, inspection and delivered quote. Free stencil/DFM offers do not make the complete device free. |
| PCBGOGO | HDI, blind/buried vias, filled-via processes and assembly | Exact fine-pitch land acceptance and itemized delivered quote; generic prototype banners do not price this board. |

Sources: [JLCPCB HDI rules](https://jlcpcb.com/help/article/hdi-pcb-capabilities-faq),
[PCBWay advanced capabilities](https://www.pcbway.com/advanced-pcb-capabilities.html),
[PCBWay assembly calculator](https://m.pcbway.com/quoteassembly.aspx),
[NextPCB advanced capabilities](https://www.nextpcb.com/advanced-pcb-quote),
[NextPCB assembly](https://www.nextpcb.com/pcb-assembly-services),
[PCBGOGO advanced fabrication](https://www.pcbgogo.com/advanced-pcb.html).

Use JLCPCB's documented geometry as a **provisional routing baseline**, while
keeping the purchasing decision open. There is no evidence yet that JLCPCB, or
any other listed supplier, is cheapest for the complete order.

## Transparent assembly budget, not a quotation

JLCPCB's currently published USD Standard fees include $51.12 for double-sided
setup, $16.42 for double-sided stencils and $16.42 for two rigid-board fixtures
at the small-quantity tier: **$83.96 before components, boards, feeder loading,
placement, inspection, shipping or tax**. The fixture applicability and charged
panel count must be confirmed. Published prices can vary with exchange rates.

The variable part includes **$1.53 × K** for the charged feeder/part setups and
**$0.0016 × J** for SMT joints at the lowest volume tier. K is the supplier's
accepted part/setup count, not the number of component references. J is their
charged SMT joint count, not a KiCad pad count. X-ray charges depend on the
inspected component quantity and should explicitly cover the hidden-joint
packages. Other operations can add charges. This deliberately leaves unknowns
blank instead of presenting a misleading complete-device price.
[Published fee schedule](https://jlcpcb.com/help/article/pcb-assembly-price)

The 70 × 45 mm individual board is below JLCPCB Standard's published 70 × 70 mm
assembly size. Compare a carrier/rails with a two-up panel (roughly 70 × 90 mm
before rails) to obtain four assemblies from two panels. The factory must approve
panel dimensions, separation method, edge clearances, tooling and fiducials.
Panel minimum order quantities can leave extra **bare boards**; do not mistake
them for extra completed devices or silently change the requested quantity.
No panel or fabrication release is approved yet.

## Provisional fabrication geometry

JLC's HDI table publishes laser drill sizes 0.075–0.15 mm and a capture land at
least 0.15 mm larger than the drill. A 0.075/0.225 mm microvia therefore needs an
outer dielectric compatible with its drilling aspect ratio. The published
outer-dielectric range alone does not mean every combination is valid. Start
with ordinary through vias where they fit and reserve laser vias for the package
escape problem. Broad routes stay broad; do not apply minimum geometry globally.

The published nominal trace/space is 3/3 mil (0.0762 mm); the extreme 2.7/2.7 mil
option increases difficulty and cost. Their HDI table also lists hole-to-trace
and different-net hole-to-hole limits. Copper clearance alone is insufficient.
Any routing profile must check the applicable hole-edge constraints and via
layer spans too. **The Nordic and ST tiny original lands are smaller than some
published capture-land minima.** Via-in-pad expansion, solder-mask definition,
paste/reflow and filled-via acceptance remain explicit review gates; they are
not solved by ignoring DRC or silently changing a chip package.
[Detailed process rules](https://jlcpcb.com/help/article/hdi-pcb-capabilities-faq)

The current native CAD's accepted route stage and actual connection counts are
recorded in [STATUS.json](STATUS.json). This research does not declare the board
manufacturable and does not authorize production.

## Complete-device costs and Sweden delivery

PCB assembly is only one part of a complete prototype. Price the display/touch
assembly, protected battery, Qi coil and ferrite, haptic actuator, temperature
sensors, harnesses, headset and enclosure separately. Ask for explicit mounting,
programming and functional-test scope when the owner obtains quotes. A populated
PCB is not automatically an assembled, programmed, functioning device. Battery
shipping restrictions and the assembler's battery policy can require separate
local integration. Current sourcing/lifecycle gaps are listed in the
[sourcing request](JLCPCB_SOURCING_REQUEST.md).

Compare total landed cost in the same currency:

`boards + components/attrition + assembly/tooling + inspection/test + external assemblies + freight/insurance + customs/handling + import VAT`

Swedish Customs says non-EU purchases require VAT and may incur customs duty;
the normal VAT rate is generally 25%. The tax base can include freight and duty.
The current online-shopping page also announces a EUR 2 handling fee from
1 November 2026. Classification, eligibility, collection method and carrier
charges need checking at the time of the actual order; no zero-duty assumption
or fixed shipping price is made here.
[Swedish Customs online purchases](https://www.tullverket.se/en/startpage/private/online/shoppingonline.4.311bf4f016e69d6ea0d3f2.html) · [VAT and its calculation base](https://www.tullverket.se/en/startpage/business/internationalbusiness/importinggoods/aboutcustomsduties/vatonimports.4.4776b304199f1ed58cc8cc48.html)

The purchasing comparison should use **four functional assemblies delivered to
Sweden** with identical inspection and accessory scope. Optional five-unit price
breaks can be shown separately. The owner retains the ordering decision.
