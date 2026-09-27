# DA14585 Standalone GCC Firmware Makefile
# =========================================
# Builds custom firmware for the DA14585 E-Ink Display board using Arm GNU Toolchain
# and flashes via ST-Link V2 with flash_spi_firmware.py.

TARGET       := eink_firmware
BUILD_DIR    := build

# Paths
SDK_PATH     ?= C:/Users/schra/DA145xx_SDK/6.0.24.1464
CROSS_COMPILE?= arm-none-eabi-
MKIMAGE      ?= $(SDK_PATH)/binaries/host/windows/mkimage/mkimage.exe
PYTHON       ?= python

CC           := "$(CROSS_COMPILE)gcc"
AS           := "$(CROSS_COMPILE)as"
OBJCOPY      := "$(CROSS_COMPILE)objcopy"
OBJDUMP      := "$(CROSS_COMPILE)objdump"
SIZE         := "$(CROSS_COMPILE)size"

# Target CPU Flags
CPU_FLAGS    := -mcpu=cortex-m0 -mthumb

# C Preprocessor Defines
DEFINES      := -D__DA14585__ \
                -D__NON_BLE_EXAMPLE__ \
                -D__ARM_FEATURE_DSP=0

# Include Directories
INCLUDES     := -I./src \
                -I.. \
                -I$(SDK_PATH)/sdk/platform/include \
                -I$(SDK_PATH)/sdk/platform/include/CMSIS/5.9.0/CMSIS/Core/Include \
                -I$(SDK_PATH)/sdk/platform/arch \
                -I$(SDK_PATH)/sdk/platform/arch/boot \
                -I$(SDK_PATH)/sdk/platform/arch/compiler \
                -I$(SDK_PATH)/sdk/platform/arch/compiler/GCC \
                -I$(SDK_PATH)/sdk/platform/arch/ll \
                -I$(SDK_PATH)/sdk/platform/arch/main \
                -I$(SDK_PATH)/sdk/platform/system_library/include \
                -I$(SDK_PATH)/sdk/platform/driver/gpio \
                -I$(SDK_PATH)/sdk/platform/driver/syscntl \
                -I$(SDK_PATH)/sdk/platform/driver/hw_otpc \
                -I$(SDK_PATH)/sdk/platform/driver/spi \
                -I$(SDK_PATH)/sdk/platform/driver/spi_flash \
                -I$(SDK_PATH)/sdk/platform/driver/uart \
                -I$(SDK_PATH)/sdk/platform/utilities/otp_cs \
                -I$(SDK_PATH)/sdk/platform/utilities/otp_hdr \
                -I$(SDK_PATH)/sdk/platform/core_modules/common/api \
                -I$(SDK_PATH)/sdk/platform/core_modules/nvds/api \
                -I$(SDK_PATH)/sdk/common_project_files \
                -I$(SDK_PATH)/projects/target_apps/peripheral_examples/shared/api \
                -I$(SDK_PATH)/projects/target_apps/peripheral_examples/shared

# Compiler & Linker Flags
CFLAGS       := $(CPU_FLAGS) $(DEFINES) $(INCLUDES) -O2 -g \
                -fno-exceptions -fno-unwind-tables \
                -Wall -Wextra -Wno-unused-parameter \
                -ffunction-sections -fdata-sections

ASFLAGS      := $(CPU_FLAGS) $(DEFINES) $(INCLUDES) \
                -fno-exceptions -fno-unwind-tables \
                -x assembler-with-cpp

LDSCRIPT     := ldscript_da14585.ld

LDFLAGS      := $(CPU_FLAGS) -nostartfiles -T$(LDSCRIPT) \
                -Wl,--gc-sections -Wl,-Map=$(BUILD_DIR)/$(TARGET).map \
                --specs=nano.specs --specs=nosys.specs

# Source Files
C_SRCS       := src/main.c \
                src/user_periph_setup.c \
                ../ssd1619.c \
                $(SDK_PATH)/sdk/platform/driver/syscntl/syscntl.c \
                $(SDK_PATH)/sdk/platform/driver/gpio/gpio.c \
                $(SDK_PATH)/projects/target_apps/peripheral_examples/shared/source/exceptions.c

ASM_SRCS     := $(SDK_PATH)/sdk/platform/arch/boot/GCC/startup_DA14585_586.S \
                $(SDK_PATH)/sdk/platform/arch/boot/GCC/ivtable_DA14585_586.S

# Object Files
OBJS         := $(patsubst %.c,$(BUILD_DIR)/%.o,$(notdir $(C_SRCS)))
OBJS         += $(BUILD_DIR)/startup_DA14585_586_asm.o
OBJS         += $(BUILD_DIR)/ivtable_DA14585_586_asm.o

# VPATH
VPATH        := src .. \
                $(SDK_PATH)/sdk/platform/driver/syscntl \
                $(SDK_PATH)/sdk/platform/driver/gpio \
                $(SDK_PATH)/projects/target_apps/peripheral_examples/shared/source

.PHONY: all clean flash info

all: $(BUILD_DIR)/$(TARGET).bin $(BUILD_DIR)/$(TARGET).img info

$(BUILD_DIR):
	$(PYTHON) -c "import os; os.makedirs('$(BUILD_DIR)', exist_ok=True)"

$(BUILD_DIR)/%.o: %.c | $(BUILD_DIR)
	@echo [CC] $<
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/startup_DA14585_586_asm.o: $(SDK_PATH)/sdk/platform/arch/boot/GCC/startup_DA14585_586.S | $(BUILD_DIR)
	@echo [AS] $<
	$(CC) $(ASFLAGS) -c $< -o $@

$(BUILD_DIR)/ivtable_DA14585_586_asm.o: $(SDK_PATH)/sdk/platform/arch/boot/GCC/ivtable_DA14585_586.S | $(BUILD_DIR)
	@echo [AS] $<
	$(CC) $(ASFLAGS) -c $< -o $@

$(BUILD_DIR)/$(TARGET).elf: $(LDSCRIPT) $(OBJS)
	@echo [LD] $@
	$(CC) $(OBJS) $(LDFLAGS) -o $@

$(BUILD_DIR)/$(TARGET).bin: $(BUILD_DIR)/$(TARGET).elf
	@echo [OBJCOPY] $@
	$(OBJCOPY) -O binary $< $@

$(BUILD_DIR)/$(TARGET).img: $(BUILD_DIR)/$(TARGET).bin mkimage.py
	@echo [MKIMAGE] Packaging with Dialog Image Header...
	$(PYTHON) mkimage.py $< $@ --id 3

info: $(BUILD_DIR)/$(TARGET).elf
	@echo "--- Memory Usage Summary ---"
	$(SIZE) $<

flash: $(BUILD_DIR)/$(TARGET).img
	@echo [FLASH] Programming to SPI Flash Image 1 (0x004000) via ST-Link...
	$(PYTHON) ../flash_spi_firmware.py write $< --addr 0x004000 --reset

clean:
	$(PYTHON) -c "import shutil, os; os.path.exists('$(BUILD_DIR)') and shutil.rmtree('$(BUILD_DIR)')"
