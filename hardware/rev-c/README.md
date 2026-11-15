# VoiceVault Rev C — simpler hardware direction

Decision record: 2026-11-15. **Requirements and migration planning only. No Rev C schematic, PCB, charging simulation or manufacturing release exists yet.** The existing Rev B board and cloud-routing evidence are preserved. [Structured decisions](decisions.json) · [Radio pin migration](ble-pin-migration.csv)

## Accepted direction

Keep the STM32U5G9ZJJ6Q, dedicated wired audio, trusted color display and local controls, offline microSD updates, isolated ciphertext-only radio interface, and separate development debug connectors. Use external AAA rechargeable cells, connected to the device and chargeable while installed, through a wired power input. Remove Qi and NFC. Use one secure element and the larger BLE package. Other optional functions, including haptics, have not been removed by this decision.

The cell chemistry is **assumed to be NiMH**, not alkaline or regulated 1.5 V lithium AAA. Cell count, exact cells, capacity, charger current, regulator choices and charging-with-a-call behavior remain engineering selections. Two series NiMH cells with a regulated supply are the starting candidate; runtime and peak-load measurements must decide whether that is sufficient.

## Charging candidate

Evaluate **TI BQ25172DSGR**, a NiMH charger supporting 1–6 series cells, programmable current and timer, and battery-temperature monitoring. It terminates by timer or overvoltage, **not negative-delta-V detection**. Its single output shares current between battery and load; it does not provide a separate system power path. The selected battery manufacturer's charging limits, temperature sensing, charge termination, load sharing and thermal dissipation must therefore be resolved before a circuit is accepted. [TI product and datasheet](https://www.ti.com/product/BQ25172)

Replace the old nPM1300 lithium charging/power circuit rather than attaching NiMH cells to it. Prefer a protected 5 V power-only charging connector, with no USB data connection to the MCU or phone. Preserve undervoltage shutdown, radio power control, reset safety and a dedicated clean audio supply. Charging-cell substitution, polarity faults and missing/open/shorted temperature sensors need hardware-level protection and tests. A keyed, matched NiMH pack with a temperature sensor is the initial mechanical candidate; ordinary loose-cell holders do not prevent someone inserting alkaline cells.

## Entropy and the single secure element

Safe 7 wallet creation combines STM32, OPTIGA, TROPIC01 and host OS randomness. That describes wallet generation, not every use of randomness in its firmware. [Trezor entropy documentation](https://trezor.io/guides/trezor-devices/trezor-fundamentals/what-is-entropy-and-how-does-trezor-generate-your-wallet)

TROPIC01 exposes random-byte retrieval and internal Ed25519 key generation/signing. It is the selected **candidate** single secure element. A public identifier can be shared; the private signing key needs protection. Internal identity-key generation uses the chip's own randomness. Separately, the MCU's session-entropy pool should cryptographically condition contributions from **both STM32 and TROPIC01**, refuse new key generation when either source fails, and never trust the phone or BLE processor as a replacement. [Manufacturer API](https://github.com/tropicsquare/libtropic/blob/master/include/libtropic.h) · [Chip capabilities](https://www.tropicsquare.com/tropic01)

The existing software model has three source slots and requires at least two passing sources. A future two-chip driver can report the absent OPTIGA slot unavailable, requiring both remaining sources without weakening that threshold. Basic stuck/repeated-block checks are already modeled; physical source quality and independence are unmeasured. TROPIC01 storage, access policy, generation counters, endurance and atomicity must also satisfy contact-storage and firmware-rollback requirements. Removing OPTIGA does not remove those requirements. No production chip drivers are implemented by this brief.

## Verification and radio

In-person enrollment compares the complete transcript fingerprint on **both trusted device displays**, requires explicit approval on each, and exchanges authenticated confirmations before pinning contacts. No NFC or physical electrical connection is required for that comparison. Public enrollment bytes may traverse hostile transport; the authenticated exchange and human comparison establish trust. The software implements a full 256-bit fingerprint, not an improvised six-digit SAS. Every call still requires verified contacts and local consent.

Select **nRF52832-QFAA-G-R7**, QFN48, **6 × 6 mm**, replacing B0's CIAA WLCSP. Nordic lists the older non-G QFAA order codes as not recommended for new designs. This changes packaging, not the trusted endpoint boundary: the radio remains hostile and carries bounded ciphertext only. [Nordic ordering information](https://docs.nordicsemi.com/r/bundle/ps_nrf52832/page/ordering_info.html)

The migration table preserves GPIO signal assignments and explicitly adds the QFN supply/ground pads. It is not an approved land pattern. Check the complete schematic, exposed-pad soldering, decoupling, reset/debug lifecycle and package-specific RF components/layout against [Nordic's pin assignments](https://docs.nordicsemi.com/r/bundle/ps_nrf52832/page/pin.html) and [QFN reference circuit](https://docs.nordicsemi.com/r/bundle/ps_nrf52832/page/ref_circuitry.html). The pitch remains 0.4 mm, but the contacts are on the perimeter. Do not copy the WLCSP RF matching circuit or assume the larger package guarantees a routed board.

## Verification of the existing model

On 2026-11-15, `cargo test --locked -p protocol --test lifecycle` passed **18 tests**, including mutual local enrollment approval, different MITM fingerprints, malformed/replayed confirmations, two-source entropy failure handling, hostile-radio bounds, sealed contacts and offline-update fault handling. This was a focused existing-model run, not a new full laboratory verdict or validation of Rev C hardware. The migration CSV was checked for all 48 numbered QFN terminals plus exposed ground, preserving every connected B0 radio net. The preserved B0 PCB hash still matches `decisions.json`.

## Next implementation gates

1. Select actual NiMH cells and charging/load policy, then calculate current, energy, voltage margins and charger heat.
2. Replace power circuitry, remove Qi/NFC and OPTIGA with a net-by-net dependency review, and implement the QFN radio circuit in separate Rev C CAD.
3. Recheck schematic pin maps, radio containment, contact/update persistence, entropy failures, charging faults and power-loss behavior. SPICE results need appropriate models and clearly stated limits.
4. Submit a clean, checked Rev C input to Quilter for placement/routing only when ready; review returned copper with native KiCad checks. No competing local autorouter pass.
5. Complete power, audio, radio, entropy and trusted-UI bench qualification before relying on a physical device. Four assembled prototypes to Sweden remain the eventual procurement target; no purchase or fabrication is authorized.
