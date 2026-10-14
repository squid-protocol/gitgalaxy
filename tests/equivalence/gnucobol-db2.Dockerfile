# The COBOL side of a Db2 equivalence case: the harness's GnuCOBOL image plus IBM's Data Server Driver for ODBC
# and CLI (free; https://www.ibm.com/support/pages/node/387577), so the SQL stub (ggsql.c) runs each statement on a
# real Db2 -- the same database the Java side reaches over JDBC.
# #4309: built FROM the pinned oracle image, so it inherits the pin (and its org.gitgalaxy.oracle.* labels, which the
# harness checks). It is built once and kept: after the oracle moves, `docker rmi gitgalaxy-gnucobol-db2:3`.
FROM gitgalaxy-gnucobol:3
# #5048: no apt step here. The driver's libxml2 dependency is already met: libcob4 in the base image depends on it
# (checked with dpkg -s libxml2), and the old `apt-get install libxml2 || true` hid a failed install behind a pass.
# #4980: the driver is not downloaded here (a bare ADD had no retry and no checksum: an IBM hiccup failed the build).
# equivalence_db2.fetch_odbc_cli() puts it in the build context, sha256-checked against odbc_cli.pin; checked again here.
COPY linuxx64_odbc_cli.tar.gz /tmp/cli.tgz
COPY odbc_cli.pin /tmp/odbc_cli.pin
RUN sed -n 's/^sha256=//p' /tmp/odbc_cli.pin | sed 's|$|  /tmp/cli.tgz|' | sha256sum -c - \
 && mkdir -p /opt/ibm && tar -xzf /tmp/cli.tgz -C /opt/ibm && rm /tmp/cli.tgz /tmp/odbc_cli.pin
ENV IBM_DB_HOME=/opt/ibm/clidriver
ENV LD_LIBRARY_PATH=/opt/ibm/clidriver/lib
