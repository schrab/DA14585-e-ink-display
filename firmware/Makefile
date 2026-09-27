# DA14585 BLE E-Ink Display Firmware Makefile
# ============================================
# Builds custom BLE firmware using the Dialog DA145xx SDK 6.0.24.1464.
# Flashes via ST-Link V2 SWD using flash_spi_firmware.py.
#
# Build targets:
#   make all    — build firmware + Dialog image header
#   make flash  — build + program to SPI flash Image 1 (0x004000)
#   make clean  — remove build directory

TARGET       := eink_ble_firmware
BUILD_DIR    := build

# ─── Platform & Paths ────────────────────────────────────────────────────────
ifeq ($(OS),Windows_NT)
    SDK_PATH      ?= C:/Users/schra/DA145xx_SDK/6.0.24.1464
    TOOLCHAIN     ?= C:/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/14.2 rel1/bin
    PYTHON        ?= python
else
    SDK_PATH      ?= $(HOME)/DA145xx_SDK/6.0.24.1464
    TOOLCHAIN     ?=
    PYTHON        ?= python3
endif

CROSS_COMPILE ?= arm-none-eabi-
TOOLCHAIN_BIN := $(if $(strip $(TOOLCHAIN)),$(strip $(TOOLCHAIN))/, )

CC           := $(TOOLCHAIN_BIN)$(CROSS_COMPILE)gcc
AS           := $(TOOLCHAIN_BIN)$(CROSS_COMPILE)as
OBJCOPY      := $(TOOLCHAIN_BIN)$(CROSS_COMPILE)objcopy
OBJDUMP      := $(TOOLCHAIN_BIN)$(CROSS_COMPILE)objdump
SIZE         := $(TOOLCHAIN_BIN)$(CROSS_COMPILE)size

# ─── Target CPU ──────────────────────────────────────────────────────────────
CPU_FLAGS    := -mcpu=cortex-m0 -mthumb

# ─── Preprocessor Defines ────────────────────────────────────────────────────
# EINK_DIAG=1 builds the RAM-CRC diagnostics into user_eink_diag.c; the default 0
# leaves them out so they do not consume retained RAM that the KE message heap needs.
EINK_DIAG   ?= 0

DEFINES      := \
    -D__DA14585__ \
    -D__ARM_FEATURE_DSP=0 \
    -DEINK_DIAG=$(EINK_DIAG)

# ─── Pre-Included Headers (Dialog SDK architecture) ──────────────────────────
PREINCLUDES  := \
    -include da1458x_config_basic.h \
    -include da1458x_config_advanced.h \
    -include user_config.h

# ─── Include Directories ─────────────────────────────────────────────────────
# Our application config headers (override SDK defaults)
APP_INCLUDES := \
    -I./ble/config \
    -I./ble \
    -I./src \
    -I..

