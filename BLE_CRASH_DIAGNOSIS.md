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

The caveat is that Write Commands have **no link-layer retransmission**, so the host can
outrun the peripheral and the tail is silently dropped — 160 bytes lost at 14.4 KB/s.
This is a transport property, not corruption. The image protocol is already idempotent
(every packet is a `memcpy` at an explicit offset), so the robust fix is client-side:
re-send the tail, or poll command `0x08` (which notifies `eink_rx_bytes`) until it reads
30000.

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
