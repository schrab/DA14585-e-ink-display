/**
 ****************************************************************************************
 * @file user_eink_app.c
 * @brief DA14585 E-Ink Display — BLE Application Implementation
 *
 * Provides the Dialog SDK application callback layer for:
 *   - BLE advertising (device name: EINK-V115-42000)
 *   - Custom GATT Service (UUID: afdbecdd-1234-abcd-2007-aabbccddeeff)
 *     - Command characteristic: receive commands (Refresh, Clear, Status)
 *     - Image Data characteristic: receive raw 1-bit scanline data chunks
 *       and reconstruct the dual-buffer (BW + Red) framebuffer in SysRAM,
 *       then trigger an SSD1619 tri-color display refresh.
 *
 * BLE Image Transfer Protocol:
 *   - Image Data writes accumulate into eink_framebuffer[30000]:
 *       Bytes [0..14999]  = Black/White RAM plane (0x24)
 *       Bytes [15000..29999] = Red RAM plane (0x26)
 *   - Each write contains a 2-byte offset header + payload:
 *       Byte 0-1: uint16_t offset into eink_framebuffer[]
 *       Byte 2-N: raw pixel data
 *   - Command 0x06 triggers epd_display_refresh_tricolor()
 *   - Command 0x07 clears both planes to white/non-red
 ****************************************************************************************
 */

#include "rwip_config.h"
#include "gap.h"
#include "app_easy_timer.h"
#include "app_default_handlers.h"
#include "app_adv_data.h"
#include "app_callback.h"
#include "ke_msg.h"
#include "custs1_task.h"
#include "user_eink_app.h"
#include "user_eink_diag.h"
#include "user_custs1_def.h"
#include "user_periph_setup.h"
#include "gpio.h"
#include "ssd1619.h"

/* ─── Retained Variables ─────────────────────────────────────────────────── */

/// Current BLE connection index (0xFF = no connection)
uint8_t app_connection_idx   __SECTION_ZERO("retention_mem_area0");

/// Framebuffer in application RAM (.bss):
///   [0..14999]     = Black/White plane (for SSD1619 0x24 command)
///   [15000..29999] = Red plane         (for SSD1619 0x26 command)
/// Total: 30000 bytes = 2 × (50 bytes × 300 lines)
uint8_t eink_framebuffer[30000];

/// Bytes received so far into eink_framebuffer (for status reporting)
uint16_t eink_rx_bytes;

/// Receipt bitmap, one bit per EINK_CHUNK_SIZE-byte chunk.
///
/// This exists because a naive byte counter is not enough to make an upload
/// self-verifying. ATT Write Without Response has no link-layer retransmission, so
/// the host can outrun this device and have whole chunks silently dropped. Measured
/// on this board, the loss is a *contiguous suffix run* whose length grows with how
/// hard the host pushes: ~30 chunks lost at 15 ms/packet, ~57 at 5 ms/packet. Because
/// eink_rx_bytes only accumulates, a large value looks "nearly complete" while a band
/// of the image in the middle is missing. A per-chunk bitmap lets the host re-send
/// exactly the gaps instead of guessing.
uint8_t eink_chunk_map[EINK_CHUNK_MAP_BYTES];


/* ─── user_app_init ──────────────────────────────────────────────────────── */

void user_app_init(void)
{
    // Initialise the GPIO pad configuration and wake the peripheral domain
    periph_init();

    // Brief double-blink on the status LED to signal BLE boot
    for (int i = 0; i < 2; i++) {
        GPIO_SetInactive(STATUS_LED_PORT, STATUS_LED_PIN); // ON  (active-LOW)
        arch_asm_delay_us(100000);
        GPIO_SetActive(STATUS_LED_PORT, STATUS_LED_PIN);   // OFF
        arch_asm_delay_us(100000);
    }

    // Default SDK handler sets device role, address, etc.
    default_app_on_init();

    // Baseline snapshot: whatever the SDK initialisation legitimately touched.
    diag_snapshot(DIAG_PHASE_BOOT);
}

/* ─── Advertising ────────────────────────────────────────────────────────── */

