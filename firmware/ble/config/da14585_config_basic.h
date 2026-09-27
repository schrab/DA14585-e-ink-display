/**
 ****************************************************************************************
 * @file da14585_config_basic.h
 * @brief DA14585 E-Ink Display BLE Firmware — Basic Compile Configuration
 ****************************************************************************************
 */

#ifndef _DA14585_CONFIG_BASIC_H_
#define _DA14585_CONFIG_BASIC_H_

#include "da1458x_stack_config.h"
#include "user_profiles_config.h"

/******************************************************************************
 * Integrated processor mode: Host app runs in DA14585.
 *****************************************************************************/
#define CFG_APP

/******************************************************************************
 * BLE security: disabled (no pairing required for e-ink image transfer).
 *****************************************************************************/
#undef CFG_APP_SECURITY

/******************************************************************************
 * Watchdog: enabled (SDK reloads it automatically on wakeup).
 *****************************************************************************/
#define CFG_WDOG

/******************************************************************************
 * Watchdog in production: generates NMI (not hard reset).
 *****************************************************************************/
#undef CFG_WDG_TRIGGER_HW_RESET_IN_PRODUCTION_MODE

/******************************************************************************
 * Maximum simultaneous BLE connections: 1 (peripheral only).
 *****************************************************************************/
#define CFG_MAX_CONNECTIONS     (1)

/******************************************************************************
 * Development/debug mode: enabled (allows hot-attach of SWD debugger).
 *****************************************************************************/
#define CFG_DEVELOPMENT_DEBUG

/******************************************************************************
 * UART console print: disabled (no UART pins available on this board).
 *****************************************************************************/
#undef CFG_PRINTF

/******************************************************************************
 * UART1 SDK driver override: disabled.
 *****************************************************************************/
#undef CFG_UART1_SDK

/******************************************************************************
 * External memory: SPI flash enabled for NVDS (BD address storage).
 *****************************************************************************/
#define CFG_SPI_FLASH_ENABLE
#undef CFG_I2C_EEPROM_ENABLE

/******************************************************************************
 * DMA: all disabled (we bit-bang SPI to the e-ink display).
 *****************************************************************************/
#undef CFG_UART_DMA_SUPPORT
#undef CFG_SPI_DMA_SUPPORT
#undef CFG_I2C_DMA_SUPPORT

#endif // _DA14585_CONFIG_BASIC_H_
