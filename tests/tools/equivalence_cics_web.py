"""#5274: the web family of the CICS harness's stub translator (equivalence_cics.translate), split out of
equivalence_cics.py: the scenario inputs the HTTP commands need (http_peers, http_request, tcpip and the config files the
stub reads them from, #4767 / #4972), WEB PARSE / SEND / EXTRACT / RECEIVE / RETRIEVE / OPEN / CONVERSE / CLOSE and the
HTTPHEADER / FORMFIELD / QUERYPARM forms, EXTRACT TCPIP, and the readers of the stub's web events. equivalence_cics's
command dispatch calls these; they reach its shared helpers (the spec, `_call`, `_resp`, the refusals) through the module
at call time, so the import works either way round."""

from __future__ import annotations

from typing import Any

import equivalence_cics as ec


_HTTP_PEER_KEYS = {"scheme", "host", "port", "urimap", "path", "exchanges"}
_HTTP_X_KEYS = {"method", "path", "query", "status", "statustext", "mediatype", "body"}


def http_peers(case: dict[str, Any], sc: dict[str, Any]) -> list[dict[str, Any]] | None:
    """#4767 zECS (X35): the HTTP servers the task can reach -- the scenario's "http_peers", else the case's: [{"scheme":
    "HTTP" | "HTTPS", "host", "port", "urimap" (the CLIENT URIMAP naming it, or null), "path" (that URIMAP's path, or null),
    "exchanges": [{"method", "path", "query" ("" for none), "status", "statustext", "mediatype", "body"}, ...]}, ...],
    each exchange the response to one request (method, path and query matched, in order), stated on both sides (the stub's
    $GGCICS_HTTP, CicsTask.withHttpPeers) in the program's characters. Unstated, None: both runtimes refuse every WEB
    command by name."""
    peers = sc.get("http_peers", case.get("http_peers"))
    if peers is None:
        return None

    def text(v: Any, blank: bool = True) -> bool:
        return isinstance(v, str) and (blank or bool(v)) and not any(c.isspace() for c in v)

    ok = isinstance(peers, list) and all(
        isinstance(p, dict) and set(p) == _HTTP_PEER_KEYS and p["scheme"] in ("HTTP", "HTTPS") and text(p["host"], False)
        and isinstance(p["port"], int) and 0 < p["port"] <= 65535
        and (p["urimap"] is None or (text(p["urimap"], False) and len(p["urimap"]) <= 8))
        and (p["path"] is None or text(p["path"], False)) and isinstance(p["exchanges"], list)
        and all(isinstance(x, dict) and set(x) == _HTTP_X_KEYS and x["method"] in ("GET", "HEAD", "DELETE", "POST", "PUT",
                                                                                  "PATCH")
                and text(x["path"], False) and text(x["query"]) and isinstance(x["status"], int) and 0 < x["status"] < 1000
                and isinstance(x["statustext"], str) and text(x["mediatype"]) and isinstance(x["body"], str)
                for x in p["exchanges"])
        for p in peers)  # fmt: skip
    if not ok:
        raise ec.Unsupported(f'scenario {sc.get("name")}: "http_peers" lists {{scheme, host, port, urimap, path, exchanges: '
                          "[{method, path, query, status, statustext, mediatype, body}]}", ["WEB OPEN"])  # fmt: skip
    return peers


def http_peers_cfg(peers: list[dict[str, Any]], enc: str) -> str:
    """#4767 (X35): the stub's $GGCICS_HTTP file (ggcics.c GGCWOPN): `P SCHEME HOSTHEX PORT URIMAP|- PATHHEX|-` per peer,
    then `X METHOD PATHHEX QUERYHEX|- STATUS STATUSTEXTHEX|- MEDIATYPEHEX|- BODYHEX|-` per response, hex in the data's page."""

    def hx(v: str | None) -> str:
        return v.encode(enc).hex().upper() if v else "-"

    lines = []
    for p in peers:
        lines.append(f"P {p['scheme']} {hx(p['host'])} {p['port']} {p['urimap'] or '-'} {hx(p['path'])}")
        lines += [f"X {x['method']} {hx(x['path'])} {hx(x['query'])} {x['status']} {hx(x['statustext'])} "
                  f"{hx(x['mediatype'])} {hx(x['body'])}" for x in p["exchanges"]]  # fmt: skip
    return "".join(f"{ln}\n" for ln in lines)


_HTTP_REQ_KEYS = {"scheme", "host", "port", "method", "version", "path", "query", "headers", "mediatype", "body"}


def http_request(case: dict[str, Any], sc: dict[str, Any]) -> dict[str, Any] | None:
    """#4767 zECS (X37): the inbound HTTP request the task serves -- the scenario's "http_request", else the case's: {"scheme":
    "HTTP" | "HTTPS", "host", "port", "method", "version" ("HTTP/1.1"), "path" ("" for none), "query" ("" for none), "headers": [[name,
    value], ...], "mediatype" and "body" (both null: no body)}. Stated on both sides (the stub's $GGCICS_WEBREQ,
    CicsTask.withHttpRequest); WEB SEND, WEB RECEIVE, WEB EXTRACT and WEB READ / WRITE HTTPHEADER need it (X37, X38).
    Unstated, None: both runtimes refuse them by name."""
    req = sc.get("http_request", case.get("http_request"))
    if req is None:
        return None

    def text(v: Any, blank: bool = False) -> bool:
        return isinstance(v, str) and (blank or bool(v)) and not any(c.isspace() for c in v)

    ok = (isinstance(req, dict) and set(req) == _HTTP_REQ_KEYS and req["scheme"] in ("HTTP", "HTTPS")
          and text(req["host"]) and isinstance(req["port"], int) and 0 < req["port"] <= 65535
          and req["method"] in ("GET", "HEAD", "DELETE", "POST", "PUT", "PATCH") and text(req["version"])
          and text(req["path"], True) and isinstance(req["query"], str) and not any(c.isspace() for c in req["query"])
          and isinstance(req["headers"], list)
          and all(isinstance(h, list) and len(h) == 2 and text(h[0]) and isinstance(h[1], str) for h in req["headers"])
          and (req["mediatype"] is None) == (req["body"] is None)
          and (req["mediatype"] is None or (text(req["mediatype"]) and isinstance(req["body"], str))))  # fmt: skip
    if not ok:
        raise ec.Unsupported(f'scenario {sc.get("name")}: "http_request" is {{scheme, host, port, method, version, path, query, '
                          "headers: [[name, value]], mediatype, body}", ["WEB SEND"])  # fmt: skip
    return req


