## The Db2 image is pinned (#4733)

A Db2 case runs its SQL on one real Db2 (IBM Db2 Community Edition, in a container), the COBOL side through IBM's CLI
driver and the Java side through JDBC (`tests/tools/equivalence_db2.py`). The image was `icr.io/db2_community/db2:latest`,
a tag that moves: a new Db2 could change a code page, a collation or a SQLCODE with no change of ours. It is now named
by content digest:

| pinned | value |
|---|---|
| Db2 image | `icr.io/db2_community/db2@sha256:2de8151713c261843868c5c3411b57be6ae79d99d70a5b3022337836776bfda6` |
| built | 2026-07-13 (the image every Db2 proof so far ran on; it was `:latest` on 2026-10-08) |

`equivalence_db2.IMAGE` is the pin. `tests/cobol_mainframe/test_db2_image_pin.py` fails when it is a tag, or when this
page does not name its digest. A container left running from another image is refused (`docker rm -f gitgalaxy-db2`),
and every Db2 case's proof report records the image under `oracle.db2`. `equivalence_db2.py` is part of the harness
fingerprint, so moving the pin makes every evidence record stale (re-proved by the Evidence Refresh bot).

Moving it is a deliberate change: resolve the new digest (`curl -sI -H 'Accept: application/vnd.oci.image.index.v1+json'
https://icr.io/v2/db2_community/db2/manifests/latest`, header `docker-content-digest`), set `IMAGE`, update this table,
and re-sweep the Db2 cases.
