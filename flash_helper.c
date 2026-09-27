#include <stdint.h>

typedef int8_t (*p_func_void_t)(void);
typedef void (*p_func_u8_t)(uint8_t);
typedef uint32_t (*p_func_u32_t)(uint32_t);
typedef void (*p_func_write_t)(const uint8_t *buf, uint32_t addr, uint32_t size, uint32_t *act_size);

#define spi_flash_is_busy       ((p_func_void_t)0x07FC973F)
#define spi_flash_write_enable  ((p_func_void_t)0x07FC9941)
#define spi_set_bitmode         ((p_func_u8_t)0x07FC9985)
#define spi_cs_low              ((p_func_void_t)0x07FC96F9)
#define spi_access              ((p_func_u32_t)0x07FC95D1)
#define spi_cs_high             ((p_func_void_t)0x07FC96E5)
#define spi_flash_wait_ready    ((p_func_void_t)0x07FC985D)
#define spi_flash_write_data    ((p_func_write_t)0x07FC9881)

#define WATCHDOG_REG            (*(volatile uint16_t *)0x50003102)

static inline void pet_watchdog(void) {
    WATCHDOG_REG = 0x00FF;
}

// Function entry 1 (0x07FD0020): Erase block (0x20 = SE 4K, 0xD8 = BE 64K, 0xC7 = Chip Erase)
int32_t flash_erase_block(uint32_t address, uint32_t erase_op) {
    pet_watchdog();
    if (spi_flash_is_busy() != 0) return -1;
    if (spi_flash_write_enable() != 0) return -2;

    spi_set_bitmode(2); // 32-bit SPI mode
    spi_cs_low();
    spi_access((erase_op << 24) | (address & 0x00FFFFFF));
    spi_cs_high();

    int8_t res = spi_flash_wait_ready();
    pet_watchdog();
    return res;
}

// Function entry 2 (0x07FD008C): Write buffer to flash
int32_t flash_write(const uint8_t *buffer, uint32_t address, uint32_t size) {
    pet_watchdog();
    uint32_t actual = 0;
    spi_flash_write_data(buffer, address, size, &actual);
    pet_watchdog();
    return (int32_t)actual;
}