def http_request_cfg(req: dict[str, Any], enc: str) -> str:
    """#4767 (X37, X38): the stub's $GGCICS_WEBREQ file (ggcics.c webreq_load): `R SCHEME HOSTHEX PORT METHOD PATHHEX
    QUERYHEX|-`, `V VERSIONHEX`, `B MEDIAHEX BODYHEX|-` (a request with a body) and a `H NAMEHEX VALUEHEX|-` line per header,
    hex in the data's page."""

    def hx(v: str | None) -> str:
        return v.encode(enc).hex().upper() if v else "-"

    lines = [f"R {req['scheme']} {hx(req['host'])} {req['port']} {req['method']} {hx(req['path'])} {hx(req['query'])}",
             f"V {hx(req['version'])}"]  # fmt: skip
    if req["body"] is not None:  # (#4767 X38: WEB RECEIVE reads the body and its media type)
        lines.append(f"B {hx(req['mediatype'])} {hx(req['body'])}")
    lines += [f"H {hx(n)} {hx(v)}" for n, v in req["headers"]]
    return "".join(f"{ln}\n" for ln in lines)


_TCPIP_KEYS = {"client_addr", "client_name", "server_addr", "server_name", "port", "ssl_type"}


def tcpip(case: dict[str, Any], sc: dict[str, Any]) -> dict[str, Any] | None:
    """#4972 (X38): the TCP/IP connection the task was started on -- the scenario's "tcpip", else the case's: {"client_addr",
    "server_addr" (IPv4 dotted decimal: any other text is refused by both runtimes), "client_name", "server_name" (null: the
    DNS knows none), "port", "ssl_type" ("SSL", "NOSSL", "CLIENTAUTH", "ATTLSAWARE")}. Stated on both sides (the stub's
    $GGCICS_TCPIP, CicsTask.withTcpip); EXTRACT TCPIP needs it. Unstated, None: both runtimes refuse it by name."""
    conn = sc.get("tcpip", case.get("tcpip"))
    if conn is None:
        return None

    def text(v: Any) -> bool:
        return isinstance(v, str) and bool(v) and not any(c.isspace() for c in v)

    ok = (isinstance(conn, dict) and set(conn) == _TCPIP_KEYS and text(conn["client_addr"]) and text(conn["server_addr"])
          and (conn["client_name"] is None or text(conn["client_name"]))
          and (conn["server_name"] is None or text(conn["server_name"]))
          and isinstance(conn["port"], int) and 0 < conn["port"] <= 65535
          and conn["ssl_type"] in ("SSL", "NOSSL", "CLIENTAUTH", "ATTLSAWARE"))  # fmt: skip
    if not ok:
        raise ec.Unsupported(f'scenario {sc.get("name")}: "tcpip" is {{client_addr, client_name, server_addr, server_name, '
                          "port, ssl_type}", ["EXTRACT TCPIP"])  # fmt: skip
    return conn


def tcpip_cfg(conn: dict[str, Any], enc: str) -> str:
    """#4972 (X38): the stub's $GGCICS_TCPIP file (ggcics.c tcpip_load): `T CLIENTADDR CLIENTNAMEHEX|- SERVERADDR
    SERVERNAMEHEX|- PORT SSLTYPE`, the names in hex in the data's page."""

    def hx(v: str | None) -> str:
        return v.encode(enc).hex().upper() if v else "-"

    return (f"T {conn['client_addr']} {hx(conn['client_name'])} {conn['server_addr']} {hx(conn['server_name'])} "
            f"{conn['port']} {conn['ssl_type']}\n")  # fmt: skip


def _web_requires(key: str, option: str, needed: str) -> str:
    """#4767: the message of the command's `requires` rule from `option` to `needed`, as the translator words it."""
    return next(
        g.msg for g in ec.SPEC[key].groups if g.kind == "requires" and g.options[0] == option and needed in g.any_of
    )


