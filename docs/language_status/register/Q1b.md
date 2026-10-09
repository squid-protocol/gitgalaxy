---
id: "Q1b"
family: "Q"
status: ""
title: "A datetime host variable Db2 rejects: -180 / 22007 on both sides — MATCHED (#4658)"
area: ""
summary: ""
reached: ""
---
- **What.** An UPDATE binding an unset (non-date) PIC X host variable to a DATE column gets SQLCODE -180, SQLSTATE 22007
  ("the string representation of a datetime value is not valid") from Db2 for LUW, and the same on z/OS Db2 (-180 is the
  documented SQLCODE for this, SQLSTATE 22007). IBM's JDBC driver refuses some such values on the client with its own
  -4220 (conversion error) before Db2 sees them; that code is never a Db2 SQLCODE an embedded-SQL program meets, so
  DetSql maps it to -180 / 22007. Other driver errors pass through unchanged. SQLERRMC/SQLERRD of the mapped error stay
  empty (the DISPLAYed SQLERRD(3) is 0 on both sides).