# SDK platform includes
SDK_INCLUDES := \
    -I$(SDK_PATH)/sdk/platform/include \
    -I$(SDK_PATH)/sdk/platform/include/CMSIS/5.9.0/CMSIS/Core/Include \
    -I$(SDK_PATH)/sdk/platform/arch \
    -I$(SDK_PATH)/sdk/platform/arch/boot \
    -I$(SDK_PATH)/sdk/platform/arch/boot/GCC \
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
    -I$(SDK_PATH)/sdk/platform/driver/battery \
    -I$(SDK_PATH)/sdk/platform/driver/wkupct_quadec \
    -I$(SDK_PATH)/sdk/platform/driver/adc \
    -I$(SDK_PATH)/sdk/platform/driver/dma \
    -I$(SDK_PATH)/sdk/platform/driver/i2c \
    -I$(SDK_PATH)/sdk/platform/driver/i2c_eeprom \
    -I$(SDK_PATH)/sdk/platform/driver/trng \
    -I$(SDK_PATH)/sdk/platform/driver/ble \
    -I$(SDK_PATH)/sdk/platform/driver/reg \
    -I$(SDK_PATH)/sdk/platform/utilities/otp_cs \
    -I$(SDK_PATH)/sdk/platform/utilities/otp_hdr \
    -I$(SDK_PATH)/sdk/platform/core_modules/common/api \
    -I$(SDK_PATH)/sdk/platform/core_modules/nvds/api \
    -I$(SDK_PATH)/sdk/platform/core_modules/rwip/api \
    -I$(SDK_PATH)/sdk/platform/core_modules/rf/api \
    -I$(SDK_PATH)/sdk/platform/core_modules/ke/api \
    -I$(SDK_PATH)/sdk/platform/core_modules/ke/src \
    -I$(SDK_PATH)/sdk/platform/core_modules/dbg/api \
    -I$(SDK_PATH)/sdk/platform/core_modules/gtl/api \
    -I$(SDK_PATH)/sdk/platform/core_modules/gtl/src \
    -I$(SDK_PATH)/sdk/platform/core_modules/h4tl/api \
    -I$(SDK_PATH)/sdk/platform/core_modules/arch_console \
    -I$(SDK_PATH)/sdk/platform/core_modules/crypto \
    -I$(SDK_PATH)/sdk/common_project_files \
    -I$(SDK_PATH)/sdk/app_modules/api \
    -I$(SDK_PATH)/sdk/ble_stack/rwble \
    -I$(SDK_PATH)/sdk/ble_stack/rwble_hl \
    -I$(SDK_PATH)/sdk/ble_stack/controller/em \
    -I$(SDK_PATH)/sdk/ble_stack/controller/llc \
    -I$(SDK_PATH)/sdk/ble_stack/controller/lld \
    -I$(SDK_PATH)/sdk/ble_stack/controller/llm \
    -I$(SDK_PATH)/sdk/ble_stack/ea/api \
    -I$(SDK_PATH)/sdk/ble_stack/em/api \
    -I$(SDK_PATH)/sdk/ble_stack/hci/api \
    -I$(SDK_PATH)/sdk/ble_stack/hci/src \
    -I$(SDK_PATH)/sdk/ble_stack/host/att \
    -I$(SDK_PATH)/sdk/ble_stack/host/att/attc \
    -I$(SDK_PATH)/sdk/ble_stack/host/att/attm \
    -I$(SDK_PATH)/sdk/ble_stack/host/att/atts \
    -I$(SDK_PATH)/sdk/ble_stack/host/gap \
    -I$(SDK_PATH)/sdk/ble_stack/host/gap/gapc \
    -I$(SDK_PATH)/sdk/ble_stack/host/gap/gapm \
    -I$(SDK_PATH)/sdk/ble_stack/host/gatt \
    -I$(SDK_PATH)/sdk/ble_stack/host/gatt/gattc \
    -I$(SDK_PATH)/sdk/ble_stack/host/gatt/gattm \
    -I$(SDK_PATH)/sdk/ble_stack/host/l2c/l2cc \
    -I$(SDK_PATH)/sdk/ble_stack/host/l2c/l2cm \
    -I$(SDK_PATH)/sdk/ble_stack/host/smp \
    -I$(SDK_PATH)/sdk/ble_stack/host/smp/smpc \
    -I$(SDK_PATH)/sdk/ble_stack/host/smp/smpm \
    -I$(SDK_PATH)/sdk/ble_stack/profiles \
    -I$(SDK_PATH)/sdk/ble_stack/profiles/dis/diss/api \
    -I$(SDK_PATH)/sdk/ble_stack/profiles/dis/disc/api \
    -I$(SDK_PATH)/sdk/ble_stack/profiles/custom \
    -I$(SDK_PATH)/sdk/ble_stack/profiles/custom/custs/api \
    -I$(SDK_PATH)/third_party/hash \
    -I$(SDK_PATH)/third_party/rand \
    -I$(SDK_PATH)/third_party/irng

INCLUDES     := $(APP_INCLUDES) $(SDK_INCLUDES)

# ─── Compiler Flags ───────────────────────────────────────────────────────────
CFLAGS       := $(CPU_FLAGS) $(DEFINES) $(PREINCLUDES) $(INCLUDES) -O2 -g \
                -fno-exceptions -fno-unwind-tables \
                -Wall -Wno-unused-parameter -Wno-missing-braces \
                -Wno-int-conversion -Wno-unused-variable -Wno-switch \
                -ffunction-sections -fdata-sections


