"""#3620: CICS TS / TD queues and IBM MQ -> messaging ports and adapters.

A real scan of a small estate:
- STATEW writes, rewrites, reads and deletes TS queue STATE, and STATER reads it back:
  a producer / consumer pair;
- STATEW also writes TD CSSL (a CICS log), TD JOBS (the internal reader, as CardDemo's CSD
  defines it), TD @tdq@ (an installation symbol) and a TS queue named by a data item;
- MQSVC is a triggered MQ service: MQGET from the trigger-named queue, MQPUT to a named
  queue, MQPUT1 to the reply-to queue.
Pinned: each site's helper and route, the ports and the adapter per integration.messaging,
the MQ listener, the build dependencies, the manifest and the worklist. The generated Java
compiles in java_target_matrix (messaging-jms / messaging-kafka-plain).
"""

import json
import shutil
import sys
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_refractor_controller as refractor
import gitgalaxy.cobol_to_java_controller as java_controller
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import scan_to_db
from gitgalaxy.tools.cobol_to_java.java_target import ConfigError, target_from_dict


def _program(name: str, storage: str, body: str) -> str:
    return (
        "       IDENTIFICATION DIVISION.\n"
        f"       PROGRAM-ID. {name}.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        f"{storage}"
        "       PROCEDURE DIVISION.\n"
        "       000-MAIN.\n"
        f"{body}"
        "           EXEC CICS RETURN END-EXEC.\n"
    )


STORAGE = (
    "       01  WS-REC             PIC X(40).\n"
    "       01  WS-JCL             PIC X(80).\n"
    "       01  WS-N               PIC S9(4) COMP.\n"
    "       01  WS-QNAME           PIC X(8).\n"
)

STATEW = _program("STATEW", STORAGE, (
    "           EXEC CICS WRITEQ TS QUEUE('STATE') FROM(WS-REC) END-EXEC.\n"       # 11
    "           EXEC CICS WRITEQ TS QUEUE('STATE') FROM(WS-REC) ITEM(WS-N)\n"      # 12
    "                REWRITE END-EXEC.\n"                                          # 13
    "           EXEC CICS READQ TS QUEUE('STATE') INTO(WS-REC) ITEM(1)\n"          # 14
    "                END-EXEC.\n"                                                  # 15
    "           EXEC CICS DELETEQ TS QUEUE('STATE') END-EXEC.\n"                   # 16
    "           EXEC CICS WRITEQ TS QUEUE(WS-QNAME) FROM(WS-REC) END-EXEC.\n"      # 17
    "           EXEC CICS WRITEQ TD QUEUE('CSSL') FROM(WS-REC) END-EXEC.\n"        # 18
    "           EXEC CICS WRITEQ TD QUEUE('JOBS') FROM(WS-JCL) END-EXEC.\n"        # 19
    "           EXEC CICS WRITEQ TD QUEUE('@tdq@') FROM(WS-REC) END-EXEC.\n"       # 20
))  # fmt: skip

STATER = _program("STATER", STORAGE, "           EXEC CICS READQ TS QUEUE('STATE') INTO(WS-REC) END-EXEC.\n")

