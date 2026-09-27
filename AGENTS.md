# AGENTS.md — DA14585 E-Ink Display Reverse-Engineering Guide

This document is the primary reference for AI coding agents and human engineers working on the DA14585-based smart display reverse-engineering project.

---

## 1. System Architecture & Hardware Context

* **Target Microcontroller**: Dialog Semiconductor / Renesas **DA14585**
  * **Core**: ARM Cortex-M0 (ARMv6-M architecture, Thumb-1 instruction set)
  * **System Clock**: 16 MHz (Internal RC or 16 MHz XTAL; optional PLL)
  * **Internal Memory**:
    * **SysRAM**: 96 KB total SRAM (divided into 4 cells: 32 KB, 16 KB, 16 KB, 32 KB)
    * **ROM**: 64 KB internal Boot ROM
    * **OTP**: 64 KB One-Time-Programmable Memory (read-only)
    * **No internal flash**: All non-volatile firmware, fonts, graphics, and e-ink display lookup tables (LUTs) reside on an external SPI NOR flash.
* **Storage**: Fudan Micro **FM25Q04** (512 KB SPI NOR Flash, JEDEC ID: `0xA14013`).
* **Display Controller**: Solomon Systech **SSD1619 / SSD1683** family.
* **Display Panel**: 4.2-inch Electronic Paper Display (EPD), **400 x 300 pixels** (Active resolution: 50 bytes x 300 lines = 15,000 bytes 1-bit monochrome/bicolor).
* **Debug Hardware**: ST-Link V2 USB debugger connected via SWD.

---

## 2. Critical Hardware Rules & Safety Constraints

### ⚠️ Rule 1: Reset is Active-HIGH (`RST`)
* **Do NOT connect ST-Link `NRST` to the board!**
* Standard ARM debuggers pull `NRST` active-LOW. The DA14585 reset line is **active-HIGH** (pulled low on-board; pulled to 3.3V to reset).
* Connecting an active-low debugger reset pin will hold the chip in permanent reset or cause bus contention.
* PyOCD must always be run with `connect_mode="attach"` or software reset (`reset_type="software"`).

### ⚠️ Rule 2: Extended Sleep & PD_DBG Power-Down
* Production firmware on the DA14585 puts the SoC into Extended or Deep Sleep between BLE advertising events or e-ink refreshes.
* In sleep mode:
  1. The 16 MHz high-speed oscillator is stopped.
  2. Power domain `PD_DBG` (Debug Power Domain) is powered off.
* **Symptom**: SWD fails with `ProbeError: STLink error (9): Get IDCODE error`.
* **Remedy**:
  * Run the probe script with aggressive retry loops (`--timeout 30`).
  * Power-cycle the target board or momentarily touch the `RST` pad to 3.3V.
  * On reset, the internal Boot ROM executes for ~100 ms before entering sleep. The debugger will latch onto the core during this window.

### ⚠️ Rule 3: Watchdog Freezing (`SET_FREEZE_REG`)
* The DA14585 has an active hardware NMI watchdog (`WATCHDOG_REG` at `0x50003102`).
* When the Cortex-M0 is halted by SWD, the watchdog continues running and will trigger a hardware reset or NMI after ~2.6 seconds.
* **Mandatory Action**: Whenever the target core is halted, immediately write `0x0008` (bit 3 `FRZ_WDOG`) to `SET_FREEZE_REG` (`0x50003300`).

---

## 3. Hardware Pinout & GPIO Multiplexing Map

The firmware uses an efficient multiplexing scheme where SPI lines are shared between the external SPI NOR flash and the E-Ink display controller:

