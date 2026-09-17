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
.ifndef GENDER_Y
.equ GENDER_Y, 44
.endif
.ifndef GENDER_X
.equ GENDER_X, 149
.endif

.equ font_pointer, 0xA378
.equ name_table, 0x166D

# This module is appended to FONT-100 and executes from the FONT allocation.
# AX = NAME-1 record id, DS = game data segment. The resident trampoline leaves
# the caller's original ES below this far function's return address.
cjk_name_cache_start:
.ifdef view_character
    cmp ax, 0xFFEC
    je view_label_entry
    cmp ax, 0xFFEB
    je view_number_entry
.endif
.ifdef fixed_abilities
    # Dedicated adapter-call tag; normal NAME consumers supply IDs < 9999.
    cmp ax, 0xFFED
    je ability_ui_entry
.endif
.ifdef fixed_labels
    cmp ax, 0xFFE9
    je ac_label_entry
    cmp ax, 0xFFEA
    je psi_label_entry
.endif
.ifdef fixed_materials
    cmp ax, 0xFFE7
    je material_label_entry
.endif
.ifdef fixed_identity
    cmp ax, 0xFFCC
    je race_label_entry
    cmp ax, 0xFFCD
    je gender_label_entry
.endif
.ifdef fixed_backpack
    # Only the new bottom-label wrapper has this continuation. The four
    # existing NAME callers use 2516, 2B93, 0FFD, and 102E instead.
    push bp
    mov bp, sp
    cmp word ptr ss:[bp+4], 0x23A0
    pop bp
    je fixed_ui_entry
.endif
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
.ifdef fixed_backpack
    cmp ax, 0xFFFE
    jne name_table_source
    push cs
    pop es
    mov si, OFFSET backpack_source
    jmp decode_start
name_table_source:
.endif
.ifdef fixed_abilities
    cmp ax, 0xFFF0
    jb ordinary_name_source
    cmp ax, 0xFFF6
    jae ordinary_name_source
    sub ax, 0xFFF0
    shl ax, 3
    mov si, OFFSET ability_sources
    add si, ax
    push cs
    pop es
    jmp decode_start
ordinary_name_source:
.endif
.ifdef fixed_labels
    # AC/PSI share the ability decoder's two-triple layout but their own
    # dedicated tag range, so extending them can never change an already
    # shipped ability_ids build (which validates against a fixed 12-id count).
    cmp ax, 0xFFF6
    jb ordinary_label_source
    cmp ax, 0xFFF8
    jae ordinary_label_source
    sub ax, 0xFFF6
    shl ax, 3
    mov si, OFFSET label_sources
    add si, ax
    push cs
    pop es
    jmp decode_start
ordinary_label_source:
.endif
.ifdef fixed_materials
    # Materials are 2-4 Base94 triples each (variable length, unlike the
    # fixed-stride ability/label sources), so lookup goes through a small
    # offset table instead of a constant stride.
    cmp ax, 0xFFD8
    jb ordinary_material_source
    cmp ax, 0xFFDE
    jae ordinary_material_source
    sub ax, 0xFFD8
    shl ax, 1
    mov si, ax
    mov si, word ptr cs:[material_offsets + si]
    push cs
    pop es
    jmp decode_start
ordinary_material_source:
.endif
.ifdef fixed_identity
    # Gender (男性/女性) is fixed two-character text like the ability
    # labels, so it uses the same constant-stride lookup.
    cmp ax, 0xFFCE
    jb ordinary_gender_source
    cmp ax, 0xFFD0
    jae ordinary_gender_source
    sub ax, 0xFFCE
    shl ax, 3
    mov si, OFFSET gender_sources
    add si, ax
    push cs
    pop es
    jmp decode_start
ordinary_gender_source:
    # Race names are 2-3 characters (variable length), so this goes
    # through the same small offset-table style as materials.
    cmp ax, 0xFFD0
    jb ordinary_race_source
    cmp ax, 0xFFD8
    jae ordinary_race_source
    sub ax, 0xFFD0
    shl ax, 1
    mov si, ax
    mov si, word ptr cs:[race_offsets + si]
    push cs
    pop es
    jmp decode_start