def _web_parse(opts: dict[str, str | None], labels: list[str] | None) -> list[str]:
    """#4767 zECS (register X36): WEB PARSE URL -> GGCWPRS (URLLENGTH in GG-LEN, HOSTLENGTH / PATHLENGTH / QUERYSTRLEN in
    GG-HOURS / GG-MINS / GG-SECS, GG-FLAGS names SCHEME HOST PATH QUERY given; the stub writes the pieces), then on NORMAL
    the pieces' lengths and PORTNUMBER (GG-NUM) moved back to the program's fields. The option rules as the det
    translator's."""
    key = "WEB PARSE URL"
    ec._check_spec(key, opts, ("WEB", "PARSE"), lambda bad: [f"{key} {o}" for o in bad])
    for o in ("URL", "URLLENGTH"):
        if not opts.get(o):
            raise ec.Unsupported(ec._rule(key, "required", o), [key])
    for a, n in (("HOST", "HOSTLENGTH"), ("PATH", "PATHLENGTH"), ("QUERYSTRING", "QUERYSTRLEN")):
        if (a in opts) != (n in opts):
            raise ec.Unsupported(_web_requires(key, a, n), [key])
        if a in opts and not (opts[a] and opts[n]):
            raise ec.Unsupported(ec.NEEDS_ARGUMENT, [key])
    for o in ("SCHEMENAME", "PORTNUMBER"):
        if o in opts and not opts[o]:
            raise ec.Unsupported(ec.NEEDS_ARGUMENT, [key])
    for o in ("URL", "SCHEMENAME", "HOST", "PATH", "QUERYSTRING"):
        if opts.get(o) and ec._literal(opts[o]):
            raise ec.Unsupported(f"{key} {o} as a literal: a data area is the COBOL form", [key])
    given = [w for o, w in (("SCHEMENAME", "SCHEME"), ("HOST", "HOST"), ("PATH", "PATH"), ("QUERYSTRING", "QUERY"))
             if o in opts]  # fmt: skip
    lines = [f"MOVE {opts['URLLENGTH']} TO GG-LEN"]
    for n, gg in (("HOSTLENGTH", "GG-HOURS"), ("PATHLENGTH", "GG-MINS"), ("QUERYSTRLEN", "GG-SECS")):
        lines.append(f"MOVE {opts.get(n) or '0'} TO {gg}")
    lines.append(f"MOVE '{' '.join(given)}' TO GG-FLAGS" if given else "MOVE SPACES TO GG-FLAGS")
    args = []
    for o in ("URL", "SCHEMENAME", "HOST", "PATH", "QUERYSTRING"):
        area = opts.get(o) or "GG-QNAME"  # (an option not given: a placeholder the stub does not read)
        args += [f"BY REFERENCE {area}", f"BY VALUE LENGTH OF {area}"]
    back = [f"    MOVE {gg} TO {opts[n]}" for n, gg in (("HOSTLENGTH", "GG-HOURS"), ("PATHLENGTH", "GG-MINS"),
                                                      ("QUERYSTRLEN", "GG-SECS")) if opts.get(n)]  # fmt: skip
    if opts.get("PORTNUMBER"):
        back.append(f"    MOVE GG-NUM TO {opts['PORTNUMBER']}")
    after = ["IF GG-RESP = 0", *back, "END-IF"] if back else []
    return lines + ec._call("GGCWPRS", args) + after + ec._resp(opts, True, labels)


def _web_send(opts: dict[str, str | None], labels: list[str] | None) -> list[str]:
    """#4767 zECS (register X37): WEB SEND -> GGCWSND (FROMLENGTH in GG-LEN, ACTION's CVDA in GG-ITEM (0: none), STATUSCODE in
    GG-NUM (-1: none), STATUSLEN in GG-HOURS (-1: the whole STATUSTEXT area, ASSUMED), the conversion in GG-MINS (0 / 1
    SRVCONVERT / 2 NOSRVCONVERT); GG-FLAGS names MEDIA STEXT given). The option rules as the det translator's."""
    key = "WEB SEND"
    ec._check_spec(key, opts, ("WEB", "SEND"), lambda bad: [f"{key} {o}" for o in bad])
    if sum(o in opts for o in ("FROM", "DOCTOKEN", "CONTAINER")) != 1:
        raise ec.Unsupported(ec._rule(key, "one_of", "FROM"), [key])
    if "CHANNEL" in opts and "CONTAINER" not in opts:
        raise ec.Unsupported(_web_requires(key, "CHANNEL", "CONTAINER"), [key])
    if "FROM" in opts and "FROMLENGTH" not in opts:
        raise ec.Unsupported(_web_requires(key, "FROM", "FROMLENGTH"), [key])
    if "FROMLENGTH" in opts and "FROM" not in opts:
        raise ec.Unsupported(_web_requires(key, "FROMLENGTH", "FROM"), [key])
    if "SRVCONVERT" in opts and "NOSRVCONVERT" in opts:
        raise ec.Unsupported(ec._rule(key, "at_most_one", "SRVCONVERT"), [key])
    if "STATUSLEN" in opts and "STATUSTEXT" not in opts:
        raise ec.Unsupported(_web_requires(key, "STATUSLEN", "STATUSTEXT"), [key])
    if "DOCSTATUS" in opts and "DOCTOKEN" not in opts:
        raise ec.Unsupported(_web_requires(key, "DOCSTATUS", "DOCTOKEN"), [key])
    for o in (
        "FROMLENGTH",
        "DOCTOKEN",
        "CONTAINER",
        "CHANNEL",
        "MEDIATYPE",
        "ACTION",
        "DOCSTATUS",
        "STATUSCODE",
        "STATUSTEXT",
        "STATUSLEN",
    ):
        if o in opts and not opts[o]:
            raise ec.Unsupported(ec.NEEDS_ARGUMENT, [key])
    for o in ("FROM", "DOCTOKEN", "MEDIATYPE", "STATUSTEXT"):
        if opts.get(o) and ec._literal(opts[o]):
            raise ec.Unsupported(f"{key} {o} as a literal: a data area is the COBOL form", [key])
    conv = 1 if "SRVCONVERT" in opts else 2 if "NOSRVCONVERT" in opts else 0
    given = [w for o, w in (("MEDIATYPE", "MEDIA"), ("STATUSTEXT", "STEXT"), ("CHANNEL", "CHANNEL")) if o in opts]
    lines = [f"MOVE {opts.get('FROMLENGTH') or '0'} TO GG-LEN", f"MOVE {opts.get('ACTION') or '0'} TO GG-ITEM",
             f"MOVE {opts.get('STATUSCODE') or '-1'} TO GG-NUM", f"MOVE {opts.get('STATUSLEN') or '-1'} TO GG-HOURS",
             f"MOVE {conv} TO GG-MINS", f"MOVE '{' '.join(given)}' TO GG-FLAGS" if given else "MOVE SPACES TO GG-FLAGS"]  # fmt: skip
    if "DOCTOKEN" in opts:  # #4941 (X37): DOCSTATUS's CVDA in GG-SECS (0: none; DOCDELETE 295, NODOCDELETE 296)
        lines.append(f"MOVE {opts.get('DOCSTATUS') or '0'} TO GG-SECS")
    args = []
    for o in ("DOCTOKEN" if "DOCTOKEN" in opts else "FROM", "MEDIATYPE", "STATUSTEXT"):
        area = opts.get(o) or "GG-QNAME"  # (an option not given: a placeholder the stub does not read)
        args += [f"BY REFERENCE {area}", f"BY VALUE LENGTH OF {area}"]
    if "CONTAINER" in opts:  # #5037 (X37): the response is a container's data (GG-QNAME its name, GG-CHAN its channel)
        lines.append(f"MOVE {opts['CONTAINER']} TO GG-QNAME")
        if "CHANNEL" in opts:
            lines.append(f"MOVE {opts['CHANNEL']} TO GG-CHAN")
        args = []
        for o in ("MEDIATYPE", "STATUSTEXT"):
            area = opts.get(o) or "GG-QNAME"
            args += [f"BY REFERENCE {area}", f"BY VALUE LENGTH OF {area}"]
        return lines + ec._call("GGCWSCT", args) + ec._resp(opts, True, labels)
    # (#4767 X37: DOCTOKEN -> GGCWSDC, the response being the document the token names)
    return lines + ec._call("GGCWSDC" if "DOCTOKEN" in opts else "GGCWSND", args) + ec._resp(opts, True, labels)


