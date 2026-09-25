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
.ifndef ALIGNMENT_Y
.equ ALIGNMENT_Y, 93
.endif
.ifndef ALIGNMENT_X
.equ ALIGNMENT_X, 149
.endif
# VIEW CHARACTER lower half: the HP:/PSI: labels' row (re_95: 125), and the
# class-name row. The class row's own EXE immediate (0x8A1E4) overlaps an
# overlay relocation, so the class-name redirect moves it instead (re_102).
.ifndef VIEW_STAT_ROW_Y
.equ VIEW_STAT_ROW_Y, 125
.endif
# plan_name_slot_consumers.py writes this file from the current CJK mapping;
# it defines the ui_text_* macros used by the material/identity/class tables.
.ifdef generated_ui_text
.include "name_slot_ui_text.inc"
.endif

.equ font_pointer, 0xA378
# Dialogue menu title buffer (DGROUP:5504) and its private decode source id.
.equ MENU_TITLE_BUFFER, 0x5504
.equ MENU_TITLE_SOURCE_ID, 0xFF80
# One-line window text (message boxes, "SAVING GAME"): its private source id.
.equ STATUS_TEXT_SOURCE_ID, 0xFF83
# The resident draw_text wrapper 191F:0A40: its private source id.
.equ TEXT_DRAW_SOURCE_ID, 0xFF85
# The overlay draws the title at x=6, y=4. English capitals sit in the top
# seven rows of FONT-100's nine-row cell, but a CJK glyph fills all ten, so
# at y=4 it touched the first choice (y=13); Chinese titles draw 2px higher.
.equ MENU_TITLE_X, 6
.equ MENU_TITLE_ENGLISH_Y, 4
.equ MENU_TITLE_CHINESE_Y, 2
.equ name_table, 0x166D
# The fixed 4-byte gap between [font_pointer]'s own runtime offset and
# this payload's CS:0 (see plan_name_slot_consumers.py's
# FONT_RUNTIME_BASE_OFFSET, and re_94's live confirmation that CS
# equals [font_pointer]'s segment exactly at runtime): subtracting this
# from any `OFFSET label` inside this payload converts it into the same
# "[font_pointer]-relative" space staging_offset/first_slot_offset
# already use, which is what copy_staging_to_slot needs to place
# class_extra_slots' glyph data where the resident renderer will find
# it. This is NOT the same constant as FONT_CORE_PAYLOAD_OFFSET
# (0x239B) -- that one converts the opposite direction (font_pointer-
# relative to CS-relative, for jumping into code) and re_93 mistakenly
# reused it here, which is why that attempt's extra glyph slots ended
# up overwriting unrelated FONT memory instead of their own storage.
.equ FONT_RUNTIME_BASE_OFFSET, 0x0004
# re_94: raised from 7 to 10 so a single VIEW CHARACTER draw (e.g. a
# three-class character's combined class-name render, which needs every
# distinct glyph across all three class names alive in the physical
# glyph pool at once -- see class_skip_reset) has enough headroom for
# names that need more than 7 distinct characters. Slots 1-7 still live
# in the game's own pre-allocated FONT scratch area (first_slot_offset);
# slots 8-10 live in class_extra_slots, storage this payload brings with
# it, since the game's own scratch area is a fixed size we can't grow.
.equ glyph_slot_count, 10

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
    cmp ax, 0xFFC9
    je view_hp_label_entry
    cmp ax, 0xFFCA
    je view_psi_label_entry
.endif
.ifdef fixed_materials
    cmp ax, 0xFFE7
    je material_label_entry
.endif
.ifdef fixed_class_names
    cmp ax, 0xFF90
    je class_slot1_label_entry
    cmp ax, 0xFF91
    je class_slot2_label_entry
    cmp ax, 0xFF92
    je class_slot3_label_entry
.endif
.ifdef fixed_identity
    cmp ax, 0xFFCB
    je alignment_label_entry
    cmp ax, 0xFFCC
    je race_label_entry
    cmp ax, 0xFFCD
    je gender_label_entry
.endif
.ifdef menu_titles
    cmp ax, 0xFF81
    je menu_title_entry
.endif
.ifdef status_texts
    cmp ax, 0xFF82
    je status_text_entry
.endif
.ifdef text_draws
    cmp ax, 0xFF84
    je text_draw_entry
    cmp ax, 0xFF86
    je text_width_entry
.endif
.ifdef cursor_hotkeys
    cmp ax, 0xFF87
    je cursor_hotkey_entry
.endif
.ifdef smart_cursor
    cmp ax, 0xFF88
    je smart_click_entry
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
.ifdef menu_titles
    # The dialogue menu title buffer DGROUP:5504 (GSTR[1], GSTR[4] or an
    # inline prompt copied there by the menu opcode).
    cmp ax, MENU_TITLE_SOURCE_ID
    jne ordinary_title_source
    push ds
    pop es
    mov si, MENU_TITLE_BUFFER
    jmp decode_start
ordinary_title_source:
.endif
.ifdef status_texts
    cmp ax, STATUS_TEXT_SOURCE_ID
    jne ordinary_status_source
    les si, dword ptr cs:[status_source]
    jmp decode_start
ordinary_status_source:
.endif
.ifdef text_draws
    cmp ax, TEXT_DRAW_SOURCE_ID
    jne ordinary_text_draw_source
    les si, dword ptr cs:[text_draw_source]
    jmp decode_start
ordinary_text_draw_source:
.endif
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
    # AC/PSI (item panel) plus VIEW CHARACTER's own HP:/PSI: labels all
    # share the ability decoder's two-triple layout but their own dedicated
    # tag range, so extending them can never change an already shipped
    # ability_ids build (which validates against a fixed 12-id count).
    cmp ax, 0xFFF6
    jb ordinary_label_source
    cmp ax, 0xFFFA
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
.ifdef fixed_class_names
    # Class names (Cleric..Thief) are 2-3 characters, variable length like
    # materials/race, so this also goes through a small offset table. All
    # three class slots share the same 17-entry table (IDs 1-17).
    cmp ax, 0xFFA0
    jb ordinary_class_source
    cmp ax, 0xFFB1
    jae ordinary_class_source
    sub ax, 0xFFA0
    shl ax, 1
    mov si, ax
    mov si, word ptr cs:[class_offsets + si]
    push cs
    pop es
    jmp decode_start
ordinary_class_source:
.endif
.ifdef fixed_identity
    # Alignment (e.g. 混亂善良) is fixed four-character text, one constant
    # stride wider than gender's two-character entries but the same idea.
    cmp ax, 0xFFC0
    jb ordinary_alignment_source
    cmp ax, 0xFFC9
    jae ordinary_alignment_source
    sub ax, 0xFFC0
    shl ax, 4
    mov si, OFFSET alignment_sources
    add si, ax
    push cs
    pop es
    jmp decode_start
