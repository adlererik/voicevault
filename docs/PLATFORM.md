# Cortex-M33 software fit

The reference capacity is an STM32U585-class Cortex-M33: 2 MiB flash and 768 KiB of main SRAM with ECC off. The separate SRAM4 and backup RAM are not credited. The choice is a capacity reference, not a final hardware selection. Turning on SRAM ECC changes the available budget and requires a new fit check. [ST datasheet](https://www.st.com/resource/en/datasheet/stm32u585vi.pdf)

`platform/` builds the same trusted protocol, codec, device-core, link and call-state crates for `thumbv8m.main-none-eabihf` without `std`, libc, OS randomness or codec heap buffers. The separate lockfile pins the ARM graph. The diagnostic is linked into a 960 KiB image slot and 768 KiB RAM. Two image slots plus a 128 KiB root/storage allowance fit within 2 MiB flash; the installer also checks each image bank's actual capacity.

The diagnostic runs on QEMU MPS2 AN505, which emulates Cortex-M33 CPU execution. Its secure memory addresses differ from STM32 addresses, and it does not emulate STM32 peripherals. It is not proof of TrustZone isolation. [QEMU board documentation](https://www.qemu.org/docs/master/system/arm/mps2.html)

## What executes

The program completes a full Noise XX enrollment and fingerprint confirmation, seals/restores contact state, verifies signed invitations, compares accepted-call bindings, rejects privileged radio commands, exercises a modeled signed offline install/boot/rollback, and injects onboard entropy sources. It then processes 32 real 20 ms audio frames through Opus encoding, Noise media encryption, bounded fragmentation/reassembly, authentication and decoding. A diagnostic peer echoes the encoded audio; only one encoder and one decoder are allocated, as required per physical endpoint. The extra peer's crypto state is included in the memory measurement. This is not a two-device acoustic call.

The codec's inline encoder is 308,880 bytes and its decoder 178,572 bytes on this target/version. Earlier approximate library estimates understated the actual current profile. Returning these aggregates through the stack failed the fit experiment. A small vendored initialization-only patch writes encoder/CELT state directly into final storage, using the library's existing in-place buffer operations. Host tests compare 100 alternating speech/silence frames against the upstream constructor, and an integrity check verifies all upstream source files and complete initialized-field coverage. Codec algorithms are unchanged; independent unsafe-boundary review remains required.

## Budget and measurements

Each run saves exact values and ELF hash in `platform/platform.json`, plus sections, dependency graph, emulator log and a clearly labeled diagnostic ELF. The software reserves a 32 KiB heap, a guarded 128 KiB stack and 64 KiB for future display, DMA, interrupts and drivers. The heap allocator is diagnostic-only, scrubs retired allocations and counts cumulative allocations without reuse. Its number is conservative cumulative demand for the exercised path, not a production allocator benchmark. Cortex-M runtime paints the stack and sets MSPLIM; the report records observed high-water use and requires at least 16 KiB of remaining stack margin. [Runtime stack features](https://docs.rs/cortex-m-rt/0.7.7/cortex_m_rt/)

The 64 KiB peripheral allowance assumes partial display rendering. It cannot hold a full 240×240 RGB565 framebuffer, which alone needs 115,200 bytes. A full framebuffer, different codec mode, larger contact store, ECC or an RTOS can invalidate this budget. The final board needs a new whole-firmware link and worst-case measurement.

## Repeating the check

`./lab test` and `./lab watch` require the platform group. The exact Rust pin needs the `thumbv8m.main-none-eabihf` target. Provide `arm-none-eabi-size` and an official QEMU build with `mps2-an505`; `QEMU_SYSTEM_ARM` can specify its path. The recorded host uses account-local xPack QEMU 9.2.4-1 in `.lab-cache/qemu/`, with no system installation. [Official xPack installation documentation](https://xpack-dev-tools.github.io/qemu-arm-xpack/docs/install/)

To run it separately in the launcher's Rust environment:

```sh
export CARGO_HOME="$PWD/.lab-cache/cargo"
export PATH="$CARGO_HOME/bin:$PATH"
python3 scripts/platform_check.py /absolute/path/to/platform-report
```

The code deliberately uses public fixture identities, release signing keys and deterministic randomness. The resulting ELF is named `PUBLIC-TEST-KEYS-DO-NOT-FLASH.elf`. It is not production firmware. The run demonstrates linked capacity and functional CPU execution for specified paths. It does not measure real-time throughput, power, radio behavior, real interrupts, peripheral memory, complete erasure, worst-case stack, fault resistance or acoustic security.
