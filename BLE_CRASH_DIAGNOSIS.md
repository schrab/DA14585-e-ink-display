# DA14585 Firmware — BLE Crash & Memory-Budget Findings

Reverse-engineering notes for two distinct problems found while bringing the custom BLE
firmware up on Linux (SDK 6.0.24.1464, GCC 16.2.0). One is **fixed and verified**; the
other is **characterised but not fixed**.

Read this before changing `firmware/Makefile`, the KE heap sizes, or the BLE transport.

---

## 1. Fixed: KE message heap starvation (NMI / watchdog reset)

### Symptom

Streaming the 30,000-byte tri-color frame (125 × 240-byte ATT writes) made the board die
with `IPSR = 2` (NMI). NMI here is the hardware watchdog, so the practical effect was a
reset and loss of advertising.

### Root cause

The DA14585 BLE stack allocates **every** KE message from one fixed-size pool,
`rwip_heap_msg_ret`. Its size is hard-coded in `sdk/platform/arch/main/jump_table.c`:

```c
/// Msg Heap
#ifndef MSG_HEAP_SZ
    #define RWIP_HEAP_MSG_SIZE_JT   RWIP_HEAP_MSG_SIZE_USER   // = 1392 bytes
#else
    #define RWIP_HEAP_MSG_SIZE_JT   MSG_HEAP_SZ               // override
#endif
```

At an MTU of 247 each ATT write produces a ~250-byte KE message, so the default 1392-byte
pool holds only ~5 messages in flight. Streaming faster than the stack drains it exhausts
the pool, and the allocator then returns blocks that overlap already-freed ones.

The overlap was observed directly: the faulting `struct ke_msg` (12 bytes,
`param_len = 0`) was followed immediately by `0x0048A55A` — `0xA55A` being the KE
memory-block free-list magic — inside `rwip_heap_msg_ret`.

### Why the pool is so small here

The application framebuffer dominates RAM and squeezes everything else:

| Region | Bytes |
|---|---|
| `code` (.text + rodata) | 30,944 |
| `data` + `.bss` — of which `eink_framebuffer` is **30,000** | 30,316 |
| `rwip_heap_non_ret` | 1,036 |
| main stack | 2,048 |
| `RET_HEAP` (env 628 + db 1,036 + **msg 1,404**) | 3,068 |
| slack left in `LR_RETAINED_RAM0` | 128 |

`eink_framebuffer` is **91 % of `.bss`**. The retained region is the binding constraint,
so `MSG_HEAP_SZ` cannot grow much further without shrinking the framebuffer.

### Fix

`firmware/ble/config/user_config.h`:

```c
/* firmware/ble/config/user_config.h — note the guard, see caveat below */
#if !EINK_DIAG
#define MSG_HEAP_SZ  (1904)   /* was 1392 */
#endif
```

> **Caveat on this fix's scope (found while re-checking §2).** The enlarge is compiled in only
> for non-diagnostic builds: `EINK_DIAG=1` silently falls back to the SDK default 1392-byte pool,
> because the ~650 bytes of retained CRC history do not fit alongside it (`LR_RETAINED_RAM0`
> overflows by ~456 B). That is deliberate and correct for linking, but it means a diagnostic
> build is **not** testing the fixed heap. Any experiment whose result depends on pool size must
> say which build it ran in — see §2 · "Build caveat that invalidates several negative results".
> (§1's verification table above does not state its build; the crash-path evidence in §2 was
> captured with `EINK_DIAG=1`, so the two may not describe the same pool. Worth pinning down.)

512 bytes were freed by making the diagnostics compile-time optional
(`EINK_DIAG=0` is now the Makefile default; see §4).

### Verification

| Metric | Before | After |
|---|---|---|
| 30 KB stream | NMI / reset | **76.9 KB/s, clean** |
| `IPSR` after stream | 2 | **0** |
| Link after stream | dropped | **held** |
| BW plane `[0..14999]` | — | **byte-exact, 0 mismatches** |
| Red plane `[15000..29999]` | — | 1487 B lost @ 77 KB/s, 160 B @ 14.4 KB/s |

`ip_src/../check` of the framebuffer was done by reading `eink_framebuffer` over SWD and
comparing against the host-side conversion — **no display refresh involved**.

---

## 2. Open: HardFault on any ATT Write Request (with response)

