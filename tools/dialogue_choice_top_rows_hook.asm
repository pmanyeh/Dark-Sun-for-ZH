.intel_syntax noprefix
.code16
.section .text
.global choice_top_rows_start

# Entered by a far call that replaces the 7-byte prologue of 3241:07FA
# (SetButtonText). Stack on entry:
#   [sp+0]  return into 07FA (discarded)
#   [sp+4]  caller return address
#   [sp+8]  window handle (far)
#   [sp+12] control ID
#
# For dialogue choices 081C..081F, stamp the clean panel row onto the top
# two scanlines of the choice on the hidden VGA page. The native redraw
# then clears the rest and draws the new text; the game flips the page.
#
# Lives in the dead 0x155-byte block at 147D:000F. Its module has a single
# function (147D:0166) that only reads and writes cs:0164, and nothing else
# references the block.

.equ first_choice,  0x081C
.equ first_row,     153
.equ choice_pitch,  11
.equ row_bytes,     80
.equ panel_bytes,   76

choice_top_rows_start:
    pusha
    push ds
    push es
    mov bp, sp
    mov ax, [bp + 32]
    sub ax, first_choice
    cmp ax, 3
    ja done
    imul di, ax, choice_pitch * row_bytes
    add di, first_row * row_bytes
    pushf
    cli
    cld

    # Hidden page = CRTC start address XOR 0x4000.
    mov dx, 0x3D4
    in al, dx
    mov bl, al
    mov al, 0x0C
    out dx, al
    inc dx
    in al, dx
    xor al, 0x40
    mov ah, al
    dec dx
    mov al, 0x0D
    out dx, al
    inc dx
    in al, dx
    add di, ax
    dec dx
    mov al, bl
    out dx, al

    mov dx, 0x3C4
    in al, dx
    mov bl, al
    mov al, 2
    out dx, al
    inc dx
    in al, dx
    mov bh, al

    push cs
    pop ds
    push 0xA000
    pop es
    lea si, panel
    mov ah, 1

# Per plane: 19 bytes of 2-bit values (0x18 + v, low bits first), then
# the raw value of byte 0, which is outside 0x18..0x1B on some planes.
plane_loop:
    mov al, ah
    out dx, al
    push di
    mov cx, panel_bytes / 4
byte_loop:
    lodsb
    mov bp, 4
value_loop:
    push ax
    and al, 3
    add al, 0x18
    mov es:[di], al
    mov es:[di + row_bytes], al
    inc di
    pop ax
    shr al, 2
    dec bp
    jnz value_loop
    loop byte_loop
    pop di
    lodsb
    mov es:[di], al
    mov es:[di + row_bytes], al
    shl ah, 1
    cmp ah, 0x10
    jb plane_loop

    mov al, bh
    out dx, al
    dec dx
    mov al, bl
    out dx, al
    popf

done:
    pop es
    pop ds
    popa
    add sp, 4
    push bp
    mov bp, sp
    sub sp, 0xEA
    # Segment word is added to the MZ relocation table.
    .byte 0xEA
    .word 0x0801, 0x2A1D

panel:
    .include "panel.inc"
