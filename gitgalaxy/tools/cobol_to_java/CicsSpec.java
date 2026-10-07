// generated from gitgalaxy/standards/cics by `python -m gitgalaxy.standards.cics regen`; do not edit
package __PACKAGE__.cics;

/** The CICS command spec's tables (gitgalaxy/standards/cics): RESP values and the default abend codes. */
public final class CicsSpec {
    private CicsSpec() {
    }

    /** The condition name of a RESP value (IBM CICS TS, RESP values: DFHRESP; never an alias), null for a number
     *  DFHRESP has no name for. */
    public static String name(int resp) {
        return switch (resp) {
            case 0 -> "NORMAL";
            case 1 -> "ERROR";
            case 2 -> "RDATT";
            case 3 -> "WRBRK";
            case 4 -> "EOF";
            case 5 -> "EODS";
            case 6 -> "EOC";
            case 7 -> "INBFMH";
            case 8 -> "ENDINPT";
            case 9 -> "NONVAL";
            case 10 -> "NOSTART";
            case 11 -> "TERMIDERR";
            case 12 -> "FILENOTFOUND";
            case 13 -> "NOTFND";
            case 14 -> "DUPREC";
            case 15 -> "DUPKEY";
            case 16 -> "INVREQ";
            case 17 -> "IOERR";
            case 18 -> "NOSPACE";
            case 19 -> "NOTOPEN";
            case 20 -> "ENDFILE";
            case 21 -> "ILLOGIC";
            case 22 -> "LENGERR";
            case 23 -> "QZERO";
            case 24 -> "SIGNAL";
            case 25 -> "QBUSY";
            case 26 -> "ITEMERR";
            case 27 -> "PGMIDERR";
            case 28 -> "TRANSIDERR";
            case 29 -> "ENDDATA";
            case 30 -> "INVTSREQ";
            case 31 -> "EXPIRED";
            case 32 -> "RETPAGE";
            case 33 -> "RTEFAIL";
            case 34 -> "RTESOME";
            case 35 -> "TSIOERR";
            case 36 -> "MAPFAIL";
            case 37 -> "INVERRTERM";
            case 38 -> "INVMPSZ";
            case 39 -> "IGREQID";
            case 40 -> "OVERFLOW";
            case 41 -> "INVLDC";
            case 42 -> "NOSTG";
            case 43 -> "JIDERR";
            case 44 -> "QIDERR";
            case 45 -> "NOJBUFSP";
            case 46 -> "DSSTAT";
            case 47 -> "SELNERR";
            case 48 -> "FUNCERR";
            case 49 -> "UNEXPIN";
            case 50 -> "NOPASSBKRD";
            case 51 -> "NOPASSBKWR";
            case 53 -> "SYSIDERR";
            case 54 -> "ISCINVREQ";
            case 55 -> "ENQBUSY";
            case 56 -> "ENVDEFERR";
            case 57 -> "IGREQCD";
            case 58 -> "SESSIONERR";
            case 59 -> "SYSBUSY";
            case 60 -> "SESSBUSY";
            case 61 -> "NOTALLOC";
            case 62 -> "CBIDERR";
            case 63 -> "INVEXITREQ";
            case 64 -> "INVPARTNSET";
            case 65 -> "INVPARTN";
            case 66 -> "PARTNFAIL";
            case 69 -> "USERIDERR";
            case 70 -> "NOTAUTH";
            case 71 -> "VOLIDERR";
            case 72 -> "SUPPRESSED";
            case 75 -> "RESIDERR";
            case 80 -> "NOSPOOL";
            case 81 -> "TERMERR";
            case 82 -> "ROLLEDBACK";
            case 83 -> "END";
            case 84 -> "DISABLED";
            case 85 -> "ALLOCERR";
            case 86 -> "STRELERR";
            case 87 -> "OPENERR";
            case 88 -> "SPOLBUSY";
            case 89 -> "SPOLERR";
            case 90 -> "NODEIDERR";
            case 91 -> "TASKIDERR";
            case 92 -> "TCIDERR";
            case 93 -> "DSNNOTFOUND";
            case 94 -> "LOADING";
            case 95 -> "MODELIDERR";
            case 96 -> "OUTDESCRERR";
            case 97 -> "PARTNERIDERR";
            case 98 -> "PROFILEIDERR";
            case 99 -> "NETNAMEIDERR";
            case 100 -> "LOCKED";
            case 101 -> "RECORDBUSY";
            case 102 -> "UOWNOTFOUND";
            case 103 -> "UOWLNOTFOUND";
            case 110 -> "CONTAINERERR";
            case 122 -> "CHANNELERR";
            case 123 -> "CCSIDERR";
            case 124 -> "TIMEDOUT";
            case 125 -> "CODEPAGEERR";
            case 126 -> "INCOMPLETE";
            case 127 -> "APPNOTFOUND";
            case 128 -> "BUSY";
            default -> null;
        };
    }

    /** The condition a RESP value names; "RESP" + the number for one DFHRESP has no name for. */
    public static String condition(int resp) {
        String name = name(resp);
        return name != null ? name : "RESP" + resp;
    }

