/**
 ****************************************************************************************
 * @file user_eink_diag.c
 * @brief RAM-region CRC snapshots — see user_eink_diag.h for rationale.
 *
 * The monitored regions were chosen from the linker map to bracket every owner of
 * writable RAM on the DA14585:
 *
 *   code         0x07FC0000  vectors + .text + .rodata (RAM-backed: this SoC has no
 *                            internal flash, so "flash" is ordinary writable RAM).
 *                            Holds the const KE state-handler and GATT DB tables.
 *   data_bss     .data through end of .bss, i.e. eink_framebuffer. Expected to change
 *                            between snapshots — that is the image being written.
 *   rwip_nonret  rwip_heap_non_ret — the RWIP/KE message heap (only 0x40C B).
 *   gaptail      the empty app .heap plus the 2 KB main stack.
 *   retention    intr_cb, prf_env.prf[i].desc and the TASK_APP ke_state_t array.
 *   heap_env     rwip_heap_env_ret.
 *   heap_db      rwip_heap_db_ret.
 *   heap_msg     rwip_heap_msg_ret.
 *   rom_tables   the unallocated tail of SysRAM4 that the ROM owns at runtime: ke_env
 *                            and the KE task table whose handler slot resolved to garbage.
 *
 * None of these regions contains diag_history or diag_next, so taking a snapshot can
 * never perturb the CRCs it records.
 *
 * NOTE: these addresses are tied to the current link layout and MUST be re-derived from
 * build/eink_ble_firmware.map whenever the .bss size or retained-RAM usage changes.
 * diag_crc.py verifies them against the map and warns on drift.
 ****************************************************************************************
 */

#include "user_eink_diag.h"

/// CRC-32 (IEEE 802.3, reflected) — same polynomial as zlib, so it matches mkimage.py.
static uint32_t diag_crc32(const uint8_t *data, uint32_t len)
{
    uint32_t crc = 0xFFFFFFFFu;
    uint32_t i;

    for (i = 0; i < len; i++) {
        crc ^= data[i];
        {
            uint8_t bit;
            for (bit = 0; bit < 8; bit++) {
                crc = (crc >> 1) ^ (0xEDB88320u & (uint32_t)(-(int32_t)(crc & 1)));
            }
        }
    }

    return ~crc;
}

typedef struct {
    const char *name;
    uint32_t    addr;
    uint32_t    size;
} diag_region_t;

static const diag_region_t diag_regions[DIAG_REGION_COUNT] = {
    { "code",        0x07FC0000u, 0x78E0u },
    { "data_bss",    0x07FC78E0u, 0x766Cu },
    { "rwip_nonret", 0x07FCEF4Cu, 0x040Cu },
    { "gaptail",     0x07FCF358u, 0x08A8u },
    { "retention",   0x07FD4B80u, 0x044Cu },
    { "heap_env",    0x07FD4FCCu, 0x0274u },
    { "heap_db",     0x07FD5240u, 0x040Cu },
    { "heap_msg",    0x07FD564Cu, 0x057Cu },
    { "rom_tables",  0x07FD5BC8u, 0x2438u },
};

/// Retained so the history survives the HardFault that we are trying to diagnose.
typedef struct {
    uint8_t  valid;                        ///< non-zero once the slot has been written
    uint8_t  phase;                        ///< DIAG_PHASE_* tag
    uint16_t count;                        ///< messages received when snapshotted
    uint32_t crc[DIAG_REGION_COUNT];
} diag_snapshot_t;

static diag_snapshot_t diag_history[DIAG_SNAPSHOT_COUNT] __SECTION_ZERO("retention_mem_area0");

/// Index of the next slot to write. Retained so a crash does not rewind the history.
static volatile uint8_t diag_next __SECTION_ZERO("retention_mem_area0");

void diag_snapshot(uint8_t phase)
{
    diag_snapshot_t *slot;
    uint32_t i;

    if (diag_next >= DIAG_SNAPSHOT_COUNT) {
        return; // history full; keep the oldest evidence intact
    }

    slot = &diag_history[diag_next];

    for (i = 0; i < DIAG_REGION_COUNT; i++) {
        slot->crc[i] = diag_crc32((const uint8_t *)diag_regions[i].addr, diag_regions[i].size);
    }

    slot->phase = phase;
    slot->valid = 1;
    slot->count = 0; // patched by the caller via diag_set_count()

    diag_next++;
}

/**
 * @brief Records how many image bytes had been received when a snapshot was taken.
 *
 * Kept separate from diag_snapshot() so the CRC loop stays independent of application
 * state; the count is what lets us tell a mid-stream snapshot from a post-stream one.
 */
void diag_set_count(uint16_t bytes);
void diag_set_count(uint16_t bytes)
{
    if (diag_next > 0) {
        diag_history[diag_next - 1].count = bytes;
    }
}

/**
 * @brief Absolute address of the retained snapshot history, for host-side readback.
 */
uint32_t diag_history_addr(void)
{
    return (uint32_t)diag_history;
}

/* ─── Write-indication observation log ────────────────────────────────────── */

typedef struct {
    uint16_t msgid;
    uint16_t dest;
    uint16_t src;
    uint16_t handle;   ///< ATT attribute handle from custs1_val_write_ind
    uint16_t length;
    uint8_t  first_byte;
    uint8_t  routed;   ///< 0=none 1=CMD 2=DATA 3=unrecognised handle
} diag_obs_t;

static diag_obs_t diag_obs[DIAG_OBS_COUNT] __SECTION_ZERO("retention_mem_area0");
static volatile uint8_t diag_obs_next __SECTION_ZERO("retention_mem_area0");

void diag_observe(uint16_t msgid, uint16_t dest, uint16_t src,
                  uint16_t handle, uint16_t length, uint8_t first_byte)
{
    if (diag_obs_next >= DIAG_OBS_COUNT) {
        diag_obs_next = 0; // wrap: the last few writes are the interesting ones
    }
    diag_obs[diag_obs_next].msgid      = msgid;
    diag_obs[diag_obs_next].dest       = dest;
    diag_obs[diag_obs_next].src        = src;
    diag_obs[diag_obs_next].handle     = handle;
    diag_obs[diag_obs_next].length     = length;
    diag_obs[diag_obs_next].first_byte = first_byte;
    diag_obs[diag_obs_next].routed     = 0;
    diag_obs_next++;
}

void diag_route(uint8_t which);
void diag_route(uint8_t which)
{
    /* Attribute the previous observation, which diag_observe() just stored. */
    if (diag_obs_next > 0) {
        diag_obs[diag_obs_next - 1].routed = which;
    }
}

uint32_t diag_obs_addr(void);
uint32_t diag_obs_addr(void)
{
    return (uint32_t)diag_obs;
}

/**
 * @brief Number of snapshot slots written so far.
 */
uint8_t diag_snapshot_total(void);
uint8_t diag_snapshot_total(void)
{
    return diag_next;
}
