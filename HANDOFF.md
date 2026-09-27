# DA14585 E-Ink Display — Developer Handoff Guide

This document is the complete guide for continuing development, compilation, flashing, and wireless BLE image streaming on a **Linux machine** with a fresh environment and the original **Renesas / Dialog DA145xx SDK (v6.0.24.1464 or v6.0.22.1401)**.

> **Read [`BLE_CRASH_DIAGNOSIS.md`](BLE_CRASH_DIAGNOSIS.md) before changing the build, the
> KE heap sizes, or the BLE transport.** It documents a fixed KE-message-heap starvation
> bug, an **unresolved** HardFault on any ATT Write Request (with two withdrawn analyses
> recorded, so the dead ends are not repeated), and the environment gotchas in §3 below.

---

## 1. System & Hardware Summary

* **Target SoC**: Dialog / Renesas **DA14585** (ARM Cortex-M0 @ 16 MHz, 96 KB SysRAM).
* **Storage**: Fudan Micro **FM25Q04** (512 KB SPI NOR Flash).
* **Display**: 4.2-inch Tri-Color E-Paper Display (400 &times; 300 pixels, Solomon Systech **SSD1619** controller).
* **Debug Probe**: ST-Link V2 USB connected via SWD.
* **Firmware Location**: Stored in SPI Flash **Image 1** (`0x004000`), packaged with a 64-byte Dialog Image Header (`s_imageHeader`, imageid &ge; 3).

---

## 2. Linux Environment Setup

### A. Install Toolchain & System Packages
On Ubuntu / Debian:
```bash
sudo apt update
sudo apt install -y \
    gcc-arm-none-eabi \
    binutils-arm-none-eabi \
    libnewlib-arm-none-eabi \
    build-essential \
    make \
    python3 \
    python3-pip \
    python3-venv \
    bluez \
    libusb-1.0-0-dev \
    git
```

On Arch Linux:
```bash
sudo pacman -S arm-none-eabi-gcc arm-none-eabi-binutils arm-none-eabi-newlib make python python-pip bluez bluez-utils
```

### B. Python Virtual Environment & Dependencies
```bash
# In the repository root:
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install pyocd bleak pillow
```

### C. ST-Link V2 Linux Udev Rules
To allow `pyocd` to talk to the ST-Link V2 without requiring `sudo`:
```bash
sudo tee /etc/udev/rules.d/49-stlinkv2.rules << 'EOF'
# ST-Link / V2
SUBSYSTEMS=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="3748", MODE="0666", GROUP="plugdev"
# ST-Link / V2-1
SUBSYSTEMS=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="374b", MODE="0666", GROUP="plugdev"
# ST-Link / V3
SUBSYSTEMS=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="374d", MODE="0666", GROUP="plugdev"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger
sudo usermod -aG plugdev $USER
# Log out and log back in, or run: newgrp plugdev
```

Verify your ST-Link is recognized:
```bash
pyocd list
```

---

## 3. Hardware Connection & Critical Rules

### ST-Link V2 &rarr; DA14585 Wiring
```text
ST-Link V2 Pin      DA14585 Test Pad
--------------      ----------------
GND            <->  GND
3.3V           <->  3.3V / VDD
SWDIO          <->  SWDIO
SWCLK          <->  SWCLK
NRST           <->  [DO NOT CONNECT!]
```

### ⚠️ Critical Hardware Constraints
1. **Reset is Active-HIGH (`RST`)**:
   * **Never connect ST-Link `NRST` to the board!** Standard debuggers assert active-LOW reset, which permanently resets the DA14585.
   * `pyocd` and `flash_spi_firmware.py` always use `connect_mode="attach"`.
2. **Extended Sleep & Debugger Latch**:
   * The DA14585 powers down its debug power domain (`PD_DBG`) during BLE sleep.
   * If SWD fails with `Get IDCODE error`, momentarily touch the board's `RST` pad to 3.3V while running the script with retry loops. The Boot ROM runs for ~100 ms on reset, allowing SWD to latch.
3. **Hardware Watchdog (`WATCHDOG_REG` at `0x50003100`)**:
   * Watchdog expires in ~2.6 seconds if not petted.
   * When halted via SWD, immediately freeze it: `SET_FREEZE_REG` (`0x50003300 = 0x0008`).

---

## 4. DA145xx SDK Directory Layout on Linux

Download or extract the Renesas/Dialog DA145xx SDK (e.g. `DA145xx_SDK_v_6.0.24.1464.zip`) into a directory of your choice, for example:
```bash
mkdir -p ~/DA145xx_SDK
unzip DA145xx_SDK_v_6.0.24.1464.zip -d ~/DA145xx_SDK/6.0.24.1464
```

Verify the following directory exists:
`~/DA145xx_SDK/6.0.24.1464/sdk/platform/arch/main/arch_main.c`

---

## 5. Building the BLE Firmware on Linux

The build system in `firmware/` uses standard GNU Make, GCC, and `python3`:

