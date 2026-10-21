"""#5053: a det facade's wide-RETURN answer (#4695) is a byte[] in the region's EBCDIC, while the bytes beside a request
(handleTransaction / handleLink's byte[] area, lastAnswerBytes / lastLinkBytes) are in the port's page. An `Object`
request can be that answer, so handing it back together with an area is one COMMAREA in two charsets: the facade stops
by name. A typed request cannot be a byte[], and an overload with no area has nothing to mix."""

import pytest
from gitgalaxy.tools.cobol_to_java.det import program as P

GUARD = "if (request instanceof byte[] && area != null) {"


def _stub(req: str, meth: str = "handleTransaction") -> str:
    lead = "String transid, " if meth == "handleTransaction" else ""
    body = (
        'region.run(task, "PROG", this::runTask);\n return task.returned(%s.class);\n' % req
        if meth == "handleTransaction"
        else 'region.run(task, "PROG", this::runTask);\n return request;\n'
    )
    return (
        f"public {req} {meth}({lead}{req} request) {{\n{body}}}\n"
        f"public {req} {meth}({lead}{req} request, byte[] area) {{\n{body}}}\n"
        "public byte[] lastAnswerBytes() { return null; }\npublic byte[] lastLinkBytes() { return null; }\n"
    )


@pytest.mark.parametrize("meth", ["handleTransaction", "handleLink"])
@pytest.mark.parametrize("passes_bytes", [False, True])
def test_an_object_request_with_bytes_beside_it_refuses_by_name(meth, passes_bytes):
    java = "\n".join(P.facades(_stub("Object", meth), passes_bytes))
    assert java.count(GUARD) == 1  # the area overload only
    assert java.index(GUARD) < java.index("CicsTask.region()", java.index(GUARD) - 200)
    assert f"{meth}: the request is the COMMAREA as bytes" in java


@pytest.mark.parametrize("meth", ["handleTransaction", "handleLink"])
def test_a_typed_request_cannot_be_bytes_so_nothing_changes(meth):
    java = "\n".join(P.facades(_stub("CaDto", meth), True))
    assert "instanceof byte[]" not in java.replace("task.returned(Object.class) instanceof byte[] wide", "")
