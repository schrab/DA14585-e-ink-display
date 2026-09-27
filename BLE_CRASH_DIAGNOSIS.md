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
#define MSG_HEAP_SZ  (1904)   /* was 1392 */
```

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
so `r0 = 0x0101` is the **message id**. `KE_FIRST_MSG(task) = task << 8`, so `0x0101`
means task type 1 (`TASK_ID_LLC`), message 1 — and `dest_id = 0x0001` agrees. The message
is self-consistent; the ROM simply had no valid handler and fell through to garbage.

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
