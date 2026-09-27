"""
DA14585 Standalone Bare-Metal 3-Color E-Ink Driver & Refresh (Black + White + Red)
==================================================================================
- Streams BW Framebuffer (15,000 bytes) to 0x24 (WRITE_RAM_BW)
- Streams RED Framebuffer (15,000 bytes) to 0x26 (WRITE_RAM_RED)
- Triggers 3-color full electrophoretic refresh cycle (0x22 / 0x20)
- Monitors P2_0 (BUSY) line until physical refresh finishes (~17s)
- Holds watchdog-fed retention loop in SysRAM4 to prevent factory reboot
"""

import sys
import time
import keystone
from pyocd.core.helpers import ConnectHelper

DRIVER_ASM = """
.syntax unified
.thumb

.global _start
_start:
    // ----------------------------------------------------
    // 1. Freeze Watchdog Timer & Reload
    // ----------------------------------------------------
    ldr r0, =0x50003300     // SET_FREEZE_REG
    movs r1, #8             // FRZ_WDOG
    strh r1, [r0]

    ldr r0, =0x50003100     // WATCHDOG_REG
    movs r1, #0xC8
    strh r1, [r0]

    // ----------------------------------------------------
    // 2. Configure GPIO Pin Modes
    // Output mode = 0x0300 (PID 0 GPIO, Mode OUTPUT)
    // Input mode  = 0x0000 (PID 0 GPIO, Mode INPUT)
    // ----------------------------------------------------
    ldr r2, =0x0300         // OUTPUT mode (0x0300)

    // P0_0 (CLK) -> P00_MODE_REG (0x50003006)
    ldr r0, =0x50003006
    strh r2, [r0]

    // P0_3 (FLASH_CS) -> P03_MODE_REG (0x5000300C) - Keep Flash deselected!
    ldr r0, =0x5000300C
    strh r2, [r0]

    // P0_5 (D/C) -> P05_MODE_REG (0x50003010)
    ldr r0, =0x50003010
    strh r2, [r0]

    // P0_6 (MOSI) -> P06_MODE_REG (0x50003012)
    ldr r0, =0x50003012
    strh r2, [r0]

    // P0_7 (RST) -> P07_MODE_REG (0x50003014)
    ldr r0, =0x50003014
    strh r2, [r0]

    // P2_0 (BUSY) -> P20_MODE_REG (0x50003046) = 0x0000 (INPUT)
    ldr r0, =0x50003046
    movs r1, #0
    strh r1, [r0]

    // P2_1 (CS) -> P21_MODE_REG (0x50003048) = 0x0300 (OUTPUT)
    ldr r0, =0x50003048
    strh r2, [r0]

    // P2_3 (PWR_EN) -> P23_MODE_REG (0x5000304C) = 0x0300 (OUTPUT)
    ldr r0, =0x5000304C
    strh r2, [r0]

    // ----------------------------------------------------
    // 3. Set Default Inactive States & Power Up PMIC
    // P0_3 (FLASH_CS) = 1 (Deselect SPI Flash)
    // P0_5 (D/C)      = 1
    // P0_7 (RST)      = 1
    // P0_0 (CLK)      = 0
    // P0_6 (MOSI)     = 0
    // P2_1 (EPD_CS)   = 1
    // P2_3 (PWR_EN)   = 1 (Enable PMIC / Boost Converter)
    // ----------------------------------------------------
    ldr r0, =0x50003002     // P0_SET_DATA_REG
    movs r1, #0xA8          // Bit 3 (FLASH_CS) + Bit 5 (D/C) + Bit 7 (RST)
    strh r1, [r0]

    ldr r0, =0x50003004     // P0_RESET_DATA_REG
    movs r1, #0x41          // Bit 0 (CLK) + Bit 6 (MOSI)
    strh r1, [r0]

    ldr r0, =0x50003042     // P2_SET_DATA_REG
    movs r1, #0x0A          // Bit 1 (CS) + Bit 3 (PWR_EN = 1)
    strh r1, [r0]

    // Delay 30ms for PMIC power rail stabilization
    movs r0, #30
    bl delay_ms

    // ----------------------------------------------------
    // 4. Hardware Reset Pulse (P0_7: High -> Low -> High)
    // ----------------------------------------------------
    ldr r0, =0x50003004     // P0_RESET_DATA_REG
    movs r1, #0x80          // P0_7 LOW
    strh r1, [r0]
    movs r0, #30
    bl delay_ms

    ldr r0, =0x50003002     // P0_SET_DATA_REG
    movs r1, #0x80          // P0_7 HIGH
    strh r1, [r0]
    movs r0, #30
    bl delay_ms

    // Wait until BUSY line (P2_0) drops to 0
    bl wait_busy

    // ----------------------------------------------------
    // 5. Software Reset & Display Configuration
    // ----------------------------------------------------
    movs r0, #0x12          // SW_RESET
    bl send_cmd
    bl wait_busy

    movs r0, #0x3C          // BORDER_WAVEFORM_CONTROL
    bl send_cmd
    movs r0, #0x01
    bl send_data

    movs r0, #0x18          // TEMP_SENSOR_CONTROL
    bl send_cmd
    movs r0, #0x80
    bl send_data

    movs r0, #0x11          // DATA_ENTRY_MODE
    bl send_cmd
    movs r0, #0x03          // AM=0 (X-mode), ID=11 (X inc, Y inc)
    bl send_data

    movs r0, #0x44          // SET_RAM_X_START_END
    bl send_cmd
    movs r0, #0x00          // Start = 0
    bl send_data
    movs r0, #0x31          // End = 49 (50 bytes = 400 pixels)
    bl send_data

    movs r0, #0x45          // SET_RAM_Y_START_END
    bl send_cmd
    movs r0, #0x00          // Start LSB = 0
    bl send_data
    movs r0, #0x00          // Start MSB = 0
    bl send_data
    movs r0, #0x2B          // End LSB = 0x2B (299)
    bl send_data
    movs r0, #0x01          // End MSB = 0x01
    bl send_data

    movs r0, #0x4E          // SET_RAM_X_COUNTER
    bl send_cmd
    movs r0, #0x00
    bl send_data

    movs r0, #0x4F          // SET_RAM_Y_COUNTER
    bl send_cmd
    movs r0, #0x00
    bl send_data
    movs r0, #0x00
    bl send_data

    // ----------------------------------------------------
    // 6. Stream Black/White Framebuffer (15,000 bytes)
    // Polarity: 1 = White/Red, 0 = Black
    // ----------------------------------------------------
    movs r0, #0x24          // WRITE_RAM_BW
    bl send_cmd

    // Select Data mode (P0_5 HIGH) & Assert CS (P2_1 LOW)
    ldr r0, =0x50003002     // P0_SET_DATA_REG
    movs r1, #0x20          // P0_5 HIGH (Data)
    strh r1, [r0]

    ldr r0, =0x50003044     // P2_RESET_DATA_REG
    movs r1, #0x02          // P2_1 LOW (CS Assert)
    strh r1, [r0]

    ldr r4, =0x07FC8000     // BW Framebuffer in SysRAM2
    ldr r5, =15000          // Total bytes
stream_bw_loop:
    ldrb r0, [r4]
    bl spi_write_byte
    adds r4, r4, #1
    subs r5, r5, #1
    bne stream_bw_loop

    // Deassert CS (P2_1 HIGH)
    ldr r0, =0x50003042     // P2_SET_DATA_REG
    movs r1, #0x02
    strh r1, [r0]

    // ----------------------------------------------------
    // 7. Stream Red Framebuffer (15,000 bytes)
    // Polarity: 1 = Red, 0 = Non-Red
    // ----------------------------------------------------
    movs r0, #0x26          // WRITE_RAM_RED
    bl send_cmd

    // Select Data mode & Assert CS
    ldr r0, =0x50003002
    movs r1, #0x20
    strh r1, [r0]

    ldr r0, =0x50003044
    movs r1, #0x02
    strh r1, [r0]

    ldr r4, =0x07FD1000     // RED Framebuffer in SysRAM4
    ldr r5, =15000
stream_red_loop:
    ldrb r0, [r4]
    bl spi_write_byte
    adds r4, r4, #1
    subs r5, r5, #1
    bne stream_red_loop

    // Deassert CS
    ldr r0, =0x50003042
    movs r1, #0x02
    strh r1, [r0]

    // ----------------------------------------------------
    // 8. Trigger Display Refresh (Master Activation)
    // ----------------------------------------------------
    movs r0, #0x22          // DISPLAY_UPDATE_CONTROL_2
    bl send_cmd
    movs r0, #0xF7          // Sequence: Clocks ON -> CP ON -> Refresh -> CP OFF -> Clocks OFF
    bl send_data

    movs r0, #0x20          // MASTER_ACTIVATION
    bl send_cmd

    // Small delay to allow BUSY pin to go HIGH
    movs r0, #50
    bl delay_ms

    // Wait until BUSY (P2_0) drops back to 0 (electrophoretic refresh complete!)
    bl wait_busy

    // ----------------------------------------------------
    // 9. Deep Sleep & Power Down PMIC
    // ----------------------------------------------------
    movs r0, #0x10          // DEEP_SLEEP_MODE
    bl send_cmd
    movs r0, #0x01
    bl send_data

    // Shut down PMIC / Boost Converter (P2_3 LOW)
    ldr r0, =0x50003044     // P2_RESET_DATA_REG
    movs r1, #0x08
    strh r1, [r0]

    // ----------------------------------------------------
    // 10. Mark Completion Flag in Memory (0x07FD03FC = 0xAA55AA55)
    // ----------------------------------------------------
    ldr r0, =0x07FD03FC
    ldr r1, =0xAA55AA55
    str r1, [r0]

    // ----------------------------------------------------
    // 11. Safe Active Idle Loop: continuously feed watchdog
    // Keeps watchdog fed so stock firmware never reboots to erase screen!
    // ----------------------------------------------------
    ldr r4, =0x50003100     // WATCHDOG_REG
safe_idle:
    movs r0, #0xC8
    strh r0, [r4]           // Reload Watchdog (never trips!)
    ldr r1, =1000000        // ~250ms delay loop at 16 MHz
safe_idle_delay:
    subs r1, r1, #1
    bne safe_idle_delay
    b safe_idle

// ========================================================
// Helper Subroutines
// ========================================================

// Wait while BUSY (P2_0) is 1, reloading watchdog continuously
wait_busy:
    push {r4, r5, lr}
    ldr r4, =0x50003040     // P2_DATA_REG
    ldr r5, =0x50003100     // WATCHDOG_REG
wait_busy_loop:
    movs r0, #0xC8
    strh r0, [r5]           // Reload Watchdog timer
    ldrh r0, [r4]
    movs r1, #1
    ands r0, r1
    bne wait_busy_loop
    pop {r4, r5, pc}

// Send Command byte in r0 (P0_5 LOW)
send_cmd:
    push {r4, lr}
    mov r4, r0
    ldr r0, =0x50003004     // P0_RESET_DATA_REG
    movs r1, #0x20          // P0_5 LOW (Command)
    strh r1, [r0]

    ldr r0, =0x50003044     // P2_RESET_DATA_REG
    movs r1, #0x02          // P2_1 LOW (CS Assert)
    strh r1, [r0]

    mov r0, r4
    bl spi_write_byte

    ldr r0, =0x50003042     // P2_SET_DATA_REG
    movs r1, #0x02          // P2_1 HIGH (CS Deassert)
    strh r1, [r0]

    ldr r0, =0x50003002     // P0_SET_DATA_REG
    movs r1, #0x20          // P0_5 HIGH (Restore Data default)
    strh r1, [r0]
    pop {r4, pc}

// Send Data byte in r0 (P0_5 HIGH)
send_data:
    push {r4, lr}
    mov r4, r0
    ldr r0, =0x50003002     // P0_SET_DATA_REG
    movs r1, #0x20          // P0_5 HIGH (Data)
    strh r1, [r0]

    ldr r0, =0x50003044     // P2_RESET_DATA_REG
    movs r1, #0x02          // P2_1 LOW (CS Assert)
    strh r1, [r0]

    mov r0, r4
    bl spi_write_byte

    ldr r0, =0x50003042     // P2_SET_DATA_REG
    movs r1, #0x02          // P2_1 HIGH (CS Deassert)
    strh r1, [r0]
    pop {r4, pc}

// Bit-Bang SPI byte in r0 (MSB first, P0_0 CLK, P0_6 MOSI)
spi_write_byte:
    push {r4, r5, r6, lr}
    mov r4, r0              // r4 = byte to transmit
    movs r5, #8             // 8 bits
    ldr r6, =0x50003000     // GPIO Port 0 Base
spi_bit_loop:
    // Check MSB (bit 7)
    lsls r0, r4, #24        // Shift bit 7 into sign bit (bit 31)
    asrs r0, r0, #31        // r0 = 0xFFFFFFFF if bit 7 was 1, else 0
    cmp r0, #0
    beq spi_bit_zero
spi_bit_one:
    movs r1, #0x40          // P0_6 SET (MOSI = 1)
    strh r1, [r6, #2]       // P0_SET_DATA_REG
    b spi_clock_pulse
spi_bit_zero:
    movs r1, #0x40          // P0_6 RESET (MOSI = 0)
    strh r1, [r6, #4]       // P0_RESET_DATA_REG
spi_clock_pulse:
    movs r1, #0x01          // P0_0 CLK HIGH
    strh r1, [r6, #2]       // P0_SET_DATA_REG
    movs r1, #0x01          // P0_0 CLK LOW
    strh r1, [r6, #4]       // P0_RESET_DATA_REG

    lsls r4, r4, #1         // Shift next bit
    subs r5, r5, #1
    bne spi_bit_loop

    pop {r4, r5, r6, pc}

// Delay loop: r0 = milliseconds (~5333 iterations per ms at 16 MHz)
delay_ms:
    push {r4, lr}
    ldr r4, =0x50003100     // WATCHDOG_REG
delay_outer:
    movs r1, #0xC8
    strh r1, [r4]           // Reload Watchdog timer
    ldr r1, =5333
delay_inner:
    subs r1, r1, #1
    bne delay_inner
    subs r0, r0, #1
    bne delay_outer
    pop {r4, pc}
"""

