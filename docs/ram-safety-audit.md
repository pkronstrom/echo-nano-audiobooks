# P4a RAM ownership audit — 2026-10-13

Read-only source, stock disassembly and REA/Ghidra analysis. No firmware or USB writes. Stock SHA256 `54a45d233a23c3ce142d1da9c093cc40c46eba417aa91fe915ee867726f4a116`; tested release SHA256 `01c28d12759aea3f93125e4168c9044e8a324f3eead875bb52ae04834aa4b494`.

## Static placement

Both linker scripts intentionally allocate `[0x0309b694,0x0309fff0)`. Current playback map ends at `0x0309fe84` (364 bytes spare); refresh ends `0x0309fc2c` (964 spare). These are payload allocation margins, not stack margins. Largest stock module range is module40 code `[0x030797ec,0x0309b694)`, exactly adjacent. No table-declared initialized/BSS region enters payload. Marker `[0x0309fff0,0x030a0000)` is preserved. `ram-facts.json` retains stock/patched initial vectors and relevant module bounds.

## Stack evidence stronger than previous audit

Stock and patched module0 vector at `0x03050000`: initial SP `0x03004000`, entry `0x030660cb`. Stock trampoline `0x030588ce..d8` loads this vector, `mov sp,r0`, and branches to entry. This places known initial application stack below `0x03004000`, far from payload. It DOES NOT establish stack lower bound, peak usage, or every interrupt/context stack.

Stock CMSIS helpers at `0x03059a3c` / `0x03059a48` set PSP/MSP; no direct call to either was found in the selected module0/9/12 wrapper. That negative search is not proof of no indirect use. Current compiler .su files: largest custom individual frames find_fat672B, book_load576B, chooser_draw/install_root336B, content_scan/m3u_scan328B. C scanning is iterative bounded traversal, not recursive directory nesting. Native calls and caller/interrupt frames add to these figures, so no complete worst-case stack proof.

## Refresh/playback ownership

- `playback/hooks/loader.S` resident loader0x03072e28 checks ENP2 at0x0309b694; missing signature reads complete payload via stock0x0306b36c then verifies magic, clears BSS through playback_init. Read error or bad signature clears magic and returns failure. Queue survives repeated successful calls while signature remains.
- Menu module21 initializer, browser module31 initializer/selection, and music module33 entry call loader before payload use, with failure fallback. Save-close/stock-save wrappers explicitly check magic before entering payload.
- Module5 driver loads module40, invokes cfw_stub to overwrite payload and clear refresh BSS, then cfw_scan. Refresh first code word at payload address is `0x4ff8e92d`, not ENP2. This invalidates playback signature as part of copy.
- Full module40 load `[0x030797ec,0x0309b694)` overwrites all module33 playback hook sites `[0x03080470,0x03084968)`, browser selection/event branches, and menu dispatch branch0x03079b1e. Module5 load `[0x03079418,0x030797ec)` replaces menu strip branch0x030795b4 and menu initializer. Thus actual overlay replacement removes branch sites before refresh overwrites their destinations. There is no separate global playback-hook uninstall.
- cfw_scan installs native FAT/exFAT hooks0x0305b3ea/0x0305b2a2 and read hook0x0305c3fa. It restores read after mod39_walk, restores directory hooks after mod39_record, before sorting and return. Writes mask interrupts and use DSB/ISB. Normal cfw_scan has no early return between installation/restoration.
- Playback re-entry after refresh reloads payload and clears stale BSS. Runtime patched menu/browser tables are installed only after loader succeeds. Re-entry after failed refresh or asynchronously interrupted module switches is not fully proven.

REA/Ghidra at stock0x0306b5b6 confirms ordinary overlay loading reads table, copies code/data according to flag bits1/2 and zeroes BSS according to bit4. Wrapper0x0306b6bc calls this with existing arguments. Evidence `ram-overlay.json`, `ram-overlay-body.json`; raw disassembly `ram-stock.dis`. The existing ELF deliberately includes modules0/9/12 only; do not infer overlay callers from Ghidra's incomplete call graph.

## Partial read question

A reported read failure does NOT leave a valid signature. Existing Unicorn test deliberately copies a valid payload (including magic), returns error, and verifies loader clears magic before returning. Stock read0x0306b36c uses r9 as sticky error flag: aligned block failure0x0306b4bc..4d4, tail failure0x0306b45a..472, returns r9 at0x0306b4ee. This supports the loader's zero=success contract rather than an assumed byte-count return.

During copying, the signature is visible before initialization finishes. A concurrent reentrant payload loader could theoretically mistake that for readiness. No reachable interrupt/callback reentry into the loader was established here; this is a concurrency assumption, NOT a demonstrated defect. Likewise no evidence established a lower driver returning success after a short copy. Do not report a proven partial-read bug.

## Verification

Successful output retained in `ram-tests.log`. Command: `PYTHONPATH=tests builds/tools/test-env/bin/python -m unittest test_playback_runtime_arm.PlaybackRuntimeTests.test_loader_failure_never_leaves_a_ready_signature test_playback_runtime_arm.PlaybackRuntimeTests.test_loader_reuses_live_queue_and_reinitializes_after_refresh test_navigation_arm -v`. The first sandbox attempt left an incomplete log; the successful elevated rerun replaced it.

Ran existing focused Unicorn checks under the previously provisioned builds/tools/test-env interpreter: two loader cleanup/reuse checks plus all nine navigation ARM checks, 11/11 passed. They execute compiled hook/payload machine code with selected stock calls mocked; not device timing or driver certification. Sandbox JIT launch was unsuccessful, rerun with authorized local execution succeeded. REA sandbox launch failed; elevated local Ghidra succeeded, with saved evidence above.

## Conclusion / remaining gate

No new concrete RAM collision or reported-read-error signature bug found. Known initial stack is outside payload; ordinary overlay transitions remove obsolete hook code; normal refresh restores resident hooks. Do not call overall RAM safety proven: asynchronous lifecycle/callback reachability, DMA/dynamic allocations and total stack high-water remain unverified. The linker comment "nothing else uses it" is stronger than evidence. Hardware recovery remains a separate prerequisite to a low-risk device test recommendation.