def _web_extract(opts: dict[str, str | None], labels: list[str] | None, key: str = "WEB EXTRACT") -> list[str]:
    """#4767 zECS (register X38): WEB EXTRACT (server) -> GGCWEXT (HOSTLENGTH / METHODLENGTH / VERSIONLEN / PATHLENGTH /
    QUERYSTRLEN in GG-LEN / GG-HOURS / GG-MINS / GG-SECS / GG-ITEM, each moved back as the piece's length; GG-FLAGS names HOST
    METHOD VERSION PATH QUERY given; the stub writes the pieces, the port in GG-NUM and the scheme in GG-NAME1), then on NORMAL
    the lengths, PORTNUMBER, SCHEME (a CVDA: 1096 HTTP, 1029 HTTPS) and REQUESTTYPE (1033 HTTPYES) moved to the program's
    fields. The option rules as the det translator's. #4972: EXTRACT WEB (`key`) is the same command, IBM's synonym."""
    ec._check_spec(key, opts, tuple(key.split()), lambda bad: [f"{key} {o}" for o in bad])
    pieces = (("HOST", "HOSTLENGTH", "GG-LEN"), ("HTTPMETHOD", "METHODLENGTH", "GG-HOURS"),
              ("HTTPVERSION", "VERSIONLEN", "GG-MINS"), ("PATH", "PATHLENGTH", "GG-SECS"),
              ("QUERYSTRING", "QUERYSTRLEN", "GG-ITEM"))  # fmt: skip
    for a, n, _ in pieces:
        if (a in opts) != (n in opts):
            raise ec.Unsupported(_web_requires(key, a, n), [key])
        if a in opts and not (opts[a] and opts[n]):
            raise ec.Unsupported(ec.NEEDS_ARGUMENT, [key])
        if opts.get(a) and ec._literal(opts[a]):
            raise ec.Unsupported(f"{key} {a} as a literal: a data area is the COBOL form", [key])
    for o in ("SCHEME", "PORTNUMBER", "REQUESTTYPE"):
        if o in opts and not opts[o]:
            raise ec.Unsupported(ec.NEEDS_ARGUMENT, [key])
    words = {"HOST": "HOST", "HTTPMETHOD": "METHOD", "HTTPVERSION": "VERSION", "PATH": "PATH", "QUERYSTRING": "QUERY"}
    given = [words[a] for a, _, _ in pieces if a in opts]
    lines = [f"MOVE {opts[n]} TO {gg}" if n in opts else f"MOVE 0 TO {gg}" for _, n, gg in pieces]
    lines.append(f"MOVE '{' '.join(given)}' TO GG-FLAGS" if given else "MOVE SPACES TO GG-FLAGS")
    args = []
    for a, _, _ in pieces:
        area = opts.get(a) or "GG-QNAME"  # (a piece not asked for: a placeholder the stub does not read)
        args += [f"BY REFERENCE {area}", f"BY VALUE LENGTH OF {area}"]
    back = [f"    MOVE {gg} TO {opts[n]}" for _, n, gg in pieces if n in opts]
    if opts.get("PORTNUMBER"):
        back.append(f"    MOVE GG-NUM TO {opts['PORTNUMBER']}")
    if opts.get("SCHEME"):
        back += [f"    MOVE 1096 TO {opts['SCHEME']}", f"    IF GG-NAME1(1:5) = 'HTTPS'", f"        MOVE 1029 TO {opts['SCHEME']}",
                 "    END-IF"]  # fmt: skip
    if opts.get("REQUESTTYPE"):
        back.append(f"    MOVE 1033 TO {opts['REQUESTTYPE']}")
    after = ["IF GG-RESP = 0", *back, "END-IF"] if back else []
    return lines + ec._call("GGCWEXT", args) + after + ec._resp(opts, True, labels)