void user_app_adv_start(void)
{
    app_easy_gap_undirected_advertise_start();
}

void user_app_adv_undirect_complete(uint8_t status)
{
    // Restart advertising only if advertising was canceled (not when a connection was formed)
    if (status == GAP_ERR_CANCELED) {
        user_app_adv_start();
    }
}

/* ─── Connection Lifecycle ───────────────────────────────────────────────── */

void user_app_connection(uint8_t connection_idx,
                         struct gapc_connection_req_ind const *param)
{
    app_connection_idx = connection_idx;

    // LED: solid ON while connected
    GPIO_SetInactive(STATUS_LED_PORT, STATUS_LED_PIN);

    // Let the SDK handle default connection setup (version exchange, etc.)
    default_app_on_connection(connection_idx, param);
}

void user_app_disconnect(struct gapc_disconnect_ind const *param)
{
    // A disconnect is the known trigger for the refresh HardFault, so capture the
    // RAM state at the exact moment the link drops.
    diag_snapshot(DIAG_PHASE_DISCONNECT);
    diag_set_count(eink_rx_bytes);

    // LED: OFF when disconnected
    GPIO_SetActive(STATUS_LED_PORT, STATUS_LED_PIN);

    app_connection_idx = GAP_INVALID_CONIDX;

    // Restart advertising
    user_app_adv_start();
}

/* ─── Deferred E-Ink Refresh Callback ────────────────────────────────────── */

static void user_eink_refresh_timer_cb(void)
{
    // LED ON during refresh
    GPIO_SetInactive(STATUS_LED_PORT, STATUS_LED_PIN);

    // Bracket the blocking cycle: anything the ROM stack or our own bit-banged SPI
    // writes into the wrong region shows up as a CRC delta between these two.
    diag_snapshot(DIAG_PHASE_PRE_REFRESH);
    diag_set_count(eink_rx_bytes);

    // Initialise display and execute physical 3-color refresh cycle (~17s)
    epd_init();
    epd_display_refresh_tricolor(eink_framebuffer,
                                 eink_framebuffer + 15000);

    diag_snapshot(DIAG_PHASE_POST_REFRESH);
    diag_set_count(eink_rx_bytes);

    // LED OFF after refresh completes
    GPIO_SetActive(STATUS_LED_PORT, STATUS_LED_PIN);
    eink_rx_bytes = 0;
}

/* ─── Command Characteristic Write Handler ───────────────────────────────── */

void user_eink_cmd_wr_handler(ke_msg_id_t const msgid,
                              struct custs1_val_write_ind const *param,
                              ke_task_id_t const dest_id,
                              ke_task_id_t const src_id)
{
    if (param->length < 1) {
        return;
    }

    uint8_t cmd_id = param->value[0];

    switch (cmd_id) {

    case 0x06:
        // Schedule refresh to run in 100ms via SDK easy timer so GATT write response is sent first
        diag_snapshot(DIAG_PHASE_CMD_REFRESH);
        diag_set_count(eink_rx_bytes);
        app_easy_timer(10, user_eink_refresh_timer_cb);
        break;

    case 0x07:
        // Clear: fill both planes to white/non-red
        for (uint16_t i = 0; i < 15000; i++) {
            eink_framebuffer[i]         = 0xFF; // BW plane: all-white
            eink_framebuffer[i + 15000] = 0x00; // Red plane: non-red
        }
        eink_rx_bytes = 0;
        memset(eink_chunk_map, 0, sizeof(eink_chunk_map));
        diag_snapshot(DIAG_PHASE_CMD_CLEAR);
        diag_set_count(eink_rx_bytes);
        break;

    case 0x08:
        // Status query: notify the chunk-receipt bitmap (16 B) followed by the
        // 2-byte byte counter, so the host can re-send exactly the chunks that were
        // dropped. A scalar counter is not enough - see eink_chunk_map.
        {
            uint8_t rsp[EINK_CHUNK_MAP_BYTES + 2];
            memcpy(rsp, eink_chunk_map, EINK_CHUNK_MAP_BYTES);
            rsp[EINK_CHUNK_MAP_BYTES]     = eink_rx_bytes & 0xFF;
            rsp[EINK_CHUNK_MAP_BYTES + 1] = (eink_rx_bytes >> 8) & 0xFF;
            struct custs1_val_ntf_ind_req *ntf_req =
                KE_MSG_ALLOC_DYN(CUSTS1_VAL_NTF_REQ,
                                 prf_get_task_from_id(KE_BUILD_ID(TASK_ID_CUSTS1,
                                                                   app_connection_idx)),
                                 TASK_APP,
                                 custs1_val_ntf_ind_req,
                                 sizeof(rsp));
            ntf_req->conidx      = app_connection_idx;
            ntf_req->notification = true;
            ntf_req->handle      = EINK_CMD_VAL;
            ntf_req->length      = sizeof(rsp);
            memcpy(ntf_req->value, rsp, sizeof(rsp));
            ke_msg_send(ntf_req);
        }
        break;

    case 0x09:
        // On-demand CRC snapshot, for bisecting the corruption over SWD.
        diag_snapshot(DIAG_PHASE_MANUAL);
        diag_set_count(eink_rx_bytes);
        break;

    default:
        // Unknown command — ignore
        break;
    }
}