ordinary_alignment_source:
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
    # `class_skip_reset` lets a multiclass character's 2nd/3rd class-name
    # field keep accumulating into the SAME physical glyph slots its
    # earlier sibling field(s) already allocated this draw, instead of
    # wiping them out from under a pointer that's still waiting to be
    # drawn (see re_93/re_94: the 2-/3-class draw paths collect every
    # slot's far pointer and only call the shared renderer once, after
    # all fields have decoded, so a later field's fresh `slot_count=0`
    # reset would silently repaint the very glyph memory an earlier
    # field's pointer still relies on). It is a one-shot flag: whoever
    # sets it to 1 (class_slot2_label_entry/class_slot3_label_entry,
    # only when their own record check finds an earlier class slot
    # already populated) is asking for exactly the one decode_start call
    # that follows to skip the reset; every other caller leaves it 0, so
    # this never affects any other NAME-slot field.
    cmp byte ptr cs:[class_skip_reset], 0
    je decode_reset_slots
    mov byte ptr cs:[class_skip_reset], 0
    jmp decode_start_ready
decode_reset_slots:
    mov byte ptr cs:[slot_count], 0
decode_start_ready:
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
    cmp bl, glyph_slot_count
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
    # re_94: this used to only `inc si` (skip the 0x5E tag byte alone),
    # leaving the triple's two Base94 data bytes still sitting at `si`
    # for the next decode_next iteration to copy through as two literal
    # garbage characters (neither byte is 0x5E, so the "not a tag" path
    # takes them verbatim). Never observed before this session because
    # nothing used to decode a string that both needed more than the
    # 7-slot glyph pool has room for *and* kept decoding past that point
    # in the same call -- the multiclass accumulate-across-slots fix
    # (`class_skip_reset`) is what first makes a single class name's
    # own decode able to run out of physical slots mid-string. Skipping
    # the full 3-byte triple (matching emit_slot's `add si, 3` for the
    # success case) is what the trailing decode_next loop actually
    # expects for "this triple, whatever happened to it, is consumed".
    add si, 3
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
    cmp al, 7
    ja copy_slot_extra
    dec ax
    mov cx, cjk_record_bytes
    mul cx
    add ax, first_slot_offset
    jmp copy_slot_target_ready
copy_slot_extra:
    # re_94: slots 8-10 live in class_extra_slots (this payload's own
    # storage), addressed as `OFFSET class_extra_slots` -- which is
    # CS-relative, not [font_pointer]-relative like first_slot_offset --
    # so it needs FONT_RUNTIME_BASE_OFFSET subtracted to land in the
    # same space before the rest of this routine (and the renderer's own
    # later lookup through the pointer table this writes) can use it the
    # same way as a built-in slot's offset.
    sub al, 8
    cbw
    mov cx, cjk_record_bytes
    mul cx
    push ax
    mov ax, OFFSET class_extra_slots
    sub ax, FONT_RUNTIME_BASE_OFFSET
    pop cx
    add ax, cx
copy_slot_target_ready:
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
class_skip_reset: .byte 0
slot_ids:        .space 20, 0
loader_saved_id: .word 0
saved_game_ds:   .word 0
handle:          .word 0
dir_entry:       .long 0
# One "C<n>" file per CJB1 bank. The v75 line shipped six banks; the main
# build passes its own bank_count (twelve as of v87) so item names whose
# glyphs live in the later banks decode instead of falling back to '?'.
bank_names:
.irp n, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15
.if \n < bank_count
    .word bank\n
.endif
.endr
.irp n, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15
.if \n < bank_count
bank\n: .asciz "C\n"
.endif
.endr
# re_94: the last three (backtick/underscore/pipe) are the pool-
# expansion codes for slots 8-10. Chosen the same way as the original
# seven -- confirmed absent from all 13295 dialogue_units.json entries
# -- and deliberately not '/', since VIEW CHARACTER's own multiclass
# template already draws a literal '/' separator between class names on
# this exact screen; reusing it as a transport code would make that
# separator glyph flicker between '/' and whatever CJK character last
# claimed that physical slot.
transport_codes: .byte 0x22, 0x23, 0x26, 0x3C, 0x3E, 0x5C, 0x7E, 0x60, 0x5F, 0x7C
name_buffer: .space 25, 0
class_extra_slots: .space 306, 0
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
.ifdef menu_titles
# Replacement for overlay bytes 7D818..7D83A of the dialogue menu title draw:
#     lcall strupr(ds:5504)          ; 7D813, now aimed at strupr's own retf
#     add sp, 4                      ; \
#     push ds; push 5504h            ;  | this span
#     push the %C colour words, "%C%C%C%s" (ds:1F58) and x=6,y=4
#                                    ; /
#     push dword [3C8:0]; lcall 0150:016D   ; 7D83B, untouched
# 339E:016D cannot decode Base94 and strupr would turn the triples' a-z into
# other characters. A Chinese title is decoded into NAME glyph slots; an
# English one is upper-cased here and drawn as before.
menu_title_entry:
    pop es
    pop cx
    pop dx
    add sp, 4
    push dx
    push cx
    push si
    mov si, MENU_TITLE_BUFFER
menu_title_scan:
    mov al, byte ptr [si]
    test al, al
    jz menu_title_english
    cmp al, 0x5E
    je menu_title_chinese
    inc si
    jmp menu_title_scan
menu_title_english:
    mov si, MENU_TITLE_BUFFER
menu_title_upper:
    mov al, byte ptr [si]
    test al, al
    jz menu_title_upper_done
    sub al, 0x61
    cmp al, 0x19
    ja menu_title_upper_next
    add al, 0x41
    mov byte ptr [si], al
menu_title_upper_next:
    inc si
    jmp menu_title_upper
menu_title_upper_done:
    pop si
    mov word ptr cs:[menu_title_y], MENU_TITLE_ENGLISH_Y
    mov ax, MENU_TITLE_BUFFER
    mov dx, ds
    jmp menu_title_arguments
menu_title_chinese:
    pop si
    mov word ptr cs:[menu_title_y], MENU_TITLE_CHINESE_Y
    # Titles change from menu to menu; never reuse the previous decode.
    mov word ptr cs:[cached_id], 0xFFFF
    mov ax, MENU_TITLE_SOURCE_ID
    push cs
    push OFFSET menu_title_decoded
    push es
    jmp name_cache_entry
menu_title_decoded:
    pop ax
    pop dx
