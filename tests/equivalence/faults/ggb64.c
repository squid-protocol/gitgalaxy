/*
 * ggb64.c -- the equivalence harness's stand-in that computes EPSMPMT's payment formula in IEEE 754 binary64
 * (owner ruling 2026-10-27, #5867; register C6). GnuCOBOL evaluates a COMPUTE with a float operand through
 * decimals and loses about 1e-6 relative inside the larger expression, so equivalence_binary64.py lowers the two
 * statements the ruling names into CALLs of these routines. The det port computes the same statements in Java double
 * (gen.py ieee_num): each operand the nearest double, each operation one double operation, the result stored into the
 * fixed-point receiver truncated. It is an owner-stated assumption, not a z/OS calibration.
 *
 * The interest rate is NOT read from WS-CALC-INTEREST: GnuCOBOL holds a COMP-1 as IEEE binary32, which differs from
 * the short HFP z/OS (and the port) hold by up to 2**-21 relative, and 360 months of it is cents. The stub rebuilds
 * the rate from the quoted rate the way the port does (det/hfp.py): (rate / 100) / 12 in long HFP, each step cut to
 * 14 hex digits, then LOAD ROUNDED to 6 (equivalence_binary64.py checks the program's COMPUTE is that expression).
 *
 * Operand layouts are the ones -std=ibm gives (binary-size 1-2-4-8, big-endian, truncation on):
 *   GGB64PAY(principal S9(9)V99 COMP, quoted rate S9(2)V9(3) COMP, months 9(9)V99 COMP, payment S9(7)V99 COMP)   -- line 125
 *   GGB64ANN(loan 9(9)V99, interest 9(9)V9999, periods 999, payment 9(9)V99), unsigned DISPLAY    -- line 144
 */
#pragma GCC optimize("fp-contract=off")
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

static int64_t be(const unsigned char *p, int n, int is_signed) {
    uint64_t v = 0;
    for (int i = 0; i < n; i++) v = (v << 8) | p[i];
    if (is_signed && (p[0] & 0x80) && n < 8) return (int64_t)v - ((int64_t)1 << (8 * n));
    return (int64_t)v;
}

static void put_be(unsigned char *p, int n, int64_t v) {
    uint64_t u = (uint64_t)v;
    for (int i = n - 1; i >= 0; i--) {
        p[i] = (unsigned char)(u & 0xFF);
        u >>= 8;
    }
}

static int64_t digits(const unsigned char *p, int n) {
    int64_t v = 0;
    for (int i = 0; i < n; i++) v = v * 10 + (p[i] - '0');
    return v;
}

static void put_digits(unsigned char *p, int n, int64_t v) {
    for (int i = n - 1; i >= 0; i--) {
        p[i] = (unsigned char)('0' + v % 10);
        v /= 10;
    }
}

/* a long HFP value m * 16**sh (m a 14-hex-digit mantissa) from num / den * 16**sh0, cut as the port's chop cuts it */
typedef unsigned __int128 u128;
typedef struct { u128 m; int sh; } hfp_t;
#define HFP13 ((u128)1 << 52) /* 16**13 */

static hfp_t hfp_div(u128 m, int sh, unsigned long den) {
    int t = 0;
    while (((m << (4 * t)) / den) < HFP13) t++;
    hfp_t r = { (m << (4 * t)) / den, sh - t };
    return r;
}

/* the short HFP rate (rate / 100) / 12 as a double; `quoted` is thousandths of a percent */
static double hfp_rate(int64_t quoted) {
    if (quoted == 0) return 0.0;
    u128 q = (u128)(quoted < 0 ? -quoted : quoted);
    hfp_t a = hfp_div(q, 0, 1000), b = hfp_div(a.m, a.sh, 100), c = hfp_div(b.m, b.sh, 12);
    u128 f = (c.m + ((u128)1 << 31)) >> 32; /* long to short, half up at the first discarded bit */
    int sh = c.sh + 8;
    if (f == ((u128)1 << 24)) { f = (u128)1 << 20; sh++; }
    double r = ldexp((double)(uint64_t)f, 4 * sh);
    return quoted < 0 ? -r : r;
}

#ifdef GGB64_TEST
double ggb64_rate(int64_t quoted) { return hfp_rate(quoted); }
#endif

/* IBM's ANNUITY (6.4 Language Reference): r / (1 - (1 + r) ** -n), or 1 / n when r is 0 */
static double annuity(double r, double n) {
    if (r == 0) return 1 / n;
    return r / (1 - (double)powl((long double)(1 + r), (long double)(-n)));
}

/* the value stored as COBOL stores an arithmetic result: truncated to `scale` decimals (d * 10^scale is exact in a
 * long double: 53 + 7 bits), refused where a double has no value (a NaN, an infinity) or no int64 */
static int64_t scaled(double d, int scale) {
    long double t = (long double)d * (scale == 2 ? 100.0L : 10000.0L);
    if (!isfinite(d) || fabsl(t) >= 9.0e18L) {
        fprintf(stderr, "GGB64: the binary64 result %g has no fixed-point value\n", d);
        fflush(NULL);
        exit(1);
    }
    return (int64_t)truncl(t);
}

int GGB64PAY(unsigned char *principal, unsigned char *quoted, unsigned char *months, unsigned char *payment) {
    double p = (double)be(principal, 8, 1) / 100.0;
    double c = hfp_rate(be(quoted, 4, 1));
    double n = (double)be(months, 8, 0) / 100.0;
    double pw = (double)powl((long double)(1 + c), (long double)n);
    double v = p * (c * pw) / (pw - 1);
    int64_t cents = scaled(v, 2) % 1000000000; /* S9(7)V99: the high-order digits go, as the store does */
    put_be(payment, 4, cents);
    return 0; /* RETURN-CODE is the callee's return value to cobc */
}

int GGB64ANN(unsigned char *loan, unsigned char *interest, unsigned char *periods, unsigned char *payment) {
    double l = (double)digits(loan, 11) / 100.0;
    double i = (double)digits(interest, 13) / 10000.0;
    double n = (double)digits(periods, 3);
    double v = l * annuity(i / 12, n);
    int64_t cents = scaled(v, 2) % 100000000000LL;
    put_digits(payment, 11, cents < 0 ? -cents : cents);
    return 0;
}