| Pin | Function Name | Direction | Active Level | Default State | Description |
|---|---|---|---|---|---|
| **`P0_0`** | `SPI_CLK` | Output | Clock Pulse | Low | Shared SPI Clock for Flash & E-Ink controller (`epd_write_byte`) |
| **`P0_3`** | `FLASH_CS` | Output | Active-LOW | High (Inactive) | External SPI NOR Flash Chip Select |
| **`P0_4`** | `STATUS_LED` | Output | Active-LOW / Pulse | High / Hi-Z | Status LED indicator (toggled during BLE events & display update) |
| **`P0_5`** | `EPD_DC` / `FLASH_MISO` | Multiplexed | D/C: 0=Cmd, 1=Data | Low | Multiplexed: SPI Flash MISO input during flash reads; E-Ink Data/Command output during screen updates |
| **`P0_6`** | `SPI_MOSI` | Output | Data bit | Low | Shared SPI Master Out Slave In (`DIN` to display, `DI` to flash) |
| **`P0_7`** | `EPD_RST` | Output | Active-LOW | High (Inactive) | Display Hardware Reset (pulse: High $\rightarrow$ Low 20ms $\rightarrow$ High 20ms) |
| **`P2_0`** | `EPD_BUSY` | Input | Active-HIGH | Low (Idle) | Display Busy Line (`1` = Busy executing command/refresh, `0` = Idle / Ready) |
| **`P2_1`** | `EPD_CS` | Output | Active-LOW | High (Inactive) | Display Controller Chip Select |
| **`P2_3`** | `EPD_PWR_EN` | Output | Active-HIGH | Low (Off) | Display Power / High-Voltage PMIC & Boost Converter Enable |

---

## 4. Memory Map & Register Reference

### Memory Layout
| Address Range | Size | Region | Description |
|---|---|---|---|
| `0x0000_0000 - 0x0007_FFFF` | 512 KB | Remapped Area | Aliased to Boot ROM, OTP, or SysRAM via `SYS_CTRL_REG.REMAP_ADR0` |
| `0x07FC_0000 - 0x07FC_7FFF` | 32 KB | **SysRAM1** | Base of SysRAM; holds vector table & main application image |
| `0x07FC_8000 - 0x07FC_BFFF` | 16 KB | **SysRAM2** | Heap / BLE exchange memory |
| `0x07FC_C000 - 0x07FC_FFFF` | 16 KB | **SysRAM3** | Data / Stack / **Image Framebuffer (`0x07FCF908`)** |
| `0x07FD_0000 - 0x07FD_7FFF` | 32 KB | **SysRAM4** | High SysRAM; scratchpad for RAM loader stub |
| `0x4000_0000 - 0x4001_FFFF` | 64 KB | **OTP ROM** | One-Time-Programmable memory (headers, BD address) |
| `0x5000_0000 - 0x5000_33FF` | — | **Peripherals** | Memory-mapped control and status registers |

### Key Hardware Registers
* `SYS_CTRL_REG` (`0x50000012`, 16-bit):
  * Bit 15: `DEBUGGER_ENABLE` (1 = keep SWD interface powered)
  * Bits 1:0: `REMAP_ADR0` (0 = ROM @ 0x0, 1/2 = OTP @ 0x0, 3 = SysRAM @ 0x0)
* `SET_FREEZE_REG` (`0x50003300`, 16-bit):
  * Bit 3: `FRZ_WDOG` (1 = freeze watchdog timer during halt)
* `P0_DATA_REG` (`0x50003000`), `P0_SET_DATA_REG` (`0x50003002`), `P0_RESET_DATA_REG` (`0x50003004`)
* `P2_DATA_REG` (`0x50003040`), `P2_SET_DATA_REG` (`0x50003042`), `P2_RESET_DATA_REG` (`0x50003044`)

---

## 5. E-Ink Display Controller Architecture (SSD1619 / SSD1683)

### Display Dimensions & Framebuffer
* **Resolution**: 400 pixels (width) $\times$ 300 pixels (height).
* **Scanline Size**: $400 / 8 = 50$ bytes (`0x32`).
* **Total Frame Size**: $50 \times 300 = 15,000$ bytes (1-bit monochrome).
* **RAM Framebuffer Address**: `0x07FCF908` in SysRAM3.
* **Transmission Slicing**: To prevent BLE connection timeouts, the firmware transfers data in 6 batches of 50 scanlines (2,500 bytes per slice), yielding to the BLE task between slices.

### Controller Command Sequence (Reverse-Engineered from `0x07FC28DC` & `0x07FC2948`)
1. **Power Up**:
   * Set `P2_3` (`EPD_PWR_EN`) = `1` (Enable boost converter / PMIC).
   * Delay 20 ms.