```bash
cd firmware

# Build firmware (specify your SDK_PATH):
make SDK_PATH=~/DA145xx_SDK/6.0.24.1464 all
```

### ⚠️ Build gotchas
* **`make flash` calls bare `python3`, which has no `pyocd`.** Use
  `make SDK_PATH=~/DA145xx_SDK/6.0.24.1464 PYTHON=../venv/bin/python flash`.
* **There is no header dependency tracking.** After editing `user_config.h` or any
  `-include`d config header, run `make clean` or your change will be silently ignored.
* The prebuilt Keil `da14585_586.lib` produces `Forcing branch to absolute symbol in
  Thumb mode` warnings. These are expected and harmless.
* `MSG_HEAP_SZ` in `user_config.h` is load-bearing — see
  [`BLE_CRASH_DIAGNOSIS.md`](BLE_CRASH_DIAGNOSIS.md) §1 before changing it.

### Build Output:
* `build/eink_ble_firmware.elf`: Linked ELF with complete symbol and debug table.
* `build/eink_ble_firmware.bin`: Raw ARM Cortex-M0 binary (~30 KB).
* `build/eink_ble_firmware.img`: Packaged binary with 64-byte Dialog Image Header (`s_imageHeader`, imageid=3, CRC-32).

---

## 6. Flashing to Hardware via ST-Link V2

Program directly to external SPI NOR Flash Image 1 at offset `0x004000`:
```bash
# From firmware/ directory:
make SDK_PATH=~/DA145xx_SDK/6.0.24.1464 flash

# Or from repository root:
python3 flash_spi_firmware.py write firmware/build/eink_ble_firmware.img --addr 0x004000 --reset
```

The flasher automatically:
1. Connects to the DA14585 over SWD (hot-attach).
2. Injects a 1,008-byte Thumb-1 flasher stub (`flash_raw.bin`) into SysRAM4 (`0x07FD0000`).
3. Wakes the FM25Q04 SPI NOR flash from deep sleep (`0xAB`).
4. Erases 8 &times; 4 KB sectors (`0x004000` to `0x00C000`).
5. Programs 256-byte pages in RAM-resident burst mode at ~3.0 KB/s.
6. Reads back and verifies data bit-by-bit (100% bit-exact).
7. Executes software reset (`SYS_CTRL_REG = 0x8082`), causing the secondary bootloader to load Image 1 and boot into our BLE application!

---

## 7. Wireless BLE Image Uploading (Linux Client)

### ⚠️ Use Write Without Response, not Write With Response

An ATT **Write Request** (`response=True`) currently **hardfaults the firmware** inside the
ROM's `ke_queue_insert`. A **Write Command** (`response=False`) works. Use
[`upload_noresp.py`](upload_noresp.py), which also paces the stream:

```bash
./venv/bin/python upload_noresp.py --image test_pattern_red_400x300.png
```

The client is self-verifying: the firmware keeps a per-chunk receipt bitmap
(`eink_chunk_map[16]`, one bit per 240-byte chunk) and command `0x08` notifies it, so
`upload_noresp.py` re-sends only the chunks that were actually dropped. Loss is a
**contiguous band, not just the tail**, which is why the old byte counter was not good
enough — see [`BLE_CRASH_DIAGNOSIS.md`](BLE_CRASH_DIAGNOSIS.md) §2b.

The panel is only touched if you pass `--refresh`; routine uploads leave it alone.

```bash
# Upload and verify, without redrawing the panel (fast):
./venv/bin/python upload_noresp.py --image test_pattern_red_400x300.png

# Upload, verify, then actually redraw the panel (adds ~17 s):
./venv/bin/python upload_noresp.py --image test_pattern_red_400x300.png --refresh
```

### Ensure Bluetooth is Active
```bash
sudo systemctl start bluetooth
sudo rfkill unblock bluetooth
```

### Run the Client
```bash
# Automatically scan, connect, stream 30,000 bytes, and trigger e-ink refresh:
./venv/bin/python ble_eink_client.py --image test_pattern_red_400x300.png

# Or specify MAC address directly if known:
./venv/bin/python ble_eink_client.py --image test_pattern_red_400x300.png --device 18:BC:5A:7D:26:0D
```

### What Happens:
1. Client connects with MTU 247.
2. Sends Command `0x07` to initialize the display buffer.
3. Streams 30,000 bytes in 125 packets (240 bytes payload + 2 bytes offset header) at ~7.6 KB/s in ~3.8 seconds.
4. Sends Command `0x06` (refresh trigger).
5. The firmware immediately acknowledges the GATT write, then executes a deferred refresh via SDK `app_easy_timer(10, user_eink_refresh_timer_cb)` (100 ms delay).
6. The SSD1619 controller drives physical electrophoretic pigment migration for ~17 seconds.
7. The status LED turns ON during refresh and OFF upon completion.
8. Upon refresh completion, the display retains the image permanently with zero power draw!

> Steps 2–4 use Write With Response and are affected by the open bug above. Treat the
> throughput and "acknowledged" messages from `ble_eink_client.py` as unreliable until
> it is fixed — prefer `upload_noresp.py`.