ordinary_race_source:
.endif
    mov bx, ax
    imul bx, bx, 25
    les si, [name_table]
    add si, bx
decode_start:
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
.ifdef fixed_backpack
backpack_source:
    .byte 0x5E, (backpack_id_0 / 94) + 0x21, (backpack_id_0 % 94) + 0x21
    .byte 0x5E, (backpack_id_1 / 94) + 0x21, (backpack_id_1 % 94) + 0x21, 0

# Replacement for the first 15 bytes of overlay function 6E111.
# Stack on entry: saved ES, synthetic return IP/CS, original return IP/CS,
# original text offset/segment. Recreate the original BP frame and arguments
# before returning to its untouched renderer call at 6E120.
fixed_ui_entry:
    pop es
    pop cx
    pop dx
    push bp
    mov bp, sp
    push dx
    push cx
    cmp word ptr ss:[bp+6], 0x1853
    jne fixed_passthrough
    mov ax, ds
    cmp word ptr ss:[bp+8], ax
    jne fixed_passthrough
    mov ax, 0xFFFE
    push cs
    push OFFSET fixed_decoded
    push es
    jmp name_cache_entry
fixed_decoded:
    pop ax
    pop dx
    jmp fixed_arguments
fixed_passthrough:
    mov ax, word ptr ss:[bp+6]
    mov dx, word ptr ss:[bp+8]
fixed_arguments:
    pop cx
    pop bx
    push dx
    push ax
    push 0x2C06
    push dword ptr ds:[0x11A4]
    push bx
    push cx
    lret
.endif
.ifdef fixed_abilities
# Six fixed eight-byte strings: two Base94 triples, colon, NUL.
.macro ability_text first, second
    .byte 0x5E, (\first / 94) + 0x21, (\first % 94) + 0x21
    .byte 0x5E, (\second / 94) + 0x21, (\second % 94) + 0x21, 0x3A, 0
.endm
ability_sources:
    ability_text ability_id_0, ability_id_1
    ability_text ability_id_2, ability_id_3
    ability_text ability_id_4, ability_id_5
    ability_text ability_id_6, ability_id_7
    ability_text ability_id_8, ability_id_9
    ability_text ability_id_10, ability_id_11

# Replace only the argument-building portion of the shared label loop.
# BP is the original routine's frame; SI is the current row. Preserve the
# original formatter call and loop tail in the overlay. Translate/reflow
# only the inventory coordinate pair; all other callers keep their pointers.
ability_ui_entry:
    pop es
    pop cx
    pop dx
    push dx
    push cx
    cmp word ptr ss:[bp+0x0A], 236
    jne ability_passthrough
    cmp word ptr ss:[bp+0x0C], 8
    jne ability_passthrough
    mov ax, si
    add ax, 0xFFF0
    push cs
    push OFFSET ability_decoded
    push es
    jmp name_cache_entry
ability_decoded:
    pop ax
    pop dx
    jmp ability_arguments
ability_passthrough:
    mov bx, si
    shl bx, 2
    mov ax, word ptr ds:[bx+0x0EF2]
    mov dx, word ptr ds:[bx+0x0EF4]
ability_arguments:
    pop cx
    pop bx
    push dx
    push ax
    push word ptr ds:[0x3270]
    push 0x14
    push word ptr ds:[0x326E]
    .byte 0x66, 0x68   # push dword 00FE00FFh (two palette arguments)
    .long 0x00FE00FF
    push 0
    push ds
    push 0x0E11
    imul ax, si, 7
    cmp word ptr ss:[bp+0x0A], 236
    jne ability_y_ready
    cmp word ptr ss:[bp+0x0C], 8
    jne ability_y_ready
    imul ax, si, 10
ability_y_ready:
    add ax, word ptr ss:[bp+0x0C]
    push ax
    push word ptr ss:[bp+0x0A]
    push dword ptr ss:[bp+6]
    push bx
    push cx
    lret
.endif
.ifdef fixed_labels
label_sources:
    ability_text ac_label_id_0, ac_label_id_1
    ability_text psi_label_id_0, psi_label_id_1