    /** The RESP value of a condition (an alias too: DSIDERR is FILENOTFOUND's number). */
    public static int resp(String condition) {
        return switch (condition) {
            case "NORMAL" -> 0;
            case "ERROR" -> 1;
            case "RDATT" -> 2;
            case "WRBRK" -> 3;
            case "EOF" -> 4;
            case "EODS" -> 5;
            case "EOC" -> 6;
            case "INBFMH" -> 7;
            case "ENDINPT" -> 8;
            case "NONVAL" -> 9;
            case "NOSTART" -> 10;
            case "TERMIDERR" -> 11;
            case "FILENOTFOUND" -> 12;
            case "DSIDERR" -> 12;
            case "NOTFND" -> 13;
            case "DUPREC" -> 14;
            case "DUPKEY" -> 15;
            case "INVREQ" -> 16;
            case "IOERR" -> 17;
            case "NOSPACE" -> 18;
            case "NOTOPEN" -> 19;
            case "ENDFILE" -> 20;
            case "ILLOGIC" -> 21;
            case "LENGERR" -> 22;
            case "QZERO" -> 23;
            case "SIGNAL" -> 24;
            case "QBUSY" -> 25;
            case "ITEMERR" -> 26;
            case "PGMIDERR" -> 27;
            case "TRANSIDERR" -> 28;
            case "ENDDATA" -> 29;
            case "INVTSREQ" -> 30;
            case "EXPIRED" -> 31;
            case "RETPAGE" -> 32;
            case "RTEFAIL" -> 33;
            case "RTESOME" -> 34;
            case "TSIOERR" -> 35;
            case "MAPFAIL" -> 36;
            case "INVERRTERM" -> 37;
            case "INVMPSZ" -> 38;
            case "IGREQID" -> 39;
            case "OVERFLOW" -> 40;
            case "INVLDC" -> 41;
            case "NOSTG" -> 42;
            case "JIDERR" -> 43;
            case "QIDERR" -> 44;
            case "NOJBUFSP" -> 45;
            case "DSSTAT" -> 46;
            case "SELNERR" -> 47;
            case "FUNCERR" -> 48;
            case "UNEXPIN" -> 49;
            case "NOPASSBKRD" -> 50;
            case "NOPASSBKWR" -> 51;
            case "SYSIDERR" -> 53;
            case "ISCINVREQ" -> 54;
            case "ENQBUSY" -> 55;
            case "ENVDEFERR" -> 56;
            case "IGREQCD" -> 57;
            case "SESSIONERR" -> 58;
            case "SYSBUSY" -> 59;
            case "SESSBUSY" -> 60;
            case "NOTALLOC" -> 61;
            case "CBIDERR" -> 62;
            case "INVEXITREQ" -> 63;
            case "INVPARTNSET" -> 64;
            case "INVPARTN" -> 65;
            case "PARTNFAIL" -> 66;
            case "USERIDERR" -> 69;
            case "NOTAUTH" -> 70;
            case "VOLIDERR" -> 71;
            case "SUPPRESSED" -> 72;
            case "RESIDERR" -> 75;
            case "NOSPOOL" -> 80;
            case "TERMERR" -> 81;
            case "ROLLEDBACK" -> 82;
            case "END" -> 83;
            case "DISABLED" -> 84;
            case "ALLOCERR" -> 85;
            case "STRELERR" -> 86;
            case "OPENERR" -> 87;
            case "SPOLBUSY" -> 88;
            case "SPOLERR" -> 89;
            case "NODEIDERR" -> 90;
            case "TASKIDERR" -> 91;
            case "TCIDERR" -> 92;
            case "DSNNOTFOUND" -> 93;
            case "LOADING" -> 94;
            case "MODELIDERR" -> 95;
            case "OUTDESCRERR" -> 96;
            case "PARTNERIDERR" -> 97;
            case "PROFILEIDERR" -> 98;
            case "NETNAMEIDERR" -> 99;
            case "LOCKED" -> 100;
            case "RECORDBUSY" -> 101;
            case "UOWNOTFOUND" -> 102;
            case "UOWLNOTFOUND" -> 103;
            case "CONTAINERERR" -> 110;
            case "CHANNELERR" -> 122;
            case "CCSIDERR" -> 123;
            case "TIMEDOUT" -> 124;
            case "CODEPAGEERR" -> 125;
            case "INCOMPLETE" -> 126;
            case "APPNOTFOUND" -> 127;
            case "BUSY" -> 128;
            default -> throw new IllegalArgumentException("no RESP value known for condition " + condition);
        };
    }

    /** The abend code of an unhandled condition (IBM's AEIx / AEYx / AEZx abend codes, the AEIA topic). */
    public static String abcodeFor(String condition) {
        return switch (condition) {
            case "NOTFND" -> "AEIM";
            case "LENGERR" -> "AEIV";
            case "ITEMERR" -> "AEIZ";
            case "QIDERR" -> "AEYH";
            case "MAPFAIL" -> "AEI9";
            case "ENDDATA" -> "AEI2";
            case "PGMIDERR" -> "AEI0";
            case "INVREQ" -> "AEIP";
            case "CONTAINERERR" -> "AEZJ";
            case "CHANNELERR" -> "AEZV";
            default -> throw new IllegalArgumentException("no abend code known for condition " + condition);
        };
    }
}