def main():
    print("=" * 70)
    print("DA14585 BARE-METAL 3-COLOR E-INK HARDWARE REFRESH (BW + RED)")
    print("=" * 70)

    # 1. Assemble driver with Keystone
    print("[*] Assembling bare-metal Thumb-1 driver stub...")
    ks = keystone.Ks(keystone.KS_ARCH_ARM, keystone.KS_MODE_THUMB)
    encoding, count = ks.asm(DRIVER_ASM, 0x07FD0000)
    stub_bytes = bytes(encoding)
    print(f"[+] Driver assembled successfully: {len(stub_bytes)} bytes ({count} instructions)")

    # 2. Load test framebuffers
    bw_file = "test_bw_framebuffer_15k.bin"
    red_file = "test_red_framebuffer_15k.bin"
    with open(bw_file, "rb") as f:
        bw_data = f.read()
    with open(red_file, "rb") as f:
        red_data = f.read()
    print(f"[+] Loaded BW framebuffer:  {len(bw_data)} bytes from {bw_file}")
    print(f"[+] Loaded RED framebuffer: {len(red_data)} bytes from {red_file}")

    # 3. Connect to target via ST-Link
    print("[*] Connecting to DA14585 target via ST-Link SWD...")
    probes = ConnectHelper.get_all_connected_probes()
    if not probes:
        print("[-] Error: No ST-Link probe found!")
        sys.exit(1)

    probe = probes[0]
    session = ConnectHelper.session_with_chosen_probe(
        unique_id=probe.unique_id,
        target_override="cortex_m",
        frequency=1000000,
        connect_mode="attach"
    )
    session.open()
    target = session.target

    # Halt core & freeze watchdog
    print("[*] Halting core and freezing watchdog...")
    target.halt()
    target.write16(0x50003300, 0x0008)

    # 4. Inject driver stub and framebuffers into SysRAM
    STUB_ADDR = 0x07FD0000     # Driver in SysRAM4
    BW_ADDR   = 0x07FC8000     # BW Buffer in SysRAM2
    RED_ADDR  = 0x07FD1000     # RED Buffer in SysRAM4
    FLAG_ADDR = 0x07FD03FC     # Completion Flag
    STACK_TOP = 0x07FD7FE0

    # Clear completion flag
    target.write32(FLAG_ADDR, 0x00000000)

    print(f"[*] Injecting driver stub to 0x{STUB_ADDR:08X}...")
    target.write_memory_block8(STUB_ADDR, list(stub_bytes))

    print(f"[*] Injecting BW framebuffer (15,000 bytes) to 0x{BW_ADDR:08X}...")
    target.write_memory_block8(BW_ADDR, list(bw_data))

    print(f"[*] Injecting RED framebuffer (15,000 bytes) to 0x{RED_ADDR:08X}...")
    target.write_memory_block8(RED_ADDR, list(red_data))

    # 5. Set up CPU registers for execution
    target.write_core_register("sp", STACK_TOP)
    target.write_core_register("pc", STUB_ADDR | 1)  # Thumb bit
    target.write_core_register("lr", STUB_ADDR)
    target.write_core_register("xpsr", 0x01000000)   # Thumb state

    print(f"[*] CPU State: PC=0x{STUB_ADDR:08X} (Thumb), SP=0x{STACK_TOP:08X}")
    print("[*] Resuming target to trigger physical 3-color display refresh...")
    t_start = time.time()
    target.resume()

    # Monitor completion flag at FLAG_ADDR (0xAA55AA55)
    print("[*] Monitoring display refresh completion flag (0x07FD03FC)...")
    completed = False
    for attempt in range(90):  # Wait up to 45 seconds (0.5s interval)
        time.sleep(0.5)
        try:
            val = target.read32(FLAG_ADDR)
            if val == 0xAA55AA55:
                elapsed = time.time() - t_start
                print(f"\n[+] 3-Color display refresh COMPLETED in {elapsed:.2f} seconds!")
                print("    - Completion flag 0xAA55AA55 detected.")
                print("    - Target is now running in watchdog-fed idle loop.")
                print("    - Stock firmware will NOT reboot or erase the screen!")
                completed = True
                break
        except Exception:
            pass
        if attempt % 2 == 0:
            try:
                p2 = target.read16(0x50003040)
                busy_str = "BUSY (refreshing)" if (p2 & 1) else "IDLE / processing"
            except Exception:
                busy_str = "RUNNING"
            sys.stdout.write(f"\r    [T+{attempt*0.5:4.1f}s] Panel state: {busy_str:22s}")
            sys.stdout.flush()

    session.close()
    print("\n" + "=" * 70)
    if completed:
        print("[SUCCESS] Check the physical 4.2\" E-Ink display!")
        print("          - Header banner: Solid RED with white text")
        print("          - Borders: Black outer border, RED inner border")
        print("          - Swatches: White, Black, and Solid RED")
        print("          - Checkerboard: Alternating Black and RED squares!")
        print("          - Permanent retention: Watchdog actively fed")
    else:
        print("[WARNING] Refresh flag was not detected within timeout.")
    print("=" * 70)

if __name__ == "__main__":
    main()
