# Mainframe estate ingestion checklist

Most gaps in a scanned mainframe estate come from inputs that were not handed
over, not from the extractor. After a scan, the completeness report
(`python -m gitgalaxy.tools.cobol_to_cobol.completeness_report <master.db>`,
#3498) counts each gap and names the missing input below. Ask for these up front.

| Input | What it unlocks | How to extract it | Completeness signal when missing |
|---|---|---|---|
| **CSD definitions** | The transaction → program map, so pseudo-conversational flow and the CICS front doors are known. It is rarely in source control: it lives in the DFHCSD dataset or CICSPlex SM. | `DFHCSDUP LIST ALL OBJECTS` (or `EXTRACT`) to a sequential dataset; CICSPlex SM BAS export. | *transactions*: "CICS program no transaction reaches" |
| **Web / API layer** (z/OS Connect, Liberty, CICS web services) | Programs LINKed from an API rather than a transaction (e.g. CBSA's ACCTCTRL). | z/OS Connect `.sar` / `.aar` archives and API projects; CSD URIMAP / PIPELINE / WEBSERVICE definitions. | *transactions*: "CICS program no transaction reaches" (#3496) |
| **Copybook libraries** | Every record layout a program COPYs; field lineage and COMMAREA / CALL contracts. | Unload every COPYLIB / SYSLIB PDS the compile JCL concatenates. | *copybooks*: "missing copybook" |
| **Vendor and system copybooks** (DFHAID, DFHBMSCA, CMQ*V, SQLCA) | Not required: GitGalaxy treats their names as runtime-supplied. They are optional, for byte-exact layouts. | The CICS SDFHCOB, MQ SCSQCOBC and DB2 SDSNSAMP libraries. | counted as *system*, not a gap |
| **BMS map sources** | Screen layouts and the generated symbolic maps (#3490), so screen fields resolve. | The map source PDS (`.bms`), not only the generated copybooks. | *screens*: "missing BMS source" |
| **PSB / DBD generation sources** | Which IMS database a segment is in, and whether a program's PSB allows each access (#3477). | The PSBGEN / DBDGEN source PDS. | *IMS PSBs*: "DL/I program with no PSB" |
| **JCL and PROC libraries** | Batch entry points, job flow, and dataset lineage across jobs. | Unload the production JCL and every PROCLIB in the JES `PROCLIB` concatenation. | *batch entry*: "batch program no JCL step runs" |
| **Application programs** (source, or at least a load-module list) | The call graph: every CALLed / LINKed / XCTLed program. A load-module list at least separates "not supplied" from "does not exist". | Unload the source PDSs; a `LISTLOAD` / LISTPDS of the load libraries. | *program calls*: "missing program"; *transactions*: "transaction to a missing program" |
| **Scheduler export** (CA-7, Control-M, TWS / IWS) | Cross-job order and triggers, so a dataset's producer job can be ordered before its consumer. | CA-7 `LJOB,LIST=ALL`; the Control-M or TWS application / job-stream export. | always reported when the estate has more than one job |

Gaps that are **engine limits, not missing inputs**, so there is nothing to ask for:

- a dynamic CALL / XCTL target (#3493);
- a dynamic map name;
- a program in assembler or PL/I that calls do not yet link to (#3491, #3495);
- names produced by `COPY … REPLACING`.
