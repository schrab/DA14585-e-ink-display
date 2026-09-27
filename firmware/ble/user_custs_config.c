/**
 ****************************************************************************************
 * @file user_custs_config.c
 * @brief DA14585 E-Ink Display — Custom Profile Server Configuration
 *
 * Registers the e-ink CUSTS1 database with the SDK profile framework.
 ****************************************************************************************
 */

#include "app_prf_types.h"
#include "app_customs.h"
#include "user_custs1_def.h"

#if (BLE_CUSTOM1_SERVER)
extern const struct attm_desc_128 custs1_att_db[EINK_CUSTS1_IDX_NB];
#endif

/// Custom 1/2 server function callback table
const struct cust_prf_func_callbacks cust_prf_funcs[] =
{
#if (BLE_CUSTOM1_SERVER)
    {
        TASK_ID_CUSTS1,
        custs1_att_db,
        EINK_CUSTS1_IDX_NB,
#if (BLE_APP_PRESENT)
        app_custs1_create_db, NULL,
#else
        NULL, NULL,
#endif
        NULL, NULL,
    },
#endif
    // DO NOT MOVE — must always be last
    {TASK_ID_INVALID, NULL, 0, NULL, NULL, NULL, NULL},
};
