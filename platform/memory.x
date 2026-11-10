/* QEMU MPS2 AN505 secure addresses; U585-class capacity limits.
 * This is CPU execution evidence, not an STM32 peripheral simulation. */
MEMORY {
  FLASH : ORIGIN = 0x10000000, LENGTH = 960K
  RAM   : ORIGIN = 0x38000000, LENGTH = 768K
}
_stack_start = ORIGIN(RAM) + LENGTH(RAM);
_stack_end = _stack_start - 128K;
ASSERT(__ebss + 64K <= _stack_end, "Insufficient display, DMA and driver reserve");