def _extract_tcpip(opts: dict[str, str | None], labels: list[str] | None) -> list[str]:
    """#4972 zECS (register X38): EXTRACT TCPIP -> GGCTCPX (CADDRLENGTH / CNAMELENGTH / SADDRLENGTH / SNAMELENGTH in GG-LEN /
    GG-HOURS / GG-MINS / GG-SECS, 0 for an area asked for whose length option is missing, each moved back as the piece's
    length; GG-FLAGS names A1 N1 A2 N2 the areas given and U1 U2 F1 F2 the client / server address number and address
    family asked for), then on NORMAL each number from GGCTCPN (CLIENTADDRNU, SERVERADDRNU, PORTNUMNU, SSLTYPE's CVDA)
    and the families (IPV4, 300) moved to the program's fields. The option rules as the det translator's."""
    key = "EXTRACT TCPIP"
    ec._check_spec(key, opts, ("EXTRACT", "TCPIP"), lambda bad: [f"{key} {o}" for o in bad])
    pieces = (("CLIENTADDR", "CADDRLENGTH", "GG-LEN", "A1"), ("CLIENTNAME", "CNAMELENGTH", "GG-HOURS", "N1"),
              ("SERVERADDR", "SADDRLENGTH", "GG-MINS", "A2"), ("SERVERNAME", "SNAMELENGTH", "GG-SECS", "N2"))  # fmt: skip
    for a, n, _, _ in pieces:
        if n in opts and a not in opts:
            raise ec.Unsupported(_web_requires(key, n, a), [key])
        if a in opts and (not opts[a] or ec._literal(opts[a])):
            raise ec.Unsupported(
                ec.NEEDS_ARGUMENT if not opts[a] else f"{key} {a} as a literal: a data area is the COBOL form", [key]
            )
        if n in opts and not opts[n]:
            raise ec.Unsupported(ec.NEEDS_ARGUMENT, [key])
    numbers = (("CLIENTADDRNU", "U1"), ("SERVERADDRNU", "U2"), ("CLNTIPFAMILY", "F1"), ("SRVRIPFAMILY", "F2"))
    for o in ("CLIENTADDRNU", "SERVERADDRNU", "CLNTIPFAMILY", "SRVRIPFAMILY", "PORTNUMNU", "SSLTYPE"):
        if o in opts and not opts[o]:
            raise ec.Unsupported(ec.NEEDS_ARGUMENT, [key])
    given = [w for a, _, _, w in pieces if a in opts] + [w for o, w in numbers if o in opts]
    lines = [f"MOVE {(opts.get(n) or '0') if a in opts else '0'} TO {gg}" for a, n, gg, _ in pieces]
    lines.append(f"MOVE '{' '.join(given)}' TO GG-FLAGS" if given else "MOVE SPACES TO GG-FLAGS")
    args = []
    for a, _, _, _ in pieces:
        area = opts.get(a) or "GG-QNAME"  # (an area not asked for: a placeholder the stub does not read)
        args += [f"BY REFERENCE {area}", f"BY VALUE LENGTH OF {area}"]
    back = [f"    MOVE {gg} TO {opts[n]}" for a, n, gg, _ in pieces if n in opts and a in opts]
    for o, token in (("CLIENTADDRNU", "CNU"), ("SERVERADDRNU", "SNU"), ("PORTNUMNU", "PORT"), ("SSLTYPE", "SSL")):
        if opts.get(o):
            back += [
                f"    MOVE '{token}' TO GG-FLAGS",
                "    CALL 'GGCTCPN' USING GG-CICS",
                f"    MOVE GG-NUM TO {opts[o]}",
            ]
    back += [
        f"    MOVE 300 TO {opts[o]}" for o in ("CLNTIPFAMILY", "SRVRIPFAMILY") if opts.get(o)
    ]  # (IPV4: IPv6 is refused)
    after = ["IF GG-RESP = 0", *back, "END-IF"] if back else []
    return lines + ec._call("GGCTCPX", args) + after + ec._resp(opts, True, labels)


def _web_receive(opts: dict[str, str | None], labels: list[str] | None) -> list[str]:
    """#4767 zECS (register X38): WEB RECEIVE INTO (server) -> GGCWRCV (MAXLENGTH in GG-NUM; GG-FLAGS MEDIA when MEDIATYPE is
    given; the stub writes INTO and MEDIATYPE and sets GG-LEN to the bytes returned), then on NORMAL / LENGERR 57 LENGTH moved
    from GG-LEN. #4771 (X47): SET(pointer) -> GGCWRCS, the body in a new block the pointer addresses (MAXLENGTH optional: all
    the data). The option rules as the det translator's."""
    key = "WEB RECEIVE"
    ec._check_spec(key, opts, ("WEB", "RECEIVE"), lambda bad: [f"{key} {o}" for o in bad])
    if ("INTO" in opts) == ("SET" in opts) or not (opts.get("INTO") or opts.get("SET")):
        raise ec.Unsupported(ec._rule(key, "one_of", "INTO"), [key])
    if "INTO" in opts and not opts.get("MAXLENGTH"):
        raise ec.Unsupported(_web_requires(key, "INTO", "MAXLENGTH"), [key])
    if "SET" in opts and not opts.get("LENGTH"):
        raise ec.Unsupported(_web_requires(key, "SET", "LENGTH"), [key])
    if "SRVCONVERT" in opts and "NOSRVCONVERT" in opts:
        raise ec.Unsupported(ec._rule(key, "at_most_one", "SRVCONVERT"), [key])
    for o in ("INTO", "MEDIATYPE"):
        if o in opts and (not opts[o] or ec._literal(opts[o])):
            raise ec.Unsupported(
                ec.NEEDS_ARGUMENT if not opts[o] else f"{key} {o} as a literal: a data area is the COBOL form", [key]
            )
    if "LENGTH" in opts and not opts["LENGTH"]:
        raise ec.Unsupported(ec.NEEDS_ARGUMENT, [key])
    lines = [
        f"MOVE {opts['MAXLENGTH']} TO GG-NUM" if opts.get("MAXLENGTH") else "MOVE 2147483647 TO GG-NUM",
        "MOVE 'MEDIA' TO GG-FLAGS" if "MEDIATYPE" in opts else "MOVE SPACES TO GG-FLAGS",
    ]
    media = opts.get("MEDIATYPE") or "GG-QNAME"
    if "SET" in opts:
        args = [f"BY REFERENCE {ec._pointer(key, opts['SET'])}", f"BY REFERENCE {media}", f"BY VALUE LENGTH OF {media}"]
        entry = "GGCWRCS"
    else:
        args = [f"BY REFERENCE {opts['INTO']}", f"BY VALUE LENGTH OF {opts['INTO']}", f"BY REFERENCE {media}",
                f"BY VALUE LENGTH OF {media}"]  # fmt: skip
        entry = "GGCWRCV"
    after = (
        ["IF GG-RESP = 0 OR GG-RESP2 = 57", f"    MOVE GG-LEN TO {opts['LENGTH']}", "END-IF"]
        if opts.get("LENGTH")
        else []
    )
    return lines + ec._call(entry, args) + after + ec._resp(opts, True, labels)


