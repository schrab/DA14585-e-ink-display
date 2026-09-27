/**
 ****************************************************************************************
 * @file user_callback_config.h
 * @brief DA14585 E-Ink Display — BLE Callback Registration
 *
 * Wires the user_eink_app.c functions into the SDK app_entry_point dispatch tables.
 ****************************************************************************************
 */

#ifndef _USER_CALLBACK_CONFIG_H_
#define _USER_CALLBACK_CONFIG_H_

#include <stdio.h>
#include "app_callback.h"
#include "app_default_handlers.h"
#include "app_entry_point.h"
#include "app_prf_types.h"
#include "user_eink_app.h"
#include "custs1_task.h"
#include "user_custs1_def.h"

/* ─── GAP / App Callbacks ────────────────────────────────────────────────── */

static const struct app_callbacks user_app_callbacks = {
    .app_on_connection                  = user_app_connection,
    .app_on_disconnect                  = user_app_disconnect,
    .app_on_update_params_rejected      = NULL,
    .app_on_update_params_complete      = NULL,
    .app_on_set_dev_config_complete     = default_app_on_set_dev_config_complete,
    .app_on_adv_nonconn_complete        = NULL,
    .app_on_adv_undirect_complete       = user_app_adv_undirect_complete,
    .app_on_adv_direct_complete         = NULL,
    .app_on_db_init_complete            = default_app_on_db_init_complete,
    .app_on_scanning_completed          = NULL,
    .app_on_adv_report_ind              = NULL,
    .app_on_get_dev_name                = default_app_on_get_dev_name,
    .app_on_get_dev_appearance          = default_app_on_get_dev_appearance,
    .app_on_get_dev_slv_pref_params     = default_app_on_get_dev_slv_pref_params,
    .app_on_set_dev_info                = default_app_on_set_dev_info,
    .app_on_data_length_change          = NULL,
    .app_on_update_params_request       = default_app_update_params_request,
    .app_on_generate_static_random_addr = default_app_generate_static_random_addr,
    .app_on_svc_changed_cfg_ind         = NULL,
    .app_on_get_peer_features           = NULL,
};

/* ─── Catch-All Handler ──────────────────────────────────────────────────── */

#define app_process_catch_rest_cb   user_catch_rest_hndl

/* ─── arch_main_loop Callbacks ───────────────────────────────────────────── */

static const struct arch_main_loop_callbacks user_app_main_loop_callbacks = {
    .app_on_init            = user_app_init,
    .app_on_ble_powered     = NULL,
    .app_on_system_powered  = NULL,
    .app_before_sleep       = NULL,
    .app_validate_sleep     = NULL,
    .app_going_to_sleep     = NULL,
    .app_resume_from_sleep  = NULL,
};

/* ─── Default Handler Operations ─────────────────────────────────────────── */

static const struct default_app_operations user_default_app_operations = {
    .default_operation_adv = user_app_adv_start,
};

/* ─── Custom GATT Write Dispatch ─────────────────────────────────────────── */
/*
 * These handlers are called by custs1_task.c when a central writes to our
 * custom characteristics. The SDK uses a message-ID → handler lookup table
 * built in app_entry_point.c via the process_handler array.
 *
 * CUSTS1_VAL_WRITE_IND arrives for both characteristics; we distinguish them
 * by param->handle matching EINK_CMD_VAL or EINK_DATA_VAL.
 */

/* ─── Profile Function Callbacks ─────────────────────────────────────────── */

static const struct prf_func_callbacks user_prf_funcs[] =
{
    {TASK_ID_INVALID, NULL, NULL}   // DO NOT MOVE — must always be last
};

#endif // _USER_CALLBACK_CONFIG_H_
