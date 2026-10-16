# Update-only startup hang investigation

User reports that the first boot after updating can loop or remain on the logo,
then reaches the menu after Power/reset. Similar reports occurred with20261027
andlaterbuilds. This symptom differs from the originalP4a sector-reader corruption.
The precise latest screen behavior remains unconfirmed.

## Reproduced failure

The resident payload loader accepts any RAM header beginning ENP2. Archived
20261104 and current20261108 payloads share that marker, but have different
entry addresses and BSS layouts. Running the new loader with the old payload
already in RAM returns success without a single flash read or initialization.
New native hooks can therefore call old code at incompatible addresses.

An actual-byte ARM trace follows factory image loading through the application
handoff, first/data-vector entry0x03058864, stock BSS clear0x030630d4, and
second/code-vector entry0x030660ca. This path never writes the custom payload
range0x03092400..0x0309fff0. Stock BSS clearing covers only its declared region.
The readiness marker can survive this path unchanged. No custom callbacks run
before the second entry along this verified trace.

This establishes a retained-RAM startup failure. It does not prove the complete
update-file writer→reset→ROM RAM-retention path on the physical Nano, or exclude
other causes of the observed first-boot anomaly. First-post-update hardware
acceptance remains required; do not describe host emulation as that acceptance.

## Correction

A pinned application-entry branch at0x030660ca executes a32-byte resident stub.
It preserves the original register frame and entry arguments, clears only the
custom readiness word, applies barriers, and resumes at0x030660ce. The first
ordinary menu/player load must then copy the current payload and clear its BSS.
Repeated menu/player entries within the same boot retain the normal cached path.

The stub reclaims the exact SafePoweroff diagnostic at0x030733e0. The sole
absolute reference, module1 literal0x0307a444, is pinned; its printf at0x0307a240
is suppressed. Integration rejects changed cave/prologue/reference bytes and
unexpected absolute references, including interior and unaligned pointers.
No bootloader code, flash-layout record, reboot marker or playback boundary is
changed. The correction lives in the application image.

Tests execute the stock application trampoline and real flash byte reader, with
sector I/O/locks mocked. They reproduce stale-header acceptance before the fix,
then verify current-payload loading and BSS initialization in both firmware-slot
mappings, cold startup, preserved arguments/native stack frame and reboot marker.
Negative checks exercise altered cave/prologue/literal and unexpected references.

## Device test

Use only the latest archived candidate/recovery pair recorded in the incident
log. Stage and fully verify the internal update file on a freshly identified
Nano, then safely eject. Observe the first automatic boot after updating before
using Power/reset. Record whether normal menu appears, the logo stays static,
or animation repeats. If it fails, retain the exact candidate and symptom; do
not simply re-date and reflash the same image. A reset reaching the menu remains
a workaround until the first boot is confirmed.