ASFLAGS      := $(CPU_FLAGS) $(DEFINES) $(INCLUDES) -D__STACK_SIZE=0x800 \
                -fno-exceptions -fno-unwind-tables \
                -x assembler-with-cpp

# ─── Linker Script ────────────────────────────────────────────────────────────
# The SDK linker script is a C preprocessor template (.lds.S).
# We preprocess it with GCC using our config headers to produce the final .ld.
LDS_TEMPLATE  := ldscript_ble.lds.S
LDS_PROCESSED := $(BUILD_DIR)/ldscript_ble.ld
LDSCRIPT      := $(LDS_PROCESSED)

LDFLAGS      := $(CPU_FLAGS) -T$(LDSCRIPT) \
                -L$(SDK_PATH)/sdk/common_project_files/misc \
                -L$(SDK_PATH)/sdk/common_project_files/ldscripts \
                -L$(SDK_PATH)/sdk/platform/system_library/output/Keil_5 \
                -Wl,--gc-sections -Wl,-Map=$(BUILD_DIR)/$(TARGET).map \
                --specs=nano.specs --specs=nosys.specs \
                -l:da14585_586.lib




# ─── Application Source Files ─────────────────────────────────────────────────
APP_SRCS     := \
    ble/user_eink_app.c \
    ble/user_custs1_def.c \
    ble/user_custs_config.c \
    src/user_periph_setup.c \
    ../ssd1619.c

ifeq ($(EINK_DIAG),1)
APP_SRCS     += ble/user_eink_diag.c
$(BUILD_DIR)/user_eink_diag.o: ble/user_eink_diag.c | $(BUILD_DIR)
	@echo "[CC] $<"
	$(CC) $(CFLAGS) -c $< -o $@
endif