menu_title_arguments:
    pop cx
    pop bx
    push dx
    push ax
    .byte 0x66, 0x68
    .long 0x00110014
    .byte 0x66, 0x68
    .long 0x002F00FE
    .byte 0x66, 0x68
    .long 0x00FF0000
    push ds
    push 0x1F58
    push word ptr cs:[menu_title_y]
    push MENU_TITLE_X
    push bx
    push cx
    lret
menu_title_y: .word MENU_TITLE_ENGLISH_Y
.endif
.ifdef status_texts
# Replacement for overlay bytes 704AB..704BD of the window text setter
# (overlay segment 25, entry 0580:005C), which every message box uses:
#     mov [5435], si                 ; \  this span
#     mov byte [bp-28h], 0           ;  |
#     push 1Fh; push dword [bp+0Ch]; push ss:bp-28h
#     lcall strncpy                  ; 704BE, untouched
#     lcall strupr(bp-28h)           ; then drawn one byte per glyph
# The draw loop cannot decode Base94 and strupr would rewrite the triples'
# a-z. A Chinese text is decoded into NAME glyph slots (whose codes strupr
# leaves alone) and strncpy copies those instead; English passes through.
status_text_entry:
    pop es
    pop cx
    pop dx
    push dx
    push cx
    mov word ptr [0x5435], si
    mov byte ptr ss:[bp-0x28], 0
    mov ax, word ptr ss:[bp+0x0C]
    mov dx, word ptr ss:[bp+0x0E]
    mov word ptr cs:[status_source], ax
    mov word ptr cs:[status_source+2], dx
    push es
    push si
    les si, dword ptr cs:[status_source]
status_text_scan:
    mov al, byte ptr es:[si]
    test al, al
    jz status_text_english
    cmp al, 0x5E
    je status_text_chinese
    inc si
    jmp status_text_scan
status_text_english:
    pop si
    pop es
    mov ax, word ptr cs:[status_source]
    mov dx, word ptr cs:[status_source+2]
    jmp status_text_arguments
status_text_chinese:
    pop si
    pop es
    mov word ptr cs:[cached_id], 0xFFFF
    mov ax, STATUS_TEXT_SOURCE_ID
    push cs
    push OFFSET status_text_decoded
    push es
    jmp name_cache_entry
status_text_decoded:
    pop ax
    pop dx
status_text_arguments:
    pop cx
    pop bx
    push 0x1F
    push dx
    push ax
    push ss
    lea ax, [bp-0x28]
    push ax
    push bx
    push cx
    lret
status_source: .long 0
.endif
.ifdef text_draws
# Replacement for the argument pushes of the resident draw_text wrapper
# 191F:0A40 (file 1F033..1F050), which formats "%C%C%C%s" through 339E:016D:
#     push dword [bp+0Ah]            ; the text        #     push [bp+14h]; push 14h; push [bp+12h]           |  this span
#     push dword 00FE00FFh; push 0; push ds:0D8F       |
#     push [bp+10h]; push [bp+0Eh]                     /
#     push dword [bp+6]; lcall 339E:016D      ; 1F051, untouched
# Portrait status words, item panel labels and other callers pass their
# text here; a Chinese one is decoded into NAME glyph slots first.
text_draw_entry:
    pop es
    pop cx
    pop dx
    push dx
    push cx
    mov ax, word ptr ss:[bp+0x0A]
    mov dx, word ptr ss:[bp+0x0C]
    mov word ptr cs:[text_draw_source], ax
    mov word ptr cs:[text_draw_source+2], dx
    push es
    push si
    les si, dword ptr cs:[text_draw_source]
text_draw_scan:
    mov al, byte ptr es:[si]
    test al, al
    jz text_draw_english
    cmp al, 0x5E
    je text_draw_chinese
    inc si
    jmp text_draw_scan
text_draw_english:
    pop si
    pop es
    mov word ptr cs:[text_draw_dy], 0
    mov ax, word ptr cs:[text_draw_source]
    mov dx, word ptr cs:[text_draw_source+2]
    jmp text_draw_arguments
text_draw_chinese:
    pop si
    pop es
    # CJK glyphs fill all ten rows where capitals use the middle seven, so a
    # Chinese line drawn 7px under another (inventory HP/status) would touch it.
    mov word ptr cs:[text_draw_dy], 2
    mov word ptr cs:[cached_id], 0xFFFF
    mov ax, TEXT_DRAW_SOURCE_ID
    push cs
    push OFFSET text_draw_decoded
    push es
    jmp name_cache_entry
text_draw_decoded:
    pop ax
    pop dx
text_draw_arguments:
    pop cx
    pop bx
    push dx
    push ax
    push word ptr ss:[bp+0x14]
    push 0x14
    push word ptr ss:[bp+0x12]
    .byte 0x66, 0x68
    .long 0x00FE00FF
    push 0
    push ds
    push 0x0D8F
    mov ax, word ptr ss:[bp+0x10]
    add ax, word ptr cs:[text_draw_dy]
    push ax
    push word ptr ss:[bp+0x0E]
    push bx
    push cx
    lret

# Replacement for 191F:0401..0416 (file 1E9F6..1EA06), the width of a string
# as the sum of its glyph widths, used to centre the VIEW/USE portrait status:
#     if (!text) return 0; si = di = 0; goto loop_test (0x042A)
# A Chinese text is decoded into NAME glyph slots and the width loop then
# measures the slot codes, i.e. what text_draw_entry will draw.
text_width_entry:
    pop es
    pop cx
    pop dx
    xor si, si
    xor di, di
    mov ax, word ptr ss:[bp+0x06]
    or ax, word ptr ss:[bp+0x08]
    jnz text_width_measure
    mov cx, 0x0437
    push dx
    push cx
    lret
text_width_measure:
    push dx
    push cx
    mov ax, word ptr ss:[bp+0x06]
    mov dx, word ptr ss:[bp+0x08]
    mov word ptr cs:[text_draw_source], ax
    mov word ptr cs:[text_draw_source+2], dx
    push es
    les si, dword ptr cs:[text_draw_source]
text_width_scan:
    mov al, byte ptr es:[si]
    test al, al
    jz text_width_english
    cmp al, 0x5E
    je text_width_chinese
    inc si
    jmp text_width_scan
text_width_english:
    pop es
    xor si, si
    lret
text_width_chinese:
    pop es
    mov word ptr cs:[cached_id], 0xFFFF
    mov ax, TEXT_DRAW_SOURCE_ID
    push cs
    push OFFSET text_width_decoded
    push es
    jmp name_cache_entry
text_width_decoded:
    pop ax
    pop dx
    mov word ptr ss:[bp+0x06], ax
    mov word ptr ss:[bp+0x08], dx
    xor si, si
    lret