# AC: the inventory info panel already sprintf's "AC: %2d" into a stack
# buffer before drawing it. "AC" and the translated label are both exactly
# two bytes, so only the first two buffer bytes are overwritten; ':', ' '
# and the sprintf'd digits are left untouched and the original draw call
# immediately after this span is never modified.
ac_label_entry:
    pop es
    pop cx
    pop dx
    push dx
    push cx
    mov ax, 0xFFF6
    push cs
    push OFFSET ac_decoded
    push es
    jmp name_cache_entry
ac_decoded:
    pop ax
    pop dx
    pop cx
    pop bx
    push si
    mov si, ax
    mov al, byte ptr cs:[si]
    mov byte ptr ss:[bp - 0x50], al
    mov al, byte ptr cs:[si + 1]
    mov byte ptr ss:[bp - 0x4f], al
    pop si
    push ss
    lea ax, [bp - 0x50]
    push ax
    push word ptr ds:[0x3270]
    push 0x14
    push word ptr ds:[0x326e]
    .byte 0x66, 0x68
    .long 0x00FE00FF
    push 0
    push ds
    push 0x0E11
    push word ptr ss:[bp + 0x0e]
    push word ptr ss:[bp + 0x0c]
    push dword ptr ss:[bp + 6]
    push bx
    push cx
    lret

# PSI: "%C%C%C" ahead of the label is a fixed draw-color escape, not
# translatable text, so it is kept as a literal prefix in a dedicated
# buffer and the decoded "PSI:" replacement is copied in right after it.
# The replaced span starts one push earlier than the string pointer itself
# (to reach the 22-byte minimum for the shared redirect stub) and stops
# before the draw call itself, whose far-call segment word is an overlay
# relocation target that must never be overwritten.
psi_buffer: .byte 0x25, 0x43, 0x25, 0x43, 0x25, 0x43, 0, 0, 0, 0
psi_label_entry:
    pop es
    pop cx
    pop dx
    push dx
    push cx
    mov ax, 0xFFF7
    push cs
    push OFFSET psi_decoded
    push es
    jmp name_cache_entry
psi_decoded:
    pop ax
    pop dx
    pop cx
    pop bx
    push si
    push di
    mov si, ax
    mov di, OFFSET psi_buffer + 6
    mov al, byte ptr cs:[si]
    mov byte ptr cs:[di], al
    mov al, byte ptr cs:[si + 1]
    mov byte ptr cs:[di + 1], al
    mov al, byte ptr cs:[si + 2]
    mov byte ptr cs:[di + 2], al
    mov byte ptr cs:[di + 3], 0
    pop di
    pop si
    .byte 0x66, 0x68
    .long 0x00FE00FF
    push 0
    push cs
    push OFFSET psi_buffer
    .byte 0x66, 0x68
    .long 0x004500EC
    push dword ptr ds:[0x11A4]
    push bx
    push cx
    lret
.endif
.ifdef fixed_materials
# Weapon/armor material adjective ("Bone", "Wooden", ...), prefixed onto the
# item's already-CJK-decoded base name by a single shared caller before the
# combined buffer reaches the bottom hover label and the right-click card
# (both read the same built string; there is only one call site to patch).
# DX still holds the material flag byte read by the untouched caller code
# immediately before this span; bits 0-3 are the material index (0..5),
# already range-checked (<6) by that same untouched code.
material_offsets: .word material_0, material_1, material_2, material_3, material_4, material_5
material_0: .byte 0x5E, (367 / 94) + 0x21, (367 % 94) + 0x21, 0x5E, (691 / 94) + 0x21, (691 % 94) + 0x21, 0
material_1: .byte 0x5E, (849 / 94) + 0x21, (849 % 94) + 0x21, 0x5E, (691 / 94) + 0x21, (691 % 94) + 0x21, 0
material_2: .byte 0x5E, (544 / 94) + 0x21, (544 % 94) + 0x21, 0x5E, (691 / 94) + 0x21, (691 % 94) + 0x21, 0
material_3: .byte 0x5E, (871 / 94) + 0x21, (871 % 94) + 0x21, 0x5E, (544 / 94) + 0x21, (544 % 94) + 0x21, 0x5E, (691 / 94) + 0x21, (691 % 94) + 0x21, 0
material_4: .byte 0x5E, (762 / 94) + 0x21, (762 % 94) + 0x21, 0x5E, (222 / 94) + 0x21, (222 % 94) + 0x21, 0x5E, (691 / 94) + 0x21, (691 % 94) + 0x21, 0
material_5: .byte 0x5E, (528 / 94) + 0x21, (528 % 94) + 0x21, 0x5E, (691 / 94) + 0x21, (691 % 94) + 0x21, 0
material_label_entry:
    mov bx, dx
    and bx, 0xf
    pop es
    pop cx
    pop dx
    push dx
    push cx
    mov ax, 0xFFD8
    add ax, bx
    push cs
    push OFFSET material_decoded
    push es
    jmp name_cache_entry
