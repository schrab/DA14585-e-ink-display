/**
 * @file ssd1619.h
 * @brief Solomon Systech SSD1619 / SSD1683 E-Paper Display Controller Driver
 * @details Reverse-engineered bare-metal driver for Dialog DA14585 4.2" E-Ink Tag
 *          Display Resolution: 400 x 300 pixels (1-bit monochrome / bicolor)
 */

#ifndef SSD1619_H
#define SSD1619_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Display Dimensions */
#define EPD_WIDTH               400
#define EPD_HEIGHT              300
#define EPD_BYTES_PER_LINE      (EPD_WIDTH / 8)          /* 50 bytes */
#define EPD_FRAMEBUFFER_SIZE    (EPD_BYTES_PER_LINE * EPD_HEIGHT) /* 15,000 bytes */

/* SSD1619 / SSD1683 Controller Command Codes */
#define EPD_CMD_DRIVER_OUTPUT_CTRL          0x01
#define EPD_CMD_BOOSTER_SOFT_START          0x0C
#define EPD_CMD_DEEP_SLEEP_MODE             0x10
#define EPD_CMD_DATA_ENTRY_MODE             0x11
#define EPD_CMD_SW_RESET                    0x12
#define EPD_CMD_TEMP_SENSOR_CTRL            0x18
#define EPD_CMD_MASTER_ACTIVATION           0x20
#define EPD_CMD_DISPLAY_UPDATE_CTRL_1       0x21
#define EPD_CMD_DISPLAY_UPDATE_CTRL_2       0x22
#define EPD_CMD_WRITE_RAM_BW                0x24
#define EPD_CMD_WRITE_RAM_RED               0x26
#define EPD_CMD_BORDER_WAVEFORM_CTRL        0x3C
#define EPD_CMD_SET_RAM_X_START_END         0x44
#define EPD_CMD_SET_RAM_Y_START_END         0x45
#define EPD_CMD_SET_RAM_X_COUNTER           0x4E
#define EPD_CMD_SET_RAM_Y_COUNTER           0x4F

/* DA14585 Hardware Pinout Mapping */
#define EPD_PIN_CLK             0  /* P0_0: Shared SPI Clock */
#define EPD_PIN_DC              5  /* P0_5: Data/Command (0=Cmd, 1=Data) */
#define EPD_PIN_MOSI            6  /* P0_6: Shared SPI MOSI / DIN */
#define EPD_PIN_RST             7  /* P0_7: Hardware Reset (Active Low) */
#define EPD_PIN_BUSY            0  /* P2_0: Busy Status (1=Busy, 0=Idle) */
#define EPD_PIN_CS              1  /* P2_1: Display Chip Select (Active Low) */
#define EPD_PIN_PWR_EN          3  /* P2_3: Boost PMIC Power Enable (Active High) */
#define EPD_PIN_LED             4  /* P0_4: Status LED (Active Low) */

/* API Functions */

/**
 * @brief Initialize DA14585 GPIOs for the E-Ink display controller.
 */
void epd_gpio_init(void);

/**
 * @brief Power up the boost converter / display PMIC (P2_3 = 1).
 */
void epd_power_on(void);

/**
 * @brief Power down the boost converter to achieve sub-microamp sleep (P2_3 = 0).
 */
void epd_power_off(void);

/**
 * @brief Perform hardware and software initialization sequence.
 */
void epd_init(void);

/**
 * @brief Wait until the display finishes internal operations (EPD_BUSY P2_0 drops to 0).
 */
void epd_wait_busy(void);

/**
 * @brief Send a 1-byte command to the SSD1619 controller.
 */
void epd_write_command(uint8_t cmd);

/**
 * @brief Send a 1-byte parameter/data to the SSD1619 controller.
 */
void epd_write_data(uint8_t data);

/**
 * @brief Clear the RAM framebuffer (inverts: 1 = White, 0 = Black).
 * @param color 1 for White, 0 for Black
 */
void epd_framebuffer_clear(uint8_t color);

/**
 * @brief Set pixel color at coordinate (x, y).
 * @param x Horizontal pixel position (0 to 399)
 * @param y Vertical pixel position (0 to 299)
 * @param color 0 for Black, 1 for White
 */
void epd_draw_pixel(uint16_t x, uint16_t y, uint8_t color);

/* Color definitions */
#define EPD_COLOR_BLACK         0
#define EPD_COLOR_WHITE         1
#define EPD_COLOR_RED           2

/**
 * @brief Copy a 15,000-byte 1-bit bitmap buffer into the local framebuffer.
 */
void epd_load_framebuffer(const uint8_t *bitmap);

/**
 * @brief Stream the framebuffer to the display controller and trigger panel refresh.
 */
void epd_display_refresh(void);

/**
 * @brief Stream both Black/White and Red framebuffers and trigger 3-color panel refresh.
 * @param bw_bitmap Pointer to 15,000-byte BW buffer (1=White/Red, 0=Black)
 * @param red_bitmap Pointer to 15,000-byte RED buffer (1=Red, 0=Non-Red)
 */
void epd_display_refresh_tricolor(const uint8_t *bw_bitmap, const uint8_t *red_bitmap);

/**
 * @brief Put the display controller into ultra-low-power Deep Sleep mode.
 */
void epd_enter_deep_sleep(void);

#ifdef __cplusplus
}
#endif

#endif /* SSD1619_H */