---

## 8. Key Architectural Solutions & Gotchas Solved

### 1. The 2 KB Dedicated Stack Fix (`ldscript_ble.lds.S`)
* **Bug**: The SDK template discarded `.stack` due to a missing dot (`KEEP(*(stack))`), resulting in `__StackLimit == __StackTop` (0 bytes). Stack allocations overwrote the heap and corrupted return addresses during GATT database creation.
* **Fix**: Created [`firmware/ldscript_ble.lds.S`](firmware/ldscript_ble.lds.S) with `KEEP(*(.stack*))` and `-D__STACK_SIZE=0x800` (2 KB dedicated stack top at `0x07FCF700`), safely separated from the non-retained heap.

### 2. The Connection State Assertion Fix (`user_eink_app.c`)
* **Bug**: Upon disconnection, `gapc_disconnect_ind_handler` hit `ASSERT_ERROR(0)` (`__BKPT(0)`) because `ke_state_get(dest_id)` returned `APP_CONNECTABLE` (`2`) instead of `APP_CONNECTED` (`3`).
* **Root Cause**: In `user_app_adv_undirect_complete(status)`, when a central connects, the stack completes advertising with `status = GAP_ERR_NO_ERROR` (`0x00`). If code checks `if (status != GAP_ERR_CANCELED)`, it immediately calls `user_app_adv_start()`, resetting the task state back to `APP_CONNECTABLE` right after connecting!
* **Fix**: Changed to `if (status == GAP_ERR_CANCELED) { user_app_adv_start(); }`. Advertising is only restarted upon disconnect in `user_app_disconnect()`.

### 3. Immediate GATT ACK via Deferred Refresh Timer
* **Design**: SSD1619 full tri-color refresh blocks the CPU for ~17 seconds while polling `EPD_BUSY`. If executed synchronously inside the GATT write handler, the central connection times out waiting for an ATT Write Response.
* **Fix**: When Command `0x06` is received, the handler registers `app_easy_timer(10, user_eink_refresh_timer_cb)` (100 ms delay) and returns immediately. The BLE stack sends the GATT Write Response in milliseconds, and the timer subsequently executes the refresh cycle.

### 4. Framebuffer Memory Layout
* Total Frame Size: 30,000 bytes in application RAM (`.bss`):
  * `eink_framebuffer[0..14999]`: Black/White RAM plane (SSD1619 command `0x24`). `1` = White/Red, `0` = Black.
  * `eink_framebuffer[15000..29999]`: Red RAM plane (SSD1619 command `0x26`). `1` = Red, `0` = Non-Red.

---

## 9. File Tree of Key Components

```text
├── BLE_CRASH_DIAGNOSIS.md         # Memory-budget + HardFault findings (READ FIRST)
├── ble_eink_client.py             # Python Bleak wireless image upload client
├── upload_noresp.py               # Working uploader (Write Without Response)
├── repro_disconnect.py            # Deterministic mid-refresh crash reproducer
├── diag_crc.py                    # Retained RAM-CRC snapshot differ (SWD)
├── regen_diag_regions.py          # Regenerate diag region table from the linker map
├── flash_spi_firmware.py          # Standalone ST-Link V2 SPI flash programmer
├── ssd1619.h / ssd1619.c          # Bare-metal C driver for SSD1619 / SSD1683
├── check_target_now.py            # SWD core status, register, and GPIO inspector
├── reboot_target.py               # Software reset (recovers from HardFault / NMI halt)
├── display_image.py               # Universal image processing pipeline
├── test_pattern_red_400x300.png   # 400x300 tri-color test graphic
├── HANDOFF.md                     # This developer handoff guide
├── AGENTS.md                      # Complete reverse-engineering technical guide
├── README.md                      # Project overview and documentation
└── firmware/
    ├── Makefile                   # Automated build & flash pipeline (Linux + Windows)
    ├── mkimage.py                 # Dialog 64-byte image header packager (CRC-32)
    ├── ldscript_ble.lds.S         # Linker script with 2KB stack fix
    ├── src/
    │   └── user_periph_setup.c/h  # GPIO pad configuration & pin reservations
    └── ble/
        ├── user_eink_app.c/h      # BLE application callbacks, GATT handlers, timers
        ├── user_eink_diag.c/h     # Optional (EINK_DIAG=1) RAM-CRC diagnostics
        ├── user_custs1_def.c/h    # Reverse-engineered 128-bit GATT service & characteristics
        ├── user_custs_config.c/h  # CUSTS1 profile structure registration
        └── config/
            ├── user_config.h      # Device name, BD address, MSG_HEAP_SZ, advertising config
            ├── user_callback_config.h # SDK callback registration
            ├── user_modules_config.h  # SDK module inclusions
            ├── user_profiles_config.h # Enabled GATT profiles (DIS, CUSTS1)
            ├── da14585_config_basic.h # Power domain, clock, and connection settings
            └── da14585_config_advanced.h # Heap, sleep, and memory configuration
```
