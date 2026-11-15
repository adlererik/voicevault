# VoiceVault Rev C — approved simplification

Decision record: 2026-11-15. The owner accepted the BL-5C-style lithium-ion battery and NXP SE050E2 recommendations, superseding the earlier AAA/NiMH and TROPIC01 proposals. **Requirements and migration planning only. No Rev C schematic, PCB, charging simulation or manufacturing release exists yet.** Existing Rev B CAD and cloud-routing evidence are preserved. [Structured decisions](decisions.json) · [Radio pin migration](ble-pin-migration.csv)

## Accepted direction

Keep the STM32U5G9ZJJ6Q, dedicated wired audio, trusted color display and local controls, offline microSD updates, isolated ciphertext-only radio interface, and separate development debug connectors. Use a replaceable protected BL-5C-style single-cell lithium-ion pack, chargeable while installed through a wired power input. Remove Qi and NFC. Use one NXP SE050E2 and the larger QFN BLE package. Other optional functions, including haptics, have not been removed by this decision.

The accepted chemistry is **single-cell lithium-ion**. Exact pack, capacity, discharge/charge limits, contact polarity and mechanical retention remain selections to verify. The intermediate two-AAA NiMH proposal and BQ25172 charger are superseded. Runtime and simultaneous charge/call power margins need measurement.

## Complete circuit and integration change list

| Area | Change from the preserved B0 design |
|---|---|
| Battery | Replace the pouch-pack candidate and harness with reviewed BL-5C-style contacts, retention and a replaceable protected pack. Rework the battery compartment and temperature sensing. |
| Charger and power rails | Replace nPM1300-CAAA and its exclusive support circuitry with the BQ24074 charger candidate, suitable regulators and supply controls. Preserve safe sequencing, undervoltage shutdown, radio power control, isolated card power and clean audio power. Final regulator parts remain open. |
| Qi | Remove STWLC38, receive coil/connector, matching/control components, coil-temperature interface and Qi power-input branch. |
| NFC | Remove ST25R3916B, antenna/matching circuit, clock, dedicated supply and interface bridges. |
| Secure elements | Remove TROPIC01 and OPTIGA Trust M plus their exclusive support parts; fit one SE050E2HQ1/Z01Z3Z. |
| Secure-element interface | Replace the old secure-element interfaces with MCU-controlled I2C and an authenticated/encrypted host channel. Provision device-specific keys and access policies; keep the radio disconnected from this bus. |
| Identity, storage and entropy | Port internal Ed25519 key generation/signing, protected storage roots and persistent generation/rollback state to NXP. Combine STM32 and NXP random output under the two-source policy. Check real API semantics, byte order, endurance and power-loss atomicity. |
| BLE | Fit nRF52832-QFAA-G-R7 QFN48 instead of CIAA WLCSP; revise pin map, footprint, decoupling and package-specific RF circuitry/layout. |
| Pairing | Compare the full transcript fingerprint in person on both trusted displays and confirm on each; remove the NFC enrollment path. Calls still require local consent. |
| PCB and enclosure | Create separate Rev C circuits and CAD, review all removed/shared-net dependencies, then revisit placement, antenna reservation, battery access, connectors and test points. Six layers remain provisional; a reduction has not been established feasible. |
| Software and checks | Add board-specific charger, power, secure-element and radio integration; update the BOM, MCU configuration, simulator hardware profile, circuit studies and checks. Preserve all existing protocol/security gates. |

The inventory has **45 Qi and 44 NFC components** on their dedicated sheets: **89 existing components** are removal candidates before power/secure-element changes and replacement circuitry. This is an inventory calculation, not a completed deletion or a final component count. Copper, unused controls, connectors and shared-net dependencies need review before generating the new design.

Audio codec/headset jack/physical mic disconnect, trusted display and local controls, MCU and radio debug access, haptics, microSD, the hybrid X25519 + ML-KEM-768 suite, Ed25519 identities, ChaCha20-Poly1305, fixed-cadence records, replay controls and offline authenticated update requirements remain. Production debug lockdown, radio isolation and secret-erasure requirements/limitations remain too.

## Charging candidate

