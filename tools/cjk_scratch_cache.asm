.intel_syntax noprefix
.code16
.section .text
.global cjk_cache_start

.ifndef scratch_offset
.equ scratch_offset, 0x3640
.endif
.ifndef cjk_record_bytes
.equ cjk_record_bytes, 242
.endif
.ifndef bank_count
.equ bank_count, 4
.endif

.equ current_bank,  0x53B6
.equ handle,        0x53B8
.equ saved_id,      0x53BA
.equ saved_game_ds, 0x53BC
.equ dir_entry,     0x53C0
.equ bank_names,    0x53F6

# Beyond 8 banks the inline table above no longer fits between bank_names
# and the resolver stub at COMMON. The filenames and their offset table
# then live instead in segment 147D's verified-dead padding (see
# tools/patch_dialogue_menu_wind.py's CHOICE_RESTORE_CAVE for how that dead
# span was confirmed: no far pointer or CS-relative reference in the whole
# module touches 147D:000F..0163 other than the one unrelated function at
# 147D:0166). bank_names_cave_table sits well clear of both that function
# and the separate dialogue choice-repair hook, which only occupies up to
# 147D:00FB.
.equ bank_names_cave_segment, 0x147D
.equ bank_names_cave_table,   0x0110

# AX=CJK ID. Read one CJB1 record directly into FONT scratch.
#
# Do not retain an open bank handle here.  Bytes at 0x5534 and above are a
# runtime work area (the spell UI overwrites them), so the complete routine
# must remain below that boundary.  Opening and closing one bank per glyph is
# both smaller than the old bank-switch helper and immune to stale handles.
cjk_cache_start:
    mov cs:[saved_id], ax
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
    jae cache_error
    xor ah, ah
    mov bx, ax
    shl bx, 1
.if bank_count > 8
    # Segment word patched to 0x147D and marked in the MZ relocation table
    # by patches(); the loader adds the same load bias it already applies
    # to every other far reference in this module. DS is left pointing at
    # this segment afterward: the seek below only uses cs:-prefixed and
    # register operands, and the dir_entry read further down saves and
    # restores DS around itself independently, so nothing here needs DS
    # put back first -- that saves the one byte this branch would otherwise
    # cost over the inline table below, keeping the resident cache inside
    # its fixed 0x5534 boundary.
    push bank_names_cave_segment
    pop ds
    mov dx, [bank_names_cave_table+bx]
    mov ax, 0x3D00
    int 0x21
.else
    push ds
    push cs
    pop ds
    mov dx, cs:[bank_names+bx]
    mov ax, 0x3D00
    int 0x21
    pop ds
.endif
    jc cache_error
    mov cs:[handle], ax

    mov ax, cs:[saved_id]
    xor ah, ah
    mov dx, ax
    shl dx, 2
    add dx, 16
    xor cx, cx
    mov bx, cs:[handle]
    mov ax, 0x4200
    int 0x21
    jc cache_close_error

    push ds
    push cs
    pop ds
    mov dx, dir_entry
    mov cx, 4
    mov bx, cs:[handle]
    mov ah, 0x3F
    int 0x21
    pop ds
    jc cache_close_error
    cmp ax, 4
    jne cache_close_error
    mov ax, cs:[saved_id]
    xor ah, ah
    cmp cs:[dir_entry], ax
    jne cache_close_error

    mov dx, cs:[dir_entry+2]
    xor cx, cx
    mov bx, cs:[handle]
    mov ax, 0x4200
    int 0x21
    jc cache_close_error

    mov ax, cs:[saved_game_ds]
    mov ds, ax
    les di, [0xA378]
    mov word ptr es:[di+0x0206], scratch_offset
    add di, scratch_offset
    mov ax, es
    mov ds, ax
    mov dx, di
    mov cx, cjk_record_bytes
    mov bx, cs:[handle]
    mov ah, 0x3F
    int 0x21
    jc cache_close_error
    cmp ax, cjk_record_bytes
    jne cache_close_error
    mov dx, 0x017F
    jmp cache_close

cache_close_error:
    mov dx, 0x013F
cache_close:
    mov bx, cs:[handle]
    mov ah, 0x3E
    int 0x21
    mov ax, dx
    jmp cache_return

cache_error:
    mov ax, 0x013F
cache_return:
    pop es
    pop ds
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret
