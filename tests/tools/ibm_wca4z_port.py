#!/usr/bin/env python3
"""IBM watsonx Code Assistant for Z's published LGACDB01 translation, run through our equivalence harness.

    python tests/tools/ibm_wca4z_port.py --work DIR [--faults all|none] [--junit]

IBM published one WCA4Z COBOL-to-Java translation with its validation inputs: GenApp's LGACDB01, paragraph
INSERT-CUSTOMER (https://github.com/sandeephans/validation-c2j, the data behind arXiv 2506.10999 / 2504.10548).
The repository carries no license, so nothing of it is committed here: this script fetches it at a pinned commit
and lays it into a port next to code we wrote. docs/language_status/ibm_wca4z_lgacdb01.md has the results.

The port the harness proves (DIR/port):
  ours   our det port of the genapp-lgacdb01 case (det_port.py --translate-only): LGACDB01's other paragraphs and
         the programs it LINKs to (LGACVS01, LGACDB02), proven equivalent on their own;
  IBM    their generated classes, byte for byte (DIR/port/ibm), with LGACDB01's INSERT-CUSTOMER paragraph running
         IBM's Lgacdb01.insertCustomer in place of ours;
  adapter (tests/tools/ibm_wca4z): the det method for INSERT-CUSTOMER replaced by a call that hands IBM's method
         the paragraph's host variables and takes back the customer number; a JDBC driver for IBM's placeholder
         URL "endpoint_url" that answers with the task's own Db2 connection; a compile shim for the JZOS field
         API IBM's classes reference (JZOS ships only with IBM's Java for z/OS; the shim refuses every byte
         conversion, which the adapter never uses).

--junit also builds IBM's own generated JUnit test (PowerMock, mocked JDBC) against IBM's classes as published.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parent.parent
sys.path.insert(0, str(REPO_ROOT))
from gitgalaxy.core.source_text import read_source  # noqa: E402

ADAPTER = TOOLS / "ibm_wca4z"

IBM_REPO = "https://github.com/sandeephans/validation-c2j"
IBM_SHA = "967d00b588057f12946058f2faa37c8d49824f7e"  # 2024-10-11, the repository's only commit
CASE = "genapp-lgacdb01"
SERVICE = "service/Lgacdb01Service.java"

# The det method that becomes the adapter call: INSERT-CUSTOMER, up to the next paragraph's method.
PARAGRAPH = re.compile(r"(    /\*\* INSERT-CUSTOMER\. \*/\n    private int (p\d+)\(\) \{\n)(.*?)(\n    /\*\* )", re.S)

# What the det port names the paragraph's data (f<n>_<NAME>); the numbers vary with the translator's version.
HOST_VARIABLES = ("LGAC_NCS", "DB2_CUSTOMERNUM_INT", "CA_CUSTOMER_NUM", "CA_FIRST_NAME", "CA_LAST_NAME", "CA_DOB",
                  "CA_HOUSE_NAME", "CA_HOUSE_NUM", "CA_POSTCODE", "CA_PHONE_MOBILE", "CA_PHONE_HOME",
                  "CA_EMAIL_ADDRESS")  # fmt: skip

ADAPTER_BODY = """\
        // IBM WCA4Z adapter (tests/tools/ibm_wca4z_port.py): this paragraph runs IBM's translation,
        // com.ibm.wcaz.implementation.Lgacdb01.insertCustomer, fetched unmodified. The adapter hands it the
        // paragraph's host variables as IBM's method takes them and takes back what IBM's method reports.
        com.ibm.wcaz.implementation.CaCustomerRequest ibmRequest = new com.ibm.wcaz.implementation.CaCustomerRequest();
        com.ibm.wcaz.datamodel.Genasa1Customer ibmCustomer = ibmRequest.getGenasa1Customer();
        ibmCustomer.setFirstname(Cobol.text({CA_FIRST_NAME}, CS));
        ibmCustomer.setLastname(Cobol.text({CA_LAST_NAME}, CS));
        try {  // IBM's model types DATEOFBIRTH as java.sql.Date; CA-DOB is the COBOL's yyyy-mm-dd text
            ibmCustomer.setDateofbirth(java.sql.Date.valueOf(Cobol.text({CA_DOB}, CS).strip()));
        } catch (IllegalArgumentException notADate) {
            // left as IBM's model initialises it
        }
        ibmCustomer.setHousename(Cobol.text({CA_HOUSE_NAME}, CS));
        ibmCustomer.setHousenumber(Cobol.text({CA_HOUSE_NUM}, CS));
        ibmCustomer.setPostcode(Cobol.text({CA_POSTCODE}, CS));
        ibmCustomer.setPhonemobile(Cobol.text({CA_PHONE_MOBILE}, CS));
        ibmCustomer.setPhonehome(Cobol.text({CA_PHONE_HOME}, CS));
        ibmCustomer.setEmailaddress(Cobol.text({CA_EMAIL_ADDRESS}, CS));
        com.ibm.wcaz.implementation.Lgacdb01.insertCustomer(
                Cobol.num({DB2_CUSTOMERNUM_INT}, CS).longValue(), Cobol.text({LGAC_NCS}, CS), ibmRequest);
        // IBM's method reports the customer number through caCustomerRequest.setCaCustomerNum only (its
        // db2CustomernumInt is a parameter): read as both the COBOL's DB2-CUSTOMERNUM-INT, which the program's
        // LINK to LGACDB02 uses after this paragraph, and CA-CUSTOMER-NUM, which the paragraph ends by setting.
        Cobol.store({DB2_CUSTOMERNUM_INT}, BigDecimal.valueOf(ibmRequest.getCaCustomerNum()), false, CS);
        Cobol.store({CA_CUSTOMER_NUM}, BigDecimal.valueOf(ibmRequest.getCaCustomerNum()), false, CS);
        return {NEXT};"""


def run(argv: list[str], cwd: Path = REPO_ROOT, log: Path | None = None) -> int:
    if log is None:
        return subprocess.run(argv, cwd=cwd, check=False).returncode  # noqa: S603
    with log.open("wb") as fh:
        return subprocess.run(argv, cwd=cwd, check=False, stdout=fh, stderr=subprocess.STDOUT).returncode  # noqa: S603


def fetch(work: Path) -> Path:
    """IBM's repository at the pinned commit (cloned once into work/ibm-src)."""
    src = work / "ibm-src"
    if not (src / ".git").is_dir():
        shutil.rmtree(src, ignore_errors=True)
        subprocess.run(["git", "clone", "-q", IBM_REPO, str(src)], check=True)  # noqa: S603, S607
    subprocess.run(["git", "-C", str(src), "checkout", "-q", IBM_SHA], check=True)  # noqa: S603, S607
    head = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], check=True, capture_output=True,  # noqa: S603, S607
                          text=True).stdout.strip()  # fmt: skip
    if head != IBM_SHA:
        raise SystemExit(f"IBM's repository is at {head}, not the pinned {IBM_SHA}")
    return src


def adapt(service: str) -> str:
    """Our det service with INSERT-CUSTOMER's method body replaced by the adapter call."""
    m = PARAGRAPH.search(service)
    if not m:
        raise SystemExit("INSERT-CUSTOMER's method not found in the det port (the translator's layout changed?)")
    names = {}
    for var in HOST_VARIABLES:
        found = sorted(set(re.findall(rf"\bf\d+_{var}\b", service)))
        if len(found) != 1:
            raise SystemExit(f"the det port names {var} {found or 'nowhere'}: expected exactly one field")
        names[var] = found[0]
    returns = re.findall(r"return (\d+);", m.group(3))
    if not returns:
        raise SystemExit("INSERT-CUSTOMER's method has no fall-through return")
    body = ADAPTER_BODY.replace("{NEXT}", returns[-1]) + "\n    }\n"  # group 3 runs through the method's brace
    for var, field in names.items():
        body = body.replace("{" + var + "}", field)
    return service[: m.start(3)] + body + service[m.end(3) :]


# --clamp-error-msg: OUR det port's LINK to LGSTSQ with COMMAREA(ERROR-MSG) (71 bytes) marshals it with the DTO
# of CA-ERROR-MSG (FILLER X(9), CA-DATA X(90)), so it reads past the record on the error path -- a det-port bug,
# reached only when an SQL statement fails, which none of our scenarios did before IBM's INSERT failed (register
# M2). The flag clamps that slice to the record, in this run's copy only, so the run reaches the comparison.
ERROR_MSG_SLICE = re.compile(r"(private void (?:fill|in)_\w*ErrorMsg\(.*?\n    \}\n)", re.S)
CA_DATA = re.compile(r"Field\.alphanumeric\(s, base \+ (\d+), (\d+), false\)")


def clamp_error_msg(service: str) -> str:
    def clamp(m: re.Match[str]) -> str:
        return CA_DATA.sub(lambda f: f"Field.alphanumeric(s, base + {f.group(1)}, Math.max(0, Math.min({f.group(2)}, "
                                     f"s.bytes.length - base - {f.group(1)})), false)", m.group(1))  # fmt: skip

    return ERROR_MSG_SLICE.sub(clamp, service)


def build_port(work: Path, src: Path, clamp: bool = False) -> Path:
    """DIR/port: our det port, the adapter, and IBM's classes."""
    det = work / "det" / CASE / "port"
    port = work / "port"
    shutil.rmtree(port, ignore_errors=True)
    shutil.copytree(det, port)
    service = port / SERVICE
    service.write_text(adapt(service.read_text(encoding="utf-8")), encoding="utf-8")
    if clamp:
        for svc in sorted((port / "service").glob("*.java")):
            svc.write_text(clamp_error_msg(svc.read_text(encoding="utf-8")), encoding="utf-8")
    shutil.copytree(src / "generated_code" / "java", port / "ibm", ignore=shutil.ignore_patterns("*.class"))
    shutil.copytree(ADAPTER / "shim", port / "ibmshim")
    shutil.copytree(ADAPTER / "adapter", port, dirs_exist_ok=True)
    return port


