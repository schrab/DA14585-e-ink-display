/**
 ****************************************************************************************
 * @file user_periph_setup.h
 * @brief DA14585 E-Ink Display Board Hardware Configuration
 ****************************************************************************************
 */

#ifndef _USER_PERIPH_SETUP_H_
#define _USER_PERIPH_SETUP_H_

#include <stdint.h>
#include <stdbool.h>
#include "gpio.h"

// Hardware Pinout Definitions (Reverse-Engineered from Production Hardware)
#define STATUS_LED_PORT     GPIO_PORT_0
#define STATUS_LED_PIN      GPIO_PIN_4

// External SPI Flash Chip Select (Must remain HIGH while talking to display)
#define FLASH_CS_PORT       GPIO_PORT_0
#define FLASH_CS_PIN        GPIO_PIN_3

// Solomon SSD1619 / SSD1683 E-Ink Display Pinout Map
#define EPD_PWR_EN_PORT     GPIO_PORT_2
#define EPD_PWR_EN_PIN      GPIO_PIN_3

#define EPD_BUSY_PORT       GPIO_PORT_2
#define EPD_BUSY_PIN        GPIO_PIN_0

#define EPD_RST_PORT        GPIO_PORT_0
#define EPD_RST_PIN         GPIO_PIN_7

#define EPD_CS_PORT         GPIO_PORT_2
#define EPD_CS_PIN          GPIO_PIN_1

#define EPD_DC_PORT         GPIO_PORT_0
#define EPD_DC_PIN          GPIO_PIN_5

#define EPD_CLK_PORT        GPIO_PORT_0
#define EPD_CLK_PIN         GPIO_PIN_0

#define EPD_MOSI_PORT       GPIO_PORT_0
#define EPD_MOSI_PIN        GPIO_PIN_6

// Watchdog Configuration (Enabled with ~2.6 second timeout)
#define USER_WDG_CFG        (0xC8)

void periph_init(void);

#endif // _USER_PERIPH_SETUP_H_
