/*
 * DA14585 Standalone GNU Linker Script
 * =====================================
 * Memory map for Dialog / Renesas DA14585 96KB SysRAM
 */

MEMORY
{
    RAM (rwx) : ORIGIN = 0x07FC0000, LENGTH = 96K
}

ENTRY(Reset_Handler)

SECTIONS
{
    /* Reset vectors & startup */
    .text :
    {
        KEEP(*(.vectors))
        . = 0x0C0;
        KEEP(*(.patch_table))
        . = 0x0C0 + 0x050;

        *(.text*)
        *(.isr_impl*)
        *(.rodata*)
        *(.rodata.*)
        . = ALIGN(4);
        __etext = .;
    } > RAM

    .data :
    {
        . = ALIGN(4);
        __data_start__ = .;
        *(vtable)
        *(.data*)
        . = ALIGN(4);
        __data_end__ = .;
    } > RAM

    /* CMSIS copy table (Empty for RAM-resident images) */
    .copy.table :
    {
        . = ALIGN(4);
        __copy_table_start__ = .;
        __copy_table_end__ = .;
    } > RAM

    /* CMSIS zero-initialization table */
    .zero.table :
    {
        . = ALIGN(4);
        __zero_table_start__ = .;
        LONG (__bss_start__)
        LONG (__bss_end__ - __bss_start__)
        __zero_table_end__ = .;
    } > RAM

    /* BSS uninitialized data */
    .bss :
    {
        . = ALIGN(4);
        __bss_start__ = .;
        *(.bss*)
        *(COMMON)
        . = ALIGN(4);
        __bss_end__ = .;
    } > RAM

    /* Heap memory */
    .heap (NOLOAD) :
    {
        . = ALIGN(8);
        __HeapBase = .;
        . += 0x800;
        __HeapLimit = .;
    } > RAM

    /* Stack memory */
    .stack (NOLOAD) :
    {
        . = ALIGN(8);
        __StackLimit = .;
        . += 0x1000;
        __StackTop = .;
    } > RAM

    /* Discard unused C++ exception tables */
    /DISCARD/ :
    {
        *(.ARM.exidx*)
        *(.ARM.extab*)
    }

    __exidx_start = .;
    __exidx_end = .;
}