text_draw_source: .long 0
text_draw_dy: .word 0
.endif
.ifdef cursor_hotkeys
# Cursor-mode hotkeys (re_104). The overlay hotkey dispatcher (overlay
# segment 25, file 71153) sends Space, A/a and S/s to a tag-FF87 redirect at
# file 711D0 (T's dead debug handler; T now shares A's animation toggle):
#     Space = walk (1), A = attack (4), S = look (2)    ; DGROUP:11B8
# The new mode is reached by calling the game's own right-click cycle
# 1587:01C7 (1 -> 4 -> 2 [-> 3] -> 1) until it matches, so every side
# effect, guard and cursor icon stays the game's. A call that leaves the
# mode unchanged means the game refused (combat turn, no map input): stop.
# Segments below are load-relative (file) values; runtime adds the load
# base, which is DS minus DGROUP's own load-relative segment 4356.
.equ CURSOR_MODE, 0x11B8
.equ ACTIVE_WINDOW, 0x11A4
.equ DGROUP_LOAD_SEGMENT, 0x4356
.equ RIGHT_CLICK_CYCLE_SEGMENT, 0x1587
.equ RIGHT_CLICK_CYCLE_OFFSET, 0x01C7
.equ MOUSE_POSITION_SEGMENT, 0x3118
.equ MOUSE_POSITION_OFFSET, 0x002E
.equ ICON_AT_POINTER_OFFSET, 0x29FA
.equ SET_CURSOR_ICON_SEGMENT, 0x4211
.equ SET_CURSOR_ICON_OFFSET, 0x0061
# Dispatcher IPs: its epilogue, and the original Space/1-4 handler.
.equ HOTKEY_DONE_IP, 0x1DD0
.equ HOTKEY_SPACE_IP, 0x150D
cursor_hotkey_entry:
    pop es
    pop cx
    pop dx
    mov ax, word ptr ss:[bp+0x12]
    mov bx, 1
    cmp ax, 0x3920
    je cursor_hotkey_space
    mov bx, 4
    cmp ax, 0x1E41
    je cursor_hotkey_map_only
    cmp ax, 0x1E61
    je cursor_hotkey_map_only
    mov bx, 2
    cmp ax, 0x1F53
    je cursor_hotkey_map_only
    cmp ax, 0x1F73
    je cursor_hotkey_map_only
    jmp cursor_hotkey_return
cursor_hotkey_space:
    # With a window open ([11A4] != 0: inventory, VIEW...) Space keeps its
    # original job there; on the map that handler did nothing.
    mov ax, word ptr [ACTIVE_WINDOW]
    or ax, word ptr [ACTIVE_WINDOW+2]
    jz cursor_hotkey_cycle
    mov cx, HOTKEY_SPACE_IP
    jmp cursor_hotkey_return
cursor_hotkey_map_only:
    mov ax, word ptr [ACTIVE_WINDOW]
    or ax, word ptr [ACTIVE_WINDOW+2]
    jnz cursor_hotkey_return
cursor_hotkey_cycle:
    push cx
    push dx
    push si
    push di
    push es
    mov word ptr cs:[cursor_hotkey_target], bx
    mov si, ds
    sub si, DGROUP_LOAD_SEGMENT
    mov di, 4
cursor_hotkey_step:
    mov ax, word ptr [CURSOR_MODE]
    cmp ax, word ptr cs:[cursor_hotkey_target]
    je cursor_hotkey_finish
    mov word ptr cs:[cursor_hotkey_previous], ax
    # get_mouse_position(&x, &y), in 320x200 screen pixels
    push cs
    push OFFSET cursor_hotkey_y
    push cs
    push OFFSET cursor_hotkey_x
    mov ax, si
    add ax, MOUSE_POSITION_SEGMENT
    mov word ptr cs:[cursor_hotkey_far+2], ax
    mov word ptr cs:[cursor_hotkey_far], MOUSE_POSITION_OFFSET
    .byte 0x2E, 0xFF, 0x1E
    .word cursor_hotkey_far
    add sp, 8
    # The cycle takes a 24-byte input event by value and only reads the
    # pointer position from it (event +0Ch x, +0Eh y) to pick the icon.
    push 0
    push 0
    push 0
    push 0
    push word ptr cs:[cursor_hotkey_y]
    push word ptr cs:[cursor_hotkey_x]
    push 0
    push 0
    push 0
    push 0
    push 0
    push 0
    mov ax, si
    add ax, RIGHT_CLICK_CYCLE_SEGMENT
    mov word ptr cs:[cursor_hotkey_far+2], ax
    mov word ptr cs:[cursor_hotkey_far], RIGHT_CLICK_CYCLE_OFFSET
    .byte 0x2E, 0xFF, 0x1E
    .word cursor_hotkey_far
    add sp, 0x18
    mov ax, word ptr [CURSOR_MODE]
    cmp ax, word ptr cs:[cursor_hotkey_previous]
    je cursor_hotkey_finish
    dec di
    jnz cursor_hotkey_step
cursor_hotkey_finish:
    # The cycle's attack -> look step hands an icon id (1777h) to the
    # mode-indexed icon setter 191F:0A99, which falls back to the hourglass
    # (177Ah); a right click never shows it because the next pointer move
    # redraws the icon. A key press has no pointer move, so set the look icon
    # the way the walk -> attack step sets its own: icon_at(x, y) (1587:29FA)
    # then set_cursor_icon(icon, 1) (4211:0061).
    cmp di, 4
    je cursor_hotkey_restore
    cmp word ptr [CURSOR_MODE], 2
    jne cursor_hotkey_restore
    push word ptr cs:[cursor_hotkey_y]
    push word ptr cs:[cursor_hotkey_x]
    mov ax, si
    add ax, RIGHT_CLICK_CYCLE_SEGMENT
    mov word ptr cs:[cursor_hotkey_far+2], ax
    mov word ptr cs:[cursor_hotkey_far], ICON_AT_POINTER_OFFSET
    .byte 0x2E, 0xFF, 0x1E
    .word cursor_hotkey_far
    add sp, 4
    push 1
    push ax
    mov ax, si
    add ax, SET_CURSOR_ICON_SEGMENT
    mov word ptr cs:[cursor_hotkey_far+2], ax
    mov word ptr cs:[cursor_hotkey_far], SET_CURSOR_ICON_OFFSET
    .byte 0x2E, 0xFF, 0x1E
    .word cursor_hotkey_far
    add sp, 4
