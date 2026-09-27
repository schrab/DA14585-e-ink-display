/**
 * @file ssd1619.c
 * @brief Solomon Systech SSD1619 / SSD1683 E-Paper Display Controller Driver
 * @details Reverse-engineered implementation for DA14585 Cortex-M0.
 */

#include "ssd1619.h"
#include <string.h>

/* DA14585 Hardware Registers */
#define P0_DATA_REG         (*(volatile uint16_t *)0x50003000)
#define P0_SET_DATA_REG     (*(volatile uint16_t *)0x50003002)
#define P0_RESET_DATA_REG   (*(volatile uint16_t *)0x50003004)
#define P00_MODE_REG        (*(volatile uint16_t *)0x50003006)
#define P05_MODE_REG        (*(volatile uint16_t *)0x50003010)
#define P06_MODE_REG        (*(volatile uint16_t *)0x50003012)
#define P07_MODE_REG        (*(volatile uint16_t *)0x50003014)

#define P2_DATA_REG         (*(volatile uint16_t *)0x50003040)
#define P2_SET_DATA_REG     (*(volatile uint16_t *)0x50003042)
#define P2_RESET_DATA_REG   (*(volatile uint16_t *)0x50003044)
#define P20_MODE_REG        (*(volatile uint16_t *)0x50003046)
#define P21_MODE_REG        (*(volatile uint16_t *)0x50003048)
#define P23_MODE_REG        (*(volatile uint16_t *)0x5000304C)

/* Local Framebuffer in SysRAM (15,000 bytes) */
static uint8_t epd_framebuffer[EPD_FRAMEBUFFER_SIZE];

/* Simple CPU busy-wait delay at 16 MHz */
static void delay_ms(uint32_t ms)
{
    while (ms--) {
        for (volatile uint32_t i = 0; i < 5333; i++) {
            __asm__ volatile ("nop");
        }
    }
}

/* Bit-bang SPI write byte (MSB first, Mode 0: CPOL=0, CPHA=0) */
static void epd_spi_write_byte(uint8_t byte)
{
    for (uint8_t i = 0; i < 8; i++) {
        if (byte & 0x80) {
            P0_SET_DATA_REG = (1 << EPD_PIN_MOSI);   /* MOSI = 1 */
        } else {
            P0_RESET_DATA_REG = (1 << EPD_PIN_MOSI); /* MOSI = 0 */
        }
        P0_SET_DATA_REG = (1 << EPD_PIN_CLK);       /* SCLK = 1 */
        __asm__ volatile ("nop");
        P0_RESET_DATA_REG = (1 << EPD_PIN_CLK);     /* SCLK = 0 */
        byte <<= 1;
    }
}

void epd_gpio_init(void)
{
    /* Mode: 0x0300 = OUTPUT (PID 0 GPIO) */
    P00_MODE_REG = 0x0300; /* CLK */
    P05_MODE_REG = 0x0300; /* D/C */
    P06_MODE_REG = 0x0300; /* MOSI */
    P07_MODE_REG = 0x0300; /* RST */

    P20_MODE_REG = 0x0000; /* BUSY (INPUT) */
    P21_MODE_REG = 0x0300; /* CS */
    P23_MODE_REG = 0x0300; /* PWR_EN */

    /* Default pin states */
    P0_SET_DATA_REG = (1 << EPD_PIN_DC) | (1 << EPD_PIN_RST);
    P0_RESET_DATA_REG = (1 << EPD_PIN_CLK) | (1 << EPD_PIN_MOSI);
    P2_SET_DATA_REG = (1 << EPD_PIN_CS);
    P2_RESET_DATA_REG = (1 << EPD_PIN_PWR_EN);
}

void epd_power_on(void)
{
    P2_SET_DATA_REG = (1 << EPD_PIN_PWR_EN);
    delay_ms(20);
}

void epd_power_off(void)
{
    P2_RESET_DATA_REG = (1 << EPD_PIN_PWR_EN);
}

void epd_wait_busy(void)
{
    /* Loop while EPD_BUSY (P2_0) is active HIGH (1) */
    while (P2_DATA_REG & (1 << EPD_PIN_BUSY)) {
        delay_ms(1);
    }
}

void epd_write_command(uint8_t cmd)
{
    P0_RESET_DATA_REG = (1 << EPD_PIN_DC); /* D/C = 0 (Command) */
    P2_RESET_DATA_REG = (1 << EPD_PIN_CS); /* CS = 0 (Assert) */
    epd_spi_write_byte(cmd);
    P2_SET_DATA_REG = (1 << EPD_PIN_CS);   /* CS = 1 (Deassert) */
    P0_SET_DATA_REG = (1 << EPD_PIN_DC);   /* Restore D/C = 1 */
}

