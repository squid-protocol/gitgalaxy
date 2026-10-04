/*
 * ggdisplay.c -- DISPLAY as IBM Enterprise COBOL writes it, for the equivalence harness's SYSOUT comparison (#4056).
 *
 * Preloaded (LD_PRELOAD) into a GnuCOBOL program, it stands in front of libcob's cob_display. GnuCOBOL and IBM
 * write the same text for alphanumeric, group, edited and unsigned or SIGN SEPARATE numeric items, but not for
 * these two (IBM Enterprise COBOL Language Reference, DISPLAY statement: an operand is written as its external
 * representation; a binary or packed operand is first converted to external decimal):
 *
 *   - a signed zoned item, sign embedded (PIC S9(3) VALUE -12): IBM writes its bytes, the sign overpunched in the
 *     digit ("01K"); GnuCOBOL writes the digits and a separate sign ("012-").
 *   - a binary or packed item (PIC S9(4) COMP VALUE -7): IBM writes it as zoned decimal of the item's PICTURE
 *     digits, the sign overpunched if the item is signed ("000P"); GnuCOBOL writes "-00007".
 *
 * So each such operand is replaced by its IBM text before libcob writes the line: the zoned item's own bytes, or
 * the binary/packed value MOVEd into a zoned item of the same digits, scale and signedness (the program is
 * compiled -fsign=EBCDIC, so the overpunch is the EBCDIC one: { A-I positive, } J-R negative). Everything else
 * passes through unchanged. An operand this model does not cover (floating point, more than MAX_OPERANDS
 * operands) is written as is, and a line GGDISPLAY-NOT-MODELLED is written after it: the harness then does not
 * compare SYSOUT for that run and says so -- it never compares GnuCOBOL's text as if it were IBM's.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdarg.h>
#include <stdio.h>
#include <libcob.h>

#define MAX_OPERANDS 32
#define MAX_DIGITS 38

typedef void (*display_fn)(const int, const int, const int, ...);

static const cob_field_attr ALNUM = {COB_TYPE_ALPHANUMERIC, 0, 0, 0, NULL};

void cob_display(const int to_device, const int newline, const int varcnt, ...) {
    static display_fn real = NULL;
    if (real == NULL) {
        real = (display_fn)dlsym(RTLD_NEXT, "cob_display");
    }
    cob_field *in[MAX_OPERANDS] = {0};
    cob_field text[MAX_OPERANDS];
    cob_field zoned[MAX_OPERANDS];
    cob_field_attr zoned_attr[MAX_OPERANDS];
    unsigned char digits[MAX_OPERANDS][MAX_DIGITS];
    int modelled = varcnt <= MAX_OPERANDS;
    va_list ap;
    va_start(ap, varcnt);
    for (int i = 0; i < varcnt && i < MAX_OPERANDS; i++) {
        in[i] = va_arg(ap, cob_field *);
    }
    va_end(ap);
    for (int i = 0; i < varcnt && i < MAX_OPERANDS; i++) {
        cob_field *f = in[i];
        unsigned short type = f->attr->type;
        unsigned short flags = f->attr->flags;
        if (type == COB_TYPE_NUMERIC_DISPLAY && (flags & COB_FLAG_HAVE_SIGN) && !(flags & COB_FLAG_SIGN_SEPARATE)) {
            text[i].size = f->size; /* its own bytes: the overpunched digit is the sign */
            text[i].data = f->data;
            text[i].attr = &ALNUM;
            in[i] = &text[i];
        } else if (type == COB_TYPE_NUMERIC_BINARY || type == COB_TYPE_NUMERIC_PACKED) {
            unsigned short n = f->attr->digits;
            if (n == 0 || n > MAX_DIGITS) {
                modelled = 0;
                continue;
            }
            zoned_attr[i].type = COB_TYPE_NUMERIC_DISPLAY;
            zoned_attr[i].digits = n;
            zoned_attr[i].scale = f->attr->scale;
            zoned_attr[i].flags = flags & COB_FLAG_HAVE_SIGN; /* trailing, embedded: the external decimal */
            zoned_attr[i].pic = NULL;
            zoned[i].size = n;
            zoned[i].data = digits[i];
            zoned[i].attr = &zoned_attr[i];
            cob_move(f, &zoned[i]);
            text[i].size = n;
            text[i].data = digits[i];
            text[i].attr = &ALNUM;
            in[i] = &text[i];
        } else if (type == COB_TYPE_NUMERIC_FLOAT || type == COB_TYPE_NUMERIC_DOUBLE
                   || type == COB_TYPE_NUMERIC_L_DOUBLE || type == COB_TYPE_NUMERIC_FP_BIN32
                   || type == COB_TYPE_NUMERIC_FP_BIN64 || type == COB_TYPE_NUMERIC_FP_BIN128
                   || type == COB_TYPE_NUMERIC_FP_DEC64 || type == COB_TYPE_NUMERIC_FP_DEC128) {
            modelled = 0;
        }
    }
    real(to_device, newline, varcnt < MAX_OPERANDS ? varcnt : MAX_OPERANDS, in[0], in[1], in[2], in[3], in[4],
         in[5], in[6], in[7], in[8], in[9], in[10], in[11], in[12], in[13], in[14], in[15], in[16], in[17], in[18],
         in[19], in[20], in[21], in[22], in[23], in[24], in[25], in[26], in[27], in[28], in[29], in[30], in[31]);
    if (!modelled) {
        fflush(stdout);
        fputs("GGDISPLAY-NOT-MODELLED\n", stdout);
        fflush(stdout);
    }
}
