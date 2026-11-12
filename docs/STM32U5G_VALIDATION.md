> The active [B0 target](../hardware/rev-b/target.json) is the standalone STM32U5G9ZJJ6Q UFBGA144 board. The DK2 below remains a manufacturer reference and possible bench comparison, not the selected compute module. B0 uses SAI1; the older SAI2/DK2 fixtures must not be relabeled as B0 measurements. No peripheral model or physical B0 measurement is qualified.

# STM32U5G emulation validation

The current QEMU check executes the real VoiceVault code on the Cortex-M33 in the Arm MPS2 AN505 model. It exercises the hybrid handshake, audio processing and memory budget. The probe uses MPS2 addresses, synthetic I/O and disabled interrupts. Treat its results as CPU and memory-fit evidence. The installed Renode 1.17.0 distribution has no bundled STM32U5G board description. [Current platform check](PLATFORM.md) · [QEMU AN505 documentation](https://www.qemu.org/docs/master/system/arm/mps2.html)

## Reference target and source of truth

Use ST's STM32U5G9J-DK2 as the first bench reference candidate. ST documents an STM32U5G9ZJT6Q on this board, with revision Z in the published board history. Record the actual board revision, silicon ID, clock configuration, memory bank and ECC configuration, and option bytes when taking measurements. Use the board schematic, RM0456, ES0595 and ST's exact device headers to check assumptions. For example, ES0595 §2.2.8 documents a flash programming sequence error that can leave programming stuck. A model that always completes flash writes could hide a bug in recovery from that error. [Board manual](https://www.st.com/resource/en/user_manual/um3223-discovery-kit-with-stm32u5g9zj-mcu-stmicroelectronics.pdf) · [RM0456](https://www.st.com/resource/en/reference_manual/rm0456-stm32u5-series-armbased-32bit-mcus-stmicroelectronics.pdf) · [ES0595](https://www.st.com/resource/en/errata_sheet/es0595-stm32u5fxxx-and-stm32u5gxxx-device-errata-stmicroelectronics.pdf)

I checked these addresses and interrupt numbers against ST's pinned `stm32u5g9xx.h`. They establish the starting map for candidate interfaces. Reset values, register side effects, interrupts and DMA behavior need their own checks. [Pinned ST header](https://github.com/STMicroelectronics/cmsis-device-u5/blob/624374fa1e21ca195d6f2102ac0caaa50d0ea4c8/Include/stm32u5g9xx.h)

| Candidate resource | Nonsecure address | Secure address | Interrupt example |
|---|---:|---:|---|
| Flash memory | `0x08000000` | `0x0C000000` | |
| SRAM1 | `0x20000000` | `0x30000000` | |
| SAI1 audio interface | `0x40015400` | `0x50015400` | SAI1 IRQ 90 |
| GPDMA1 | `0x40020000` | `0x50020000` | Channel 0 IRQ 29 |
| SDMMC1 | `0x420C8000` | `0x520C8000` | SDMMC1 IRQ 78 |
| GTZC1 peripheral security controller (TZSC) | `0x40032400` | `0x50032400` | GTZC IRQ 8 |

## Reject incomplete tests

An empty Renode machine returned `0x00000000` for reads at the candidate SAI1 and SDMMC1 addresses, logged that the peripherals were absent and exited with status 0. This deliberately incomplete machine is a negative control. A future test must fail if it touches an unmodeled register required for the scenario, times out, or fails to observe the expected data, interrupt or access denial. Preserve the emulator warnings and verify that removing a required model makes the test fail. [Renode behavior on unmapped accesses](https://renode.readthedocs.io/en/latest/advanced/writing-peripherals.html#what-if-there-is-no-peripheral-mapped-at-given-offset)

## Verify one interface at a time

| Area | Evidence to collect |
|---|---|
| Reset, clocks and interrupts | Boot a small STM32-target test using the candidate memory map. Check reset values, readiness flags and interrupt order. Compare with a trace from the matching development board. |
| Audio and DMA | Use known samples to check both audio directions, buffer boundaries, completion interrupts and underrun recovery. Compare the samples and interrupt order on the board. Measure deadline margin and peak stack on silicon with display and radio traffic active. |
| Isolation | Exercise allowed transfers and denied CPU/DMA accesses to trusted memory with the intended TrustZone and peripheral configuration. Verify denials on silicon, with the radio interface deliberately sending invalid traffic. |
| microSD and flash | Test removals, read errors, stale or altered images, flash programming errors and reset during update. Verify on hardware that recovery boots only a verified image at or above the protected version floor. |

Start from independent STM32CubeU5 examples such as `DMA_FLASHToRAM` and `FLASH_EraseProgram` for the DK2. Add VoiceVault-specific cases after the basics agree. Run the same STM32-target test logic and fixtures in the model and on the board, record any test adapter differences, and compare observable results. Publish which behavior is specification-checked, tested in a model, or measured on the board. Reserve timing, real access-control enforcement, power loss and physical leakage conclusions for bench evidence. [ST board examples](https://github.com/STMicroelectronics/STM32CubeU5/tree/main/Projects/STM32U5G9J-DK2/Examples)
