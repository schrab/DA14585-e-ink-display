/**
 ****************************************************************************************
 * @file main.c
 * @brief DA14585 E-Ink Display Custom Firmware Application
 ****************************************************************************************
 */

#include <stdint.h>
#include <stdbool.h>
#include "arch_system.h"
#include "user_periph_setup.h"
#include "gpio.h"
#include "ssd1619.h"

// Hardware Watchdog reload (~2.6s timeout at 0xC8)
static inline void feed_watchdog(void)
{
    SetWord16(WATCHDOG_REG, USER_WDG_CFG);
}

// Simple busy-wait delay
static void delay_ms(uint32_t ms)
{
    for (uint32_t i = 0; i < ms; i++) {
        for (volatile uint32_t j = 0; j < 1600; j++) {
            __NOP();
        }
        feed_watchdog();
    }
}

static void draw_demo_pattern(void)
{
    // Clear screen to white
    epd_framebuffer_clear(EPD_COLOR_WHITE);

    // Draw border rectangle around active 400x300 area
    for (uint16_t x = 5; x < 395; x++) {
        epd_draw_pixel(x, 5, EPD_COLOR_BLACK);
        epd_draw_pixel(x, 294, EPD_COLOR_BLACK);
    }
    for (uint16_t y = 5; y < 295; y++) {
        epd_draw_pixel(5, y, EPD_COLOR_BLACK);
        epd_draw_pixel(394, y, EPD_COLOR_BLACK);
    }

    // Draw solid black and red demo boxes
    for (uint16_t y = 40; y < 120; y++) {
        for (uint16_t x = 40; x < 120; x++) {
            epd_draw_pixel(x, y, EPD_COLOR_BLACK);
        }
    }
}

int main(void);

// Reset handler calls _start after zeroing BSS and initializing data
void _start(void)
{
    main();
    while (1);
}

int main(void)
{
    // Reload watchdog (~2.6s timeout at 0xC8)
    feed_watchdog();

    // Initialize peripheral pads and GPIOs
    periph_init();

    // Blink Status LED twice on boot (Active-LOW)
    for (int i = 0; i < 2; i++) {
        GPIO_SetInactive(STATUS_LED_PORT, STATUS_LED_PIN); // LED ON
        delay_ms(100);
        GPIO_SetActive(STATUS_LED_PORT, STATUS_LED_PIN);   // LED OFF
        delay_ms(100);
    }

    // Initialize SSD1619 Display Controller
    epd_init();

    // Render pattern into memory buffer
    draw_demo_pattern();

    // Trigger physical panel refresh
    epd_display_refresh();

    // Put display controller into ultra-low-power sleep
    epd_enter_deep_sleep();

    // Main Idle Loop: Blink Status LED every 3 seconds and keep watchdog fed
    while (1) {
        feed_watchdog();

        // Brief 50ms heartbeat pulse on LED
        GPIO_SetInactive(STATUS_LED_PORT, STATUS_LED_PIN); // LED ON
        delay_ms(50);
        GPIO_SetActive(STATUS_LED_PORT, STATUS_LED_PIN);   // LED OFF
        delay_ms(2950);
    }
}
