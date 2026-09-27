import capstone

with open('da14585_fw_image1.bin', 'rb') as f:
    data = f.read()

base = 0x07FC0000
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

def disasm_range(start_addr, end_addr, title):
    print(f"\n{'='*30} {title} (0x{start_addr:08X} - 0x{end_addr:08X}) {'='*30}")
    offset = start_addr - base
    length = end_addr - start_addr
    chunk = data[offset : offset + length]
    for ins in md.disasm(chunk, start_addr):
        hex_str = ' '.join(f'{b:02x}' for b in ins.bytes)
        print(f"  0x{ins.address:08X}: {hex_str:12s} {ins.mnemonic:8s} {ins.op_str}")

disasm_range(0x07FC28A0, 0x07FC28DC, "spi_bitbang_write_byte")
disasm_range(0x07FC28DC, 0x07FC2948, "epd_init_table_or_config")
disasm_range(0x07FC2948, 0x07FC2A00, "epd_reset_and_power")
disasm_range(0x07FC2A00, 0x07FC2A28, "epd_subroutine_A00")
disasm_range(0x07FC2A28, 0x07FC2A54, "epd_write_command")
disasm_range(0x07FC2A54, 0x07FC2A78, "epd_write_data")
disasm_range(0x07FC2A78, 0x07FC2A90, "epd_refresh_or_wait")
disasm_range(0x07FC2A90, 0x07FC2AC8, "epd_send_ram_buffer")