material_decoded:
    pop ax
    pop dx
    pop cx
    pop bx
    push si
    push di
    mov si, ax
    mov di, -0x28
material_copy_loop:
    mov al, byte ptr cs:[si]
    mov byte ptr ss:[bp + di], al
    inc si
    inc di
    test al, al
    jnz material_copy_loop
    pop di
    pop si
    push bx
    push cx
    lret
.endif
.ifdef fixed_identity
# Gender and race are per-character numeric fields (not a pre-built
# English string, unlike the material case) at fixed offsets in the
# 71-byte VIEW CHARACTER identity record: [bp+0xA] holds that record's
# far pointer (unchanged since the caller's own "les bx,[bp+0xA]" a few
# instructions earlier; BP itself is never touched by this decoder or
# the redirect it was reached through). Gender is a two-character fixed
# string like the ability labels; race is variable length (2-3
# characters) like the material adjectives.
# Plain two-character text, unlike ability_text's fixed ":" suffix.
.macro identity_text first, second
    .byte 0x5E, (\first / 94) + 0x21, (\first % 94) + 0x21
    .byte 0x5E, (\second / 94) + 0x21, (\second % 94) + 0x21, 0, 0
.endm
gender_sources:
    identity_text 512, 269
    identity_text 189, 269

race_offsets: .word race_0, race_1, race_2, race_3, race_4, race_5, race_6, race_7
race_0: .byte 0x5E, (27 / 94) + 0x21, (27 % 94) + 0x21, 0x5E, (838 / 94) + 0x21, (838 % 94) + 0x21, 0
race_1: .byte 0x5E, (543 / 94) + 0x21, (543 % 94) + 0x21, 0x5E, (27 / 94) + 0x21, (27 % 94) + 0x21, 0
race_2: .byte 0x5E, (586 / 94) + 0x21, (586 % 94) + 0x21, 0x5E, (822 / 94) + 0x21, (822 % 94) + 0x21, 0
race_3: .byte 0x5E, (106 / 94) + 0x21, (106 % 94) + 0x21, 0x5E, (586 / 94) + 0x21, (586 % 94) + 0x21, 0x5E, (822 / 94) + 0x21, (822 % 94) + 0x21, 0
race_4: .byte 0x5E, (106 / 94) + 0x21, (106 % 94) + 0x21, 0x5E, (227 / 94) + 0x21, (227 % 94) + 0x21, 0x5E, (27 / 94) + 0x21, (27 % 94) + 0x21, 0
race_5: .byte 0x5E, (106 / 94) + 0x21, (106 % 94) + 0x21, 0x5E, (724 / 94) + 0x21, (724 % 94) + 0x21, 0x5E, (27 / 94) + 0x21, (27 % 94) + 0x21, 0
race_6: .byte 0x5E, (1317 / 94) + 0x21, (1317 % 94) + 0x21, 0x5E, (484 / 94) + 0x21, (484 % 94) + 0x21, 0x5E, (27 / 94) + 0x21, (27 % 94) + 0x21, 0
race_7: .byte 0x5E, (1319 / 94) + 0x21, (1319 % 94) + 0x21, 0x5E, (1318 / 94) + 0x21, (1318 % 94) + 0x21, 0x5E, (27 / 94) + 0x21, (27 % 94) + 0x21, 0