cursor_hotkey_restore:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    # Never return into overlay 25 after calling the game: the cycle and
    # set_cursor_icon load overlays 15 and 26, which can evict or move the
    # dispatcher's overlay, and the saved CS:IP (DX:CX) sits outside any BP
    # frame, so the overlay manager cannot fix it up (v108 crashed now and
    # then on quick A/S/Space). Run the dispatcher's own epilogue at IP 1DD0
    # instead -- pop si ([bp-5Ch], saved after "sub sp,5Ah"); leave; retf --
    # which returns straight to its resident caller.
    mov si, word ptr ss:[bp-0x5C]
    mov sp, bp
    pop bp
    lret
cursor_hotkey_return:
    push dx
    push cx
    lret
cursor_hotkey_target: .word 0
cursor_hotkey_previous: .word 0
cursor_hotkey_x: .word 0
cursor_hotkey_y: .word 0
cursor_hotkey_far: .long 0
.endif
.ifdef smart_cursor
# Smart walk cursor (re_104 §9-§11). One tag-FF88 redirect at file 1B483
# (dead debug-only code in the left-click dispatcher 1587:06D8) serves three
# callers, told apart by CX:
#   * CX = BEF0h: the non-combat frame update. Its call at 1C9DE now goes
#     through "mov cx,BEF0h; jmp 1B483" at 1B4F5 (dead bytes); this entry
#     runs the arrival check and then tail-jumps to the original target
#     1587:1754 (1C3C4) with the caller's return address and argument still
#     on the stack.
#   * CX = BEEFh: the look path's "NO LINE OF SIGHT" / "TOO FAR AWAY"
#     branches; walk towards the clicked point (walk path 1B3CF).
#   * anything else: the walk (mode 1) entry of the left-click mode table,
#     frame BP of 1587:06D8 with the input event at [bp+6] (pointer x/y at
#     [bp+12h]/[bp+14h]). Outside combat a map object that is not a party
#     member (index >= 4) is looked at (look path 1B407) when it stands next
#     to the leader, otherwise walked to (original walk entry 1B396).
# A walk towards an object remembers it; once the walker's move order
# (3972:08AA + walker*13h) is back to 0 and the walker stands next to the
# object, the frame check runs the look path's own interaction (191F:0135,
# 41F9:004D, then set_mode_save(3) if something was picked up). Holding
# Ctrl (BIOS 0040:0017 bit 2) at the click only walks: no look next to the
# object, no look on arrival.
.equ SMART_WALK_TOWARDS_MAGIC, 0xBEEF
.equ SMART_FRAME_MAGIC, 0xBEF0
.equ SMART_WALK_ENTRY_IP, 0x0726
.equ SMART_WALK_PATH_IP, 0x075F
.equ SMART_LOOK_PATH_IP, 0x0797
.equ SMART_FRAME_UPDATE_IP, 0x1754
.equ SMART_DGROUP_LOAD_SEGMENT, 0x4356
.equ SMART_COMBAT_SEGMENT, 0x377E
.equ SMART_ORDER_SEGMENT, 0x3972
.equ SMART_LEADER, 0x4979
.equ SMART_LOOK_OBJECT, 0x496E
.equ SMART_MAP_INPUT, 0x0BC9
.equ SMART_CAMERA_X, 0x1178
.equ SMART_CAMERA_Y, 0x117A
.equ SMART_OBJECT_X, 0x6697
.equ SMART_OBJECT_Y, 0x6699
# Borland far functions: only SI, DI, BP and DS survive them.
.macro smart_far_call segment, offset
    mov ax, si
    add ax, \segment
    mov word ptr cs:[smart_click_far+2], ax
    mov word ptr cs:[smart_click_far], \offset
    .byte 0x2E, 0xFF, 0x1E
    .word smart_click_far
.endm
.macro smart_ctrl_test
    mov ax, 0x40
    mov es, ax
    test byte ptr es:[0x17], 4
.endm
smart_click_entry:
    pop es
    pop bx
    pop dx
    push dx
    push si
    push di
    mov si, ds
    sub si, SMART_DGROUP_LOAD_SEGMENT
    cmp cx, SMART_FRAME_MAGIC
    je smart_frame
    cmp cx, SMART_WALK_TOWARDS_MAGIC
    je smart_towards
    mov word ptr cs:[smart_pending], 0
    mov ax, si
    add ax, SMART_COMBAT_SEGMENT
    mov es, ax
    cmp word ptr es:[0x19], 0
    jne smart_walk
    smart_ctrl_test
    jnz smart_walk
    # find_object(camera x, camera y, pointer x, pointer y), as 1B32F does
    push word ptr ss:[bp+0x14]
    push word ptr ss:[bp+0x12]
    push word ptr [SMART_CAMERA_Y]
    push word ptr [SMART_CAMERA_X]
    smart_far_call 0x1DF3, 0x2822
    add sp, 8
    cmp ax, 4
    jl smart_walk
    mov di, ax
    # "Next to" is the attack icon's melee test (1D7E5):
    # distance(walker, object) = 1A0A:2BA5 <= 1.
    push di
    push word ptr [SMART_LEADER]
    smart_far_call 0x1A0A, 0x2BA5
    add sp, 4
    cmp ax, 1
    jle smart_look
    mov ax, word ptr [SMART_LEADER]
    mov word ptr cs:[smart_pending_walker], ax
    mov word ptr cs:[smart_pending_object], di
    mov word ptr cs:[smart_pending], 1
smart_walk:
    mov cx, SMART_WALK_ENTRY_IP
    jmp smart_exit
smart_look:
    mov cx, SMART_LOOK_PATH_IP
    jmp smart_exit
smart_towards:
    # The look path already stored its object in [496E].
    mov word ptr cs:[smart_pending], 0
    smart_ctrl_test
    jnz smart_towards_walk
    mov ax, word ptr [SMART_LEADER]
    mov word ptr cs:[smart_pending_walker], ax
    mov ax, word ptr [SMART_LOOK_OBJECT]
    mov word ptr cs:[smart_pending_object], ax
    mov word ptr cs:[smart_pending], 1
smart_towards_walk:
    mov cx, SMART_WALK_PATH_IP
    jmp smart_exit
