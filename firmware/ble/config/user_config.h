/**
 ****************************************************************************************
 * @file user_config.h
 * @brief DA14585 E-Ink Display — BLE GAP / Advertising Configuration
 *
 * Advertising packet: Complete Local Name "EINK-V115-42000"
 * Matches factory firmware advertising behavior.
 ****************************************************************************************
 */

#ifndef _USER_CONFIG_H_
#define _USER_CONFIG_H_

#include "app_user_config.h"
#include "arch_api.h"
#include "app_default_handlers.h"
#include "app_adv_data.h"
#include "co_bt.h"

/* ─── Privacy / Addressing ───────────────────────────────────────────────── */

// Use the public BD address stored in NVDS (flash 0x040000 = 11:E9:8F:9E:2A:86)
#define USER_CFG_ADDRESS_MODE       APP_CFG_ADDR_PUB
#define USER_CFG_CNTL_PRIV_MODE     APP_CFG_CNTL_PRIV_MODE_NETWORK

/* ─── Sleep Mode ─────────────────────────────────────────────────────────── */

// Sleep disabled — DA14585 stays powered to keep the e-ink image alive via
// watchdog. Extended sleep would cause the factory bootloader to wipe the screen.
static const sleep_state_t app_default_sleep_mode = ARCH_SLEEP_OFF;

/* ─── Advertising Data ────────────────────────────────────────────────────── */

// Complete Local Name: "EINK-V115-42000" (15 bytes)
// AD Structure: [length=0x10][type=0x09][EINK-V115-42000]
#define USER_ADVERTISE_DATA \
    "\x10" "\x09" "EINK-V115-42000"

#define USER_ADVERTISE_DATA_LEN     (sizeof(USER_ADVERTISE_DATA) - 1)

// Scan response: empty
#define USER_ADVERTISE_SCAN_RESPONSE_DATA       ""
#define USER_ADVERTISE_SCAN_RESPONSE_DATA_LEN   (sizeof(USER_ADVERTISE_SCAN_RESPONSE_DATA) - 1)

/* ─── Device Name ────────────────────────────────────────────────────────── */

#define USER_DEVICE_NAME        "EINK-V115-42000"
#define USER_DEVICE_NAME_LEN    (sizeof(USER_DEVICE_NAME) - 1)

/* ─── GAPM Configuration ─────────────────────────────────────────────────── */

static const struct gapm_configuration user_gapm_conf = {
    .role        = GAP_ROLE_PERIPHERAL,
    .max_mtu     = 247,  // Match factory MTU for image data transfer
    .addr_type   = APP_CFG_ADDR_TYPE(USER_CFG_ADDRESS_MODE),
    .renew_dur   = 15000,
    .addr        = {0x00, 0x00, 0x00, 0x00, 0x00, 0x00}, // from NVDS
    .irk         = {0x00, 0x01, 0x02, 0x03, 0x04, 0x05,
                    0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b,
                    0x0c, 0x0d, 0x0e, 0x0f},
    .att_cfg     = GAPM_MASK_ATT_SVC_CHG_EN,
    .gap_start_hdl  = 0,
    .gatt_start_hdl = 0,
    .max_mps        = 0,
    .max_txoctets   = 251,
    .max_txtime     = 2120,
};

/* ─── Advertising Intervals ──────────────────────────────────────────────── */

static const struct advertise_configuration user_adv_conf = {
    .addr_src       = APP_CFG_ADDR_SRC(USER_CFG_ADDRESS_MODE),
    .intv_min       = MS_TO_BLESLOTS(687.5),
    .intv_max       = MS_TO_BLESLOTS(687.5),
    .channel_map    = ADV_ALL_CHNLS_EN,
    .mode           = GAP_GEN_DISCOVERABLE,
    .adv_filt_policy = ADV_ALLOW_SCAN_ANY_CON_ANY,
    .peer_addr      = {0x1, 0x2, 0x3, 0x4, 0x5, 0x6},
    .peer_addr_type = 0,
};

/* ─── Connection Parameters ──────────────────────────────────────────────── */

static const struct connection_param_configuration user_connection_param_conf = {
    .intv_min   = MS_TO_DOUBLESLOTS(10),
    .intv_max   = MS_TO_DOUBLESLOTS(20),
    .latency    = 0,
    .time_out   = MS_TO_TIMERUNITS(1250),
    .ce_len_min = MS_TO_DOUBLESLOTS(0),
    .ce_len_max = MS_TO_DOUBLESLOTS(0),
};

/* ─── Default Handler Configuration ─────────────────────────────────────── */

static const struct default_handlers_configuration user_default_hnd_conf = {
    .adv_scenario              = DEF_ADV_FOREVER,
    .advertise_period          = MS_TO_TIMERUNITS(180000),
    .security_request_scenario = DEF_SEC_REQ_NEVER,
};

/* ─── Central / Security Config (unused — peripheral only) ──────────────── */

static const struct central_configuration user_central_conf = {
    .code = GAPM_CONNECTION_DIRECT,
    .addr_src       = APP_CFG_ADDR_SRC(USER_CFG_ADDRESS_MODE),
    .scan_interval  = 0x180,
    .scan_window    = 0x160,
    .con_intv_min   = 100,
    .con_intv_max   = 100,
    .con_latency    = 0,
    .superv_to      = 0x1F4,
    .ce_len_min     = 0,
    .ce_len_max     = 0x5,
    .peer_addr_0    = {0},  .peer_addr_0_type = 0,
    .peer_addr_1    = {0},  .peer_addr_1_type = 0,
    .peer_addr_2    = {0},  .peer_addr_2_type = 0,
    .peer_addr_3    = {0},  .peer_addr_3_type = 0,
    .peer_addr_4    = {0},  .peer_addr_4_type = 0,
    .peer_addr_5    = {0},  .peer_addr_5_type = 0,
    .peer_addr_6    = {0},  .peer_addr_6_type = 0,
    .peer_addr_7    = {0},  .peer_addr_7_type = 0,
};

static const struct security_configuration user_security_conf = {
    .iocap    = GAP_IO_CAP_NO_INPUT_NO_OUTPUT,
    .oob      = GAP_OOB_AUTH_DATA_NOT_PRESENT,
    .auth     = GAP_AUTH_NONE,
    .key_size = KEY_LEN,
    .ikey_dist = GAP_KDIST_NONE,
    .rkey_dist = GAP_KDIST_ENCKEY,
    .sec_req  = GAP_NO_SEC,
};

/*
 * KE message heap size (bytes of payload; jump_table.c adds a 12-byte block header).
 *
 * The SDK default is RWIP_HEAP_MSG_SIZE_USER == 1392 bytes, which is the *only*
 * source of KE messages. At an MTU of 247 every ATT write allocates a ~250-byte
 * message, so the default pool holds only ~5 in flight. Streaming the 30,000-byte
 * tri-color frame faster than the stack drains it exhausts the pool, and the
 * allocator then hands out blocks that overlap already-freed ones (observed: a
 * faulting ke_msg whose 12 bytes sat on top of an 0xA55A free-block header in
 * rwip_heap_msg_ret), which the ROM dereferences as a garbage handler address.
 *
 * Raised to 1904 to absorb the write burst. The retained RAM region
 * (LR_RETAINED_RAM0) has only ~640 bytes of slack, so this cannot grow much further
 * without shrinking eink_framebuffer, which accounts for 30,000 of our 30,316
 * bytes of .bss.
 *
 * The EINK_DIAG=1 build adds ~650 bytes of retained RAM for the CRC history, which
 * does not fit alongside the enlarged pool (LR_RETAINED_RAM0 overflows by ~456 B).
 * Diagnostic builds therefore fall back to the SDK default so they always link;
 * EINK_DIAG is a debugging build, so it does not need the bigger pool.
 */
#if EINK_DIAG
/* Step-zero follow-up (2026-09-28). The ATT Write-Request failure on EINK_DIAG=1 was
 * initially blamed on heap budget. It is not: the binding constraint is the ~37 ms
 * blocking CRC32 pass that diag_snapshot() runs inside the KE write handler. With
 * EINK_DIAG_CRC_OFF=1 and these original SDK pool sizes the failure disappears, so the
 * pools are left at the SDK defaults here.
 *
 * (An intermediate experiment traded 408 B out of MSG_HEAP_SZ into ENV_HEAP_SZ --
 * msg 1392->984, env 616->1024, net zero -- to test env exhaustion. It did not help;
 * see BLE_CRASH_DIAGNOSIS.md. ENV_HEAP_SZ also cannot simply be raised: it overflows
 * LR_RETAINED_RAM0 by 280 B on EINK_DIAG=0 and 352 B on EINK_DIAG=1, because the
 * diagnostic build already spends ~650 B of retained RAM on the CRC history.) */
#else
#define MSG_HEAP_SZ  (1904)
#endif

#endif // _USER_CONFIG_H_