gender_label_entry:
    les bx, [bp + 0x0A]
    mov al, es:[bx + 0x19]
    dec al
    cbw
    pop es
    pop cx
    pop dx
    push dx
    push cx
    add ax, 0xFFCE
    push cs
    push OFFSET gender_decoded
    push es
    jmp name_cache_entry
gender_decoded:
    # v65 moves gender up onto the equipment row, so this span was widened
    # to also absorb the original code's own remaining argument pushes
    # (color escape, template id, and the position pair it was about to
    # push from DI/SI) up to -- but not including -- the still-untouched
    # "call 339E:016D" draw itself. GENDER_Y/GENDER_X replace what would
    # have been "push di; push si".
    pop ax
    pop dx
    pop cx
    pop bx
    push dx
    push ax
    push word ptr ds:[0x3270]
    push 0x14
    push word ptr ds:[0x326E]
    .byte 0x66, 0x68
    .long 0x00FE00FF
    push 0
    push ds
    push 0x0E11
    push GENDER_Y
    push GENDER_X
    push dword ptr ss:[bp + 6]
    push bx
    push cx
    lret

race_label_entry:
    les bx, [bp + 0x0A]
    mov al, es:[bx + 0x18]
    dec al
    cbw
    pop es
    pop cx
    pop dx
    push dx
    push cx
    add ax, 0xFFD0
    push cs
    push OFFSET race_decoded
    push es
    jmp name_cache_entry
race_decoded:
    pop ax
    pop dx
    pop cx
    pop bx
    push dx
    push ax
    push word ptr ds:[0x3270]
    push bx
    push cx
    lret
.endif
cjk_name_cache_end:
.ifdef view_character
# Independent VIEW CHARACTER loops. They render into the surface at 0430:0000,
# not the original BP-relative surface used by the shared inventory routine.
view_label_entry:
    pop es
    pop cx
    pop dx
    push dx
    push cx
    mov ax, si
    add ax, 0xFFF0
    push cs
    push OFFSET view_label_decoded
    push es
    jmp name_cache_entry
view_label_decoded:
    pop ax
    pop dx
    pop cx
    pop bx
    push dx
    push ax
    push word ptr ds:[0x3270]
    push 0x14
    push word ptr ds:[0x326E]
    .byte 0x66, 0x68
    .long 0x00FE00FF
    push 0
    push ds
    push 0x3351
    call view_coordinates
    push ax
    push dx
    push bx
    push cx
    lret
view_number_entry:
    pop es
    pop cx
    pop bx
    push word ptr ds:[0x3270]
    push 0x14
    push word ptr ds:[0x326E]
    .byte 0x66, 0x68
    .long 0x00FE00FF
    push 0
    push ds
    push 0x335A
    call view_coordinates
    add dx, 28
    push ax
    push dx
    # Return BEFORE the original relocated mov ax,0430 / surface argument.
    # The overlay loader owns that segment operand; never clone it into FONT.
    push bx
    push cx
    lret

# SI, BX and CX all carry values the caller still needs after this call
# returns (BX/CX are threaded straight through to the final push/lret in
# view_label_decoded/view_number_entry) -- only AX and DX may be touched.
# The stack (push/pop, net zero by the time RET runs) stands in for the
# extra scratch register a three-column split would otherwise need.
#
# AX=y and DX=label x. Three columns (SI mod 3) by two rows (SI div 3):
# row 0 holds STR/DEX/CON, row 1 holds INT/WIS/CHA, matching the prior
# two-column grouping just laid out horizontally instead.
view_coordinates:
    mov ax, si
    cmp ax, 3
    jb view_top_row
    sub ax, 3
    push ax
    mov ax, 12
    jmp view_have_row
view_top_row:
    push ax
    xor ax, ax
view_have_row:
    add ax, view_y_origin
    pop dx
    imul dx, dx, 44
    add dx, 149
    ret
.endif
