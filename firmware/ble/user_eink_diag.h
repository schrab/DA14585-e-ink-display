/**
 ****************************************************************************************
 * @file user_eink_diag.h
 * @brief RAM-region CRC snapshots — transient memory-corruption forensics.
 *
 * The firmware hardfaults when a peer disconnects while the CPU is blocked inside the
 * ~17 s e-ink refresh. The faulting instruction is `blx r5` in the ROM's ke_queue_insert,
 * where r5 is a KE message-handler pointer resolved for a message whose msgid was 0x0101
 * (KE task type 1, which does not exist in this build). The ROM therefore resolved a
 * nonexistent task and branched into an uninitialised handler slot.
 *
 * That proves a KE *message header* was corrupted, but not who wrote it. These snapshots
 * CRC eight non-overlapping RAM regions at each interesting point in the application flow
 * so a host script can diff them and identify exactly which region changed, and when.
 ****************************************************************************************
 */

#ifndef _USER_EINK_DIAG_H_
#define _USER_EINK_DIAG_H_

#include <stdint.h>

/*
 * The diagnostics are compile-time optional. When EINK_DIAG is 0 every entry point
 * below becomes an inline no-op and user_eink_diag.c is not linked, which keeps the
 * ~650 bytes of retained RAM and the CRC32 code out of production images. That space
 * matters here: the retained region has only a few tens of bytes of slack, and the
 * KE message heap competes for the same region (see MSG_HEAP_SZ).
 */
#ifndef EINK_DIAG
#define EINK_DIAG 0
#endif

#if EINK_DIAG

/// Number of monitored RAM regions.
#define DIAG_REGION_COUNT      (9)

/// Number of retained snapshot slots (one per phase).
#define DIAG_SNAPSHOT_COUNT    (12)

/* ─── Snapshot phase tags ─────────────────────────────────────────────────── */
#define DIAG_PHASE_BOOT            (0)  ///< end of user_app_init
#define DIAG_PHASE_CMD_CLEAR       (1)  ///< after command 0x07
#define DIAG_PHASE_PRE_REFRESH     (2)  ///< immediately before the blocking e-ink cycle
#define DIAG_PHASE_POST_REFRESH    (3)  ///< immediately after the blocking e-ink cycle
#define DIAG_PHASE_DISCONNECT      (4)  ///< inside user_app_disconnect
#define DIAG_PHASE_CMD_REFRESH     (5)  ///< on receipt of command 0x06
#define DIAG_PHASE_CMD_STATUS      (6)  ///< on receipt of command 0x08
#define DIAG_PHASE_MANUAL          (7)  ///< on demand (command 0x09)
#define DIAG_PHASE_PRE_WRITE       (8)  ///< entering a CUSTS1 write indication
#define DIAG_PHASE_POST_WRITE      (9)  ///< our write handler has returned

/**
 * @brief CRCs every monitored RAM region and appends the result to the retained history.
 *
 * Cheap enough (a few hundred microseconds) to call around the blocking refresh.
 * A region whose CRC differs between two phases was written by someone other than
 * the code that was supposed to own it.
 *
 * @param phase  One of the DIAG_PHASE_* tags.
 */
void diag_snapshot(uint8_t phase);

/* ─── Write-indication observation log ────────────────────────────────────── */

/// Number of retained observation slots.
#define DIAG_OBS_COUNT           (8)

/**
 * @brief Records one CUSTS1 write indication exactly as the kernel delivered it.
 *
 * `handle` in struct custs1_val_write_ind is the ATT attribute handle assigned when
 * the database was created - it is NOT the GATT database index used by the
 * EINK_*_VAL enum. Logging both lets us confirm which of the two the routing in
 * user_catch_rest_hndl() is actually comparing against.
 */
void diag_observe(uint16_t msgid, uint16_t dest, uint16_t src,
                  uint16_t handle, uint16_t length, uint8_t first_byte);

/// Attaches the application-level byte counter to the most recent snapshot.
void diag_set_count(uint16_t bytes);

/// Attributes the previous observation: 0=none 1=CMD 2=DATA 3=unrecognised handle.
void diag_route(uint8_t which);

#else /* EINK_DIAG == 0 */

#define DIAG_REGION_COUNT       (0)
#define DIAG_SNAPSHOT_COUNT     (0)
#define DIAG_PHASE_BOOT            (0)
#define DIAG_PHASE_CMD_CLEAR       (1)
#define DIAG_PHASE_PRE_REFRESH     (2)
#define DIAG_PHASE_POST_REFRESH    (3)
#define DIAG_PHASE_DISCONNECT      (4)
#define DIAG_PHASE_CMD_REFRESH     (5)
#define DIAG_PHASE_CMD_STATUS      (6)
#define DIAG_PHASE_MANUAL          (7)
#define DIAG_PHASE_PRE_WRITE       (8)
#define DIAG_PHASE_POST_WRITE      (9)

static inline void diag_snapshot(uint8_t phase) { (void)phase; }
static inline void diag_observe(uint16_t msgid, uint16_t dest, uint16_t src,
                                uint16_t handle, uint16_t length, uint8_t first_byte)
{
    (void)msgid; (void)dest; (void)src; (void)handle; (void)length; (void)first_byte;
}
static inline void diag_set_count(uint16_t bytes) { (void)bytes; }
static inline void diag_route(uint8_t which) { (void)which; }

#endif /* EINK_DIAG */

#endif // _USER_EINK_DIAG_H_