2. **Hardware Reset**:
   * Pulse `P0_7` (`EPD_RST`): `High` $\rightarrow$ `Low` (20 ms) $\rightarrow$ `High` (20 ms).
   * Wait for `P2_0` (`EPD_BUSY`) == `0`.
3. **Software Initialization**:
   * Command `0x12` (`SW_RESET`).
   * Wait for `P2_0` (`EPD_BUSY`) == `0`.
   * Command `0x3C` (`BORDER_WAVEFORM_CONTROL`): Data `0x01`.
   * Command `0x18` (`TEMP_SENSOR_CONTROL`): Data `0x80`.
   * Command `0x11` (`DATA_ENTRY_MODE`): Data `0x03` (AM=0: X-mode, ID[1:0]=11: X increment, Y increment).
   * Command `0x44` (`SET_RAM_X_START_END`): Data `0x00`, `0x31` (0 to 49 = 50 bytes = 400 pixels).
   * Command `0x45` (`SET_RAM_Y_START_END`): Data `0x00`, `0x00`, `0x2B`, `0x01` (0 to 299 = 300 lines).
   * Command `0x4E` (`SET_RAM_X_COUNTER`): Data `0x00`.
   * Command `0x4F` (`SET_RAM_Y_COUNTER`): Data `0x00`, `0x00`.
4. **RAM Streaming (Tri-Color Black / White / Red)**:
   * **RAM Plane 1: Black/White RAM** via Command `0x24` (`WRITE_RAM_BW`): Streams 15,000 bytes.
     * `1` = White / Red pixel
     * `0` = Black pixel
   * **RAM Plane 2: Red RAM** via Command `0x26` (`WRITE_RAM_RED`): Streams 15,000 bytes.
     * `1` = Red pixel
     * `0` = Non-Red pixel (Black or White)
   * **Tri-Color Pixel Truth Table**:
     | Desired Color | `0x24` (BW Bit) | `0x26` (RED Bit) | Electrophoretic Result |
     |---|---|---|---|
     | **White** | `1` | `0` | Clean white reflective background |
     | **Black** | `0` | `0` | Deep black pigment |
     | **Red** | `1` | `1` | High-chroma electrophoretic red particles |
5. **Display Refresh & Power Down**:
   * Command `0x22` (`DISPLAY_UPDATE_CONTROL_2`): Data `0xF7` (Display mode 1, enable clocks, enable CP, refresh, disable CP, disable clocks).
   * Command `0x20` (`MASTER_ACTIVATION`): Triggers panel refresh.
   * Wait for `P2_0` (`EPD_BUSY`) == `0` while petting watchdog (Measured hardware duration: **17.08 seconds** for physical electrophoretic particle alignment).
   * Command `0x10` (`DEEP_SLEEP_MODE`): Data `0x01`.
   * Set `P2_3` (`EPD_PWR_EN`) = `0` (Shut down PMIC).
6. **Bi-Stable Image Retention & Stock Firmware Warning**:
   * E-Ink displays are intrinsically bi-stable: once drawn, the image remains indefinitely without power (0.00 µA current draw).
   * **Important**: If the DA14585 watchdog resets the SoC, the factory production firmware in SPI flash will boot, clear the screen buffer to all white (`0xFF`), and trigger a blank screen refresh.
   * To maintain a custom image, either maintain power while keeping the CPU in an idle loop that periodically feeds `WATCHDOG_REG` (`0x50003100 = 0xC8`), or disconnect power completely.

---

## 6. Bluetooth Low Energy (BLE) Profile & Protocol

### Advertising & Device Identity
* **Complete Local Name**: `EINK-V115-42000` (or `EINK-V113-42000`)
* **Manufacturer Specific Data**: `0xCDAB` (Type `0xFF`, 5 bytes payload)
* **Default BD Address**: Defined in NVDS at flash `0x040000` (e.g. `11:E9:8F:9E:2A:86`)

### GATT Services & Characteristics

#### 1. Custom Display Service (Primary Service)
* **Service 128-bit UUID**:
  * **RFC4122 Format**: `afdbecdd-1234-abcd-2007-aabbccddeeff`
  * **Wire / Little-Endian**: `FF EE DD CC BB AA 07 20 CD AB 34 12 DD EC DB AF`

