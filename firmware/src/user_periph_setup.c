/**
 ****************************************************************************************
 * @file user_periph_setup.c
 * @brief Peripheral and GPIO initialization for DA14585 E-Ink Display board
 ****************************************************************************************
 */

#include "user_periph_setup.h"
#include "datasheet.h"
#include "gpio.h"
#include "syscntl.h"

#if DEVELOPMENT_DEBUG
void GPIO_reservations(void)
{
    RESERVE_GPIO(STATUS_LED, STATUS_LED_PORT, STATUS_LED_PIN, PID_GPIO);
    RESERVE_GPIO(FLASH_CS, FLASH_CS_PORT, FLASH_CS_PIN, PID_GPIO);
    RESERVE_GPIO(EPD_PWR_EN, EPD_PWR_EN_PORT, EPD_PWR_EN_PIN, PID_GPIO);
    RESERVE_GPIO(EPD_RST, EPD_RST_PORT, EPD_RST_PIN, PID_GPIO);
    RESERVE_GPIO(EPD_CS, EPD_CS_PORT, EPD_CS_PIN, PID_GPIO);
    RESERVE_GPIO(EPD_BUSY, EPD_BUSY_PORT, EPD_BUSY_PIN, PID_GPIO);
    RESERVE_GPIO(EPD_CLK, EPD_CLK_PORT, EPD_CLK_PIN, PID_GPIO);
    RESERVE_GPIO(EPD_MOSI, EPD_MOSI_PORT, EPD_MOSI_PIN, PID_GPIO);
    RESERVE_GPIO(EPD_DC, EPD_DC_PORT, EPD_DC_PIN, PID_GPIO);
}
#endif

static void set_pad_functions(void)
{
    // Status LED: Output, start inactive (HIGH / OFF)

    GPIO_ConfigurePin(STATUS_LED_PORT, STATUS_LED_PIN, OUTPUT, PID_GPIO, true);

    // Flash CS: Output, inactive (HIGH) to avoid bus contention with E-Ink
    GPIO_ConfigurePin(FLASH_CS_PORT, FLASH_CS_PIN, OUTPUT, PID_GPIO, true);

    // Display Power Enable: Output, initially OFF (LOW)
    GPIO_ConfigurePin(EPD_PWR_EN_PORT, EPD_PWR_EN_PIN, OUTPUT, PID_GPIO, false);

    // Display Reset: Output, initially HIGH (Inactive)
    GPIO_ConfigurePin(EPD_RST_PORT, EPD_RST_PIN, OUTPUT, PID_GPIO, true);

    // Display Chip Select: Output, initially HIGH (Inactive)
    GPIO_ConfigurePin(EPD_CS_PORT, EPD_CS_PIN, OUTPUT, PID_GPIO, true);

    // Display Busy Line: Input (pulled down, active-HIGH)
    GPIO_ConfigurePin(EPD_BUSY_PORT, EPD_BUSY_PIN, INPUT_PULLDOWN, PID_GPIO, false);

    // Shared SPI lines:
    GPIO_ConfigurePin(EPD_CLK_PORT, EPD_CLK_PIN, OUTPUT, PID_GPIO, false);
    GPIO_ConfigurePin(EPD_MOSI_PORT, EPD_MOSI_PIN, OUTPUT, PID_GPIO, false);
    GPIO_ConfigurePin(EPD_DC_PORT, EPD_DC_PIN, OUTPUT, PID_GPIO, false);
}

void periph_init(void)

{
    // Power up peripheral domain
    SetBits16(PMU_CTRL_REG, PERIPH_SLEEP, 0);
    while (!(GetWord16(SYS_STAT_REG) & PER_IS_UP));

    // Configure pads
    set_pad_functions();

    // Enable PAD latches
    SetBits16(SYS_CTRL_REG, PAD_LATCH_EN, 1);
}

// Microsecond delay implementation for 16MHz system clock
void arch_asm_delay_us(int nof_us)
{
    while (nof_us-- > 0) {
        __NOP(); __NOP(); __NOP(); __NOP(); __NOP();
        __NOP(); __NOP(); __NOP(); __NOP(); __NOP();
    }
}