def _web_retrieve(opts: dict[str, str | None], labels: list[str] | None) -> list[str]:
    """#4941 (register X41): WEB RETRIEVE DOCTOKEN(area) -> GGCWRTV, which writes the DOCTOKEN of the last ACTION(EVENTUAL)
    document send on NORMAL only. The option rules as the det translator's."""
    key = "WEB RETRIEVE"
    ec._check_spec(key, opts, ("WEB", "RETRIEVE"), lambda bad: [f"{key} {o}" for o in bad])
    if not opts.get("DOCTOKEN"):
        raise ec.Unsupported(ec._rule(key, "required", "DOCTOKEN"), [key])
    if ec._literal(opts["DOCTOKEN"]):
        raise ec.Unsupported(f"{key} DOCTOKEN as a literal: a data area is the COBOL form", [key])
    area = opts["DOCTOKEN"]
    return ec._call("GGCWRTV", [f"BY REFERENCE {area}", f"BY VALUE LENGTH OF {area}"]) + ec._resp(opts, True, labels)


def _web_header(form: str, opts: dict[str, str | None], labels: list[str] | None) -> list[str]:
    """#4767 zECS (register X38): WEB READ HTTPHEADER -> GGCWRDH, WEB WRITE HTTPHEADER -> GGCWWRH (NAMELENGTH in GG-LEN,
    VALUELENGTH in GG-NUM; READ's VALUELENGTH moved back from GG-NUM on NORMAL). The option rules as the det translator's."""
    key = f"WEB {form} HTTPHEADER"
    ec._check_spec(key, opts, ("WEB", form), lambda bad: [f"{key} {o}" for o in bad])
    for o in ("HTTPHEADER", "NAMELENGTH", "VALUE", "VALUELENGTH"):
        if not opts.get(o):
            raise ec.Unsupported(ec._rule(key, "required", o), [key])
    for o in ("HTTPHEADER", "VALUE"):
        if ec._literal(opts[o]):
            raise ec.Unsupported(f"{key} {o} as a literal: a data area is the COBOL form", [key])
    lines = [f"MOVE {opts['NAMELENGTH']} TO GG-LEN", f"MOVE {opts['VALUELENGTH']} TO GG-NUM"]
    args = [f"BY REFERENCE {opts['HTTPHEADER']}", f"BY VALUE LENGTH OF {opts['HTTPHEADER']}",
            f"BY REFERENCE {opts['VALUE']}", f"BY VALUE LENGTH OF {opts['VALUE']}"]  # fmt: skip
    entry = "GGCWRDH" if form == "READ" else "GGCWWRH"
    after = ["IF GG-RESP = 0", f"    MOVE GG-NUM TO {opts['VALUELENGTH']}", "END-IF"] if form == "READ" else []
    return lines + ec._call(entry, args) + after + ec._resp(opts, True, labels)


_WEB_KIND = {"HTTPHEADER": 0, "FORMFIELD": 1, "QUERYPARM": 2}  # GG-ITEM: which pairs a WEB READ / browse form reads


def _web_forms(form: str, opts: dict[str, str | None], labels: list[str] | None) -> list[str]:
    """#4940 (register X38): WEB READ FORMFIELD / QUERYPARM -> GGCWRDP (NAMELENGTH in GG-LEN, VALUELENGTH in GG-NUM, moved
    back when the value was returned, also cut), WEB STARTBROWSE -> GGCWSBR (GG-FLAGS NAME when a name is given), WEB READNEXT
    -> GGCWRNX (both lengths in, the pair's whole lengths out), WEB ENDBROWSE -> GGCWEBR; GG-ITEM names the kind
    (_WEB_KIND). The option rules as the det translator's."""
    kind = next(k for k in _WEB_KIND if k in opts)
    key = f"WEB {form} {kind}"
    ec._check_spec(key, opts, ("WEB", form), lambda bad: [f"{key} {o}" for o in bad])
    item = f"MOVE {_WEB_KIND[kind]} TO GG-ITEM"
    if form == "ENDBROWSE":
        return [item] + ec._call("GGCWEBR", []) + ec._resp(opts, True, labels)
    if form == "STARTBROWSE":
        named = bool(opts.get(kind))
        if kind == "HTTPHEADER" and named:
            raise ec.Unsupported(
                "WEB STARTBROWSE HTTPHEADER: a name to start at is not documented: not modelled", [key]
            )
        if named and not opts.get("NAMELENGTH"):
            raise ec.Unsupported(
                f"WEB STARTBROWSE {kind}(name) without NAMELENGTH (IBM: it is required with a name)", [key]
            )
        if "NAMELENGTH" in opts and not named:
            raise ec.Unsupported(f"WEB STARTBROWSE {kind} NAMELENGTH without a name", [key])
        if named and ec._literal(opts[kind]):
            raise ec.Unsupported(f"{key} {kind} as a literal: a data area is the COBOL form", [key])
        area = opts[kind] if named else "GG-QNAME"
        lines = [item, f"MOVE {opts['NAMELENGTH']} TO GG-LEN" if named else "MOVE 0 TO GG-LEN",
                 "MOVE 'NAME' TO GG-FLAGS" if named else "MOVE SPACES TO GG-FLAGS"]  # fmt: skip
        return (
            lines
            + ec._call("GGCWSBR", [f"BY REFERENCE {area}", f"BY VALUE LENGTH OF {area}"])
            + ec._resp(opts, True, labels)
        )
    for o in (kind, "NAMELENGTH", "VALUE", "VALUELENGTH"):
        if not opts.get(o):
            raise ec.Unsupported(ec._rule(key, "required", o), [key])
    for o in (kind, "VALUE"):
        if ec._literal(opts[o]):
            raise ec.Unsupported(f"{key} {o} as a literal: a data area is the COBOL form", [key])
    lines = [item, f"MOVE {opts['NAMELENGTH']} TO GG-LEN", f"MOVE {opts['VALUELENGTH']} TO GG-NUM"]
    args = [f"BY REFERENCE {opts[kind]}", f"BY VALUE LENGTH OF {opts[kind]}",
            f"BY REFERENCE {opts['VALUE']}", f"BY VALUE LENGTH OF {opts['VALUE']}"]  # fmt: skip
    if form == "READ":
        after = [
            "IF GG-RESP = 0 OR (GG-RESP = 22 AND GG-RESP2 = 5)",
            f"    MOVE GG-NUM TO {opts['VALUELENGTH']}",
            "END-IF",
        ]
        return lines + ec._call("GGCWRDP", args) + after + ec._resp(opts, True, labels)
    after = ["IF GG-RESP = 0 OR (GG-RESP = 22 AND (GG-RESP2 = 4 OR GG-RESP2 = 5))",
             f"    MOVE GG-LEN TO {opts['NAMELENGTH']}", f"    MOVE GG-NUM TO {opts['VALUELENGTH']}", "END-IF"]  # fmt: skip
    return lines + ec._call("GGCWRNX", args) + after + ec._resp(opts, True, labels)


