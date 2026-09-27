/**
 ****************************************************************************************
 * @file user_modules_config.h
 * @brief DA14585 E-Ink Display — BLE Module Enable/Disable Configuration
 ****************************************************************************************
 */

#ifndef _USER_MODULES_CONFIG_H_
#define _USER_MODULES_CONFIG_H_

/*
 * (0) = module included — SDK handles its messages.
 * (1) = module excluded — user must handle its messages.
 */

#define EXCLUDE_DLG_GAP             (0)  // GAP: included
#define EXCLUDE_DLG_TIMER           (0)  // Timer: included
#define EXCLUDE_DLG_MSG             (1)  // GTL msg: excluded (no external host)
#define EXCLUDE_DLG_SEC             (1)  // Security: excluded
#define EXCLUDE_DLG_DISS            (0)  // DIS: included
#define EXCLUDE_DLG_PROXR           (1)  // Proximity Reporter: excluded
#define EXCLUDE_DLG_BASS            (1)  // Battery Service: excluded
#define EXCLUDE_DLG_FINDL           (1)  // Find Me Locator: excluded
#define EXCLUDE_DLG_FINDT           (1)  // Find Me Target: excluded
#define EXCLUDE_DLG_SUOTAR          (1)  // SUOTA OTA: excluded
#define EXCLUDE_DLG_CUSTS1          (0)  // Custom Service 1 (e-ink): INCLUDED
#define EXCLUDE_DLG_CUSTS2          (1)  // Custom Service 2: excluded

#endif // _USER_MODULES_CONFIG_H_