Evaluate **TI BQ24074**, a single-cell 4.2 V lithium-ion charger with system power-path management and temperature monitoring. Select charge current from the actual pack limits, input-power capability and thermal calculations; operation during charging depends on the available power budget. Its system output does not replace the required MCU/radio/audio voltage regulators. [TI product and datasheet](https://www.ti.com/product/BQ24074)

Use protected 5 V power-only USB-C, with no USB data connection to the MCU or phone. Replacing the fine-pitch nPM1300 is a simplification choice, not a claim that it cannot charge lithium-ion cells. The selected BL-5C-style pack needs charging and mechanical acceptance. Its BSI contact is battery identification, not an assumed NTC sensor; provide real temperature sensing as required. Review reverse insertion, pack removal during writes, missing-pack operation, open/shorted sensors and brownouts. [Example replacement pack](https://www.batteriexperten.com/sv/artiklar/bl-5c-ersattningsbatteri.html) · [Nokia battery interface documentation](https://electronicsandbooks.com/edt/manual/Hardware/N/Nokia/Phone/NOKIA%201110%20RH-70/NOKIA%201110%20RH-70.pdf)

## Entropy and the single secure element

Safe 7 wallet creation combines STM32, OPTIGA, TROPIC01 and host OS randomness. That describes wallet generation, not every use of randomness in its firmware. [Trezor entropy documentation](https://trezor.io/guides/trezor-devices/trezor-fundamentals/what-is-entropy-and-how-does-trezor-generate-your-wallet)

The accepted part is **NXP SE050E2HQ1/Z01Z3Z**, pending integration qualification. Its E configuration supports Ed25519, random generation and no enabled contactless interface; other SE050 variants are not interchangeable. Configure internal identity-key generation/signing without private-key export. Separately, condition contributions from **both STM32 and NXP** for session entropy, refuse new key generation when either source fails, and never trust the phone or BLE processor as a replacement. Internal identity-key generation uses the secure element's own randomness, not the MCU's two-source pool. [NXP configurations](https://www.nxp.com/docs/en/application-note/AN12436.pdf) · [Command specification](https://www.nxp.com/docs/en/application-note/AN12413.pdf)

The existing model has three source slots and requires at least two passing sources. A future driver can report the absent second secure-element slot unavailable, requiring both remaining sources without weakening the threshold. Physical source quality and independence are unmeasured. Real NXP storage, access policy, generation counters, endurance, counter deletion/reset restrictions and atomicity must satisfy contact-storage and firmware-rollback requirements. Pin the delivered applet/OS revision and errata and provision the protected channel before acceptance. The chip's internal RNG/channel uses NIST-standard components; the approved VoiceVault call suite stays unchanged. No production chip drivers are implemented here, and comparable four-unit cost savings over TROPIC01 are not yet established.

## Verification and radio

In-person enrollment compares the complete transcript fingerprint on **both trusted device displays**, requires explicit approval on each, and exchanges authenticated confirmations before pinning contacts. No NFC or physical electrical connection is required for that comparison. Public enrollment bytes may traverse hostile transport; the authenticated exchange and human comparison establish trust. The software implements a full 256-bit fingerprint, not an improvised six-digit SAS. Every call still requires verified contacts and local consent.

Select **nRF52832-QFAA-G-R7**, QFN48, **6 × 6 mm**, replacing B0's CIAA WLCSP. Nordic lists the older non-G QFAA order codes as not recommended for new designs. This changes packaging, not the trusted endpoint boundary: the radio remains hostile and carries bounded ciphertext only. [Nordic ordering information](https://docs.nordicsemi.com/r/bundle/ps_nrf52832/page/ordering_info.html)

The migration table preserves GPIO signal assignments and explicitly adds the QFN supply/ground pads. It is not an approved land pattern. Check the complete schematic, exposed-pad soldering, decoupling, reset/debug lifecycle and package-specific RF components/layout against [Nordic's pin assignments](https://docs.nordicsemi.com/r/bundle/ps_nrf52832/page/pin.html) and [QFN reference circuit](https://docs.nordicsemi.com/r/bundle/ps_nrf52832/page/ref_circuitry.html). The pitch remains 0.4 mm, but the contacts are on the perimeter. Do not copy the WLCSP RF matching circuit or assume the larger package guarantees a routed board.

## Verification of the existing model

On 2026-11-15, before the updated battery/secure-element selection, `cargo test --locked -p protocol --test lifecycle` passed **18 tests**, including mutual local enrollment approval, different MITM fingerprints, malformed/replayed confirmations, two-source entropy failure handling, hostile-radio bounds, sealed contacts and offline-update fault handling. This was a focused existing-model run, not a new full verdict or validation of NXP hardware or charging. The migration CSV covers all 48 numbered QFN terminals plus exposed ground, preserving every connected B0 radio net. The preserved B0 PCB hash is recorded in `decisions.json`.

## Next implementation gates

1. Accept the exact lithium-ion pack and charging/load policy, then calculate current, energy, voltage margins and charger heat. Review NXP operations, provisioning and errata.
2. Replace power circuitry, remove Qi/NFC and both old secure elements with a net-by-net dependency review, and implement NXP and QFN radio circuits in separate Rev C CAD.
3. Recheck schematic pin maps, radio containment, contact/update persistence, entropy failures, charging faults and power-loss behavior. SPICE results need appropriate models and clearly stated limits.
4. Submit a clean, checked Rev C input to Quilter for placement/routing only when ready; review returned copper with native KiCad checks. No competing local autorouter pass.
5. Complete power, audio, radio, entropy and trusted-UI bench qualification before relying on a physical device. Four assembled prototypes to Sweden remain the eventual procurement target; no purchase or fabrication is authorized.