#### 2. Command / Control Characteristic (`0x07FCD435`)
* **Characteristic 128-bit UUID**:
  * **RFC4122 Format**: `9e1547ba-c365-57b5-2947-c5e1c1e1d528`
  * **Wire / Little-Endian**: `28 D5 E1 C1 E1 C5 47 29 B5 57 65 C3 BA 47 15 9E`
* **Properties**: Write, Notify (Max Length: 20 bytes)
* **Framing Protocol**:
  * Byte 0: Command ID (`0x06` Refresh Screen, `0x07` Clear Screen, `0x08` Status Query, etc.)
  * Byte 1: Payload Length
  * Bytes 2..N: Command Parameters

#### 3. Image Data Stream Characteristic (`0x07FCD445`)
* **Characteristic 128-bit UUID**:
  * **RFC4122 Format**: `772ae377-b3d2-4f8e-4042-5481d121199c`
  * **Wire / Little-Endian**: `9C 19 21 D1 81 54 42 40 8E 4F D2 B3 77 E3 2A 77`
* **Properties**: Write Without Response / Write (Max Length: **247 bytes** MTU)
* **Usage**: Pushes raw or compressed 1-bit scanline chunks directly into the RAM framebuffer at `0x07FCF908`.

#### 4. Standard Device Information Service (DIS, UUID `0x180A`)
* **Manufacturer Name** (`0x2A29`): String
* **Model Number** (`0x2A24`): `"EINK-V115-42000"`
* **Firmware Revision** (`0x2A26`): `"6.0.22.1401"`
* **Hardware Revision** (`0x2A27`): `"DA14585-EINK-V1.1"`

---

## 7. Flash Partition Map & Carved Files

