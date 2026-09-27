/**
 ****************************************************************************************
 * @file user_custs1_def.c
 * @brief DA14585 E-Ink Display — Custom GATT Service 1 Database Implementation
 *
 * Builds the CUSTS1 ATT database with:
 *   - One primary service (128-bit UUID)
 *   - Command characteristic (Write + Notify, 20 bytes)
 *   - Image data characteristic (Write Without Response + Write, 247 bytes)
 ****************************************************************************************
 */

#include <stdint.h>
#include "co_utils.h"
#include "prf_types.h"
#include "attm_db_128.h"
#include "user_custs1_def.h"

/*
 * Service and characteristic UUID constants (little-endian wire format)
 */
static const att_svc_desc128_t eink_svc_uuid  = DEF_EINK_SVC_UUID_128;

static const uint8_t EINK_CMD_UUID[ATT_UUID_128_LEN]  = DEF_EINK_CMD_UUID_128;
static const uint8_t EINK_DATA_UUID[ATT_UUID_128_LEN] = DEF_EINK_DATA_UUID_128;

/* Standard ATT declaration UUIDs */
static const uint16_t att_decl_svc       = ATT_DECL_PRIMARY_SERVICE;
static const uint16_t att_decl_char      = ATT_DECL_CHARACTERISTIC;
static const uint16_t att_desc_cfg       = ATT_DESC_CLIENT_CHAR_CFG;
static const uint16_t att_desc_user_desc = ATT_DESC_CHAR_USER_DESCRIPTION;

/* Service table export — required by user_custs_config.c */
const uint8_t  custs1_services[]       = {EINK_SVC_IDX, EINK_CUSTS1_IDX_NB};
const uint8_t  custs1_services_size    = ARRAY_LEN(custs1_services) - 1;
const uint16_t custs1_att_max_nb       = EINK_CUSTS1_IDX_NB;

/**
 * Full CUSTS1 Attribute Database
 *
 * Layout:
 *   [EINK_SVC_IDX]          — Primary Service Declaration
 *   [EINK_CMD_CHAR]         — Command Char Declaration
 *   [EINK_CMD_VAL]          — Command Char Value (Write, Notify)
 *   [EINK_CMD_NTF_CFG]      — Command CCCD (enable notifications)
 *   [EINK_CMD_USER_DESC_IDX]— Command User Description
 *   [EINK_DATA_CHAR]        — Image Data Char Declaration
 *   [EINK_DATA_VAL]         — Image Data Char Value (Write WR + Write)
 *   [EINK_DATA_USER_DESC_IDX]— Image Data User Description
 */
const struct attm_desc_128 custs1_att_db[EINK_CUSTS1_IDX_NB] =
{
    // Primary Service Declaration
    [EINK_SVC_IDX] = {
        (uint8_t*)&att_decl_svc,
        ATT_UUID_128_LEN,
        PERM(RD, ENABLE),
        sizeof(eink_svc_uuid), sizeof(eink_svc_uuid),
        (uint8_t*)&eink_svc_uuid
    },

    /* ── Command / Control Characteristic ─────────────────────────────── */

    // Characteristic Declaration
    [EINK_CMD_CHAR] = {
        (uint8_t*)&att_decl_char, ATT_UUID_16_LEN, PERM(RD, ENABLE),
        0, 0, NULL
    },

    // Characteristic Value — Write (with response) + Notify
    [EINK_CMD_VAL] = {
        (uint8_t*)EINK_CMD_UUID,
        ATT_UUID_128_LEN,
        PERM(WR, ENABLE) | PERM(WRITE_REQ, ENABLE) | PERM(NTF, ENABLE),
        DEF_EINK_CMD_CHAR_LEN, 0, NULL
    },

    // Client Characteristic Configuration Descriptor (for Notify)
    [EINK_CMD_NTF_CFG] = {
        (uint8_t*)&att_desc_cfg,
        ATT_UUID_16_LEN,
        PERM(RD, ENABLE) | PERM(WR, ENABLE) | PERM(WRITE_REQ, ENABLE),
        sizeof(uint16_t), 0, NULL
    },

    // User Description
    [EINK_CMD_USER_DESC_IDX] = {
        (uint8_t*)&att_desc_user_desc,
        ATT_UUID_16_LEN,
        PERM(RD, ENABLE),
        sizeof(DEF_EINK_CMD_USER_DESC) - 1, sizeof(DEF_EINK_CMD_USER_DESC) - 1,
        (uint8_t*)DEF_EINK_CMD_USER_DESC
    },

    /* ── Image Data Stream Characteristic ──────────────────────────────── */

    // Characteristic Declaration
    [EINK_DATA_CHAR] = {
        (uint8_t*)&att_decl_char, ATT_UUID_16_LEN, PERM(RD, ENABLE),
        0, 0, NULL
    },

    // Characteristic Value — Write Without Response + Write
    [EINK_DATA_VAL] = {
        (uint8_t*)EINK_DATA_UUID,
        ATT_UUID_128_LEN,
        PERM(WR, ENABLE) | PERM(WRITE_COMMAND, ENABLE) | PERM(WRITE_REQ, ENABLE),
        DEF_EINK_DATA_CHAR_LEN, 0, NULL
    },

    // User Description
    [EINK_DATA_USER_DESC_IDX] = {
        (uint8_t*)&att_desc_user_desc,
        ATT_UUID_16_LEN,
        PERM(RD, ENABLE),
        sizeof(DEF_EINK_DATA_USER_DESC) - 1, sizeof(DEF_EINK_DATA_USER_DESC) - 1,
        (uint8_t*)DEF_EINK_DATA_USER_DESC
    },
};
