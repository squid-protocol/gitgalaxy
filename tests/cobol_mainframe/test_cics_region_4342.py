"""The generated CicsRegion (#4342 / #4343): the deployment's region every CICS facade runs its task in.

Two shapes the dsf corpus showed the compile matrix: two sources under one program name (src/R0010101.pli and
src/GML/R0010101.pli) must not become two `case` labels (javac: duplicate case label) nor a Set.of with a duplicate
(IllegalArgumentException when Spring makes the bean); and the region's clock is the mainframe's zone, never the
JVM's (the cultural gauntlet's now()-without-a-zone rule, #3824).
"""

from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CicsForge, CicsProgram
from gitgalaxy.tools.cobol_to_java.java_target import JavaTarget


def _forge(programs: list[CicsProgram]) -> CicsForge:
    forge = CicsForge({}, "com.example")
    forge.target = JavaTarget()
    forge.programs = {p.key: p for p in programs}
    return forge


def test_one_program_name_with_two_sources_runs_neither():
    region = _forge([
        CicsProgram("src_r0010101", "SrcR0010101", "src/R0010101.pli", ["R0010101"]),
        CicsProgram("src_gml_r0010101", "SrcGmlR0010101", "src/GML/R0010101.pli", ["R0010101"]),
        CicsProgram("menu", "Menu", "cbl/MENU.cbl", ["MENU"], transactions=[{"transid": "MN01"}]),
    ]).region_source()
    assert region.count('case "R0010101"') == 1
    assert ('case "R0010101" -> throw new IllegalStateException("program R0010101 has more than one source '
            '(src/GML/R0010101.pli, src/R0010101.pli); the CSD decides which one runs");') in region
    assert 'static final Set<String> PROGRAMS = Set.of("MENU", "R0010101");' in region
    assert 'case "MENU" -> context.getBean(MenuService.class).runTask(task);' in region
    assert "SrcR0010101Service" not in region and "SrcGmlR0010101Service" not in region


def test_the_region_clock_is_the_mainframes_zone():
    forge = _forge([CicsProgram("menu", "Menu", "cbl/MENU.cbl", ["MENU"])])
    region = forge.region_source()
    assert "LocalDateTime.now()" not in region
    assert '@Value("${gitgalaxy.zone:${gitgalaxy.culture.zone:UTC}}") String zoneId' in region
    assert "at.isEmpty() ? () -> LocalDateTime.now(zone) : () -> LocalDateTime.parse(at)" in region
    task = forge.runtime_sources()["CicsTask"]
    assert "LocalDateTime.now()" not in task and '() -> LocalDateTime.now(ZoneId.of("UTC"))' in task
    assert "__ZONE__" not in task
