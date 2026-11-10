"""Link and execute the trusted software under explicit MCU capacity limits."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TARGET = "thumbv8m.main-none-eabihf"


def command(args, env, verbose=True):
    result = subprocess.run(list(map(str, args)), cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            timeout=240, check=False)
    if verbose:
        print(result.stdout, end="", flush=True)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed: {result.returncode}")
    return result.stdout


def run(out):
    out.mkdir(parents=True, exist_ok=True)
    qemu = os.environ.get("QEMU_SYSTEM_ARM") or shutil.which("qemu-system-arm")
    if not qemu:
        candidate = ROOT / ".lab-cache/qemu/xpack-qemu-arm-9.2.4-1/bin/qemu-system-arm"
        qemu = str(candidate) if candidate.is_file() else None
    if not qemu or not shutil.which("arm-none-eabi-size"):
        raise RuntimeError("missing QEMU Cortex-M33 emulator or arm-none-eabi-size")
    env = os.environ | {"CARGO_TARGET_DIR": str(ROOT / "platform/target"), "CARGO_BUILD_JOBS": "2"}
    manifest = ROOT / "platform/Cargo.toml"
    metadata = json.loads(command(["cargo", "metadata", "--locked", "--manifest-path", manifest,
                                   "--filter-platform", TARGET, "--format-version", "1"], env, verbose=False))
    (out / "target-dependencies.json").write_text(json.dumps(metadata,indent=2)+"\n")
    # Metadata merges features of host build/proc-macro units with target
    # units. Audit the actual normal target graph, excluding those host units.
    tree = command(["cargo", "tree", "--locked", "--manifest-path", manifest,
                    "--target", TARGET, "--edges", "normal,no-proc-macro", "--prefix", "none",
                    "--format", "{p}|{f}"], env, verbose=False)
    (out / "target-runtime-dependencies.txt").write_text(tree)
    for line in tree.splitlines():
        package, features = line.split("|", 1)
        name = package.split()[0]
        enabled = set(features.removesuffix(" (*)").split(","))
        assert name not in ("getrandom", "libc"), "OS dependency in target runtime graph"
        if name in ("opus-rs", "snow", "protocol", "codec", "device-core", "libcrux-ml-kem", "libcrux-sha3", "libcrux-traits", "rand"):
            assert not {"std", "heap", "sys_rng", "thread_rng"}.intersection(enabled), (name, enabled)
    command(["cargo", "build", "--locked", "--manifest-path", manifest,
             "--release", "--target", TARGET], env)
    elf = ROOT / "platform/target" / TARGET / "release/quietlink-m33-probe"
    listing = command(["arm-none-eabi-size", "-A", elf], env)
    (out / "sections.txt").write_text(listing)
    sections = {}
    for line in listing.splitlines():
        pieces = line.split()
        if len(pieces) == 3 and pieces[0].startswith("."):
            sections[pieces[0]] = {"bytes": int(pieces[1]), "address": int(pieces[2])}
    flash_base = 0x10000000
    flash = max(v["address"] + v["bytes"] for v in sections.values()
                if flash_base <= v["address"] < flash_base + 960*1024) - flash_base
    flash += sections.get(".data", {"bytes": 0})["bytes"]
    static = sum(sections.get(key, {"bytes": 0})["bytes"] for key in (".data", ".bss", ".uninit"))
    executed = command([qemu, "-M", "mps2-an505", "-nographic", "-semihosting-config",
                        "enable=on,target=native", "-kernel", elf], env)
    (out / "emulator.log").write_text(executed)
    evidence = next(json.loads(line) for line in executed.splitlines() if line.startswith("{"))
    stack_reserve = 128 * 1024
    peripheral_reserve = 64 * 1024
    assert evidence["pipeline"] == evidence["policy_paths"] == "pass" and evidence["frames"] == 32
    assert evidence["hybrid_handshake"] == "pass"
    assert evidence["suite"] == "Noise_KKhfs_25519+MLKEM768_ChaChaPoly_BLAKE2s"
    assert evidence["heap_cumulative_bytes"] <= 32*1024
    assert evidence["stack_high_water_bytes"] + 16*1024 <= stack_reserve, "stack margin below 16 KiB"
    assert flash <= 960*1024 and 2*(flash+128)+128*1024 <= 2*1024*1024, "dual bank flash capacity"
    assert static + stack_reserve + peripheral_reserve <= 768*1024, "RAM budget exceeded"
    report = {
        "schema": 1, "status": "pass", "target": TARGET, "cpu_model": "QEMU MPS2 AN505 Cortex-M33",
        "reference_capacity": "STM32U585-class: main SRAM, ECC off; no SRAM4 or backup RAM credit",
        "flash_image_bytes": flash, "flash_slot_budget_bytes": 960*1024,
        "static_ram_including_32k_heap_bytes": static, "stack_reserved_bytes": stack_reserve,
        "future_display_dma_driver_reserve_bytes": peripheral_reserve,
        "ram_budget_bytes": 768*1024, "unassigned_ram_bytes": 768*1024-static-stack_reserve-peripheral_reserve,
        "diagnostic_elf_sha256": hashlib.sha256(elf.read_bytes()).hexdigest(),
        "qemu": command([qemu, "--version"], env).splitlines()[0],
        "measured": evidence,
        "limits": ["32 fixture frames and selected policy paths; not a worst-case stack proof",
                   "No real-time throughput, power or hardware latency evidence",
                   "No STM32 peripherals, display, real BLE, secure element, RNG, MPU/TrustZone or flash emulation",
                   "64 KiB future peripheral reserve assumes partial display rendering, not a full RGB565 framebuffer",
                   "Public test keys and deterministic entropy: never flash this diagnostic image"],
    }
    (out / "platform.json").write_text(json.dumps(report, indent=2) + "\n")
    shutil.copyfile(elf, out / "PUBLIC-TEST-KEYS-DO-NOT-FLASH.elf")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    try:
        run(Path(sys.argv[1]).resolve())
    except (OSError, RuntimeError, AssertionError, StopIteration, subprocess.TimeoutExpired) as error:
        sys.exit(f"Platform check failed: {error}")