def _web(opts: dict[str, str | None], labels: list[str] | None) -> list[str]:
    """#4767 zECS (register X35): WEB OPEN -> GGCWOPN (GG-FLAGS URIMAP, the name in GG-NAME1; or HOST [PORT], HOSTLENGTH in
    GG-LEN, the SCHEME CVDA in GG-ITEM, PORTNUMBER in GG-NUM), the SESSTOKEN area written by the stub on NORMAL; WEB
    CONVERSE -> GGCWCNV (the METHOD CVDA in GG-NUM, PATHLENGTH / QUERYSTRLEN / FROMLENGTH in GG-HOURS / GG-MINS / GG-SECS,
    MAXLENGTH -- INTO's length when omitted -- in GG-LEN, STATUSLEN in GG-ITEM (-1: none); GG-FLAGS names PATH QUERY FROM
    MEDIA given; the stub writes INTO / STATUSTEXT / MEDIATYPE), TOLENGTH and STATUSCODE moved from GG-LEN / GG-NUM when a
    response came back (NORMAL, LENGERR 57); WEB CLOSE -> GGCWCLS. The option rules as the det translator's."""
    form = next(f for f in ("OPEN", "CONVERSE", "CLOSE") if f in opts)
    key = f"WEB {form}"
    ec._check_spec(key, opts, ("WEB", form), lambda bad: [f"{key} {o}" for o in bad])
    tok = opts.get("SESSTOKEN")
    if not tok:
        raise ec.Unsupported(ec._rule(key, "required", "SESSTOKEN"), [key])
    for o in ("SESSTOKEN", "HOST", "PATH", "QUERYSTRING", "FROM", "MEDIATYPE", "INTO", "STATUSTEXT"):
        if opts.get(o) and ec._literal(opts[o]):  # (IBM's COBOL form takes a data area)
            raise ec.Unsupported(f"{key} {o} as a literal: a data area is the COBOL form", [key])
    if form == "CLOSE":
        return ec._call("GGCWCLS", [f"BY REFERENCE {tok}"]) + ec._resp(opts, True, labels)
    if form == "OPEN":
        if ("URIMAP" in opts) == ("HOST" in opts):
            raise ec.Unsupported(ec._rule(key, "one_of", "URIMAP"), [key])
        if ("HOST" in opts) != ("HOSTLENGTH" in opts):
            raise ec.Unsupported(_web_requires(key, "HOST", "HOSTLENGTH"), [key])
        if "HOST" in opts and "SCHEME" not in opts:
            raise ec.Unsupported(_web_requires(key, "HOST", "SCHEME"), [key])
        for o in ("PORTNUMBER", "SCHEME"):
            if o in opts and "HOST" not in opts:
                raise ec.Unsupported(_web_requires(key, "PORTNUMBER", "HOST").format(o), [key])
        if "URIMAP" in opts:
            if not opts["URIMAP"]:
                raise ec.Unsupported(ec.NEEDS_ARGUMENT, [key])
            lines = [f"MOVE {opts['URIMAP']} TO GG-NAME1", "MOVE 'URIMAP' TO GG-FLAGS"]
            return (lines + ec._call("GGCWOPN", [f"BY REFERENCE {tok}", "BY REFERENCE GG-QNAME", "BY VALUE LENGTH OF GG-QNAME"])
                    + ec._resp(opts, True, labels))  # fmt: skip
        for o in ("HOST", "HOSTLENGTH", "SCHEME", "PORTNUMBER"):
            if o in opts and not opts[o]:
                raise ec.Unsupported(ec.NEEDS_ARGUMENT, [key])
        lines = [f"MOVE {opts['HOSTLENGTH']} TO GG-LEN", f"MOVE {opts['SCHEME']} TO GG-ITEM"]
        if opts.get("PORTNUMBER"):
            lines += [f"MOVE {opts['PORTNUMBER']} TO GG-NUM", "MOVE 'HOST PORT' TO GG-FLAGS"]
        else:
            lines.append("MOVE 'HOST' TO GG-FLAGS")
        host = opts["HOST"]
        return (lines + ec._call("GGCWOPN", [f"BY REFERENCE {tok}", f"BY REFERENCE {host}", f"BY VALUE LENGTH OF {host}"])
                + ec._resp(opts, True, labels))  # fmt: skip
    for o in ("METHOD", "INTO"):
        if not opts.get(o):
            raise ec.Unsupported(ec._rule(key, "required", o), [key])
    for a, n in (("PATH", "PATHLENGTH"), ("QUERYSTRING", "QUERYSTRLEN"), ("FROM", "FROMLENGTH"),
                 ("STATUSTEXT", "STATUSLEN")):  # fmt: skip
        if (a in opts) != (n in opts):
            raise ec.Unsupported(_web_requires(key, a, n), [key])
        if a in opts and not (opts[a] and opts[n]):
            raise ec.Unsupported(ec.NEEDS_ARGUMENT, [key])
    if sum(o in opts for o in ("CLIENTCONV", "CLICONVERT", "NOINCONVERT", "NOOUTCONVERT", "NOCLICONVERT")) > 1:
        raise ec.Unsupported(ec._rule(key, "at_most_one", "CLIENTCONV"), [key])
    if "CLIENTCONV" in opts and not opts["CLIENTCONV"]:
        raise ec.Unsupported(ec.NEEDS_ARGUMENT, [key])
    into = opts["INTO"]
    lines = [f"MOVE {opts['METHOD']} TO GG-NUM", f"MOVE {opts.get('MAXLENGTH') or f'LENGTH OF {into}'} TO GG-LEN",
             f"MOVE {opts.get('STATUSLEN') or '-1'} TO GG-ITEM"]  # fmt: skip
    for n, gg in (("PATHLENGTH", "GG-HOURS"), ("QUERYSTRLEN", "GG-MINS"), ("FROMLENGTH", "GG-SECS")):
        lines.append(f"MOVE {opts.get(n) or '0'} TO {gg}")
    given = [w for o, w in (("PATH", "PATH"), ("QUERYSTRING", "QUERY"), ("FROM", "FROM"), ("MEDIATYPE", "MEDIA"))
             if opts.get(o)]  # fmt: skip
    lines.append(f"MOVE '{' '.join(given)}' TO GG-FLAGS" if given else "MOVE SPACES TO GG-FLAGS")
    args = [f"BY REFERENCE {tok}"]
    for o in ("PATH", "QUERYSTRING", "FROM", "MEDIATYPE", "INTO", "STATUSTEXT"):
        area = opts.get(o)
        area = area or "GG-QNAME"  # (an option not given: a placeholder the stub does not read)
        args += [f"BY REFERENCE {area}", f"BY VALUE LENGTH OF {area}"]
    after = []
    if opts.get("TOLENGTH") or opts.get("STATUSCODE"):
        after = ["IF GG-RESP = 0 OR (GG-RESP = 22 AND GG-RESP2 = 57)"]
        after += [f"    MOVE GG-LEN TO {opts['TOLENGTH']}"] if opts.get("TOLENGTH") else []
        after += [f"    MOVE GG-NUM TO {opts['STATUSCODE']}"] if opts.get("STATUSCODE") else []
        after.append("END-IF")
    return lines + ec._call("GGCWCNV", args) + after + ec._resp(opts, True, labels)