| Offset Range | Size | Component | Extracted File | Description |
|---|---|---|---|---|
| `0x000000 - 0x004000` | 16 KB | Secondary Bootloader | [`da14585_bootloader.bin`](file:///C:/Users/schra/Developer/DA14585-eink-display/da14585_bootloader.bin) | Boot header `0x70 0x50` & bootloader |
| `0x004000 - 0x0136C8` | 61.7 KB | **Firmware Image 1** | [`da14585_fw_image1.bin`](file:///C:/Users/schra/Developer/DA14585-eink-display/da14585_fw_image1.bin) | **Active Application Image** (SDK 6.0.22.1401) |
| `0x01F000 - 0x02E6C0` | 61.7 KB | **Firmware Image 2** | [`da14585_fw_image2.bin`](file:///C:/Users/schra/Developer/DA14585-eink-display/da14585_fw_image2.bin) | **OTA Backup Image** (CRC: `0xFEFDC86E`) |
| `0x02E000 - 0x02F000` | 1.75 KB | Display Waveform LUTs | Included in flash dump | 1,792 bytes of factory waveform LUT tables |
| `0x038000 - 0x038020` | 32 B | Product Header | Included in flash dump | Header `0x70 0x52` pointing to Images 1 & 2 |
| `0x040000 - 0x040080` | 128 B | NVDS / Calibration | [`da14585_nvds_calib.bin`](file:///C:/Users/schra/Developer/DA14585-eink-display/da14585_nvds_calib.bin) | Bluetooth device address & RF trimming |
| `0x040080 - 0x080000` | ~256 KB | Unused Flash | Erased (`0xFF`) | Empty space on 512 KB NOR chip |

---

## 8. Reverse-Engineering Roadmap & Status

```
+-----------------------------------------------------------------------+
| PHASE 1: Hardware Bring-Up & RAM Inspection (COMPLETED)               |
| - Verified SWD connectivity with ST-Link V2                           |
| - Halted core, froze watchdog, decoded ARM vector table               |
| - Dumped complete 96 KB SysRAM (da14585_full_ram_96k.bin)             |
| - Extracted device name: EINK-V115-42000, SDK v_6.0.22.1401           |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
| PHASE 2: External SPI Flash Extraction (COMPLETED)                    |
| - Identified SPI Flash GPIO pinout: CS=P0_3, CLK=P0_0, MOSI=P0_6,     |
|   MISO=P0_5                                                           |
| - Read JEDEC ID 0xA14013: Fudan Micro FM25Q04 (512 KB)                |
| - Extracted complete 512 KB flash image (da14585_spi_flash_512k.bin)  |
| - Carved active partitions: Bootloader, Image 1, Image 2, NVDS        |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
| PHASE 3: Firmware & Asset Decompilation (COMPLETED)                   |
| - Disassembled active firmware image (da14585_fw_image1.bin)          |
| - Decoded full GPIO pinout: P2_3 (PWR), P2_0 (BUSY), P0_7 (RST),      |
|   P2_1 (CS), P0_5 (DC), P0_0 (CLK), P0_6 (MOSI), P0_4 (LED)           |
| - Identified Display Controller: Solomon Systech SSD1619 (400x300)   |
| - Located 1792-byte Waveform LUT block at flash 0x02E000              |
| - Extracted custom BLE Service UUID (afdbecdd-...) & Characteristics  |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
| PHASE 4: Custom Drivers & Hardware Verification (COMPLETED)           |
| - Verified in-silicon 400x300 monochrome refresh (test_eink_hardware) |
| - Verified in-silicon 400x300 tri-color refresh (test_eink_red)      |
| - Reverse-engineered dual-buffer 3-color RAM plane mapping (0x24/0x26)|
| - Implemented active watchdog retention loop (bypasses stock wipe)    |
| - Developed open-source bare-metal C driver (ssd1619.h / ssd1619.c)   |
| - Built Python BLE GATT transmitter (ble_eink_client.py)              |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
| PHASE 5: Standalone Toolchain & SPI NOR Flash Writer (COMPLETED)      |
| - Set up GNU Arm Embedded Toolchain 14.2 & GNU Make 3.81             |
| - Reverse-engineered firmware flash write/erase routines & opcodes    |
| - Built 1008-byte zero-dependency RAM flasher stub (flash_raw.c/bin)  |
| - Built standalone ST-Link V2 SPI flash writer (flash_spi_firmware.py)|
| - In-silicon verified 4KB sector erase, page write, and verify        |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
| PHASE 6: Custom Bare-Metal C Firmware & Flash Boot (COMPLETED)        |
| - Developed standalone GNU Make + GCC project in firmware/            |
| - Implemented SysRAM1 linker script (ldscript_da14585.ld)             |
| - Resolved CMSIS Cortex-M0 zero-table unaligned fault (byte count)   |
| - Built standalone Dialog image packager (firmware/mkimage.py)        |
| - Reverse-engineered Dialog Boot ROM & Secondary Bootloader handoff:  |
|   * Product Header at 0x038000 (0x70 0x52)                            |
|   * 64-byte s_imageHeader (0x70 0x51), CRC32, and imageid arbitration |
|   * Start_run_user_application() SW_RESET via SYS_CTRL_REG (REMAP=2)  |
| - Successfully programmed & verified permanent boot from flash        |
| - Board boots standalone into custom firmware on hardware reset       |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
| PHASE 7: Custom BLE Peripheral Stack & OTA Image Streaming (COMPLETED)|
| - Integrated full Renesas/Dialog DA145xx SDK BLE stack (rwip/ke/gapc) |
| - Resolved linker script stack bug: allocated 2KB stack (ldscript_ble)|
| - Implemented custom 128-bit GATT service (afdbecdd-...) & chars     |
| - Fixed disconnect assertion (user_app_adv_undirect_complete status)  |
| - Added deferred refresh timer (app_easy_timer 100ms) for GATT ACK    |
| - In-silicon verified wireless 30KB dual-plane image transmission     |
| - Board boots, advertises as EINK-V115-42000, receives tri-color      |
|   graphics over BLE, and renders flawlessly to physical E-Ink display!|
+-----------------------------------------------------------------------+
```

---

## 8b. ⚠️ RAM Budget & Known Firmware Bugs

**The RAM budget is the binding constraint on any further firmware work.** This SoC has
no internal flash — the application executes from SysRAM1, so code, data, the 30 KB
framebuffer, the stacks and the BLE heaps all compete for the same 96 KB.

| Region | Bytes |
|---|---|
| `code` (.text + .rodata) | 30,944 |
| `data` + `.bss` — `eink_framebuffer` is 30,000 and `eink_chunk_map` 16 of this | 30,332 |
| `rwip_heap_non_ret` | 1,036 |
| main stack | 2,048 |
| `RET_HEAP` (env 628 + db 1,036 + msg 1,916) | 3,580 |
| **slack left in `LR_RETAINED_RAM0`** | **128** |

`eink_framebuffer` is **91 % of `.bss`**. The retained region is full, so the KE message
heap cannot grow further without shrinking the framebuffer.

### Three known bugs — see [`BLE_CRASH_DIAGNOSIS.md`](BLE_CRASH_DIAGNOSIS.md)

1. **FIXED — KE message heap starvation.** `jump_table.c` hard-codes the only KE message
   pool (`rwip_heap_msg_ret`) to 1392 B. Streaming 30 KB at MTU 247 (~250 B per message)
   exhausted it, and the allocator returned blocks overlapping freed ones — the watchdog
   then reset the board. Fixed by `#define MSG_HEAP_SZ (1904)` in `user_config.h`.
   **Do not reduce this value.**

1. **OPEN, but does not reproduce in production — HardFault/hang on ATT Write Request.**
   Write *with* response (`response=True`) was believed to fault in the ROM's
   `ke_queue_insert` (`blx r5` @ `0x07F1BDDA`, LR `0x07F1BDDD`), which
   dispatches a garbage handler `0x50001500` = `GP_ADC_CTRL_REG`.
   **Step zero (2026-09-28) narrows this sharply:** the failure is build-configuration
   dependent. On `EINK_DIAG=0` (the shipping build, `MSG_HEAP_SZ=1904`) a 1-byte
   write-with-response succeeds **3/3**; on `EINK_DIAG=1` (1392 B pool) it fails **2/2**,
   and there it presents as a *hang* (`IPSR=0`, `CFSR=0`, advertising stops) rather than
   the HardFault above. Root cause remains undetermined; the two builds differ in more than
   pool size, so size is **not** established as the cause. Write *without* response works in
   both. **Use Write Without Response; do not attempt a ROM patch** (the `PATCH_ADDR`
   controller redirects instruction fetches, not message fields, and all 22 registers
   measure their reset value). Do not restart the investigation from either retired
   framing — whether the crash-site header is an emitted message or a freed block decoded
   as a header cannot be decided from its own fields, since msgid bytes identify the
   defining module and enum index, not dest/src. Two readings have been written and
   retracted on exactly this mistake (the second time, the *retraction* cited a `KE_MSG_ID`
   macro that does not exist in the SDK). Do not propose send-time logging or a free-list
   poll: both are recorded as dead ends in
   [`BLE_CRASH_DIAGNOSIS.md`](BLE_CRASH_DIAGNOSIS.md) §2.

2. **FIXED — silent chunk loss.** Write Commands have no link-layer retransmission, so the
   host outruns the peripheral and chunks are dropped. This is a **contiguous band, not
   just the tail**, so a byte counter cannot detect it. `user_eink_app.h` now defines a
   240-byte wire chunk (`EINK_CHUNK_SIZE`, 125 chunks); `eink_chunk_map[16]` records
   receipt per chunk and command `0x08` notifies the bitmap. `upload_noresp.py` re-sends
   only the missing chunks and now yields a **byte-exact 30,000-byte upload**.

### Operational notes
* `make flash` needs `PYTHON=../venv/bin/python` (bare `python3` has no `pyocd`).
* The Makefile has **no header dependency tracking** — `make clean` after editing any
  `-include`d config header.
* A faulted or wedged board stops advertising. Recover with
  `./venv/bin/python reboot_target.py`.
* **Always label heap/KE numbers with the build that produced them.** `MSG_HEAP_SZ` is
  `#if !EINK_DIAG`, so the retained layout differs between builds. `ke_rom_dump.py --heaps`
  now derives free-list bounds from `ke_env` at run time; before that it used
  `EINK_DIAG=0` addresses hardcoded and reported healthy `EINK_DIAG=1` heaps as `BROKEN`.
* `stepzero_write_req.py` is the panel-safe reproducer for the Write-Request question: it
  sends one small command and refuses `0x06` so it cannot refresh the display.
  `IPSR`: `0` healthy, `2` NMI/watchdog, `3` HardFault.

---

## 9. DA14585 Bootloader & Dual-Image Architecture

### Boot Flow & Reset Stages
1. **Cold Reset / Power-On**:
   * Hardware pulls `SYS_CTRL_REG.REMAP_ADR0 = 0` (Internal Boot ROM aliased to `0x00000000`).
   * Boot ROM checks SPI pins (`P0_0` CLK, `P0_3` CS, `P0_5` MISO, `P0_6` MOSI).
   * Reads 8-byte AN-B-001 SPI Header at `0x000000` of SPI flash (`0x70 0x50`, length `0x2816` = 10,262 bytes).
   * Copies 10,262 bytes into `SYSRAM_BASE_ADDRESS` (`0x07FC0000`).
   * Executes **Secondary Bootloader** (`da14585_bootloader.bin`) at `0x07FC00B5`.
2. **Secondary Bootloader Execution**:
   * Bootloader relocates SPI flash driver functions into SysRAM4 (`0x07FD6000`), allowing the lower SysRAM1 (`0x07FC0000`) to be overwritten.
   * Reads **Product Header** at `0x038000`:
     * Magic: `0x70 0x52` (`pR`)
     * Offset 1: `0x004000` (Image 1)
     * Offset 2: `0x01F000` (Image 2)
   * Reads 64-byte Image Headers from Image 1 and Image 2:
     * Magic: `0x70 0x51` (`pQ`), Valid Flag: `0xAA`
     * Evaluates `findlatest(id1, id2)`: Image with highest ID is chosen (Image 1 ID `3` supersedes Image 2 ID `2`).
   * Copies selected image code into `0x07FC0000`.
   * Verifies CRC32 (`crc32(0, 0x07FC0000, code_size) == ImageHeader->CRC`).
   * Calls `Start_run_user_application()`:
     ```c
     // Remap address 0 to SysRAM1 (0x07FC0000) and trigger Software Reset
     SetWord16(SYS_CTRL_REG, (GetWord16(SYS_CTRL_REG) & ~0x0003) | 0x0002 | 0x8000);
     ```
3. **Application Boot**:
   * Cortex-M0 resets. Because `REMAP_ADR0 == 2`, address `0x00000000` maps to `0x07FC0000`.
   * Core fetches Initial SP from `0x07FC0000` and Reset_Handler from `0x07FC0004`.
   * Custom application executes!

### 64-Byte Image Header (`s_imageHeader`) Format
| Byte Offset | Size | Field Name | Value / Description |
|:---:|:---:|:---|:---|
| `0x00 - 0x01` | 2 B | `signature` | `0x70 0x51` (`pQ`) |
| `0x02` | 1 B | `validflag` | `0xAA` (`STATUS_VALID_IMAGE`) |
| `0x03` | 1 B | `imageid` | Integer sequence ID (`3` to supersede factory image ID `2`) |
| `0x04 - 0x07` | 4 B | `code_size` | Length of application binary in bytes (little-endian) |
| `0x08 - 0x0B` | 4 B | `CRC` | Standard CRC-32 (zlib / IEEE 802.3) of application binary |
| `0x0C - 0x1B` | 16 B | `version` | Null-terminated ASCII version string, padded with `0xFF` |
| `0x1C - 0x1F` | 4 B | `timestamp` | Unix epoch timestamp (little-endian unsigned 32-bit int) |
| `0x20` | 1 B | `flags` | `0x00` |
| `0x21` | 1 B | `encryption_pad` | `0x00` |
| `0x22 - 0x27` | 6 B | `keyInfo` | `0xFF` * 6 (unused / unencrypted) |
| `0x28 - 0x3F` | 24 B | `reserved` | `0xFF` * 24 |

---

## 10. Tooling Reference

* [`HANDOFF.md`](file:///C:/Users/schra/Developer/DA14585-eink-display/HANDOFF.md): Comprehensive developer guide for setting up, building, flashing, and running BLE image uploads on a Linux machine with the original DA145xx SDK.
* [`firmware/ble/`](file:///C:/Users/schra/Developer/DA14585-eink-display/firmware/ble/): Custom BLE peripheral application source code (`user_eink_app.c`, `user_custs1_def.c`, `user_custs_config.c`, configuration headers).
* [`firmware/ldscript_ble.lds.S`](file:///C:/Users/schra/Developer/DA14585-eink-display/firmware/ldscript_ble.lds.S): Custom linker script preprocessor template fixing zero-size stack bug with 2 KB dedicated stack allocation at `0x07FCF700`.
* [`firmware/Makefile`](file:///C:/Users/schra/Developer/DA14585-eink-display/firmware/Makefile): Automated cross-platform build pipeline (Linux + Windows) for compiling SDK BLE stack and flashing (`make all`, `make flash`, `make clean`).
* [`firmware/mkimage.py`](file:///C:/Users/schra/Developer/DA14585-eink-display/firmware/mkimage.py): Standalone Python packager that creates 64-byte Dialog Image Headers with bit-exact CRC-32 calculation.
* [`ble_eink_client.py`](file:///C:/Users/schra/Developer/DA14585-eink-display/ble_eink_client.py): Python Bleak-based wireless image transmitter supporting 30,000-byte tri-color streaming at ~7.6 KB/s and display refresh triggers.
* [`upload_noresp.py`](upload_noresp.py): Uploader over ATT Write Without Response — the only transport that does not currently hardfault.
* [`repro_disconnect.py`](repro_disconnect.py): Deterministic reproducer for the mid-refresh disconnect fault.
* [`diag_crc.py`](diag_crc.py) + [`regen_diag_regions.py`](regen_diag_regions.py): SWD reader/differ for the retained RAM-CRC snapshot history, and the generator for its region table.
* [`BLE_CRASH_DIAGNOSIS.md`](BLE_CRASH_DIAGNOSIS.md): Full write-up of the KE message heap starvation fix and the open Write-With-Request HardFault.
* [`flash_spi_firmware.py`](file:///C:/Users/schra/Developer/DA14585-eink-display/flash_spi_firmware.py): Standalone open-source SPI NOR flash programmer using ST-Link V2 (SWD). Includes embedded 1,008-byte Thumb-1 flasher stub (`flash_raw.bin`), sector erase, page write, read, verify, and software reset.
* [`flash_raw.c`](file:///C:/Users/schra/Developer/DA14585-eink-display/flash_raw.c) / [`flash_raw.bin`](file:///C:/Users/schra/Developer/DA14585-eink-display/flash_raw.bin): Pure standalone C Cortex-M0 RAM stub for bit-banged SPI NOR flash communication with automatic PMU wake, flash sleep exit (`0xAB`), and watchdog reload.
* [`check_target_now.py`](file:///C:/Users/schra/Developer/DA14585-eink-display/check_target_now.py): Real-time core state, PC, register, and GPIO inspector.
* [`ssd1619.h`](file:///C:/Users/schra/Developer/DA14585-eink-display/ssd1619.h) / [`ssd1619.c`](file:///C:/Users/schra/Developer/DA14585-eink-display/ssd1619.c): Standalone C driver for SSD1619 / SSD1683 displays with monochrome & tri-color API.
* [`display_image.py`](file:///C:/Users/schra/Developer/DA14585-eink-display/display_image.py): Universal image pipeline converting PNG/BMP graphics into dual-buffer tri-color e-ink framebuffers and flashing to hardware.
* [`test_eink_red.py`](file:///C:/Users/schra/Developer/DA14585-eink-display/test_eink_red.py): Injects dual-buffer tri-color graphics into SysRAM and drives physical 3-color panel refresh.
* [`generate_red_test_image.py`](file:///C:/Users/schra/Developer/DA14585-eink-display/generate_red_test_image.py): Generates 400x300 tri-color test image and splits into dual 15,000-byte BW and Red buffers.
* [`dump_spi_flash.py`](file:///C:/Users/schra/Developer/DA14585-eink-display/dump_spi_flash.py): SWD RAM-injected high-speed SPI NOR flash dumper.
* [`extract_partitions.py`](file:///C:/Users/schra/Developer/DA14585-eink-display/extract_partitions.py): Flash partition carver for bootloader, dual app images, and NVDS.

