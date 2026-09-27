/**
 ****************************************************************************************
 * @file user_eink_app.h
 * @brief DA14585 E-Ink Display BLE Application — Public API
 *
 * Implements the Dialog SDK BLE callback interface for the e-ink display device.
 * Device name: EINK-V115-42000
 * Custom Service UUID: afdbecdd-1234-abcd-2007-aabbccddeeff
 ****************************************************************************************
 */

#ifndef _USER_EINK_APP_H_
#define _USER_EINK_APP_H_

#include <stdint.h>
#include "gapc_task.h"
#include "gapm_task.h"
#include "custs1_task.h"

/* ─── BLE Advertising Configuration ─────────────────────────────────────── */

/// Device name advertised over BLE (matches factory firmware)
#define USER_DEVICE_NAME            "EINK-V115-42000"
#define USER_DEVICE_NAME_LEN        (sizeof(USER_DEVICE_NAME) - 1)

/* ─── Application Callbacks (arch_main_loop_callbacks) ──────────────────── */

/**
 * @brief Called once on first boot — initialises peripherals and starts BLE advertising.
 */
void user_app_init(void);

/* ─── BLE GAP Callbacks ──────────────────────────────────────────────────── */

/**
 * @brief Called when a central device connects.
 */
void user_app_connection(uint8_t connection_idx, struct gapc_connection_req_ind const *param);

/**
 * @brief Called when the BLE connection is terminated.
 */
void user_app_disconnect(struct gapc_disconnect_ind const *param);

/**
 * @brief Called when advertising completes (used to restart advertising).
 */
void user_app_adv_undirect_complete(uint8_t status);

/**
 * @brief Starts BLE advertising — called from default_app_on_db_init_complete.
 */
void user_app_adv_start(void);

/* ─── Custom GATT Write Handlers ─────────────────────────────────────────── */

/**
 * @brief Handles a CUSTS1 write to the Command characteristic (0x9e1547ba...).
 *        Commands: 0x06=Refresh, 0x07=Clear, 0x08=Status
 */
void user_eink_cmd_wr_handler(ke_msg_id_t const msgid,
                              struct custs1_val_write_ind const *param,
                              ke_task_id_t const dest_id,
                              ke_task_id_t const src_id);

/**
 * @brief Handles a CUSTS1 write to the Image Data characteristic (0x772ae377...).
 *        Receives raw scanline chunks and writes them into the framebuffer.
 */
void user_eink_data_wr_handler(ke_msg_id_t const msgid,
                               struct custs1_val_write_ind const *param,
                               ke_task_id_t const dest_id,
                               ke_task_id_t const src_id);

/**
 * @brief Unhandled message catch-all — required by app_entry_point.c.
 */
void user_catch_rest_hndl(ke_msg_id_t const msgid,
                          void const *param,
                          ke_task_id_t const dest_id,
                          ke_task_id_t const src_id);

#endif // _USER_EINK_APP_H_