MQSVC = _program("MQSVC", "       01  REPLY-QUEUE-NAME   PIC X(48) VALUE SPACES.\n", (
    "           EXEC CICS RETRIEVE INTO(MQTM) END-EXEC\n"
    "           MOVE MQTM-QNAME TO INPUT-QUEUE-NAME\n"
    "           MOVE 'APP.AUDIT' TO REPLY-QUEUE-NAME\n"
    "           MOVE INPUT-QUEUE-NAME TO MQOD-OBJECTNAME\n"
    "           CALL 'MQOPEN' USING QMGR-HANDLE-CONN MQ-OBJECT-DESCRIPTOR\n"
    "                MQ-OPTIONS MQ-HOBJ MQ-CC MQ-RC\n"
    "           MOVE MQ-HOBJ TO INPUT-QUEUE-HANDLE\n"
    "           MOVE REPLY-QUEUE-NAME TO MQOD-OBJECTNAME\n"
    "           CALL 'MQOPEN' USING QMGR-HANDLE-CONN MQ-OBJECT-DESCRIPTOR\n"
    "                MQ-OPTIONS MQ-HOBJ MQ-CC MQ-RC\n"
    "           MOVE MQ-HOBJ TO OUTPUT-QUEUE-HANDLE\n"
    "           MOVE INPUT-QUEUE-HANDLE TO MQ-HOBJ\n"
    "           CALL 'MQGET' USING MQ-HCONN MQ-HOBJ MQ-MD MQ-GMO\n"
    "                MQ-BUFFER-LENGTH MQ-BUFFER MQ-DATA-LENGTH MQ-CC MQ-RC\n"
    "           CALL 'MQPUT' USING MQ-HCONN OUTPUT-QUEUE-HANDLE MQ-MD\n"
    "                MQ-PMO MQ-BUFFER-LENGTH MQ-BUFFER MQ-CC MQ-RC\n"
    "           MOVE MQMD-REPLYTOQ OF MQM-MD-REQUEST TO WS-REPLY-QNAME\n"
    "           MOVE WS-REPLY-QNAME TO MQOD-OBJECTNAME OF MQM-OD-REPLY\n"
    "           CALL 'MQPUT1' USING W02-HCONN MQM-OD-REPLY MQM-MD-REPLY\n"
    "                MQM-PMO LEN BUF WS-CC WS-RC END-CALL\n"
))  # fmt: skip

CSD = """\
 DEFINE TRANSACTION(STW1) GROUP(APP) PROGRAM(STATEW)
 DEFINE TRANSACTION(STR1) GROUP(APP) PROGRAM(STATER)
 DEFINE TRANSACTION(MQS1) GROUP(APP) PROGRAM(MQSVC)
 DEFINE TDQUEUE(JOBS) GROUP(APP)
 DESCRIPTION(SUBMIT JOBS FROM CICS)
        TYPE(EXTRA) DATABUFFERS(1) DDNAME(INREADER) ERROROPTION(IGNORE)
        OPENTIME(INITIAL) TYPEFILE(OUTPUT) RECORDSIZE(80)
        RECORDFORMAT(FIXED) BLOCKFORMAT(UNBLOCKED) DISPOSITION(MOD)
"""


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("messaging")
    repo = base / "estate"
    files = {"cbl/STATEW.cbl": STATEW, "cbl/STATER.cbl": STATER, "cbl/MQSVC.cbl": MQSVC, "csd/APP.csd": CSD}
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return repo, scan_to_db(repo, base / "scan")


def _generate(scanned, tmp_path, messaging=None):
    repo, db = scanned
    work = tmp_path / "estate"
    shutil.copytree(repo, work)
    with patch.object(sys, "argv", ["refract", str(work), "--galaxy-db", str(db)]):
        refractor.main()
    (clean,) = tmp_path.glob("estate_gitgalaxy_clean_*")
    argv = ["cobol-to-java", str(clean), "--header", str(tmp_path / "none.txt")]
    if messaging:
        cfg = tmp_path / "m.json"
        cfg.write_text(json.dumps({"integration": {"messaging": messaging}}), encoding="utf-8")
        argv += ["--config", str(cfg)]
    with patch.object(sys, "argv", argv):
        java_controller.main()
    (java,) = tmp_path.glob("estate_gitgalaxy_java_spring_*")
    return java


SRC = "src/main/java/com/gitgalaxy/modernized"


def _read(java, rel):
    return (java / SRC / rel).read_text(encoding="utf-8")