def _cobol_web(kv: dict[str, str], data: bytes, enc: str) -> dict[str, Any]:
    """#4767 (X35): a WEB-CONVERSE line of the stub's events (hex fields in the data's page) as CicsTask records it."""

    def text(h: str) -> str:
        return "" if h == "-" else bytes.fromhex(h).decode(enc)

    body = kv.get("body") == "1"
    return {"host": text(kv["host"]), "method": kv["method"], "path": text(kv["path"]), "query": text(kv["query"]),
            "mediatype": text(kv["media"]) if body else None, "body": data.decode(enc) if body else None,
            "resp": int(kv["resp"]), "resp2": int(kv["resp2"])}  # fmt: skip


def _cobol_web_open(kv: dict[str, str], enc: str) -> dict[str, Any]:
    """#4767 (X35): a WEB-OPEN line of the stub's events (the host in hex, '-' none; the scheme as named, '-' none) as
    CicsTask records it."""
    return {"host": "" if kv["host"] == "-" else bytes.fromhex(kv["host"]).decode(enc),
            "scheme": None if kv["scheme"] == "-" else kv["scheme"],
            "resp": int(kv["resp"]), "resp2": int(kv["resp2"])}  # fmt: skip


def _cobol_web_send(kv: dict[str, str], data: bytes, enc: str) -> dict[str, Any]:
    """#4767 (X37): a WEB-SEND line of the stub's events (hex fields in the data's page) as CicsTask records it."""

    def text(h: str) -> str | None:
        return None if h == "-" else bytes.fromhex(h).decode(enc)

    return {"status": int(kv["status"]), "statustext": text(kv["stext"]), "mediatype": text(kv["media"]),
            "body": data.decode(enc), "action": kv["action"], "resp": int(kv["resp"]), "resp2": int(kv["resp2"])}  # fmt: skip


def _cobol_web_header(kv: dict[str, str], enc: str) -> dict[str, Any]:
    """#4767 (X38): a WEB-HEADER line of the stub's events (hex fields in the data's page) as CicsTask records it."""
    return {"name": bytes.fromhex(kv["name"]).decode(enc), "value": bytes.fromhex(kv["value"]).decode(enc),
            "resp": int(kv["resp"]), "resp2": int(kv["resp2"])}  # fmt: skip


def _cobol_web_receive(kv: dict[str, str], data: bytes, enc: str) -> dict[str, Any]:
    """#4767 (X38): a WEB-RECEIVE line of the stub's events (the media type in hex, the bytes returned as the data) as CicsTask
    records it; LENGERR 16 returned nothing (no body)."""
    none = kv["resp2"] == "16"
    return {"mediatype": None if kv["media"] == "-" else bytes.fromhex(kv["media"]).decode(enc),
            "body": None if none else data.decode(enc), "resp": int(kv["resp"]), "resp2": int(kv["resp2"])}  # fmt: skip
