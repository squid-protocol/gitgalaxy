# The COBOL side of a Db2 equivalence case: the harness's GnuCOBOL image plus IBM's Data Server Driver for ODBC
# and CLI (free; https://www.ibm.com/support/pages/node/387577), so the SQL stub (ggsql.c) runs each statement on a
# real Db2 -- the same database the Java side reaches over JDBC.
FROM gitgalaxy-gnucobol:3
ADD https://public.dhe.ibm.com/ibmdl/export/pub/software/data/db2/drivers/odbc_cli/linuxx64_odbc_cli.tar.gz /tmp/cli.tgz
RUN mkdir -p /opt/ibm && tar -xzf /tmp/cli.tgz -C /opt/ibm && rm /tmp/cli.tgz \
 && (apt-get update && apt-get install -y --no-install-recommends libxml2 && rm -rf /var/lib/apt/lists/* || true)
ENV IBM_DB_HOME=/opt/ibm/clidriver
ENV LD_LIBRARY_PATH=/opt/ibm/clidriver/lib
