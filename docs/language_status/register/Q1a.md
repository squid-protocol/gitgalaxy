---
id: "Q1a"
family: "Q"
status: "MATCHED"
title: "A binary host variable takes what its bytes hold — MATCHED (#4579)"
area: "Db2"
summary: ""
reached: "yes (GenApp, CBSA host variables)"
---
- **What.** SELECT INTO / FETCH INTO a COMP / COMP-4 / BINARY / COMP-5 host variable gives SQLCODE -304 only for a value
  outside its halfword / fullword / doubleword (Db2 types the host variable by its data type: S9(9) COMP is INTEGER), not
  beyond its PICTURE's digits: 2147483647 into `S9(9) COMP` is assigned. That holds under TRUNC(STD) too; STD limits
  COBOL's own MOVE / arithmetic (C1), not the SQL assignment. ggsql.c `num_store` and DetSql (`Cobol.storeHostChecked`) agree.
- **IBM.** Db2 12 for z/OS Codes, GC27-8847-02 (ibm.com/docs/en/SSEPEK_12.0.0/pdf/db2z_12_codesbook.pdf), and Db2 10 for z/OS Codes, SQLCODE -304 (SQLSTATE 22003): "A VALUE WITH DATA TYPE data-type1 CANNOT BE ASSIGNED TO A
  HOST VARIABLE ... the host variable with data type data-type2 was not large enough to hold the retrieved value". The test
  is the host variable's Db2 data type (halfword, fullword, doubleword), as here. Db2 13 FETCH (SQL Reference, ibm.com/docs/en/db2-for-zos/13?topic=statements-fetch): "If an
  assignment error occurs, the value is not assigned to the target and no more values are assigned to targets."
  The statement that STD does not apply is ours: the cited pages do not mention TRUNC. Not measured on z/OS (#4702 Part 2).
