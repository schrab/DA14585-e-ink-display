/**
 ****************************************************************************************
 * @file da14585_config_advanced.h
 * @brief DA14585 E-Ink Display — Advanced Compile Configuration
 *
 * Memory layout defines used by the SDK linker script preprocessor
 * (ldscript_DA14585_586.lds.S) and the BLE stack.
 ****************************************************************************************
 */

#ifndef _DA14585_CONFIG_ADVANCED_H_
#define _DA14585_CONFIG_ADVANCED_H_

#include "da1458x_stack_config.h"

// Low Power clock: external XTAL32K (matches factory firmware)
#define CFG_LP_CLK              LP_CLK_XTAL32

// Use hardcoded default XTAL16M trimming for development board
#define CFG_USE_DEFAULT_XTAL16M_TRIM_VALUE_IF_NOT_CALIBRATED

// Periodic wakeup period for GTL polling (ms)
#define CFG_MAX_SLEEP_DURATION_PERIODIC_WAKEUP_MS      500

// Max sleep duration without external wakeup (ms)
#define CFG_MAX_SLEEP_DURATION_EXTERNAL_WAKEUP_MS      600000

// External wakeup: disabled
#undef CFG_EXTERNAL_WAKEUP

// Wakeup external processor on GTL message: disabled
#undef CFG_WAKEUP_EXT_PROCESSOR

// TRNG: enabled with 1024 byte buffer for seeding
#define CFG_TRNG (1024)

// Secure connections: disabled (no pairing)
#undef CFG_ENABLE_SMP_SECURE

// Use ChaCha20 PRNG instead of C stdlib rand()
#define CFG_USE_CHACHA20_RAND

// NVDS: default BD address (overridden by NVDS read from SPI flash 0x040000)
// The actual address 11:E9:8F:9E:2A:86 is stored in the factory NVDS partition
#define CFG_NVDS_TAG_BD_ADDRESS             {0x86, 0x2A, 0x9E, 0x8F, 0xE9, 0x11}

#define CFG_NVDS_TAG_LPCLK_DRIFT            DRIFT_500PPM
#define CFG_NVDS_TAG_BLE_CA_TIMER_DUR       (500)
#define CFG_NVDS_TAG_BLE_CRA_TIMER_DUR      (8)
#define CFG_NVDS_TAG_BLE_CA_MIN_RSSI        (-60)
#define CFG_NVDS_TAG_BLE_CA_NB_PKT          (20)
#define CFG_NVDS_TAG_BLE_CA_NB_BAD_PKT      (CFG_NVDS_TAG_BLE_CA_NB_PKT/2)

// BLE statistics: disabled
#undef CFG_BLE_METRICS

// Hardfault UART output: disabled
#undef CFG_PRODUCTION_DEBUG_OUTPUT

// Max TX/RX packet length: 251 bytes (BLE 4.2 DLE)
#define CFG_MAX_TX_PACKET_LENGTH        (251)
#define CFG_MAX_RX_PACKET_LENGTH        (251)

// Transport layer: GTL auto
#define CFG_USE_H4TL                    (0)

// Duplicate scan filter
#define CFG_BLE_DUPLICATE_FILTER_MAX    (10)
#undef CFG_BLE_DUPLICATE_FILTER_FOUND

// Resolving list
#define CFG_LLM_RESOLVING_LIST_MAX      LLM_RESOLVING_LIST_MAX

// Data length negotiation: disabled
#undef AUTO_DATA_LENGTH_NEGOTIATION_UPON_NEW_CONNECTION

// Retention memory: 2048 bytes
#define CFG_RET_DATA_SIZE       (2048)
#define CFG_RET_DATA_UNINIT_SIZE (0)

// Retain all three RAM blocks across extended sleep
#define CFG_RETAIN_RAM_1_BLOCK
#define CFG_RETAIN_RAM_2_BLOCK
#define CFG_RETAIN_RAM_3_BLOCK

// Auto-detect non-retained heap block retention
#define CFG_AUTO_DETECT_NON_RET_HEAP

// Code stored on external SPI flash
#define CFG_CODE_LOCATION_EXT
#undef CFG_CODE_LOCATION_OTP
#undef CFG_CODE_SIZE_FOR_OTP_COPY_ON

// Temperature: ambient range (-40C to +40C)
#define CFG_AMB_TEMPERATURE

// XTAL16M adaptive settling for power optimization
#define CFG_XTAL16M_ADAPTIVE_SETTLING

// Wakeup metrics: disabled
#undef CFG_ENABLE_WAKEUP_METRICS

#endif // _DA14585_CONFIG_ADVANCED_H_
