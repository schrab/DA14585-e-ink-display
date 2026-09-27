/**
 ****************************************************************************************
 * @file user_profiles_config.h
 * @brief DA14585 E-Ink Display — Active BLE Profile Configuration
 *
 * Enables:
 *   - CFG_PRF_DISS  — Device Information Service (mandatory)
 *   - CFG_PRF_CUSTS1 — Custom Service 1 (e-ink image transfer + command channel)
 ****************************************************************************************
 */

#ifndef _USER_PROFILES_CONFIG_H_
#define _USER_PROFILES_CONFIG_H_

/*
 * Enabled BLE profiles (consumed by rwprf_config.h)
 */

// Device Information Service (DIS) — GATT service 0x180A
#define CFG_PRF_DISS

// Custom Profile Server 1 — 128-bit UUID e-ink display service
#define CFG_PRF_CUST1


/*
 * DISS application profile configuration
 */
#define APP_DIS_FEATURES                (DIS_MANUFACTURER_NAME_CHAR_SUP | \
                                        DIS_MODEL_NB_STR_CHAR_SUP | \
                                        DIS_FIRM_REV_STR_CHAR_SUP | \
                                        DIS_SW_REV_STR_CHAR_SUP | \
                                        DIS_PNP_ID_CHAR_SUP)

/// Manufacturer Name
#define APP_DIS_MANUFACTURER_NAME       ("Renesas")
#define APP_DIS_MANUFACTURER_NAME_LEN   (sizeof(APP_DIS_MANUFACTURER_NAME) - 1)

/// Model Number — match factory firmware
#define APP_DIS_MODEL_NB_STR            ("EINK-V115-42000")
#define APP_DIS_MODEL_NB_STR_LEN        (15)

/// Firmware Revision — match factory firmware
#define APP_DIS_FIRM_REV_STR            ("6.0.22.1401")
#define APP_DIS_FIRM_REV_STR_LEN        (sizeof(APP_DIS_FIRM_REV_STR) - 1)

/// Software Revision
#define APP_DIS_SW_REV_STR              SDK_VERSION
#define APP_DIS_SW_REV_STR_LEN          (sizeof(APP_DIS_SW_REV_STR) - 1)

/// Hardware Revision — match factory firmware
#define APP_DIS_HARD_REV_STR            ("DA14585-EINK-V1.1")
#define APP_DIS_HARD_REV_STR_LEN        (sizeof(APP_DIS_HARD_REV_STR) - 1)

/// System ID
#define APP_DIS_SYSTEM_ID               ("\x12\x34\x56\xFF\xFE\x9A\xBC\xDE")
#define APP_DIS_SYSTEM_ID_LEN           (8)

/// Serial Number
#define APP_DIS_SERIAL_NB_STR           ("1.0.0.0-LE")
#define APP_DIS_SERIAL_NB_STR_LEN       (10)

/// IEEE
#define APP_DIS_IEEE                    ("\xFF\xEE\xDD\xCC\xBB\xAA")
#define APP_DIS_IEEE_LEN                (6)

/// PNP ID
#define APP_DIS_PNP_ID                  ("\x01\xD2\x00\x80\x05\x00\x01")
#define APP_DIS_PNP_ID_LEN              (7)

// DISS Firmware Rev (SDK_VERSION macro alias)
#define APP_DIS_FIRM_REV                SDK_VERSION
#define APP_DIS_SW_REV                  SDK_VERSION

#endif // _USER_PROFILES_CONFIG_H_