/* ─── Image Data Characteristic Write Handler ────────────────────────────── */

void user_eink_data_wr_handler(ke_msg_id_t const msgid,
                               struct custs1_val_write_ind const *param,
                               ke_task_id_t const dest_id,
                               ke_task_id_t const src_id)
{
    // Packet format: [offset_lo][offset_hi][data bytes...]
    if (param->length < 3) {
        return;
    }

    uint16_t offset = (uint16_t)param->value[0] |
                     ((uint16_t)param->value[1] << 8);
    uint16_t data_len = param->length - 2;

    // Bounds check: framebuffer is 30000 bytes
    if (offset + data_len > 30000) {
        return;
    }

    memcpy(&eink_framebuffer[offset], &param->value[2], data_len);
    eink_rx_bytes += data_len;

    // Record receipt per chunk. A chunk counts as received only if the write landed
    // exactly on a chunk boundary with the full payload, so a truncated or
    // misaligned write cannot mark data as good.
    if ((offset % EINK_CHUNK_SIZE) == 0) {
        uint16_t idx = (uint16_t)(offset / EINK_CHUNK_SIZE);
        if (idx < EINK_CHUNK_COUNT) {
            eink_chunk_map[idx >> 3] |= (uint8_t)(1u << (idx & 7));
        }
    }
}

/* ─── Catch-All Handler ──────────────────────────────────────────────────── */

void user_catch_rest_hndl(ke_msg_id_t const msgid,
                          void const *param,
                          ke_task_id_t const dest_id,
                          ke_task_id_t const src_id)
{
    switch (msgid) {

    case CUSTS1_VAL_WRITE_IND: {
        // Route to the correct handler based on characteristic handle index
        const struct custs1_val_write_ind *wr =
            (const struct custs1_val_write_ind *)param;

        // Tight bracket around the write: the ROM ATT response path runs between
        // POST_WRITE and the next application entry point, and that is where the
        // firmware hardfaults, so a delta here localises the corrupting write.
        diag_snapshot(DIAG_PHASE_PRE_WRITE);
        diag_set_count(wr->length);

        diag_observe((uint16_t)msgid, (uint16_t)dest_id, (uint16_t)src_id,
                     wr->handle, wr->length,
                     (wr->length > 0) ? wr->value[0] : 0xFF);

        if (wr->handle == EINK_CMD_VAL) {
            diag_route(1);
            user_eink_cmd_wr_handler(msgid, wr, dest_id, src_id);
        } else if (wr->handle == EINK_DATA_VAL) {
            diag_route(2);
            user_eink_data_wr_handler(msgid, wr, dest_id, src_id);
        } else {
            diag_route(3);
        }

        diag_snapshot(DIAG_PHASE_POST_WRITE);
        diag_set_count(wr->length);
        break;
    }

    default:
        // Silently discard all other unhandled messages
        break;
    }
}