void epd_write_data(uint8_t data)
{
    P0_SET_DATA_REG = (1 << EPD_PIN_DC);   /* D/C = 1 (Data) */
    P2_RESET_DATA_REG = (1 << EPD_PIN_CS); /* CS = 0 (Assert) */
    epd_spi_write_byte(data);
    P2_SET_DATA_REG = (1 << EPD_PIN_CS);   /* CS = 1 (Deassert) */
}

void epd_init(void)
{
    epd_gpio_init();
    epd_power_on();

    /* Hardware Reset Pulse: High -> Low (20ms) -> High (20ms) */
    P0_RESET_DATA_REG = (1 << EPD_PIN_RST);
    delay_ms(20);
    P0_SET_DATA_REG = (1 << EPD_PIN_RST);
    delay_ms(20);
    epd_wait_busy();

    /* Software Reset */
    epd_write_command(EPD_CMD_SW_RESET);
    epd_wait_busy();

    /* Panel Configuration */
    epd_write_command(EPD_CMD_BORDER_WAVEFORM_CTRL);
    epd_write_data(0x01);

    epd_write_command(EPD_CMD_TEMP_SENSOR_CTRL);
    epd_write_data(0x80);

    /* Data Entry Mode: X-mode increment, Y-mode increment */
    epd_write_command(EPD_CMD_DATA_ENTRY_MODE);
    epd_write_data(0x03);

    /* Set RAM X window: 0 to 49 (50 bytes = 400 pixels) */
    epd_write_command(EPD_CMD_SET_RAM_X_START_END);
    epd_write_data(0x00);
    epd_write_data(0x31);

    /* Set RAM Y window: 0 to 299 lines (0x012B) */
    epd_write_command(EPD_CMD_SET_RAM_Y_START_END);
    epd_write_data(0x00);
    epd_write_data(0x00);
    epd_write_data(0x2B);
    epd_write_data(0x01);

    /* Set RAM Address Counters to (0, 0) */
    epd_write_command(EPD_CMD_SET_RAM_X_COUNTER);
    epd_write_data(0x00);

    epd_write_command(EPD_CMD_SET_RAM_Y_COUNTER);
    epd_write_data(0x00);
    epd_write_data(0x00);
}

void epd_framebuffer_clear(uint8_t color)
{
    memset(epd_framebuffer, color ? 0xFF : 0x00, EPD_FRAMEBUFFER_SIZE);
}

void epd_draw_pixel(uint16_t x, uint16_t y, uint8_t color)
{
    if (x >= EPD_WIDTH || y >= EPD_HEIGHT) {
        return;
    }
    uint32_t index = (y * EPD_BYTES_PER_LINE) + (x / 8);
    uint8_t bit_mask = 0x80 >> (x % 8);

    if (color) {
        epd_framebuffer[index] |= bit_mask;  /* White */
    } else {
        epd_framebuffer[index] &= ~bit_mask; /* Black */
    }
}

void epd_load_framebuffer(const uint8_t *bitmap)
{
    if (bitmap) {
        memcpy(epd_framebuffer, bitmap, EPD_FRAMEBUFFER_SIZE);
    }
}

void epd_display_refresh(void)
{
    epd_display_refresh_tricolor(epd_framebuffer, NULL);
}

void epd_display_refresh_tricolor(const uint8_t *bw_bitmap, const uint8_t *red_bitmap)
{
    /* 1. Stream Black/White RAM (0x24) */
    epd_write_command(EPD_CMD_WRITE_RAM_BW);
    P0_SET_DATA_REG = (1 << EPD_PIN_DC);
    P2_RESET_DATA_REG = (1 << EPD_PIN_CS);

    for (uint32_t i = 0; i < EPD_FRAMEBUFFER_SIZE; i++) {
        epd_spi_write_byte(bw_bitmap ? bw_bitmap[i] : 0xFF);
    }
    P2_SET_DATA_REG = (1 << EPD_PIN_CS);

    /* 2. Stream Red RAM (0x26) */
    epd_write_command(EPD_CMD_WRITE_RAM_RED);
    P2_RESET_DATA_REG = (1 << EPD_PIN_CS);
    for (uint32_t i = 0; i < EPD_FRAMEBUFFER_SIZE; i++) {
        epd_spi_write_byte(red_bitmap ? red_bitmap[i] : 0x00);
    }
    P2_SET_DATA_REG = (1 << EPD_PIN_CS);

    /* 3. Display Update Control 2: enable clocks, enable CP, refresh, disable CP, disable clocks */
    epd_write_command(EPD_CMD_DISPLAY_UPDATE_CTRL_2);
    epd_write_data(0xF7);

    /* 4. Master Activation: start panel physical refresh */
    epd_write_command(EPD_CMD_MASTER_ACTIVATION);

    /* 5. Wait for refresh completion (~17.08s physical electrophoretic cycle) */
    epd_wait_busy();

    /* 6. Power down into deep sleep */
    epd_enter_deep_sleep();
}

void epd_enter_deep_sleep(void)
{
    epd_write_command(EPD_CMD_DEEP_SLEEP_MODE);
    epd_write_data(0x01);
    epd_power_off();
}
