.intel_syntax noprefix
.code16
.section .text
.global cjk_name_cache_start

.ifndef staging_offset
.equ staging_offset, 0x206B
.endif
.ifndef first_slot_offset
.equ first_slot_offset, 0x20D1
.endif
.ifndef cjk_record_bytes
.equ cjk_record_bytes, 102
.endif
.ifndef bank_count
.equ bank_count, 6
.endif

.equ font_pointer, 0xA378
.equ name_table, 0x166D

# This module is appended to FONT-100 and executes from the FONT allocation.
# AX = NAME-1 record id, DS = game data segment. The resident trampoline leaves
# the caller's original ES below this far function's return address.
cjk_name_cache_start:
name_cache_entry:
    push bp
    mov bp, sp
    push bx
    push cx
    push si
    push di
    push ds
    push es
    mov cs:[pending_id], ax
    cmp ax, cs:[cached_id]
    je cache_return
    mov bx, ax
    imul bx, bx, 25
    les si, [name_table]
    add si, bx
    mov byte ptr cs:[slot_count], 0
    mov di, OFFSET name_buffer

decode_next:
    mov al, byte ptr es:[si]
    test al, al
    jz decode_done
    cmp di, OFFSET name_buffer + 24
    jae decode_done
    cmp al, 0x5E
    je decode_triple
    mov byte ptr cs:[di], al
    inc si
    inc di
    jmp decode_next

decode_triple:
    mov al, byte ptr es:[si+1]
    sub al, 0x21
    cmp al, 93
    ja malformed_triple
    xor ah, ah
    mov bx, 94
    mul bx
    mov dl, byte ptr es:[si+2]
    sub dl, 0x21
    cmp dl, 93
    ja malformed_triple
    xor dh, dh
    add ax, dx
    xor bx, bx
    mov cl, byte ptr cs:[slot_count]
    xor ch, ch
    jcxz allocate_slot
find_slot:
    cmp ax, word ptr cs:[slot_ids+bx]
    je reuse_slot
    add bx, 2
    loop find_slot

allocate_slot:
    mov bl, byte ptr cs:[slot_count]
    xor bh, bh
    cmp bl, 7
    jae malformed_triple
    shl bx, 1
    mov word ptr cs:[slot_ids+bx], ax
    mov bl, byte ptr cs:[slot_count]
    inc bl
    mov byte ptr cs:[slot_count], bl
    mov byte ptr cs:[active_slot], bl
    call glyph_loader
    cmp ax, 0x017F
    jne glyph_error
    call copy_staging_to_slot
    jmp emit_slot

reuse_slot:
    shr bx, 1
    inc bl
    mov byte ptr cs:[active_slot], bl
emit_slot:
    xor bx, bx
    mov bl, byte ptr cs:[active_slot]
    dec bx
    mov al, byte ptr cs:[transport_codes+bx]
    mov byte ptr cs:[di], al
    add si, 3
    inc di
    jmp decode_next

malformed_triple:
    inc si
    mov byte ptr cs:[di], 0x3F
    inc di
    jmp decode_next
glyph_error:
    dec byte ptr cs:[slot_count]
    add si, 3
    mov byte ptr cs:[di], 0x3F
    inc di
    jmp decode_next
decode_done:
    mov byte ptr cs:[di], 0
    mov ax, cs:[pending_id]
    mov cs:[cached_id], ax

cache_return:
    pop es
    pop ds
    pop di
    pop si
    pop cx
    pop bx
    pop bp
    mov ax, OFFSET name_buffer
    push cs
    pop dx
    pop es
    pop cx
    pop bx
    push dx
    push ax
    push bx
    push cx
    lret

# Self-contained FONT-local form of the legacy CJB1 loader.
glyph_loader:
    mov cs:[loader_saved_id], ax
    mov cs:[saved_game_ds], ds
    push bx
    push cx
    push dx
    push si
    push di
    push ds
    push es
    mov al, ah
    cmp al, bank_count
    jae loader_error
    xor ah, ah
    push ds
    push cs
    pop ds
    mov bx, ax
    shl bx, 1
    mov dx, cs:[bank_names+bx]
    mov ax, 0x3D00
    int 0x21
    pop ds
    jc loader_error
    mov cs:[handle], ax
    mov ax, cs:[loader_saved_id]
    xor ah, ah
    mov dx, ax
    shl dx, 2
    add dx, 16
    xor cx, cx
    mov bx, cs:[handle]
    mov ax, 0x4200
    int 0x21
    jc loader_close_error
    push ds
    push cs
    pop ds
    mov dx, OFFSET dir_entry
    mov cx, 4
    mov bx, cs:[handle]
    mov ah, 0x3F
    int 0x21
    pop ds
    jc loader_close_error
    cmp ax, 4
    jne loader_close_error
    mov ax, cs:[loader_saved_id]
    xor ah, ah
    cmp cs:[dir_entry], ax
    jne loader_close_error
    mov dx, cs:[dir_entry+2]
    xor cx, cx
    mov bx, cs:[handle]
    mov ax, 0x4200
    int 0x21
    jc loader_close_error
    mov ax, cs:[saved_game_ds]
    mov ds, ax
    les di, [font_pointer]
    mov word ptr es:[di+0x0206], staging_offset
    add di, staging_offset
    mov ax, es
    mov ds, ax
    mov dx, di
    mov cx, cjk_record_bytes
    mov bx, cs:[handle]
    mov ah, 0x3F
    int 0x21
    jc loader_close_error
    cmp ax, cjk_record_bytes
    jne loader_close_error
    mov dx, 0x017F
    jmp loader_close
loader_close_error:
    mov dx, 0x013F
loader_close:
    mov bx, cs:[handle]
    mov ah, 0x3E
    int 0x21
    mov ax, dx
    jmp loader_return
loader_error:
    mov ax, 0x013F
loader_return:
    pop es
    pop ds
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

copy_staging_to_slot:
    push ax
    push bx
    push cx
    push si
    push di
    push ds
    push es
    les di, [font_pointer]
    mov bx, di
    xor ax, ax
    mov al, byte ptr cs:[active_slot]
    dec ax
    mov cx, cjk_record_bytes
    mul cx
    add ax, first_slot_offset
    mov si, bx
    add si, staging_offset
    add di, ax
    push es
    pop ds
    mov cx, cjk_record_bytes / 2
    rep movsw

    mov di, bx
    xor bx, bx
    mov bl, byte ptr cs:[active_slot]
    dec bx
    mov bl, byte ptr cs:[transport_codes+bx]
    xor bh, bh
    shl bx, 1
    add di, 0x0108
    add di, bx
    mov word ptr es:[di], ax
    pop es
    pop ds
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

cached_id:       .word 0xFFFF
pending_id:      .word 0
slot_count:      .byte 0
active_slot:     .byte 0
slot_ids:        .space 14, 0
loader_saved_id: .word 0
saved_game_ds:   .word 0
handle:          .word 0
dir_entry:       .long 0
bank_names: .word bank0, bank1, bank2, bank3, bank4, bank5
bank0: .asciz "C0"
bank1: .asciz "C1"
bank2: .asciz "C2"
bank3: .asciz "C3"
bank4: .asciz "C4"
bank5: .asciz "C5"
transport_codes: .byte 0x22, 0x23, 0x26, 0x3C, 0x3E, 0x5C, 0x7E
name_buffer: .space 25, 0
cjk_name_cache_end:
