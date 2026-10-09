---
id: "Q1a"
family: "Q"
status: ""
title: "A binary host variable takes what its bytes hold — MATCHED (#4579)"
area: ""
summary: ""
reached: ""
---
- **What.** SELECT INTO / FETCH INTO a COMP / COMP-4 / BINARY / COMP-5 host variable gives SQLCODE -304 only for a value
  outside its halfword / fullword / doubleword (Db2 types the host variable by its data type: S9(9) COMP is INTEGER), not
  beyond its PICTURE's digits: 2147483647 into `S9(9) COMP` is assigned. That holds under TRUNC(STD) too; STD limits
  COBOL's own MOVE / arithmetic (C1), not the SQL assignment. ggsql.c `num_store` and DetSql (`Cobol.storeHostChecked`) agree.