smart_frame:
    cmp word ptr cs:[smart_pending], 0
    je smart_frame_done
    mov bx, word ptr cs:[smart_pending_walker]
    imul bx, bx, 0x13
    mov ax, si
    add ax, SMART_ORDER_SEGMENT
    mov es, ax
    cmp word ptr es:[bx+0x8AA], 0
    jne smart_frame_done
    mov word ptr cs:[smart_pending], 0
    cmp word ptr [SMART_MAP_INPUT], 1
    jne smart_frame_done
    mov di, word ptr cs:[smart_pending_object]
    push di
    push word ptr cs:[smart_pending_walker]
    smart_far_call 0x1A0A, 0x2BA5
    add sp, 4
    cmp ax, 1
    jg smart_frame_done
    # the look path's interaction, 1B4FB..1B53A
    smart_far_call 0x191F, 0x0135
    mov bx, di
    shl bx, 5
    mov ax, word ptr [bx+SMART_OBJECT_Y]
    sub ax, word ptr [SMART_CAMERA_Y]
    push ax
    mov ax, word ptr [bx+SMART_OBJECT_X]
    sub ax, word ptr [SMART_CAMERA_X]
    push ax
    push di
    smart_far_call 0x41F9, 0x004D
    add sp, 6
    smart_far_call 0x4281, 0x0043
    or ax, ax
    jz smart_frame_done
    push 3
    smart_far_call 0x1587, 0x28DC
    add sp, 2
smart_frame_done:
    mov cx, SMART_FRAME_UPDATE_IP
smart_exit:
    pop di
    pop si
    pop dx
    push dx
    push cx
    lret
smart_pending: .word 0
smart_pending_walker: .word 0
smart_pending_object: .word 0
smart_click_far: .long 0
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
    ability_text view_hp_label_id_0, view_hp_label_id_1
    ability_text view_psi_label_id_0, view_psi_label_id_1

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

# VIEW CHARACTER's own HP:/PSI: labels are separate literals from the item
# panel's (re_83's ac_label_entry/psi_label_entry above) -- different call
# site, different template shape (no extra ds:0x11A4 pointer afterwards,
# same trailing (color, 0x14, color, dword, 0) shape as gender/race/AC's
# view-screen draws) -- so they get their own tags and buffers rather than
# reusing the item-panel ones.
view_hp_buffer: .byte 0x25, 0x43, 0x25, 0x43, 0x25, 0x43, 0, 0, 0, 0
view_hp_label_entry:
    pop es
    pop cx
    pop dx
    push dx
    push cx
    mov ax, 0xFFF8
    push cs
    push OFFSET view_hp_decoded
    push es
    jmp name_cache_entry
view_hp_decoded:
    pop ax
    pop dx
    pop cx
    pop bx
    push si
    push di
    mov si, ax
    mov di, OFFSET view_hp_buffer + 6
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
    push OFFSET view_hp_buffer
    .byte 0x66, 0x68
    .long (VIEW_STAT_ROW_Y << 16) | 0x0095
    push bx
    push cx
    lret

view_psi_buffer: .byte 0x25, 0x43, 0x25, 0x43, 0x25, 0x43, 0, 0, 0, 0
view_psi_label_entry:
    pop es
    pop cx
    pop dx
    push dx
    push cx
    mov ax, 0xFFF9
    push cs
    push OFFSET view_psi_decoded
    push es
    jmp name_cache_entry
view_psi_decoded:
    pop ax
    pop dx
    pop cx
    pop bx
    push si
    push di
    mov si, ax
    mov di, OFFSET view_psi_buffer + 6
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
    push OFFSET view_psi_buffer
    .byte 0x66, 0x68
    .long (VIEW_STAT_ROW_Y << 16) | 0x00DE
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
.ifdef generated_ui_text
    ui_text_materials
.else
# Legacy cjk-mapping-v57 IDs (the v62-v75 line); the main build generates
# these from localization/catalog/fixed_ui_labels.csv instead.
material_0: .byte 0x5E, (367 / 94) + 0x21, (367 % 94) + 0x21, 0x5E, (691 / 94) + 0x21, (691 % 94) + 0x21, 0
material_1: .byte 0x5E, (849 / 94) + 0x21, (849 % 94) + 0x21, 0x5E, (691 / 94) + 0x21, (691 % 94) + 0x21, 0
material_2: .byte 0x5E, (544 / 94) + 0x21, (544 % 94) + 0x21, 0x5E, (691 / 94) + 0x21, (691 % 94) + 0x21, 0
material_3: .byte 0x5E, (871 / 94) + 0x21, (871 % 94) + 0x21, 0x5E, (544 / 94) + 0x21, (544 % 94) + 0x21, 0x5E, (691 / 94) + 0x21, (691 % 94) + 0x21, 0
material_4: .byte 0x5E, (762 / 94) + 0x21, (762 % 94) + 0x21, 0x5E, (222 / 94) + 0x21, (222 % 94) + 0x21, 0x5E, (691 / 94) + 0x21, (691 % 94) + 0x21, 0
material_5: .byte 0x5E, (528 / 94) + 0x21, (528 % 94) + 0x21, 0x5E, (691 / 94) + 0x21, (691 % 94) + 0x21, 0
.endif
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
# Alignment names are always exactly four characters (e.g. 混亂善良), one
# stride step wider than identity_text's two; padded to a 16-byte stride
# (shl ax,4) so the lookup stays a plain multiply like gender's.
.macro alignment_text first, second, third, fourth
    .byte 0x5E, (\first / 94) + 0x21, (\first % 94) + 0x21
    .byte 0x5E, (\second / 94) + 0x21, (\second % 94) + 0x21
    .byte 0x5E, (\third / 94) + 0x21, (\third % 94) + 0x21
    .byte 0x5E, (\fourth / 94) + 0x21, (\fourth % 94) + 0x21
    .byte 0, 0, 0, 0
.endm
.ifdef generated_ui_text
    ui_text_genders
.else
gender_sources:
    identity_text 512, 269
    identity_text 189, 269
.endif

race_offsets: .word race_0, race_1, race_2, race_3, race_4, race_5, race_6, race_7
.ifdef generated_ui_text
    ui_text_races
.else
race_0: .byte 0x5E, (27 / 94) + 0x21, (27 % 94) + 0x21, 0x5E, (838 / 94) + 0x21, (838 % 94) + 0x21, 0
race_1: .byte 0x5E, (543 / 94) + 0x21, (543 % 94) + 0x21, 0x5E, (27 / 94) + 0x21, (27 % 94) + 0x21, 0
race_2: .byte 0x5E, (586 / 94) + 0x21, (586 % 94) + 0x21, 0x5E, (822 / 94) + 0x21, (822 % 94) + 0x21, 0
race_3: .byte 0x5E, (106 / 94) + 0x21, (106 % 94) + 0x21, 0x5E, (586 / 94) + 0x21, (586 % 94) + 0x21, 0x5E, (822 / 94) + 0x21, (822 % 94) + 0x21, 0
race_4: .byte 0x5E, (106 / 94) + 0x21, (106 % 94) + 0x21, 0x5E, (227 / 94) + 0x21, (227 % 94) + 0x21, 0x5E, (27 / 94) + 0x21, (27 % 94) + 0x21, 0
race_5: .byte 0x5E, (106 / 94) + 0x21, (106 % 94) + 0x21, 0x5E, (724 / 94) + 0x21, (724 % 94) + 0x21, 0x5E, (27 / 94) + 0x21, (27 % 94) + 0x21, 0
race_6: .byte 0x5E, (1317 / 94) + 0x21, (1317 % 94) + 0x21, 0x5E, (484 / 94) + 0x21, (484 % 94) + 0x21, 0x5E, (27 / 94) + 0x21, (27 % 94) + 0x21, 0
race_7: .byte 0x5E, (1319 / 94) + 0x21, (1319 % 94) + 0x21, 0x5E, (1318 / 94) + 0x21, (1318 % 94) + 0x21, 0x5E, (289 / 94) + 0x21, (289 % 94) + 0x21, 0x5E, (1004 / 94) + 0x21, (1004 % 94) + 0x21, 0
.endif

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
    # v66 restores v64's short redirect shape: this build's parent EXE
    # (v64) only replaces the 22-byte string-pointer span (like race),
    # not the wider v65 span that also absorbed the position pushes --
    # v65's own gender-reposition candidate carries that wider EXE patch
    # separately. GENDER_Y/GENDER_X are unused now that gender shares
    # race's row again at its original, un-overridden position.
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