> **Status update (2026-09-28, fourth revision — supersedes the third).** The step-zero
> experiment has now been run (see *Step zero* below). The write-with-response failure
> **does not reproduce on the production build** (`EINK_DIAG=0`, `MSG_HEAP_SZ=1904`): 3/3
> clean. It fails 2/2 on `EINK_DIAG=1` (1392 B pool), where it presents as a *hang*, not
> the HardFault analysed below. Root cause still undetermined; the fix status is unchanged
> (use Write Without Response), but the open question is now scoped to a build we do not
> ship.
>
> **Status update (2026-09-28, third revision — supersedes the second).** Two claims that
> were written into this document as settled are now **withdrawn**:
>
> 1. *the original* "this is a valid LLC message, the ROM just had no handler" reading, and
> 2. *the retraction of it*, which argued the header was provably garbage because it failed
>    a `KE_MSG_ID(dest, src)` consistency check.
>
> **Neither holds.** There is no `KE_MSG_ID` macro in the SDK at all. This was **checked
> directly** against the local SDK at `~/DA145xx_SDK/6.0.24.1464`, not inferred:
>
> ```
> $ grep -rn "KE_MSG_ID" --include=*.h ~/DA145xx_SDK/6.0.24.1464     # no matches
> ```
>
> The real primitives, in `sdk/platform/core_modules/ke/api/ke_msg.h` and `ke_task.h`:
>
> ```c
> ke_msg.h:63   #define KE_BUILD_ID(type, index) ( (ke_task_id_t)(((index) << 8)|(type)) )
> ke_task.h:57  #define KE_FIRST_MSG(task)  ((ke_msg_id_t)((task) << 8))
> ke_task.h:59  #define MSG_T(msg)          ((ke_task_id_t)((msg) >> 8))
> ke_task.h:61  #define MSG_I(msg)          ((msg) & ((1<<8)-1))
> ```
>
> (`firmware/ble/user_eink_app.c:205` — the one place our code builds a msgid — uses
> `KE_BUILD_ID`, as required.)
> Under the real primitives, the low byte of a msgid is the **message index within the
> defining module's enum**, not `src_id`.
> Message ids are globally unique by defining module and carry **no** dest/src information,
> so neither `msgid & 0xFF == src & 0xFF` nor `MSG_T(msgid) == dest & 0xFF` is a rule the
> SDK enforces. Both candidate validators are refuted by a message we know was handled
> correctly, logged off the device by `diag_observe()`:
>
> ```
> msgid=0xFD0A  dest=0x0004  src=0x0011  handle=0x0002  length=1  b0=0x07  → CMD
>   msgid & 0xFF = 0x0A   vs   src  & 0xFF = 0x11   → differ
>   MSG_T(msgid) = 0xFD   vs   dest & 0xFF = 0x04   → differ
> ```
>
> That message produced the `CMD_CLEAR` snapshot and the clear demonstrably took effect, so
> it is ground truth for a *valid* message — and it satisfies neither rule.
>
> **Consequence: the fault record can be neither validated nor invalidated from its own
> fields.** It is genuinely undetermined whether `0x0101 / 0x0001 / 0x00FF` is an emitted
> message or a freed block decoded as a header. The investigation is blocked on evidence, not
> on analysis — every experiment proposed across the last three revisions is now recorded as a
> dead end, together with what would actually be needed to resume
> ([§2 · Dead ends](#dead-ends-why-no-further-experiment-in-this-repo-can-settle-it)).
> Decision unchanged: **live with it, do not patch the ROM.**

### Symptom

Any ATT **Write Request** (`response=True`) crashes the board. A **Write Command**
(`response=False`) of the same size does not. Reproducible with a single 1-byte write.

### Fault record

Captured from the SDK's development-debug dump at `STATUS_BASE` (`0x07FD0000`), which
`HardFault_HandlerC` fills in before halting:

```
IPSR = 3  (HardFault)
R0   = 0x00000101     msgid
R1   = 0x07FD59A8     param  => message base = R1 - 12 = 0x07FD599C
R2   = 0x00000001     dest_id
R3   = 0x000000FF     src_id  (TASK_ID_INVALID)
LR   = 0x07F1BDDD
PC   = 0x50001500     GP_ADC_CTRL_REG
CFSR = 0, HFSR = 0, DFSR = 0
```

### Faulting instruction

`LR` resolves inside the mask ROM, which is readable over SWD. Disassembling it gives an
exact match for the stacked return address:

```asm
07f1bdd0:  mov  r1, r4
07f1bdd2:  adds r1, #12          ; r1 = msg + 12 = param
07f1bdd4:  ldrh r3, [r4, #8]     ; src_id
07f1bdd6:  ldrh r2, [r4, #6]     ; dest_id
07f1bdd8:  ldrh r0, [r4, #4]     ; msgid
07f1bdda:  blx r5                ; <-- FAULTS. LR = 0x07F1BDDC|1 = 0x07F1BDDD ✓
```

`r5` is a **KE message-handler function pointer** resolved for the message being
dispatched. It held `0x50001500`, a peripheral register address, so the ROM branched into
the register map and faulted. (On Cortex-M0 an instruction fetch from a non-executable
address escalates to HardFault with `CFSR = 0`, which matches the all-zero fault status.)

The containing ROM symbol is `ke_queue_insert`. The handler signature is
`int (*ke_msg_func_t)(ke_msg_id_t msgid, void const *param, ke_task_id_t dest, ke_task_id_t src)`,
so `r0 = 0x0101` is the **message id**.

> ⚠️ **Withdrawn reading (2026-09-28).** This paragraph originally continued "`KE_FIRST_MSG(task)
> = task << 8`, so `0x0101` means task type 1 (`TASK_ID_LLC`), message 1 — and `dest_id = 0x0001`
> agrees; the message is self-consistent". That inference is **retracted**: msgid high/low bytes
> identify the *defining module* and the *index within its enum*, not dest/src, so "agrees" was a
> coincidence with no evidential weight. See the status block at the head of §2. What *is* solid
> here is independent of it: the register values, the exact `LR` match on the disassembly, and
> the fact that `r5` held a non-executable peripheral address.

The faulting message's 12 bytes are immediately followed by `0x0048A55A`, the KE
free-block magic, so this looks like the *same* allocator-overlap weakness as §1 reached
by a different path — but that has **not** been proven, and it persisted after `MSG_HEAP_SZ`
was raised.

### Hypotheses eliminated

Each of these was checked and found correct:

| Hypothesis | Evidence |
|---|---|
| Config drift vs official template | Compared with `ble-sdk6-examples/template/empty_peripheral_template`. Only deltas: `CFG_APP_SECURITY` off (intentional), `CFG_SPI_FLASH_ENABLE` on, 3 cosmetic `SDK_VERSION_STRING_*` defines. `user_modules_config.h` and `user_callback_config.h` are byte-identical. |
| GATT DB declaration format | `0, 0, NULL` for characteristic declarations is correct — the official template does the same; `attm_db_128.c` synthesises the declaration from the value attribute. |
| `TASK_DESC_APP` / `app_default_handler_RAM` | `{state_handler=NULL, default_handler=0x07FC75F4, state, state_max=4, idx_max=1}`; `app_default_state[] = {0xFFFF, app_default_hndlr}` — correctly sentinel-terminated. |
| Handler-table overrun (`func` read past array) | The ROM search is bounded by `msg_cnt` and terminates on `id == 0xFFFF`. The `code` region CRC never changed across any snapshot, so no const table is being corrupted. |
| 247-byte characteristic length | Changed to 244 (the true `MTU-3` ceiling) — no effect. |
| 11 missing SDK sources | `app_utils.c`, `dma.c`, `uart.c`, `i2c.c`, `otp_cs.c`, `arch_hibernation.c`, `app_easy_{crypto,storage,whitelist}.c`, `app_bond_db.c` were absent versus `ble_app_peripheral`'s Keil project. Added them (correct regardless) — **no effect on the crash**. |
| Zero-byte `.heap` | Our `.heap` section is byte-identical to the SDK stock linker script; the SDK's application heap comes from `jump_table.o` sections, not `.heap`. |
| `__EXCLUDE_ROM_*` RAM overrides | Neither the reference app nor ours define any. |
| Framebuffer bounds check | `offset + data_len > 30000` is computed in `int` after integer promotion, so it cannot wrap. |

### Working transport, and its one caveat

Use ATT **Write Without Response**. It needs `PERM(WRITE_COMMAND, ENABLE)` on the
characteristic, which was added to `EINK_CMD_VAL`.

Write Commands have **no link-layer retransmission**, so the host can outrun the
peripheral and chunks are silently dropped. That caveat is severe enough to have driven a
protocol change — see §2b.

### Claims that were evaluated and do not hold here

For the benefit of the next person, these were suggested and checked against this build:

* **"`.bss` risks overlapping into SysRAM3, so move the framebuffer to SysRAM4
  (`0x07FD0000`)."** Measured bounds: `.bss` = `0x07FC7648`..`0x07FCEC44`, which is SysRAM1
  plus part of SysRAM2; SysRAM3 begins at `0x07FCC000`, leaving a `0x33BC` byte gap. The
  stack is at `0x07FCF100`..`0x07FCF900` (SysRAM3), and the linker asserts
  `__StackLimit >= __HeapLimit`, which passes. SysRAM4 is also **not** free — it holds
  `intr_cb` (`0x07FD4938`), `prf_env`, `app_state`, `ke_free_bad`, `ke_mem_heaps_used`,
  `ke_env` and the `RET_HEAP` block. Putting the framebuffer there would collide with
  kernel state. **Relocating it out of `.bss` is still a reasonable idea** (SPI flash has
  ~450 KB spare) but `0x07FD0000` is the wrong destination.
* **"A double free in the write handler corrupts the queue."** We never call
  `ke_msg_free`/`ke_param2msg` and our catch-all returns `void`, so the SDK frees the
  message itself. No double free is possible.
* **"A failed `ke_msg_alloc` returns NULL and `ke_msg_send(NULL)` hardfaults."** Per the
  SDK's own platform reference, allocation failure across all heaps issues a *system
  software reset*, not a HardFault. We also never allocate a `GATTC_WRITE_CFM`.
* **"The `PERM(RI)`/`PERM(WRITE_COMMAND)` permissions cause the write-response crash."**
  Our attribute table is byte-equivalent to the official template in this respect, and
  adding `WRITE_COMMAND` changed nothing.

The underlying idea that *is* worth keeping from that line of thinking: the crash message
overlaps a freed KE block, so an allocator/free-list problem remains the most plausible
remaining cause — it just is not a double free on the application side.


---

## 2b. Fixed: silent chunk loss, and why a byte counter was not enough

### Symptom

Even at a clean 14.4 KB/s the uploaded image was wrong, with mismatches appearing from
roughly byte 28800 onward. A retry often "worked", which is the worst kind of bug: it
looks intermittent when it is deterministic.

### The wrong conclusion I first drew

I measured mismatches against the host-side conversion of the image and concluded the loss
was a **contiguous tail run** (chunks 94..123 at 15 ms, 67..123 at 5 ms), and recommended
"re-send the tail". **That conclusion was wrong, and so was the advice built on it.** One
lucky sample had shown only the last chunk or two missing and I generalised from it.

### Measuring it properly

A resampled test pattern is a bad instrument here: it has large uniform regions, so a
partially-written or stale chunk can coincidentally compare equal and hide the damage.
The measurement that settled it stamps each 240-byte chunk with a 2-byte little-endian tag
equal to its own index, making every chunk individually identifiable, then classifies the
framebuffer as *received intact* / *never arrived* / *partial or stale*.

Loss is a **contiguous band whose length varies with pacing**:

| pacing | chunks intact | 
|---|---|---|
| 0 ms | 32/125 |
| 5 ms | 43/125 |
| 15 ms | 60-65/125 |
| 30 ms | 86/125 |

Three measurement traps, each of which produced wrong numbers first:

* **The `0x07` clear is itself a Write Command**, so the "known baseline" can itself be
  dropped. A single `0x07` is not a reliable baseline.
* **Never read 30 KB over SWD while the BLE client is still connected.** Halting the core
  for several seconds trips the supervision timeout, the link drops mid-stream, and the
  run is void. Read back only *after* disconnecting.
* Chunk 62 spans the plane boundary (offset 14880 = 120 B of BW + 120 B of Red), so an
  "untouched" test must compare each byte against its own plane's clear value.

### Why `eink_rx_bytes` cannot detect this

`eink_rx_bytes` is a plain accumulator. With a contiguous band of loss it still reports a
large, plausible-looking value while a wide band of the image is missing. It cannot
distinguish "chunk 40 never arrived" from "everything after 40 is missing", and it cannot
see a chunk that was written but holds stale bytes.

### Fix: per-chunk receipt bitmap

The image protocol is already idempotent (each write is a `memcpy` at an explicit offset),
so re-sending is harmless — the only missing piece was knowing *what* to re-send.

* `firmware/ble/user_eink_app.h` defines the wire chunking: `EINK_CHUNK_SIZE 240`
  (240 + a 2-byte offset header = 242 <= MTU-3 = 244), `EINK_CHUNK_COUNT 125`,
  `EINK_CHUNK_MAP_BYTES 16`.
* `eink_chunk_map[16]` holds one bit per chunk. A bit is set only when a write lands
  exactly on a chunk boundary, so a truncated or misaligned write cannot mark data good.
* Command `0x07` (clear) zeroes the map; command `0x08` notifies
  `map[16] || rx_bytes_lo || rx_bytes_hi` (18 bytes, within the 20-byte MTU-23 limit).
* `upload_noresp.py` sends a pass, queries `0x08`, and re-sends only the chunks whose bit
  is clear, repeating up to `--rounds` times. `--refresh` is now opt-in so routine runs
  never touch the panel.

### Verification

```
[+] All 125 chunks confirmed received after 1 send pass(es)
[+] Stream complete in 11.2s
IPSR=0 (healthy)
EXACT MATCH over all 30,000 bytes: True
  BW  plane mismatches: 0
  Red plane mismatches: 0
```

The framebuffer was read back over SWD after disconnecting and compared byte-for-byte
against the host-side conversion. This is the first run in the project with a **provably
complete** upload.

### Static analysis of the faulting code (2026-09-28)

The mask ROM is fully readable over SWD. The entire 128 KB dumps cleanly (96.1% non-`0xFF`)
and `da14585_586.lib` supplies **1308 ROM symbol names**, so this is now a tractable static
problem rather than guesswork.

**The KE message module is tiny and contiguous:**

| symbol | address |
|---|---|
| `ke_msg_alloc` | `0x07F1BBB0` |
| `ke_msg_send` | `0x07F1BBE2` |
| `ke_msg_free` | `0x07F1BC36` |
| `ke_queue_insert` (fault site) | `0x07F1BCAD` |
| `ke_task_init_func` | `0x07F1BE3F` |

`ke_msg_alloc` confirms the header layout and rules out one theory:

```asm
07f1bbbe:  adds  r0, #12          ; param_len + sizeof(header)
07f1bbc0:  bl    0x07F1B994       ; ke_mem_alloc()
07f1bbc4:  movs  r1, #0
07f1bbc6:  mvns  r1, r1           ; 0xFFFFFFFF
07f1bbc8:  str   r1, [r0, #0]     ; msg->next = NOT_IN_QUEUE  <-- no NULL check
07f1bbca:  strh  r7, [r0, #4]     ; id
07f1bbcc:  strh  r6, [r0, #6]     ; dest_id
07f1bbce:  strh  r5, [r0, #8]     ; src_id
07f1bdd2:  strh  r4, [r0, #10]    ; param_len
```

There is no NULL check after `ke_mem_alloc`, but a failed allocation would fault writing to
address **0x0**, not `0x50001500` — so the NULL path is **not** our bug. The single global
referenced by `ke_msg_send` is `ke_env` at `0x07FD7E78`.

**`ke_env` is decoded.** `KE_MEM_BLOCK_MAX = 4`, `heap[]` at `ke_env + 0x3C`:

| slot | pointer | region | payload |
|---|---|---|---|
| `heap[0]` | `0x07FD4D84` | env heap | 444 B free |
| `heap[1]` | `0x07FD4FF8` | db heap | 200 B free |
| `heap[2]` | `0x07FD5404` | **msg heap** (`MSG_HEAP_SZ`) | 1784 B free |
| `heap[3]` | `0x07FCECBC` | non-retained heap | 1024 B free |

Free-block header, derived from a live walk:

```c
struct mblock_free {
    uint16_t      magic;   // +0, always 0xA55A
    uint16_t      size;    // +2
    struct mblock_free *next;  // +4, 0 terminates the list
};
```

**The key correction this produces.** The `0x0048A55A` seen next to the faulting message is
a *valid* free-block header, not evidence of a doubly-freed block. The message the ROM
dispatched therefore was **not a corrupted message** — it was a pointer into a region the
allocator considers **free**. In other words some caller passed `ke_msg_send()` a `param`
pointer that `ke_msg_alloc` never returned. That is a sharper and more testable statement
than "the free list got corrupted", and it redirects the search towards the *callers* of
`ke_msg_send` rather than the allocator.

**Why the periodic free-list validator was abandoned.** All four free lists walk correctly
and are pristine whenever the device is idle, and the corruption is transient — it exists
for microseconds and is consumed by the very dispatch that faults. A validator can only run
at a safe point in task context, i.e. *after* the damage, by which time the ROM has already
branched into the register map. It would report "healthy" every time and give false
confidence. This is an architectural limit of Cortex-M0 (no DWT watchpoints, no ETM/ITM),
not a probe limitation.

### Audit of the application's own `ke_msg_send` callers (2026-09-28)

A grep across every translation unit this Makefile actually compiles finds **exactly one**
`ke_msg_send` call: `firmware/ble/user_eink_app.c`, in command `0x08`. The crashing test
writes `0x07`, whose handler only memsets the framebuffer, resets two counters and takes a
diag snapshot — it allocates nothing and lets no pointer escape. **The application's own
code is therefore exonerated as the rogue caller; the poisoning `ke_msg_send` is in ROM.**

Two things that audit checked and cleared, recorded so nobody re-raises them:

* `KE_MSG_ALLOC_DYN(id, dest, src, param_str, length)` expands to
  `ke_msg_alloc(..., sizeof(struct param_str) + length)`. `custs1_val_ntf_ind_req::value`
  is declared `value[__ARRAY_EMPTY]`, and `__ARRAY_EMPTY` expands to *nothing*, so the
  struct is a flexible array member and `sizeof` covers zero value bytes. Passing
  `sizeof(rsp)` therefore allocates exactly the right amount. This usage is **correct** —
  it is easy to misread as a double-count.
* A failed `ke_mem_alloc` is documented to cause a system reset, and `ke_msg_alloc` has no
  NULL check of its own (it would fault writing to `0x0`, not `0x50001500`). We have added
  an explicit NULL guard in the `0x08` path anyway, since that is the only place a failed
  allocation could become a write to address 0 in our code.


**Hardware patch controller: unused.** The DA14585 does implement `PATCH_ADDR0..21_REG` at
`0x40080020 + 8n` (reset value `0x07F00000`), which redirects instruction fetches from ROM
to RAM. All 22 registers read their **reset value** — zero active patches. The Dialog
"patching" is a link-time/boot-time software mechanism, not this hardware, so the whole
hardware-hook theory is dead. (Note `0x50004000` is `SRC1_CTRL_REG`, an audio register —
not a patch controller.)

**Not yet done:** the 128 KB dump exists but has not been loaded into Ghidra. That is the
remaining step, and it is now well targeted — we know the exact 0x290-byte module, the
exact faulting instruction, the exact free-block layout, and that the crash is in the
*callers* of `ke_msg_send` rather than the allocator.


### Ghidra / static call-graph of the ROM (2026-09-28)

Ghidra 12.1.2 + PyGhidra + JDK 26 are installed, the 128 KB ROM imports cleanly at base
`0x07F00000` as ARM Cortex-M0, and `rom_callers.py` resolves the call graph with capstone
against the 794 ROM symbols.

**Every caller of `ke_msg_send` (16 sites, 12 functions):**

| caller | sites | role |
|---|---|---|
| **`atts_send_pdu`** | `0x07F1197C` | **ATT server transmit — the `ATT_WRITE_RSP` path** |
| `l2cc_pdu_recv_ind_handler_func` | 3 (`0x07F157E0`, `0x07F15A02`, `0x07F15B0E`) | L2CAP receive |
| `gattc_set_mtu` | `0x07F11B86` | MTU exchange response |
| `gapc_send_error_evt` | `0x07F14D2C` (x2) | error event |
| `gapm_send_error_evt` | `0x07F16B4A` | error event |
| `gapc_lecnx_check_rx` | `0x07F14FCE` | connection param check |
| `smpc_pdu_send` | `0x07F13D36` | Security Manager |
| `smpc_generate_e1` | `0x07F13A24` | Security Manager |
| `smpc_dhkey_calc_start` | `0x07F1B5FA` | Security Manager |
| `smpc_check_repeated_attempts` | `0x07F137EA` | Security Manager |
| `ke_msg_forward` | `0x07F1BC24` | forwarding |
| `ke_msg_forward_new_id` | `0x07F1BC34` | forwarding |

**`atts_send_pdu` is the only ATT-server transmit path**, and an `ATT_WRITE_RSP` must go
through it, so that is where the rogue pointer is being sourced. Everything else in the
list is either L2CAP/SMP plumbing or error events, none of which a 1-byte write triggers.

A verified non-bug along the way: the alloc/send pair at `0x07F11956`/`0x07F11978` looks
like a double header subtraction but is not. `ke_msg_alloc` returns `block + 12`; the helper
adds 6 and returns `block + 18`; its caller subtracts the 6 back to `block + 12`; and
`ke_msg_send` subtracts 12 to recover `block`. Consistent.

**Next step:** decompile `atts_send_pdu` (0x07F118xx) and its predecessor to find how the
response `param` pointer is derived, and check it against the `ke_msg_alloc` return.

**Tooling note.** Ghidra's headless scripting proved awkward: Ghidra 12 no longer compiles
Java scripts on the fly, and `pyghidra.run_script` silently produced an empty result. The
caller analysis is therefore done with capstone (`rom_callers.py`), which is deterministic
and fast. Ghidra remains installed and the project is at `/tmp/opencode/ghidra_proj` for
any deeper decompilation.


### RETRACTED: the "uninitialised r0 in atts_write_rsp_send" claim was wrong

An earlier revision of this document claimed the root cause was `atts_write_rsp_send`
failing to set `r0` before calling `atts_allocate_pdu`. **That claim is retracted.** It was
overclaimed, and three checks refute it:

1. **`r0` is not an uninitialised register.** `atts_write_rsp_send` takes `(r0, r1, r2)`; it
   uses `r2` as an error flag (`cmp r2, #0`) and forwards `r0` to `atts_allocate_pdu`. That is
   an ordinary three-argument function. Mistaking "the callee does not reassign r0" for "r0
   is uninitialised" was simply a misreading.
2. **The ATTS dispatcher does populate `r0` before indirect calls.** The handler loop at
   `0x07F1177E` reads the incoming ATT opcode, matches it against `atts_handlers[]`
   (`(msg_id, handler)` pairs, stride 8), loads the handler into `r5`, and sets `r0` from
   `[sp, #4]` (the caller's stack slot) before `blx r5` at `0x07F117D8`.
3. **`atts_write_rsp_send` (`0x07F10B54`) has no callers at all.** A brute-force scan of every
   `bl` and `b` encoding in all 128 KB of ROM finds zero branches targeting it, and neither a
   32-bit nor a 16-bit function-pointer table entry refers to it. It is most likely **dead
   code in the mask ROM**, which makes it an implausible crash path.

**What is actually established** about the ATT transmit path:

* `atts_allocate_pdu` (`0x07F11956`) and `atts_send_pdu` (`0x07F11978`) each have exactly
  **13 call sites**, in `atts_send_error`, `atts_send_event`, and a cluster of unnamed static
  helpers after `0x07F10B74` (dispatched through `atts_handlers[]`).
* `atts_send_pdu` is a 10-byte wrapper: `subs r0, r0, #6` then `ke_msg_send`. That offset
  round-trips correctly against `atts_allocate_pdu`'s `adds r0, r0, #6` and `ke_msg_alloc`
  returning `block + 12` — verified, not a bug.
* `ke_msg_send` itself has 16 call sites in 12 functions, of which the ATT transmit helpers
  are two, and the rest are L2CAP, Security Manager, error events, MTU exchange and the two
  forward helpers.

**Was listed as the next step, now cancelled:** *"which of those call sites produces the
observed message (`msgid=0x0101`, `dest=0x0001`, `src=0x00FF`, `param_len=0`), i.e. decompile
the `atts_handlers[]` dispatch loop and follow the handler selected for opcode `0x12`."*

Do not run that decompile. Two independent reasons, neither of which is the retracted msgid
argument below:

1. **The premise was already disproven locally.** Item 2 of this very section records that the
   dispatcher at `0x07F1177E` was read: it loads the opcode, matches against `atts_handlers[]`
   (stride 8), loads the handler into `r5` and sets `r0` from `[sp, #4]` before `blx r5`. So the
   calling convention question that motivated the decompile has an answer already, and it says
   `r0` is populated — which is also why the `atts_write_rsp_send` claim was retracted.
2. **It cannot reach the fault anyway.** The crash is a bad *handler pointer* (`r5` =
   `0x50001500`) resolved during queue dispatch — one layer above ATTS. Which ATTS helper
   calls `ke_msg_send` says nothing about how `r5` acquired that value. (This point stands on
   the disassembly alone; it deliberately does not rely on naming the destination task, because
   the enum values behind `dest_id = 1` and `src_id = 0xFF` come from SDK headers, which are
   available at `~/DA145xx_SDK/6.0.24.1464` and can be re-checked at any time.)

Recording this so the cancellation is visible where the plan was written, not only three
sections further down.


### RETRACTED: "the msgid cannot be an ATT or LLC message" (independent check, 2nd revision)

This section argued that the fault record was provably garbage because it violated a macro
it attributed to `ip_src/inc/ke_msg.h`:

```c
#define KE_MSG_ID(dest, src)  ((dest << 8) | (src & 0xFF))   /* does not exist */
```

**That macro is not in the SDK.** The name does not exist in any shipped header; the only
occurrences anywhere in this repo are inside the two markdown files that quoted it. So this
section cited a formula it had attributed to a specific file (`ip_src/inc/ke_msg.h`) without
ever opening that file — the same failure mode as the retracted `atts_write_rsp_send` claim
directly above, and this time the *retraction* inherited it. Worth naming the pattern
explicitly: the correction committed as a fix for one unverified assumption was itself built
on an unverified assumption, and both produced confident-sounding prose. The real primitives are `KE_BUILD_ID`,
`KE_FIRST_MSG`, `MSG_T` and `MSG_I`; under them the low byte of a msgid is the *index within
the defining module's enum*, not `src_id`, and ids carry no dest/src information at all. So
the two rules this section claimed were SDK-enforced (`msgid & 0xFF == src & 0xFF`, and
`MSG_T(msgid) == dest & 0xFF`) are not rules, and every conclusion drawn from them falls:

* ~~"the captured header is self-inconsistent"~~ — there is no consistency relation to violate.
* ~~"TASK_ID_LLC messages live in the unretained heap, so this block can't be one"~~ — rested
  on reading `msgid >> 8` as a task id, which is exactly the misreading being withdrawn.
* ~~"therefore the 'which of the 13 `atts_send_pdu` call sites' question is malformed"~~ — the
  question may still be malformed, but not for this reason; it is back open.

Note what did **not** change: the observation that `0x0048A55A` (free-block magic) sits
immediately after the 12-byte header is a fact about RAM, independent of any msgid rule. It
suggests-but-does-not-prove the allocator-overlap reading, exactly as §2 originally said.

Two further corrections to claims made in this section's own name:

* *"TASK_ID_LLC messages live in the unretained heap while the faulting block sits inside
  `rwip_heap_msg_ret`"* — the heap-bound half of that is real and re-confirmed here:
  `ke_rom_dump.py:34` defines the msg region as `0x07FD5404..0x07FD5B80`, and the fault base
  `0x07FD599C` is inside it (`0x07FD5404 <= 0x07FD599C < 0x07FD5B80`). The task-id half depended
  on the withdrawn msgid reading, so the combination proves nothing.
* *"the crash persisted after `MSG_HEAP_SZ` was raised"* — true, but weaker than it sounds.
  `user_config.h:155` guards the define with `#if !EINK_DIAG`, so **diagnostic builds silently
  fall back to the SDK default 1392 B pool.** Any repro run under `EINK_DIAG=1` was therefore
  testing the *unfixed* heap size. Before repeating any "persisted after the fix" statement,
  check which build produced it — this alone could account for the apparent persistence.

### Build caveat that invalidates several negative results

`firmware/ble/config/user_config.h:155` sets `MSG_HEAP_SZ (1904)` only under `#if !EINK_DIAG`,
and `firmware/Makefile:40` defaults `EINK_DIAG ?= 0`. So the two configurations differ in msg-pool
size (1904 vs 1392), in retained-RAM layout, and by the ~650-byte CRC history region. Any
conclusion that depends on heap geometry or pool pressure must therefore name its build, or it
means nothing.

One concrete inconsistency to resolve before trusting the allocator arguments in §2: the SWD heap
walk reports `heap[2]` at `0x07FD5404` with *"1784 B free"*, which implies a pool near 1904 B —
i.e. it reads as a **non-diagnostic** measurement — while the diag log line quoted at the head of
§2 (`msgid=0xFD0A ... → CMD`) can only exist in an `EINK_DIAG=1` build, where the pool is 1392 B.
Neither measurement states its build, so they may be describing different memory maps. If so, the
claim "the crash persisted after `MSG_HEAP_SZ` was raised" is not established at all, because the
diagnostic build never had the larger pool.

### Raw observations, and where each one actually came from

Withdrawing the validators above removes the *explanations*, not the *facts*. These remain on
the record exactly as measured — but they were captured by two different mechanisms, and
mixing them is how both earlier readings got their false confidence:

* The 12-byte fault header is immediately followed by `0x0048A55A`, the KE free-block magic.
* `PC = 0x50001500` (`GP_ADC_CTRL_REG`) is the value the dispatcher branched to through `r5`.

The first revision used observation 1 to argue "allocator overlap"; the second used a msgid
rule to argue "freed block decoded as a header". Neither argument survives, but neither
observation was touched by the retractions — they are raw measurements. Anyone resuming this
should start there rather than from any interpretation of them, and should note explicitly
that a plausible-sounding bridge between the two has never been demonstrated.

Provenance, stated because it was silently blurred twice:

* The `msgid` / `dest_id` / `src_id` values come from **stacked registers** `R0`–`R3` in the
  `HardFault_HandlerC` dump at `STATUS_BASE`. That is all the register capture contains.
* `param_len = 0`, and the following `0x0048A55A`, come from a **separate RAM read** of the block
  at `0x07FD599C`. They are not part of the register set, and no single snapshot gives all five
  fields side by side.

Every field list in this document that reads *"msgid=0x0101, dest=0x0001, src=0x00FF,
param_len=0"* is therefore a join across two captures taken at different times. That join is
plausible and probably harmless, but it has never been justified in writing — and a retraction
built on top of such a join is exactly what happened twice.

### Dead ends: why no further experiment in this repo can settle it

Three candidate experiments were proposed across the last three revisions. All three are dead,
each for a concrete reason — two verified here, one taken from the device-side hardware check.
Recorded so
the next reader does not re-derive them.

1. **Instrument `ke_msg_send()` to log headers at send time.** Impossible: `ke_msg_send`
   (`0x07F1BBE2`, from the ROM dump) is mask ROM and is not
   interposable — the symbol resolves into ROM and nothing in our link overrides it. Verified
   here: zero `__EXCLUDE_ROM_*` defines exist anywhere under `firmware/`, so no ROM function is
   being replaced by a RAM copy in this build.
2. **Log from `user_catch_rest_hndl()` instead.** Structurally blind to the target: the
   crashing message faults inside the ROM's dispatch, *before* any application handler runs
   (from the device-side evidence; consistent with the code here — `diag_observe()` is
   called only from `user_catch_rest_hndl`'s `CUSTS1_VAL_WRITE_IND` case, `user_eink_app.c:292`,
   so it can only ever log messages that reached an app handler).
   `diag_observe()` therefore only ever records successfully delivered messages, by
   construction. This is why the previously-suggested "diff the last logged header against the
   crashed one" cannot work — the crashed one is never in the log.
3. **Poll the free list for a corrupted block.** Same dead end as the RAM validator already
   abandoned (§2 · Claims that do not hold): the corruption is transient and is consumed by the
   very dispatch that faults, so a poll observes only the healthy state.

All of the referenced artifacts are available and were re-verified in this checkout: the
`ke_rom_128k.bin` dump and `ke_rom_symbols.csv` (gitignored, regenerable via
`ke_rom_dump.py --rom`), the Ghidra project at `/tmp/opencode/ghidra_proj`, the local SDK at
`~/DA145xx_SDK/6.0.24.1464`, and a live SWD target. The addresses cited throughout §2
(`0x07F1BDDA`, `0x07F11956`, `0x07F10B54`, the heap bounds) can be re-checked here at any time.

**Step zero — RUN 2026-09-28. Result: the fault does NOT reproduce on the production build.**

The test below was re-run in both configurations, one 1-byte write of command `0x08`
(status query; no panel side effect) to the command characteristic, never sending `0x06`.
Reproducer: `stepzero_write_req.py` (`--cmd`, `--noresp`, `--heaps`).

Pool size was read out of each built ELF rather than assumed:

| Build | `rwip_heap_msg_ret` in ELF | msg payload (`heap_size[2]`) |
|---|---|---|
| `EINK_DIAG=0` | `0x77c` = 1916 B (1904 + 12 B mblock) | **1904** |
| `EINK_DIAG=1` | `0x57c` = 1404 B (1392 + 12 B mblock) | **1392** |

| Test | `EINK_DIAG=0` (1904 B) | `EINK_DIAG=1` (1392 B) |
|---|---|---|
| write **with** response | **OK, 3/3 runs** | **fails, 2/2 runs** |
| write *without* response (control) | OK | OK, on the same boot |
| free lists after | all 4 consistent | all 4 consistent |
| `env` heap free | 444 / 616 | 32 / 616 |

`EINK_DIAG=0` with response: the write returned, the link stayed up, the core stayed in
BLE low-power sleep (`PC=0x07FC1304`, `SP=0x07FCF8D0`, unchanged across runs), and all
four free lists were consistent — 3/3.

`EINK_DIAG=1` with response: the ATT layer returned error `0x0E` (*Unlikely Error*) and
the board then **stopped advertising and hung**. On a single boot the control
(write *without* response) succeeded and the very next write *with* response killed it, so
the failure is isolated to `response=True` and is not a timing artefact of the connection.

Two corrections to the record that this test forced:

1. **It is a hang, not a HardFault.** In the `EINK_DIAG=1` runs `IPSR=0x00`, `CFSR=0`,
   `HFSR=0`, `DFR=0` — thread mode, no fault recorded — with `PC=0x07FC1E5C` and
   `LR=0xFFFFFFF9` held steady. So the signature reproduced here is a wedged stack that
   stops advertising, **not** the `ke_queue_insert` HardFault at `0x07F1BDDA` documented
   above. Whether that older HardFault is a *different* failure or a later stage of this
   one is not established; do not treat this run as a reproduction of it.
2. **`ke_rom_dump.py --heaps` was reporting false corruption.** Its free-list bounds were
   hardcoded from the `EINK_DIAG=0` linker map, so on the `EINK_DIAG=1` build it walked
   the wrong memory and printed all four lists as `BROKEN`. The heaps are in fact
   **consistent** on both builds. Bounds are now derived at run time from `ke_env`'s
   `heap[]` / `heap_size[]` (`pointer .. pointer + payload + 12`). This is a direct
   instance of the failure mode the build caveat warned about — an unlabelled number read
   as evidence. **Never walk these heaps without recording the build.**

### What this does and does not establish

* **Established:** the write-with-response failure is *build-configuration dependent* and
  does not occur on the shipping configuration. Continue to use Write Without Response;
  nothing about the production path needs to change.
* **Not established:** that the message heap *size* is the cause. `EINK_DIAG=0` and
  `EINK_DIAG=1` differ in more than pool size — the `user_eink_diag.c` code is compiled in
  and the whole retained-region layout shifts (e.g. msg heap moves
  `0x07FD5404` → `0x07FD564C`) — so this is a 1-bit comparison, n=2 vs n=3, not a
  controlled one. The `env` heap is also nearly exhausted on `EINK_DIAG=1` (32 B free of
  616), which is a plausible alternative contributor and was not separated out.
* **Decisive follow-up if anyone resumes:** build a third configuration that keeps
  `EINK_DIAG=1` but forces `MSG_HEAP_SZ (1904)` unconditionally. That isolates pool size
  from the rest of the diagnostic build in one flash.

**The recommendation to park this stands**, and is now better founded: the failure does
not reproduce in the build we actually ship.

**Beyond that**, moving this requires evidence this repo cannot generate: a second board
for A/B comparison (isolate firmware-state effects from silicon errata), or a Renesas erratum
listing for the DA14585 KE queue/allocator. Absent either, the honest status is *undetermined*.

### Decision: live with it; do not patch

Recorded because it was asked directly, and agreed by both sides of the exchange:

1. The defect (wherever it resolves to) is in mask ROM. The only RAM-side hook is the
   `PATCH_ADDR` controller, and all 22 registers measure their reset value — zero active
   patches. Enabling one redirects a ROM *instruction fetch*, which cannot rewrite a bad
   *message field*. That mismatch is the crux: even a working patch mechanism has no handle
   on this class of defect.
2. Patching would rely on undocumented silicon behaviour in a device that must survive
   field use.
3. The Write-Without-Response pipeline plus the per-chunk receipt bitmap already gives a
   byte-exact 30,000-byte upload, verified over SWD, with the panel untouched unless
   `--refresh` is passed. The crash is avoided structurally, not worked around blindly.

Root cause remains **open**, and now honestly labelled: whether the fault record is an emitted
message or a freed block decoded as a header is **undetermined**, because the fields that would
decide it have no enforceable relationship. Two bugs in this area are fixed and hardware-
verified (heap starvation §1, chunk loss §2b); this one is parked with its dead ends documented.


---

## 3. Linux environment notes

* Toolchain: Arch `arm-none-eabi-gcc` 16.2.0 / binutils 2.47 / newlib 4.6.0. The
  prebuilt Keil `da14585_586.lib` emits `Forcing branch to absolute symbol in Thumb mode`
  warnings — expected, harmless.
* `nano.specs` / `nosys.specs` live in `/usr/arm-none-eabi/lib/`, not `/usr/lib/arm-none-eabi/`.
* `make flash` invokes bare `python3`, which has no `pyocd`. Use
  `make SDK_PATH=~/DA145xx_SDK/6.0.24.1464 PYTHON=../venv/bin/python flash`.
* The Makefile has **no header dependency tracking** — editing a config header will not
  trigger a rebuild. Run `make clean` after changing `user_config.h` or any `-include`d header.
* ST-Link V2.1 enumerates as `0483:3752`, which is **not** in the udev rules in
  `HANDOFF.md` (they cover `3748`/`374b`/`374d`). Access still works because the device
  node gets a seat ACL. `plugdev` does not exist on this system, which is harmless given
  `MODE="0666"`.

---

## 4. Tooling added

| File | Purpose |
|---|---|
| `repro_disconnect.py` | Deterministic reproducer. Streams, triggers refresh, then drops the link mid-cycle. |
| `diag_crc.py` | Reads the retained RAM-CRC history over SWD and diffs it per phase. `--verify` cross-checks the firmware's region table against the linker map. |
| `regen_diag_regions.py` | Regenerates the monitored-region table in `user_eink_diag.c` from the map. Run after any build that changes `.bss` or retained-RAM usage — the table is a hand-partitioned view of RAM and drifts otherwise. |
| `upload_noresp.py` | Uploads over Write Without Response (the working transport). |
| `firmware/ble/user_eink_diag.{c,h}` | Optional (`EINK_DIAG=1`) region-CRC diagnostics plus a log of observed `CUSTS1_VAL_WRITE_IND` messages (`msgid`/`dest`/`src`/`handle`/`length`/routing). |

The `EINK_DIAG=1` build is what produced §1 and §2's evidence. It is off by default so
its ~650 bytes of retained RAM and its CRC32 code stay out of production images.

### Recovering a crashed board

`HardFault_HandlerC` and `NMI_HandlerC` halt in `while(1)` with `CFG_DEVELOPMENT_DEBUG`
defined, so the board stops advertising. A software reset recovers it:

```bash
./venv/bin/python reboot_target.py     # writes AIRCR.SYSRESETREQ = 0x05FA0004
```

Read `IPSR` to tell the three states apart: `0` healthy, `2` NMI/watchdog, `3` HardFault.

---

## 5. Known cosmetic bug

`ble_eink_client.py` prints `Connected! MTU: 23`, which is wrong. bleak 3.x needs
`_acquire_mtu()` before `client.mtu_size` is valid, so the value shown is the
never-negotiated default. The real MTU *is* negotiated — the 242-byte packets prove it.
