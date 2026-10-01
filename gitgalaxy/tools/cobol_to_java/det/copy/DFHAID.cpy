      * #3754: stand-in for the CICS attention-identifier (AID)
      * constants. Each key has a distinct value; the harness driver
      * sets EIBAID from these same names.
       01  DFHAID.
           02 DFHNULL  PIC X VALUE X'00'.
           02 DFHENTER PIC X VALUE ''''.
           02 DFHCLEAR PIC X VALUE '_'.
           02 DFHCLRP  PIC X VALUE X'6A'.
           02 DFHPEN   PIC X VALUE '='.
           02 DFHOPID  PIC X VALUE 'W'.
           02 DFHMSRE  PIC X VALUE 'X'.
           02 DFHSTRF  PIC X VALUE 'h'.
           02 DFHTRIG  PIC X VALUE '"'.
           02 DFHPA1   PIC X VALUE '%'.
           02 DFHPA2   PIC X VALUE '>'.
           02 DFHPA3   PIC X VALUE ','.
           02 DFHPF1   PIC X VALUE '1'.
           02 DFHPF2   PIC X VALUE '2'.
           02 DFHPF3   PIC X VALUE '3'.
           02 DFHPF4   PIC X VALUE '4'.
           02 DFHPF5   PIC X VALUE '5'.
           02 DFHPF6   PIC X VALUE '6'.
           02 DFHPF7   PIC X VALUE '7'.
           02 DFHPF8   PIC X VALUE '8'.
           02 DFHPF9   PIC X VALUE '9'.
           02 DFHPF10  PIC X VALUE ':'.
           02 DFHPF11  PIC X VALUE '#'.
           02 DFHPF12  PIC X VALUE '@'.
           02 DFHPF13  PIC X VALUE 'A'.
           02 DFHPF14  PIC X VALUE 'B'.
           02 DFHPF15  PIC X VALUE 'C'.
           02 DFHPF16  PIC X VALUE 'D'.
           02 DFHPF17  PIC X VALUE 'E'.
           02 DFHPF18  PIC X VALUE 'F'.
           02 DFHPF19  PIC X VALUE 'G'.
           02 DFHPF20  PIC X VALUE 'H'.
           02 DFHPF21  PIC X VALUE 'I'.
           02 DFHPF22  PIC X VALUE '['.
           02 DFHPF23  PIC X VALUE '.'.
           02 DFHPF24  PIC X VALUE '<'.