# Alignment (e.g. 混亂善良) is record+0x1A, 1-indexed 1-9 in row-major
# law/chaos-then-good/evil order (1=Lawful Good .. 5=True Neutral ..
# 9=Chaotic Evil), matching AD&D's classic 3x3 grid read row by row.
# Character IDs: 守198 序1321 善1320 良1323 中11 立1322 絕1168 對213
# 邪753 惡276 混453 亂18.
.ifdef generated_ui_text
    ui_text_alignments
.else
alignment_sources:
    alignment_text 198, 1321, 1320, 1323  # Lawful Good -> 守序善良
    alignment_text 198, 1321, 11, 1322    # Lawful Neutral -> 守序中立
    alignment_text 198, 1321, 753, 276    # Lawful Evil -> 守序邪惡
    alignment_text 11, 1322, 1320, 1323   # Neutral Good -> 中立善良
    alignment_text 1168, 213, 11, 1322    # True Neutral -> 絕對中立
    alignment_text 11, 1322, 753, 276     # Neutral Evil -> 中立邪惡
    alignment_text 453, 18, 1320, 1323    # Chaotic Good -> 混亂善良
    alignment_text 453, 18, 11, 1322      # Chaotic Neutral -> 混亂中立
    alignment_text 453, 18, 753, 276      # Chaotic Evil -> 混亂邪惡
.endif

alignment_label_entry:
    les bx, [bp + 0x0A]
    mov al, es:[bx + 0x1A]
    dec al
    cbw
    pop es
    pop cx
    pop dx
    push dx
    push cx
    add ax, 0xFFC0
    push cs
    push OFFSET alignment_decoded
    push es
    jmp name_cache_entry
alignment_decoded:
    # Alignment's own draw call has the exact same trailing-argument shape
    # as gender's (color escape, template id, position pair, then the
    # caller's own [bp+6] far pointer) right up to -- but not including --
    # the still-untouched far call itself, so this mirrors gender_decoded's
    # absorption span, moving alignment onto the equipment row in place of
    # where gender used to sit before it moved back down to share race's
    # row.
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
    push ALIGNMENT_Y
    push ALIGNMENT_X
    push dword ptr ss:[bp + 6]
    push bx
    push cx
    lret
.endif
.ifdef fixed_class_names
# VIEW CHARACTER's class-name draw (5B7C:2DC1 in the v67-era build, an
# overlay unit distinct from the one gender/race/alignment/HP:/PSI: live
# in) reads up to three 1-indexed class IDs directly from the identity
# record (record+0x21/+0x22/+0x23, confirmed live: GERAKIS=10 alone,
# K'RATCHEK=9/7/12 for its "Fighter/Druid/Psionic" display) and pushes a
# far pointer straight from an English string-pool lookup table --
# *no* NAME-slot decode in between, unlike every other identity field.
# Overwriting that table/pool in place (tried first, see re_90) draws
# raw Base94 escape bytes as literal garbage, because 339E:016D never
# runs them through decode_start. So each class slot's own
# "read record; look up table; push pointer" instruction span gets
# redirected here instead, exactly like every other field, just with
# its own record offset per slot.
class_offsets: .word class_cleric, class_cleric, class_cleric, class_cleric, class_druid, class_druid, class_druid, class_druid, class_fighter, class_gladiator, class_preserver, class_psionic, class_ranger, class_ranger, class_ranger, class_ranger, class_thief
.ifdef generated_ui_text
    ui_text_classes
.else
class_cleric: .byte 0x5E, (1325 / 94) + 0x21, (1325 % 94) + 0x21, 0x5E, (232 / 94) + 0x21, (232 % 94) + 0x21, 0
class_druid: .byte 0x5E, (261 / 94) + 0x21, (261 % 94) + 0x21, 0x5E, (1329 / 94) + 0x21, (1329 % 94) + 0x21, 0x5E, (36 / 94) + 0x21, (36 % 94) + 0x21, 0
class_fighter: .byte 0x5E, (289 / 94) + 0x21, (289 % 94) + 0x21, 0x5E, (1004 / 94) + 0x21, (1004 % 94) + 0x21, 0
class_gladiator: .byte 0x5E, (697 / 94) + 0x21, (697 % 94) + 0x21, 0x5E, (857 / 94) + 0x21, (857 % 94) + 0x21, 0x5E, (1004 / 94) + 0x21, (1004 % 94) + 0x21, 0
class_preserver: .byte 0x5E, (51 / 94) + 0x21, (51 % 94) + 0x21, 0x5E, (709 / 94) + 0x21, (709 % 94) + 0x21, 0x5E, (617 / 94) + 0x21, (617 % 94) + 0x21, 0
class_psionic: .byte 0x5E, (822 / 94) + 0x21, (822 % 94) + 0x21, 0x5E, (629 / 94) + 0x21, (629 % 94) + 0x21, 0x5E, (232 / 94) + 0x21, (232 % 94) + 0x21, 0
class_ranger: .byte 0x5E, (1240 / 94) + 0x21, (1240 % 94) + 0x21, 0x5E, (1324 / 94) + 0x21, (1324 % 94) + 0x21, 0
class_thief: .byte 0x5E, (1326 / 94) + 0x21, (1326 % 94) + 0x21, 0x5E, (1328 / 94) + 0x21, (1328 % 94) + 0x21, 0
.endif

# re_94: the 2-/3-class draw paths (5B7C:2DC1) collect every populated
# slot's far pointer and only call the shared 339E:016D renderer once,
# after ALL slots have decoded -- confirmed by live disassembly this
# session (the three-class path pushes all three pointers back-to-back,
# THEN does a single `call 339E:016D`; the two-class path is identical
# with two pointers). Decode order is always slot3 (if present), then
# slot2 (if present), then slot1 last, in both the two- and three-class
# paths -- also confirmed live. Two things break if a slot's decode is
# treated in isolation like every other identity field:
#   1. `name_buffer` is one shared 25-byte scratch buffer, so a later
#      slot's decode overwrites an earlier slot's still-unread string
#      bytes before the combined draw call ever reads them.
#   2. The 7 physical glyph slots are a shared, reused-per-decode pool
#      (`decode_start` used to reset `slot_count` to 0 on every call), so
#      a later slot's decode can evict the physical bitmap data an
#      earlier slot's transport-code characters still point to.
# The fix is two independent pieces, one per problem:
#   1. slot2/slot3 each copy their decoded string out to a private
#      buffer (class_slot2_buffer/class_slot3_buffer) instead of handing
#      back a pointer into the shared name_buffer. slot1 is always last,
#      so nothing decodes after it before the draw call reads its
#      pointer -- it can keep using name_buffer directly.
#   2. `class_skip_reset` (declared next to slot_count/active_slot) lets
#      a slot ask the *next* decode_start call to keep accumulating into
#      the same physical slot pool instead of resetting it. Each label
#      entry decides this from the character record itself rather than
#      from any saved history, so it can never go stale: slot3 is always
#      first when it fires, so it always forces a normal reset; slot2/
#      slot1 each check whether a slot that decodes *before* them (slot3
#      for slot2; slot2 or slot3 for slot1) is populated in this same
#      record, and only then ask to skip the reset. A truly single-class
#      character never sets the flag at all, so class_slot1_label_entry
#      behaves exactly as before in that case.
class_slot1_label_entry:
.ifdef CLASS_ROW_FROM
    # Slot 1 decodes exactly once per class-name draw, always before the
    # formatter call reads the row from the caller's [bp+0x10] argument.
    cmp word ptr ss:[bp + 0x10], CLASS_ROW_FROM
    jne class_row_ready
    mov word ptr ss:[bp + 0x10], CLASS_ROW_TO
class_row_ready:
.endif
    les bx, [bp + 0x0A]
    mov al, es:[bx + 0x21]
    dec al
    cbw
    push ax
    mov al, es:[bx + 0x22]
    mov cl, es:[bx + 0x23]
    or al, cl
    jz class_slot1_is_first
    mov byte ptr cs:[class_skip_reset], 1
    jmp class_slot1_check_done
class_slot1_is_first:
    mov byte ptr cs:[class_skip_reset], 0
class_slot1_check_done:
    pop ax
    pop es
    pop cx
    pop dx
    push dx
    push cx
    add ax, 0xFFA0
    push cs
    push OFFSET class_decoded
    push es
    jmp name_cache_entry
class_slot2_label_entry:
    les bx, [bp + 0x0A]
    mov al, es:[bx + 0x22]
    dec al
    cbw
    push ax
    mov al, es:[bx + 0x23]
    or al, al
    jz class_slot2_is_first
    mov byte ptr cs:[class_skip_reset], 1
    jmp class_slot2_check_done
class_slot2_is_first:
    mov byte ptr cs:[class_skip_reset], 0
class_slot2_check_done:
    pop ax
    pop es
    pop cx
    pop dx
    push dx
    push cx
    add ax, 0xFFA0
    push cs
    push OFFSET class_slot2_decoded
    push es
    jmp name_cache_entry
class_slot3_label_entry:
    # The three-class caller computed slot3's class colour into DX just
    # before this redirected span and pushes DX right after it (0x72C37),
    # but the shared decoder returns its pointer in DX:AX. Keep the caller's
    # DX so the third class name is not drawn in whatever palette index the
    # FONT segment's low byte happens to be (re_102).
    mov cs:[class3_saved_dx], dx
    les bx, [bp + 0x0A]
    mov al, es:[bx + 0x23]
    dec al
    cbw
    # slot3 (when its record field is populated at all) always decodes
    # before slot2/slot1 in both the two- and three-class draw paths, so
    # it never needs to check for an earlier sibling -- it always forces
    # a normal, full slot-pool reset.
    mov byte ptr cs:[class_skip_reset], 0
    pop es
    pop cx
    pop dx
    push dx
    push cx
    add ax, 0xFFA0
    push cs
    push OFFSET class_slot3_decoded
    push es
    jmp name_cache_entry
class_decoded:
    # Each redirect only replaces the "read record; look up table; push
    # far pointer" span and nothing else -- the surrounding color/
    # position/template pushes are untouched, original code the redirect
    # simply resumes into -- so all that's needed here is to hand back
    # the decoded string pointer in the same dx:ax shape the original
    # "push dword [bx+si]" would have left on the stack. Used by slot1
    # only (always last-decoded, so name_buffer is still valid when the
    # combined draw call reads this pointer).
    pop ax
    pop dx
    pop cx
    pop bx
    push dx
    push ax
    push bx
    push cx
    lret
class_slot2_buffer: .space 25, 0
class_slot2_decoded:
    pop ax
    pop dx
    pop cx
    pop bx
    push si
    push di
    mov si, ax
    mov di, OFFSET class_slot2_buffer
class_slot2_copy:
    mov al, byte ptr cs:[si]
    test al, al
    jz class_slot2_copy_done
    cmp di, OFFSET class_slot2_buffer + 24
    jae class_slot2_copy_done
    mov byte ptr cs:[di], al
    inc si
    inc di
    jmp class_slot2_copy
class_slot2_copy_done:
    mov byte ptr cs:[di], 0
    pop di
    pop si
    mov ax, OFFSET class_slot2_buffer
    push dx
    push ax
    push bx
    push cx
    lret
class_slot3_buffer: .space 25, 0
class_slot3_decoded:
    pop ax
    pop dx
    pop cx
    pop bx
    push si
    push di
    mov si, ax
    mov di, OFFSET class_slot3_buffer
class_slot3_copy:
    mov al, byte ptr cs:[si]
    test al, al
    jz class_slot3_copy_done
    cmp di, OFFSET class_slot3_buffer + 24
    jae class_slot3_copy_done
    mov byte ptr cs:[di], al
    inc si
    inc di
    jmp class_slot3_copy
class_slot3_copy_done:
    mov byte ptr cs:[di], 0
    pop di
    pop si
    mov ax, OFFSET class_slot3_buffer
    push dx
    push ax
    push bx
    push cx
    mov dx, cs:[class3_saved_dx]
    lret
class3_saved_dx: .word 0
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
