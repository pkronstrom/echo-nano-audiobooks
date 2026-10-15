# Stock 1.7.0 recovery analysis with REA / Ghidra

Current device outcome: P4a boot-looped; application-only USB stock restoration
succeeded, and the user confirmed the normal menu. Read the
[recovery lessons](recovery-lessons-2026-10-14.md). Statements below describe
the original offline/read-only investigation.

Date: 2026-10-13. Initial offline static analysis, followed by read-only hardware
checks documented in the factory-loader report. No firmware writes or flashing.

Follow-up: [factory loader analysis](factory-loader-analysis.md) and [RAM audit](ram-safety-audit.md) now cover the offline investigation below.

## Result

Stock Nano firmware implements a software request to enter the loader. The traced
USB and system routines are unchanged in the P4a custom image. This provides
stronger evidence for a software recovery route while the application is alive.
It does **not** prove recovery from an application that cannot service USB or its
system loop, nor by itself establish the Nano's physical boot-button sequence. Subsequent
hardware checks confirmed Previous/Up + USB recovery entry and normal-menu return.

## Provenance and method

- Stock SHA-256: `54a45d233a23c3ce142d1da9c093cc40c46eba417aa91fe915ee867726f4a116`.
- Custom SHA-256: `01c28d12759aea3f93125e4168c9044e8a324f3eead875bb52ae04834aa4b494`.
- REA CLI 6.4.0; Ghidra 12.1.4; Node 24.14.1; existing Android Studio JDK 21.
- Official Ghidra archive, native decompiler built locally for arm64.
- `builds/rea-stock/prepare.py` extracts sections using the existing image parser,
  builds a non-flashable ELF at stock virtual addresses, and verifies every
  initialized ELF section against the original bytes with SHA-256.
- Final map includes modules 0, 12, 9 and their data/BSS. It excludes the updater
  overlay: coincident addresses in different overlays must not be interpreted as
  calls to whichever overlay happens to be imported. Unmapped calls remain unknown.
- Language `ARM:LE:32:Cortex`, explicit analyst-supplied Thumb function symbols.
  This avoids REA's generic raw ARM mode, which does not support Thumb-only input.
- The early `usb-mode.json` used a preliminary map also containing module 1. Its
  tiny local function and resident event-set target were checked in assembly.
  The three `*-final.json` traces use the corrected map.
- `reset.json` is exploratory only: its analyst-assigned `reset_vector` label
  does not establish a physical reset entry. The script now calls that address
  `application_entry_candidate`. Startup ordering remains unresolved.

## Observed chain

1. USB dispatcher at `0x0307b38a` accepts opcode `FF`, subcommand `E0`, and reads
   a big-endian argument and length. Argument `FFFFFFFE` reaches the mode hook.
2. Hook `0x0307b1e4` sets event `BF` for nonzero length, or `C0` for zero length.
   Resident `0x0306b040` implements the event bitmap update.
3. System loop `0x0307c636` tests `BF` and calls `0x0307c4be(0, 3)`; `C0` calls
   that routine with `(0x8c, 1)`.
4. Reboot routine `0x0307c4be` writes `NanoCRebootFlag\0` into RAM
   `[0x0309fff0, 0x030a0000)`, performs peripheral/interrupt shutdown, and then:
   - For `(0, 3)`, the bit-1 test at `0x0307c60e` takes the register-write path.
     `0x0307c618` writes `0xffff18af` to `0x5002004c`.
     `0x0307c61e` writes `0x05fa0007` to `0xe000ed0c`, then spins.
   - For `(0x8c, 1)`, execution takes the alternative branch, reads a function
     pointer from address `0x8c`, and calls it after cleanup.

The register values/addresses above come from REA's instruction listing and the
stock literal pool, corroborated against objdump. The loader-request meaning is
an inference corroborated by the RKNano SDK's matching sequence; execution of the
ROM and USB enumeration after reset have not been observed on this device.

**Decompiler limitation:** Ghidra's pseudocode omits the two critical hardware
register writes on the reset branch. Its assembly includes them. Do not interpret
the C output alone as showing that this routine merely hangs, or as a complete
model of hardware side effects. Hardware-register mapping/volatile annotations
remain a useful follow-up.

## Comparison with P4a

`builds/rea-stock/patch-comparison.json` records byte comparisons:

- Modules 1 (update-related), 9 (system), and 12 (USB mass storage): all code/data
  identical between stock and custom images.
- Resident event routines `[0x0306b040, 0x0306b082)` are identical.
- Inspected application-entry range `[0x030660ca, 0x03066460)` is identical;
  that bounded check is not proof that every startup path is unchanged.
- Playback allocation ends at `0x0309fff0` exclusively, preserving the 16-byte
  reboot marker. No stock module-table code/data/BSS interval intersects the
  payload allocation `[0x0309b694, 0x0309fff0)`.

The module-table check does not identify dynamic buffers, stacks, DMA, or RAM
used implicitly by ROM. Refresh/playback mutual exclusion still needs a separate
lifetime/call-path audit; the 364 remaining payload bytes are not a stack margin.

## Question ledger

| Question | Status |
| --- | --- |
| Is there a software loader-entry request in stock 1.7.0? | Static chain established through the hardware reset request; ROM outcome inferred. |
| Does our patch replace the traced USB/system routines? | No, verified by byte comparison. |
| Does payload placement overwrite the reboot marker? | No, verified exclusive boundary. |
| Can the Nano enter recovery after an early application crash? | Factory code has an application-independent check; physical entry verified on stock. Deliberate crash recovery remains untested. |
| Can we dump/restore all current flash with the Mac tool? | Mac read access verified after accessory approval using 32-sector requests. Complete coverage and restore remain unproven. |
| Is all payload RAM ownership/stack use safe? | Partial: static module ranges and marker checked, runtime ownership not proven. |
| Is custom firmware hardware-validated? | No. |

Follow-up completed: factory loader extraction and hardware-entry analysis,
plus refresh/playback lifetime and initial stack audit, are linked at the top.
18 focused emulated checks passed across those follow-ups. No concrete RAM
collision was found. Physical recovery entry/exit has since been verified on
stock firmware. Installed loader identity, dynamic/DMA ownership and peak stack
usage remain unverified. See the factory-loader report for backup progress.

## Retained evidence

Full dossiers and extracted C/assembly are under `builds/rea-stock/` (local,
ignored build artifacts). Each dossier retains target identity and limitations.
`rea.sh` records the local engine configuration and exact installed CLI path.

| File | REA Evidence ID |
| --- | --- |
| `usb-mode.json` | `ev_255630928e02352f0db8b87bab2f9f6d231611943d6a3ffc2a5a85d1f8d6b8f1` |
| `usb-dispatch-final.json` | `ev_639c3ba10b45f5bd26eb7f6009cde04c95f2127968e1dd2bb859a2feb5f5941e` |
| `system-loop-final.json` | `ev_f93388e8824675f2ea19ac3a00488dc9c8d185f9ca23e250335f236fdac26998` |
| `reboot-final.json` | `ev_504b6994e034914674df8b7893258ed80f38e6880bba0b9a9c11c11b7d27e72c` |

Final analysis ELF SHA-256: `9c6f550ea1e1cad374b10dfc2ab0a1cebf5323a9b776f66d819f8c094218e74d`.
