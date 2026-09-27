#include <stdint.h>

#define P0_DATA_REG         (*(volatile uint16_t *)0x50003000)
#define P0_SET_DATA_REG     (*(volatile uint16_t *)0x50003002)
#define P0_RESET_DATA_REG   (*(volatile uint16_t *)0x50003004)
#define P00_MODE_REG        (*(volatile uint16_t *)0x50003006)
#define P03_MODE_REG        (*(volatile uint16_t *)0x5000300C)
#define P05_MODE_REG        (*(volatile uint16_t *)0x50003010)
#define P06_MODE_REG        (*(volatile uint16_t *)0x50003012)
#define WATCHDOG_REG        (*(volatile uint16_t *)0x50003100)

#define PIN_CLK   0
#define PIN_CS    3
#define PIN_MISO  5
#define PIN_MOSI  6

#define PMU_CTRL_REG        (*(volatile uint16_t *)0x50000010)
#define SYS_CTRL_REG        (*(volatile uint16_t *)0x50000012)
#define SYS_STAT_REG        (*(volatile uint16_t *)0x50000014)

#define P2_DATA_REG         (*(volatile uint16_t *)0x50003040)
#define P2_SET_DATA_REG     (*(volatile uint16_t *)0x50003042)
#define P21_MODE_REG        (*(volatile uint16_t *)0x50003048)

static inline void pet_watchdog(void) {
    WATCHDOG_REG = 0xC8;
}

static uint8_t spi_xfer(uint8_t tx);

void flash_init(void) {
    // Power up peripheral power domain
    PMU_CTRL_REG &= ~0x0002; // Clear PERIPH_SLEEP (bit 1)
    while (!(SYS_STAT_REG & 0x0008)); // Wait for PER_IS_UP (bit 3)

    // Deselect EPD (P2_1 = 1) so it doesn't contend on shared SPI lines
    P21_MODE_REG = 0x0300;
    P2_SET_DATA_REG = (1 << 1);

    P00_MODE_REG = 0x0300; /* CLK output */
    P03_MODE_REG = 0x0300; /* FLASH_CS output */
    P06_MODE_REG = 0x0300; /* MOSI output */
    P05_MODE_REG = 0x0100; /* MISO input with pull-up */

    SYS_CTRL_REG |= (1 << 5); /* PAD_LATCH_EN = 1 */

    P0_SET_DATA_REG = (1 << PIN_CS);
    P0_RESET_DATA_REG = (1 << PIN_CLK) | (1 << PIN_MOSI);

    // Release FM25Q04 from Deep Power Down (Opcode 0xAB)
    P0_RESET_DATA_REG = (1 << PIN_CS);
    spi_xfer(0xAB);
    P0_SET_DATA_REG = (1 << PIN_CS);

    // Wait t_RES1 delay (~50us)
    for (volatile int d = 0; d < 200; d++) __asm__ volatile ("nop");
}

static uint8_t spi_xfer(uint8_t tx) {
    uint8_t rx = 0;
    for (int i = 0; i < 8; i++) {
        if (tx & 0x80)
            P0_SET_DATA_REG = (1 << PIN_MOSI);
        else
            P0_RESET_DATA_REG = (1 << PIN_MOSI);
        tx <<= 1;

        for (volatile int d = 0; d < 5; d++) __asm__ volatile ("nop");

        P0_SET_DATA_REG = (1 << PIN_CLK);
        for (volatile int d = 0; d < 5; d++) __asm__ volatile ("nop");

        rx = (rx << 1) | ((P0_DATA_REG >> PIN_MISO) & 1);

        P0_RESET_DATA_REG = (1 << PIN_CLK);
        for (volatile int d = 0; d < 5; d++) __asm__ volatile ("nop");
    }
    return rx;
}

static void wait_wip_clear(void) {
    while (1) {
        pet_watchdog();
        P0_RESET_DATA_REG = (1 << PIN_CS);
        spi_xfer(0x05); // Read Status Register 1
        uint8_t status = spi_xfer(0x00);
        P0_SET_DATA_REG = (1 << PIN_CS);
        if (!(status & 1)) break; // WIP bit is 0 -> ready
    }
}

static void write_enable(void) {
    wait_wip_clear();
    P0_RESET_DATA_REG = (1 << PIN_CS);
    spi_xfer(0x06); // WREN
    P0_SET_DATA_REG = (1 << PIN_CS);
}

// Entry 0 (0x07FD0020): Read JEDEC ID -> returns 0xA14013
uint32_t flash_read_jedec(void) {
    pet_watchdog();
    flash_init();

    P0_RESET_DATA_REG = (1 << PIN_CS);
    spi_xfer(0x9F);
    uint32_t id = 0;
    id = (id << 8) | spi_xfer(0x00);
    id = (id << 8) | spi_xfer(0x00);
    id = (id << 8) | spi_xfer(0x00);
    P0_SET_DATA_REG = (1 << PIN_CS);

    return id;
}

// Entry 1: Read buffer
// r0: buffer, r1: address, r2: length
int32_t flash_read(uint8_t *buf, uint32_t addr, uint32_t len) {
    flash_init();
    pet_watchdog();
    wait_wip_clear();

    P0_RESET_DATA_REG = (1 << PIN_CS);
    spi_xfer(0x03); // Read command
    spi_xfer((addr >> 16) & 0xFF);
    spi_xfer((addr >> 8) & 0xFF);
    spi_xfer(addr & 0xFF);

    for (uint32_t i = 0; i < len; i++) {
        if ((i & 0x1FF) == 0) pet_watchdog();
        buf[i] = spi_xfer(0x00);
    }
    P0_SET_DATA_REG = (1 << PIN_CS);

    return len;
}

// Entry 2: Erase 4KB sector
// r0: address
int32_t flash_erase_sector(uint32_t addr) {
    flash_init();
    write_enable();

    P0_RESET_DATA_REG = (1 << PIN_CS);
    spi_xfer(0x20); // Sector Erase 4K
    spi_xfer((addr >> 16) & 0xFF);
    spi_xfer((addr >> 8) & 0xFF);
    spi_xfer(addr & 0xFF);
    P0_SET_DATA_REG = (1 << PIN_CS);

    wait_wip_clear();
    pet_watchdog();
    return 0;
}

// Entry 3: Write buffer (up to 4096 bytes, handles 256-byte page boundaries)
// r0: buffer, r1: address, r2: length
int32_t flash_write_data(const uint8_t *buf, uint32_t addr, uint32_t len) {
    flash_init();
    uint32_t written = 0;

    while (written < len) {
        pet_watchdog();
        write_enable();

        uint32_t page_offset = (addr + written) & 0xFF;
        uint32_t chunk = 256 - page_offset;
        if (chunk > (len - written)) chunk = len - written;

        uint32_t cur_addr = addr + written;
        P0_RESET_DATA_REG = (1 << PIN_CS);
        spi_xfer(0x02); // Page Program
        spi_xfer((cur_addr >> 16) & 0xFF);
        spi_xfer((cur_addr >> 8) & 0xFF);
        spi_xfer(cur_addr & 0xFF);

        for (uint32_t i = 0; i < chunk; i++) {
            spi_xfer(buf[written + i]);
        }
        P0_SET_DATA_REG = (1 << PIN_CS);

        wait_wip_clear();
        written += chunk;
    }

    pet_watchdog();
    return written;
}