# ─── SDK BLE Core Source Files ────────────────────────────────────────────────
SDK_SRCS     := \
    $(SDK_PATH)/sdk/platform/arch/main/arch_main.c \
    $(SDK_PATH)/sdk/platform/arch/main/arch_sleep.c \
    $(SDK_PATH)/sdk/platform/arch/main/arch_system.c \
    $(SDK_PATH)/sdk/platform/arch/main/arch_hibernation.c \
    $(SDK_PATH)/sdk/platform/arch/main/jump_table.c \
    $(SDK_PATH)/sdk/platform/arch/main/hardfault_handler.c \
    $(SDK_PATH)/sdk/platform/arch/main/nmi_handler.c \
    $(SDK_PATH)/sdk/platform/arch/boot/system_DA14585_586.c \
    $(SDK_PATH)/sdk/platform/core_modules/rwip/src/rwip.c \
    $(SDK_PATH)/sdk/platform/core_modules/nvds/src/nvds.c \
    $(SDK_PATH)/sdk/platform/core_modules/arch_console/arch_console.c \
    $(SDK_PATH)/sdk/platform/core_modules/rf/src/rf_585.c \
    $(SDK_PATH)/sdk/platform/system_library/src/DA14585_586/system_library_585_586.c \
    $(SDK_PATH)/sdk/platform/driver/gpio/gpio.c \
    $(SDK_PATH)/sdk/platform/driver/syscntl/syscntl.c \
    $(SDK_PATH)/sdk/platform/driver/battery/battery.c \
    $(SDK_PATH)/sdk/platform/driver/adc/adc_58x.c \
    $(SDK_PATH)/sdk/platform/driver/dma/dma.c \
    $(SDK_PATH)/sdk/platform/driver/uart/uart.c \
    $(SDK_PATH)/sdk/platform/driver/i2c/i2c.c \
    $(SDK_PATH)/sdk/platform/utilities/otp_cs/otp_cs.c \
    $(SDK_PATH)/sdk/platform/driver/spi_flash/spi_flash.c \
    $(SDK_PATH)/sdk/platform/driver/i2c_eeprom/i2c_eeprom.c \
    $(SDK_PATH)/sdk/platform/driver/wkupct_quadec/wkupct_quadec.c \
    $(SDK_PATH)/sdk/ble_stack/rwble/rwble.c \
    $(SDK_PATH)/sdk/ble_stack/profiles/prf.c \
    $(SDK_PATH)/sdk/ble_stack/profiles/prf_utils.c \
    $(SDK_PATH)/sdk/ble_stack/profiles/dis/diss/src/diss.c \
    $(SDK_PATH)/sdk/ble_stack/profiles/dis/diss/src/diss_task.c \
    $(SDK_PATH)/sdk/ble_stack/profiles/custom/custs/src/custs1.c \
    $(SDK_PATH)/sdk/ble_stack/profiles/custom/custs/src/custs1_task.c \
    $(SDK_PATH)/sdk/ble_stack/profiles/custom/custom_common.c \
    $(SDK_PATH)/sdk/ble_stack/host/att/attm/attm_db_128.c \
    $(SDK_PATH)/sdk/app_modules/src/app_common/app.c \
    $(SDK_PATH)/sdk/app_modules/src/app_common/app_task.c \
    $(SDK_PATH)/sdk/app_modules/src/app_default_hnd/app_default_handlers.c \
    $(SDK_PATH)/sdk/app_modules/src/app_diss/app_diss.c \
    $(SDK_PATH)/sdk/app_modules/src/app_diss/app_diss_task.c \
    $(SDK_PATH)/sdk/app_modules/src/app_custs/app_customs.c \
    $(SDK_PATH)/sdk/app_modules/src/app_custs/app_customs_common.c \
    $(SDK_PATH)/sdk/app_modules/src/app_custs/app_customs_task.c \
    $(SDK_PATH)/sdk/app_modules/src/app_easy/app_easy_msg_utils.c \
    $(SDK_PATH)/sdk/app_modules/src/app_easy/app_easy_timer.c \
    $(SDK_PATH)/sdk/platform/driver/hw_otpc/hw_otpc_58x.c \
    $(SDK_PATH)/sdk/platform/driver/trng/trng.c \
    $(SDK_PATH)/sdk/platform/arch/main/arch_rom.c \
    $(SDK_PATH)/sdk/platform/utilities/otp_hdr/otp_hdr.c \
    $(SDK_PATH)/sdk/app_modules/src/app_common/app_msg_utils.c \
    $(SDK_PATH)/sdk/app_modules/src/app_common/app_utils.c \
    $(SDK_PATH)/sdk/app_modules/src/app_easy/app_easy_storage.c \
    $(SDK_PATH)/sdk/app_modules/src/app_easy/app_easy_crypto.c \
    $(SDK_PATH)/sdk/app_modules/src/app_easy/app_easy_whitelist.c \
    $(SDK_PATH)/sdk/app_modules/src/app_entry/app_entry_point.c \
    $(SDK_PATH)/third_party/rand/chacha20.c \
    $(SDK_PATH)/third_party/hash/hash.c


C_SRCS       := $(APP_SRCS) $(SDK_SRCS)

# Assembly startup files
ASM_SRCS     := \
    $(SDK_PATH)/sdk/platform/arch/boot/GCC/startup_DA14585_586.S \
    $(SDK_PATH)/sdk/platform/arch/boot/GCC/ivtable_DA14585_586.S

# ─── Object Files ─────────────────────────────────────────────────────────────
# Each source file gets its own .o in BUILD_DIR using a unique name derived from
# the source path (replace / with _ and strip leading separators)
define obj_from_src
$(BUILD_DIR)/$(subst /,_,$(subst $(SDK_PATH)/,,$(1:.c=.o)))
endef

APP_OBJS     := $(foreach s,$(APP_SRCS),$(BUILD_DIR)/$(notdir $(s:.c=.o)))
SDK_OBJS     := $(foreach s,$(SDK_SRCS),$(call obj_from_src,$(s)))
ASM_OBJS     := $(BUILD_DIR)/startup_DA14585_586.o \
                $(BUILD_DIR)/ivtable_DA14585_586.o

OBJS         := $(APP_OBJS) $(SDK_OBJS) $(ASM_OBJS)

# ─── Build Rules ──────────────────────────────────────────────────────────────
.PHONY: all clean flash info

all: $(BUILD_DIR)/$(TARGET).bin $(BUILD_DIR)/$(TARGET).img info