JUNIT_POM = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>gitgalaxy.equivalence</groupId>
  <artifactId>ibm-wca4z-lgacdb01-junit</artifactId>
  <version>1</version>
  <properties>
    <maven.compiler.release>17</maven.compiler.release>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
  </properties>
  <dependencies>
    <dependency><groupId>junit</groupId><artifactId>junit</artifactId><version>4.13.2</version><scope>test</scope></dependency>
    <dependency><groupId>org.mockito</groupId><artifactId>mockito-inline</artifactId><version>3.12.4</version><scope>test</scope></dependency>
    <dependency><groupId>org.powermock</groupId><artifactId>powermock-module-junit4</artifactId><version>2.0.9</version><scope>test</scope></dependency>
    <dependency><groupId>org.powermock</groupId><artifactId>powermock-api-mockito2</artifactId><version>2.0.9</version><scope>test</scope></dependency>
  </dependencies>
  <build>
    <plugins>
      <plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-compiler-plugin</artifactId><version>3.11.0</version></plugin>
      <plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-surefire-plugin</artifactId><version>3.2.5</version>
        <configuration><includes><include>**/*Tests.java</include></includes></configuration></plugin>
    </plugins>
  </build>
</project>
"""


def junit(work: Path, src: Path) -> dict[str, object]:
    """IBM's generated JUnit test, built against IBM's classes as published (plus the JZOS compile shim)."""
    project = work / "ibm-junit"
    shutil.rmtree(project, ignore_errors=True)
    shutil.copytree(
        src / "generated_code" / "java", project / "src/main/java", ignore=shutil.ignore_patterns("*.class")
    )
    shutil.copytree(ADAPTER / "shim", project / "src/main/java", dirs_exist_ok=True)
    shutil.copytree(src / "generated_code" / "test", project / "src/test/java")
    (project / "pom.xml").write_text(JUNIT_POM, encoding="utf-8")
    log = work / "ibm-junit.log"
    rc = run(["mvn", "-q", "-B", "test"], cwd=project, log=log)
    text = read_source(log).text
    errors = [ln.strip() for ln in text.splitlines() if "ERROR" in ln and ".java" in ln][:10]
    return {"rc": rc, "compile_errors": errors, "log": str(log)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--faults", default="all")
    ap.add_argument("--junit", action="store_true", help="also build and run IBM's own generated JUnit test")
    ap.add_argument(
        "--clamp-error-msg",
        action="store_true",
        help="diagnostic: work around our det port's ERROR-MSG marshalling bug (see clamp_error_msg)",
    )
    ap.add_argument("--scenario", help="prove only this scenario of the case (a scratch case.json, --case-file)")
    args = ap.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    src = fetch(work)
    rc = run([sys.executable, str(TOOLS / "det_port.py"), "run", CASE, "--translate-only", "--work", str(work / "det")])
    if rc != 0 or not (work / "det" / CASE / "port" / SERVICE).is_file():
        raise SystemExit(f"det_port.py --translate-only failed (rc {rc})")
    port = build_port(work, src, clamp=args.clamp_error_msg)
    proof = work / "proof"
    shutil.rmtree(proof, ignore_errors=True)
    log = work / "proof.log"
    argv = [sys.executable, str(TOOLS / "equivalence.py"), "run", CASE, "--port", str(port), "--keep", str(proof),
            "--faults", args.faults]  # fmt: skip
    if args.scenario:
        case = json.loads((REPO_ROOT / "tests/equivalence" / CASE / "case.json").read_text(encoding="utf-8"))
        case["scenarios"] = [s for s in case["scenarios"] if s["name"] == args.scenario]
        if not case["scenarios"]:
            raise SystemExit(f"{CASE} has no scenario {args.scenario}")
        case_file = work / "case.json"
        case_file.write_text(json.dumps(case, indent=1) + "\n", encoding="utf-8")
        argv += ["--case-file", str(case_file)]
    rc = run(argv, log=log)
    lines = read_source(log).text.splitlines()
    verdicts = [ln for ln in lines if re.match(r"[A-Z0-9]+ (\S+: |COBOL coverage)|[A-Z0-9]+: the Java side failed", ln)]
    result: dict[str, object] = {"ibm_sha": IBM_SHA, "proof_rc": rc, "verdicts": verdicts, "proof_log": str(log),
                                 "report": str(proof / "report.json")}  # fmt: skip
    if args.junit:
        result["junit"] = junit(work, src)
    (work / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for v in verdicts:
        print(v)
    print(f"proof rc {rc}: {'PROVED' if rc == 0 else 'NOT PROVEN'} (see {log})")
    if args.junit:
        print(f"IBM's JUnit: rc {result['junit']['rc']} (see {result['junit']['log']})")  # type: ignore[index]
    return 0


if __name__ == "__main__":
    sys.exit(main())