def test_each_site_gets_its_helper_and_route(scanned, tmp_path):
    java = _generate(scanned, tmp_path)
    w = _read(java, "service/StatewService.java")
    assert "protected int writeqTsStateL11(String record) {" in w
    assert '        return tempStorage.writeItem("STATE", record);' in w
    assert "protected void writeqTsStateL12(int item, String record) {" in w  # ITEM(WS-N) REWRITE
    assert "protected Optional<String> readqTsStateL14() {" in w  # ITEM(1): the item is fixed
    assert '        return tempStorage.readItem("STATE", 1);' in w
    assert "Shared through TS STATE: read by cbl/STATER.cbl." in w  # the producer / consumer pair
    assert "protected int writeqTsL17(String queue, String record) {" in w  # QUEUE(WS-QNAME)
    assert "TODO: the queue name is data-driven (QUEUE(WS-QNAME)): pass it." in w
    assert "Route: log -- a CICS-supplied log destination." in w  # CSSL
    assert "TODO: this program submits a job through the internal reader: launch it (#3622)." in w  # JOBS
    assert "TODO: @tdq@ is an installation symbol: set the real queue name." in w
    route = _read(java, "messaging/RoutingTransientData.java")
    assert 'ROUTES.put("CSSL", "log");' in route and 'ROUTES.put("JOBS", "reader");' in route
    assert "Shared through TS STATE: written by cbl/STATEW.cbl." in _read(java, "service/StaterService.java")

    mq = _read(java, "service/MqsvcService.java")
    assert 'messageQueue.send("APP.AUDIT", message);' in mq  # MQPUT to a MOVEd name
    assert "protected void mqput1L26(String replyTo, String message) {" in mq  # MQPUT1 to MQMD ReplyToQ
    assert "public void handleMqMessage(String request, String replyTo) {" in mq
    assert "call it directly (in-memory adapter: no listener)" in mq
    assert (java / SRC / "messaging/InMemoryMessageQueue.java").is_file()
    assert (java / SRC / "messaging/InMemoryTempStorage.java").is_file()
    assert not list((java / SRC / "messaging").glob("*MqListener.java"))
    audit = (java / "java_migration_audit.txt").read_text(encoding="utf-8")
    assert "  • Messaging (#3620)        : 6 TS / 3 TD / 3 MQ sites; TD routes: 1 log, 1 reader, 1 symbol; " \
           "1 MQ-triggered programs; adapter: in-memory" in audit  # fmt: skip

    manifest = json.loads((java / "traceability.json").read_text(encoding="utf-8"))
    op = next(a for a in manifest["artifacts"] if a["symbol"] == "StatewService#writeqTsStateL11")
    assert op["facts"][0]["source"] == "cbl/STATEW.cbl:11" and op["facts"][0]["ledger_field"] == "CICS resources"
    worklist = json.loads((java / "migration_worklist.json").read_text(encoding="utf-8"))
    cats = {i["category"] for i in worklist["items"] if i["program"] == "cbl/STATEW.cbl"}
    assert {"queue-name", "interface-call"} <= cats  # data-driven name + @tdq@; the internal reader


def test_jms_adds_the_listener_and_the_artemis_starter(scanned, tmp_path):
    java = _generate(scanned, tmp_path, "jms")
    listener = _read(java, "messaging/MqsvcMqListener.java")
    assert '@JmsListener(destination = "${gitgalaxy.mq.mqsvc.request-queue:MQSVC.REQUEST}")' in listener
    assert "mqsvcService.handleMqMessage(body, replyTo);" in listener
    assert "jms.convertAndSend(queue, message);" in _read(java, "messaging/JmsMessageQueue.java")
    assert "spring-boot-starter-artemis" in (java / "pom.xml").read_text(encoding="utf-8")


def test_kafka_adds_the_listener_and_spring_kafka(scanned, tmp_path):
    java = _generate(scanned, tmp_path, "kafka")
    listener = _read(java, "messaging/MqsvcMqListener.java")
    assert (
        '@KafkaListener(topics = "${gitgalaxy.mq.mqsvc.request-queue:MQSVC.REQUEST}", groupId = "gitgalaxy")'
        in listener
    )
    assert 'mqsvcService.handleMqMessage(body, topic + ".reply");' in listener
    assert "<artifactId>spring-kafka</artifactId>" in (java / "pom.xml").read_text(encoding="utf-8")


def test_the_messaging_option_is_checked():
    assert target_from_dict({"integration": {"messaging": "kafka"}}).integration.messaging == "kafka"
    with pytest.raises(ConfigError, match="integration.messaging 'rabbit' is not supported"):
        target_from_dict({"integration": {"messaging": "rabbit"}})