$(BUILD_DIR):
	$(PYTHON) -c "import os; os.makedirs('$(BUILD_DIR)', exist_ok=True)"

# ─── Preprocess SDK Linker Script ─────────────────────────────────────────────
$(LDS_PROCESSED): $(LDS_TEMPLATE) | $(BUILD_DIR)
	@echo "[CPP] Preprocessing linker script..."
	$(CC) -E -P -x c \
	    $(DEFINES) $(APP_INCLUDES) \
	    -I$(SDK_PATH)/sdk/common_project_files/ldscripts \
	    -I$(SDK_PATH)/sdk/common_project_files \
	    -I$(SDK_PATH)/sdk/platform/include \
	    $(LDS_TEMPLATE) -o $@


# ─── Compile Application C Files ──────────────────────────────────────────────
$(BUILD_DIR)/user_eink_app.o: ble/user_eink_app.c | $(BUILD_DIR)
	@echo "[CC] $<"
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/user_custs1_def.o: ble/user_custs1_def.c | $(BUILD_DIR)
	@echo "[CC] $<"
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/user_custs_config.o: ble/user_custs_config.c | $(BUILD_DIR)
	@echo "[CC] $<"
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/user_periph_setup.o: src/user_periph_setup.c | $(BUILD_DIR)
	@echo "[CC] $<"
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/ssd1619.o: ../ssd1619.c | $(BUILD_DIR)
	@echo "[CC] $<"
	$(CC) $(CFLAGS) -c $< -o $@

# ─── Compile SDK C Files (each with unique object name) ───────────────────────
define compile_sdk_rule
$(call obj_from_src,$(1)): $(SDK_PATH)/$(1) | $(BUILD_DIR)
	@echo "[CC] $(1)"
	$(CC) $(CFLAGS) -c $(SDK_PATH)/$(1) -o $(call obj_from_src,$(1))
endef

$(foreach s,$(SDK_SRCS),$(eval $(call compile_sdk_rule,$(subst $(SDK_PATH)/,,$(s)))))

# ─── Assemble Startup Files ───────────────────────────────────────────────────
$(BUILD_DIR)/startup_DA14585_586.o: $(SDK_PATH)/sdk/platform/arch/boot/GCC/startup_DA14585_586.S | $(BUILD_DIR)
	@echo "[AS] $<"
	$(CC) $(ASFLAGS) -c $< -o $@

$(BUILD_DIR)/ivtable_DA14585_586.o: $(SDK_PATH)/sdk/platform/arch/boot/GCC/ivtable_DA14585_586.S | $(BUILD_DIR)
	@echo "[AS] $<"
	$(CC) $(ASFLAGS) -c $< -o $@

# ─── Link ─────────────────────────────────────────────────────────────────────
$(BUILD_DIR)/$(TARGET).elf: $(LDSCRIPT) $(OBJS)
	@echo "[LD] $@"
	$(CC) $(OBJS) $(LDFLAGS) -o $@

$(BUILD_DIR)/$(TARGET).bin: $(BUILD_DIR)/$(TARGET).elf
	@echo "[OBJCOPY] $@"
	$(OBJCOPY) -O binary $< $@

$(BUILD_DIR)/$(TARGET).img: $(BUILD_DIR)/$(TARGET).bin mkimage.py
	@echo "[MKIMAGE] Packaging with Dialog Image Header (id=3)..."
	$(PYTHON) mkimage.py $< $@ --id 3

# ─── Info ─────────────────────────────────────────────────────────────────────
info: $(BUILD_DIR)/$(TARGET).elf
	@echo "--- Memory Usage Summary ---"
	$(SIZE) $<

# ─── Flash ────────────────────────────────────────────────────────────────────
flash: $(BUILD_DIR)/$(TARGET).img
	@echo "[FLASH] Programming BLE firmware to SPI Flash Image 1 (0x004000)..."
	$(PYTHON) ../flash_spi_firmware.py write $< --addr 0x004000 --reset

# ─── Clean ────────────────────────────────────────────────────────────────────
clean:
	$(PYTHON) -c "import shutil, os; os.path.exists('$(BUILD_DIR)') and shutil.rmtree('$(BUILD_DIR)')"
