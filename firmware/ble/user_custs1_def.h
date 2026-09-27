/**
 ****************************************************************************************
 * @file user_custs1_def.h
 * @brief DA14585 E-Ink Display — Custom GATT Service 1 Database Definitions
 *
 * Reverse-engineered from factory BLE firmware (da14585_fw_image2.bin).
 * Replicates the exact 128-bit UUIDs exposed by the factory EINK-V115-42000 device.
 *
 * Service UUID (RFC4122): afdbecdd-1234-abcd-2007-aabbccddeeff
 * Wire / LE byte order:   FF EE DD CC BB AA 07 20 CD AB 34 12 DD EC DB AF
 *
 * Characteristic 1 — Command/Control (Write, Notify):
 *   RFC4122: 9e1547ba-c365-57b5-2947-c5e1c1e1d528
 *   Wire:    28 D5 E1 C1 E1 C5 47 29 B5 57 65 C3 BA 47 15 9E
 *
 * Characteristic 2 — Image Data Stream (Write Without Response / Write):
 *   RFC4122: 772ae377-b3d2-4f8e-4042-5481d121199c
 *   Wire:    9C 19 21 D1 81 54 42 40 8E 4F D2 B3 77 E3 2A 77
 ****************************************************************************************
 */

#ifndef _USER_CUSTS1_DEF_H_
#define _USER_CUSTS1_DEF_H_

#include "attm_db_128.h"

/*
 * Service UUID — 128-bit, little-endian (wire order)
 * RFC4122: afdbecdd-1234-abcd-2007-aabbccddeeff
 */
#define DEF_EINK_SVC_UUID_128 \
    {0xFF, 0xEE, 0xDD, 0xCC, 0xBB, 0xAA, 0x07, 0x20, \
     0xCD, 0xAB, 0x34, 0x12, 0xDD, 0xEC, 0xDB, 0xAF}

/*
 * Characteristic 1 — Command/Control channel
 * RFC4122: 9e1547ba-c365-57b5-2947-c5e1c1e1d528
 * Properties: Write (with response), Notify
 * Max length: 20 bytes
 */
#define DEF_EINK_CMD_UUID_128 \
    {0x28, 0xD5, 0xE1, 0xC1, 0xE1, 0xC5, 0x47, 0x29, \
     0xB5, 0x57, 0x65, 0xC3, 0xBA, 0x47, 0x15, 0x9E}
#define DEF_EINK_CMD_CHAR_LEN       (20)
#define DEF_EINK_CMD_USER_DESC      "Command"

/*
 * Characteristic 2 — Image Data Stream
 * RFC4122: 772ae377-b3d2-4f8e-4042-5481d121199c
 * Properties: Write Without Response, Write
 * Max length: 247 bytes (matches factory MTU)
 */
#define DEF_EINK_DATA_UUID_128 \
    {0x9C, 0x19, 0x21, 0xD1, 0x81, 0x54, 0x42, 0x40, \
     0x8E, 0x4F, 0xD2, 0xB3, 0x77, 0xE3, 0x2A, 0x77}
#define DEF_EINK_DATA_CHAR_LEN      (247)
#define DEF_EINK_DATA_USER_DESC     "Image Data"

/**
 * Custom Service 1 Attribute Database Index Enum
 */
enum
{
    // Primary Service Declaration
    EINK_SVC_IDX = 0,

    // Command / Control Characteristic
    EINK_CMD_CHAR,
    EINK_CMD_VAL,
    EINK_CMD_NTF_CFG,           // Client Characteristic Configuration (Notify)
    EINK_CMD_USER_DESC_IDX,

    // Image Data Stream Characteristic
    EINK_DATA_CHAR,
    EINK_DATA_VAL,
    EINK_DATA_USER_DESC_IDX,

    EINK_CUSTS1_IDX_NB
};

#endif // _USER_CUSTS1_DEF_H_
