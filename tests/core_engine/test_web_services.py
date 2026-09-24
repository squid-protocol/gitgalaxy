"""
#3496: web / API services from the CICS web-services assistant JCL
(core/web_services.py) through `extract_boundary` -- GENAPP's wsa*.jcl shape:
DFHLS2WS as a procedure with its in-stream INPUT.SYSUT1 parameters, several steps
per member, a requester, and JCL with no assistant.
"""

from gitgalaxy.core.mainframe_boundary import extract_boundary

JCL = """\
//GENASOAP  JOB  ,S8SMITH,CLASS=A
//JOBPROC JCLLIB ORDER=<CICSHLQ>.SDFHINST
//LS2WS     EXEC DFHLS2WS,
//    JAVADIR='java601_bit64_ga/J6.0.1_64'
//INPUT.SYSUT1 DD *
 PDSLIB=<SOURCEX>
 LANG=COBOL
 PGMNAME=LGICUS01
 REQMEM=SOAIC01
 RESPMEM=SOAIC01
 URI=GENAPP/LGICUS01
 PGMINT=COMMAREA
 WSBIND=<ZFSHOME>/genapp/wsdir/LGICUS01.wsbind
 WSDL=<ZFSHOME>/genapp/wsdir/LGICUS01.wsdl
/*
//WS2LS     EXEC PROC=DFHWS2LS
//INPUT.SYSUT1 DD *
 PDSLIB=MY.COPYLIB
 LANG=COBOL
 REQMEM=QUOTEREQ
 RESPMEM=QUOTERSP
 WSDL=/u/me/quote.wsdl
/*
"""


def test_assistant_steps_become_service_rows():
    rows = extract_boundary("jcl", JCL)["web_services"]
    assert [{k: v for k, v in r.items() if v} for r in rows] == [
        {"assistant": "DFHLS2WS", "direction": "provider", "program": "LGICUS01", "uri": "GENAPP/LGICUS01",
         "request": "SOAIC01", "response": "SOAIC01", "interface": "COMMAREA",
         "binding": "<ZFSHOME>/genapp/wsdir/LGICUS01.wsbind", "document": "<ZFSHOME>/genapp/wsdir/LGICUS01.wsdl",
         "line": 3},
        {"assistant": "DFHWS2LS", "direction": "requester", "request": "QUOTEREQ", "response": "QUOTERSP",
         "document": "/u/me/quote.wsdl", "line": 16},
    ]  # fmt: skip


def test_jcl_without_an_assistant_has_no_services():
    assert extract_boundary("jcl", "//J JOB\n//S1 EXEC PGM=IEFBR14\n")["web_services"] == []
