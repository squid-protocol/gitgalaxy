"""#5274: the web and document commands: WEB, EXTRACT WEB / TCPIP (#4767, #4940, #4941, #4972) and DOCUMENT (#4769), split out of det/cics.py onto CicsTask. `Cics` inherits these methods, and its COMMAND_FAMILIES
registry calls `dispatch`. The translator's shared helpers come from det/cics_common.py (#7153)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gitgalaxy.tools.cobol_to_java.det.cics_common import (
    CicsError,
    _arg,
    _msg,
    _requires,
)


class WebCommands:
    """The web and document commands of `Cics` (det/cics.py), which defines the members declared below."""

    if TYPE_CHECKING:
        g: Any
        gp: Any
        generated: Any
        package: str
        region_used: bool
        passes_bytes: bool

        def __getattr__(self, name: str) -> Any:
            """The members `Cics` defines, for the type checker."""

    def dispatch_web(self, words: list[str], verb: str, key: str, opts: dict, ind: str) -> list[str] | None:  # noqa: ARG002
        """The web and document commands, or None for a command of another family."""
        if key in ("DOCUMENT CREATE", "DOCUMENT RETRIEVE"):  # #4769 (X33): the document handler
            return self.document(key, opts, ind)
        if key in ("WEB OPEN", "WEB CONVERSE", "WEB CLOSE"):  # #4767 (X35): CICS web support, HTTP client
            return self.web(key, opts, ind)
        if key == "WEB PARSE URL":  # #4767 (X36): a URL taken apart, pure
            return self.web_parse(key, opts, ind)
        if key == "WEB SEND":  # #4767 (X37): the response to the stated inbound request
            return self.web_send(key, opts, ind)
        if key in (
            "WEB EXTRACT",
            "EXTRACT WEB",
            "WEB RECEIVE",
            "WEB READ HTTPHEADER",
            "WEB WRITE HTTPHEADER",
            "WEB RETRIEVE",
        ) or key.startswith(
            ("WEB READ FORMFIELD", "WEB READ QUERYPARM", "WEB STARTBROWSE ", "WEB READNEXT ", "WEB ENDBROWSE ")
        ):  # #4767 / #4940 (X38), #4941 (X41)
            return self.web_request(key, opts, ind)
        if key == "EXTRACT TCPIP":  # #4972 (X38): the connection the run states
            return self.extract_tcpip(key, opts, ind)
        return None

    def document(self, key: str, opts: dict, ind: str) -> list[str]:
        """DOCUMENT CREATE / DOCUMENT RETRIEVE (IBM CICS TS, EXEC CICS DOCUMENT CREATE, DOCUMENT RETRIEVE; register X33)
        on the task's documents (CicsTask). CREATE: an empty document, TEXT / BINARY(area) LENGTH(n) (the area's bytes,
        unchanged) or TEMPLATE(name) (the text the installed DOCTEMPLATE yields, as the run states it), its DOCTOKEN
        written on NORMAL only; LENGERR RESP2 1 (negative LENGTH), NOTFND RESP2 3 (no such template). RETRIEVE: the
        document INTO the area, at most MAXLENGTH bytes (rest of INTO left alone), LENGTH its length (the length it needs
        when truncated: LENGERR RESP2 2); NOTFND RESP2 1 (no such token); LENGERR RESP2 1 (MAXLENGTH below zero, no LENGTH).
        Every other option is refused by name by the spec entry (check_options); the rules that need the options together
        are the entry's groups."""
        g = self.g
        r = g.tmpname("doc")
        if not opts.get("DOCTOKEN"):
            raise CicsError(_msg(key, "required", "DOCTOKEN"))
        if key == "DOCUMENT CREATE":
            given = [o for o in ("TEXT", "BINARY", "TEMPLATE") if o in opts]
            if len(given) > 1:
                raise CicsError(_msg(key, "at_most_one", "TEXT"))
            for o in ("TEXT", "BINARY"):
                if o in opts and "LENGTH" not in opts:
                    raise CicsError(_msg(key, "requires", "TEXT"))
            if "LENGTH" in opts and not ("TEXT" in opts or "BINARY" in opts):
                raise CicsError(_msg(key, "requires", "LENGTH"))
            if "TEXT" in opts or "BINARY" in opts:
                area = _arg(opts["TEXT"] if "TEXT" in opts else opts["BINARY"])
                n = self.int_(_arg(opts["LENGTH"]))
                call = f"task.documentCreateData(DetCics.documentBytes({self.read_field(area)}, {n}), {n})"
            elif "TEMPLATE" in opts:
                template = self.name(_arg(opts["TEMPLATE"]))
                call = f"task.documentCreateTemplate({template}, CS)"
            else:
                call = "task.documentCreateEmpty()"
            return [f"{ind}CicsTask.DocumentCreated {r} = {call};",
                    f"{ind}if ({r}.resp() == 0) DetCics.putText({self.field(_arg(opts['DOCTOKEN']))}, {r}.doctoken(), CS);",
                    *self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)]  # fmt: skip
        for o in ("INTO", "MAXLENGTH", "DATAONLY"):
            if o not in opts:
                raise CicsError(_msg(key, "required", o))
        token = self.read_field(_arg(opts["DOCTOKEN"]))
        maxlength = self.int_(_arg(opts["MAXLENGTH"]))
        out = [f"{ind}CicsTask.DocumentData {r} = task.documentRetrieve(Cobol.text({token}, CS), {maxlength});",
               f"{ind}if ({r}.data() != null) DetCics.putDocument({self.field(_arg(opts['INTO']))}, {r}.data());"]  # fmt: skip
        if "LENGTH" in opts:  # (written after MAXLENGTH was read: ZECS gives both the same area)
            out.append(
                f"{ind}if ({r}.length() >= 0) "
                + g.store_into(self.ref(_arg(opts["LENGTH"])), f"BigDecimal.valueOf({r}.length())", False)
            )
        return out + self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)

    def web(self, key: str, opts: dict, ind: str) -> list[str]:
        """WEB OPEN / WEB CONVERSE / WEB CLOSE (IBM CICS TS, EXEC CICS WEB OPEN, WEB CONVERSE, WEB CLOSE; register X35) on
        the HTTP peers the run states (CicsTask.withHttpPeers). OPEN: HOST(area) HOSTLENGTH [PORTNUMBER] SCHEME, or
        URIMAP(name); the SESSTOKEN written on NORMAL only. CONVERSE: the request from METHOD, PATH / PATHLENGTH,
        QUERYSTRING / QUERYSTRLEN, FROM / FROMLENGTH and MEDIATYPE (each area's text and its length, checked by the
        task); on NORMAL or LENGERR 57 the response goes INTO (at most MAXLENGTH, INTO's length when omitted; MAXLENGTH
        read before TOLENGTH is written: zECS names one area for both), TOLENGTH, STATUSCODE, STATUSTEXT (the reason
        phrase's bytes) and MEDIATYPE (blank-padded to 56). CLOSE: NOTOPEN 27 for a token that is no open session's.
        Every other option is refused by name by the spec entry (check_options)."""
        g = self.g
        r = g.tmpname("web")
        if not opts.get("SESSTOKEN"):
            raise CicsError(_msg(key, "required", "SESSTOKEN"))
        if key == "WEB CLOSE":
            tok = f"Cobol.text({self.read_field(_arg(opts['SESSTOKEN']))}, CS)"
            return [f"{ind}int[] {r} = task.webClose({tok});", *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]
        if key == "WEB OPEN":
            if ("URIMAP" in opts) == ("HOST" in opts):
                raise CicsError(_msg(key, "one_of", "URIMAP"))
            if ("HOST" in opts) != ("HOSTLENGTH" in opts):
                raise CicsError(_requires(key, "HOST", "HOSTLENGTH"))
            if "HOST" in opts and "SCHEME" not in opts:
                raise CicsError(_requires(key, "HOST", "SCHEME"))
            for o in ("PORTNUMBER", "SCHEME"):
                if o in opts and "HOST" not in opts:
                    raise CicsError(_requires(key, "PORTNUMBER", "HOST").format(o))
            if "URIMAP" in opts:
                call = f"task.webOpenUrimap({self.name(_arg(opts['URIMAP']))})"
            else:
                host = f"Cobol.text({self.read_field(_arg(opts['HOST']))}, CS)"
                port = self.int_(_arg(opts["PORTNUMBER"])) if "PORTNUMBER" in opts else "0"
                call = (f"task.webOpenHost({host}, {self.int_(_arg(opts['HOSTLENGTH']))}, {port}, "
                        f"{'true' if 'PORTNUMBER' in opts else 'false'}, {self.int_(_arg(opts['SCHEME']))})")  # fmt: skip
            return [f"{ind}CicsTask.WebOpened {r} = {call};",
                    f"{ind}if ({r}.resp() == 0) DetCics.putText({self.field(_arg(opts['SESSTOKEN']))}, {r}.sesstoken(), CS);",
                    *self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)]  # fmt: skip
        for o in ("METHOD", "INTO"):
            if not opts.get(o):
                raise CicsError(_msg(key, "required", o))
        for a, n in (("PATH", "PATHLENGTH"), ("QUERYSTRING", "QUERYSTRLEN"), ("FROM", "FROMLENGTH"),
                     ("STATUSTEXT", "STATUSLEN")):  # fmt: skip
            if (a in opts) != (n in opts):
                raise CicsError(_requires(key, a, n))
        if sum(o in opts for o in ("CLIENTCONV", "CLICONVERT", "NOINCONVERT", "NOOUTCONVERT", "NOCLICONVERT")) > 1:
            raise CicsError(_msg(key, "at_most_one", "CLIENTCONV"))
        if "CLIENTCONV" in opts:  # (its value changes nothing within the model, but it is read as IBM reads it)
            _arg(opts["CLIENTCONV"])

        def text(o: str) -> str:
            return f"Cobol.text({self.read_field(_arg(opts[o]))}, CS)" if o in opts else "null"

        def num(o: str, absent: str) -> str:
            return self.int_(_arg(opts[o])) if o in opts else absent

        into = _arg(opts["INTO"])
        call = (f"task.webConverse({text('SESSTOKEN')}, {num('METHOD', '0')}, {text('PATH')}, {num('PATHLENGTH', '0')}, "
                f"{text('QUERYSTRING')}, {num('QUERYSTRLEN', '0')}, {text('FROM')}, {num('FROMLENGTH', '0')}, "
                f"{text('MEDIATYPE')}, {num('MAXLENGTH', str(self.size(into)))}, {num('STATUSLEN', '-1')}, CS)")  # fmt: skip

        def received(area: str, data: str, what: str) -> str:
            """What a WEB CONVERSE received, at the area's start (the rest left alone); more bytes than the area holds
            refused (PastFrom): CICS writes the storage that follows it, which GnuCOBOL lays out unlike IBM's (X6)."""
            f = self.field(area)
            return (f'{ind}    if ({data}.length > {f}.length()) throw new DetCics.PastFrom("{what} beyond its area: '
                    f'not modelled"); DetCics.put({f}, {data});')  # fmt: skip

        out = [f"{ind}CicsTask.WebResponse {r} = {call};", f"{ind}if ({r}.body() != null) {{",
               received(into, f"{r}.body()", "WEB CONVERSE INTO")]  # fmt: skip
        if "TOLENGTH" in opts:
            out.append(
                f"{ind}    "
                + g.store_into(self.ref(_arg(opts["TOLENGTH"])), f"BigDecimal.valueOf({r}.toLength())", False)
            )
        if "STATUSCODE" in opts:
            out.append(
                f"{ind}    "
                + g.store_into(self.ref(_arg(opts["STATUSCODE"])), f"BigDecimal.valueOf({r}.status())", False)
            )
        if "STATUSTEXT" in opts:
            out.append(received(_arg(opts["STATUSTEXT"]), f"{r}.statusText().getBytes(CS)", "WEB CONVERSE STATUSTEXT"))
        if opts.get("MEDIATYPE"):
            out.append(f"{ind}    DetCics.putText({self.field(_arg(opts['MEDIATYPE']))}, {r}.mediaType(), CS);")
        out.append(f"{ind}}}")
        return out + self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)

    def web_send(self, key: str, opts: dict, ind: str) -> list[str]:
        """WEB SEND (IBM CICS TS, EXEC CICS WEB SEND, server; register X37): CicsTask.webSend takes FROM's text and
        FROMLENGTH, MEDIATYPE's text, ACTION's value (0 when absent), STATUSCODE (-1), STATUSTEXT's text with STATUSLEN
        (-1: the whole area, ASSUMED) and the conversion flag; the response is recorded as WEB-SEND. Every option the
        spec entry does not model is refused by name (check_options)."""
        if sum(o in opts for o in ("FROM", "DOCTOKEN", "CONTAINER")) != 1:
            raise CicsError(_msg(key, "one_of", "FROM"))
        if "CHANNEL" in opts and "CONTAINER" not in opts:
            raise CicsError(_requires(key, "CHANNEL", "CONTAINER"))
        if "FROM" in opts and "FROMLENGTH" not in opts:
            raise CicsError(_requires(key, "FROM", "FROMLENGTH"))
        if "FROMLENGTH" in opts and "FROM" not in opts:
            raise CicsError(_requires(key, "FROMLENGTH", "FROM"))
        if "SRVCONVERT" in opts and "NOSRVCONVERT" in opts:
            raise CicsError(_msg(key, "at_most_one", "SRVCONVERT"))
        if "STATUSLEN" in opts and "STATUSTEXT" not in opts:
            raise CicsError(_requires(key, "STATUSLEN", "STATUSTEXT"))
        if "DOCSTATUS" in opts and "DOCTOKEN" not in opts:
            raise CicsError(_requires(key, "DOCSTATUS", "DOCTOKEN"))

        def text(o: str) -> str:
            return f"Cobol.text({self.read_field(_arg(opts[o]))}, CS)" if o in opts else "null"

        def num(o: str, absent: str) -> str:
            return self.int_(_arg(opts[o])) if o in opts else absent

        conv = 1 if "SRVCONVERT" in opts else 2 if "NOSRVCONVERT" in opts else 0
        r = self.g.tmpname("web")
        if "CONTAINER" in opts:  # #5037 (X37): the response is a container's data
            chan = self.name(_arg(opts["CHANNEL"])) if "CHANNEL" in opts else "null"
            call = (f"task.webSendContainer({chan}, {self.name(_arg(opts['CONTAINER']))}, {text('MEDIATYPE')}, "
                    f"{num('ACTION', '0')}, {num('STATUSCODE', '-1')}, {text('STATUSTEXT')}, {num('STATUSLEN', '-1')}, "
                    f"{conv}, CS)")  # fmt: skip
            return [f"{ind}int[] {r} = {call};", *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]
        if "DOCTOKEN" in opts:  # #4767 (X37): the response is a document the task created (DOCUMENT CREATE)
            call = (f"task.webSendDocument({text('DOCTOKEN')}, {text('MEDIATYPE')}, {num('ACTION', '0')}, "
                    f"{num('STATUSCODE', '-1')}, {text('STATUSTEXT')}, {num('STATUSLEN', '-1')}, {conv}, "
                    f"{num('DOCSTATUS', '0')}, CS)")  # fmt: skip
            return [f"{ind}int[] {r} = {call};", *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]
        frm = text("FROM")
        if "FROM" in opts and self.linkage_record(_arg(opts["FROM"])):  # #6839: an area set onto a larger block
            frm = f"DetCics.fromText({self.read_field(_arg(opts['FROM']))}, {num('FROMLENGTH', '0')}, CS)"
        call = (f"task.webSend({frm}, {num('FROMLENGTH', '0')}, {text('MEDIATYPE')}, {num('ACTION', '0')}, "
                f"{num('STATUSCODE', '-1')}, {text('STATUSTEXT')}, {num('STATUSLEN', '-1')}, {conv})")  # fmt: skip
        return [f"{ind}int[] {r} = {call};", *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]

    def web_parse(self, key: str, opts: dict, ind: str) -> list[str]:
        """WEB PARSE URL (IBM CICS TS, EXEC CICS WEB PARSE URL; register X36): CicsTask.webParse takes the URL area's text
        and URLLENGTH apart; HOSTLENGTH / PATHLENGTH / QUERYSTRLEN are read before the pieces are written and set to
        each piece's length, SCHEMENAME is blank-padded to its area, PORTNUMBER is explicit or 80 / 443. On NORMAL only
        (an error leaves every area alone: ASSUMED). The pieces' areas are checked against the lengths by the task."""
        g = self.g
        for o in ("URL", "URLLENGTH"):
            if not opts.get(o):
                raise CicsError(_msg(key, "required", o))
        for a, n in (("HOST", "HOSTLENGTH"), ("PATH", "PATHLENGTH"), ("QUERYSTRING", "QUERYSTRLEN")):
            if (a in opts) != (n in opts):
                raise CicsError(_requires(key, a, n))
        r = g.tmpname("web")

        def length(n: str) -> str:
            return f"Integer.valueOf({self.int_(_arg(opts[n]))})" if n in opts else "null"

        def cap(a: str) -> str:
            return str(self.size(_arg(opts[a]))) if a in opts else "0"

        call = (f"task.webParse(Cobol.text({self.read_field(_arg(opts['URL']))}, CS), {self.int_(_arg(opts['URLLENGTH']))}, "
                f"{cap('SCHEMENAME')}, {length('HOSTLENGTH')}, {cap('HOST')}, {length('PATHLENGTH')}, {cap('PATH')}, "
                f"{length('QUERYSTRLEN')}, {cap('QUERYSTRING')})")  # fmt: skip
        out = [f"{ind}CicsTask.WebParsed {r} = {call};", f"{ind}if ({r}.resp() == 0) {{"]
        if "SCHEMENAME" in opts:
            out.append(f"{ind}    DetCics.putText({self.field(_arg(opts['SCHEMENAME']))}, {r}.scheme(), CS);")
        for area, ln, piece in (("HOST", "HOSTLENGTH", "host"), ("PATH", "PATHLENGTH", "path"),
                                ("QUERYSTRING", "QUERYSTRLEN", "query")):  # fmt: skip
            if area in opts:
                out.append(f"{ind}    DetCics.putText({self.field(_arg(opts[area]))}, {r}.{piece}(), CS);")
                out.append(
                    f"{ind}    "
                    + g.store_into(self.ref(_arg(opts[ln])), f"BigDecimal.valueOf({r}.{piece}().length())", False)
                )
        if "PORTNUMBER" in opts:
            out.append(
                f"{ind}    "
                + g.store_into(self.ref(_arg(opts["PORTNUMBER"])), f"BigDecimal.valueOf({r}.port())", False)
            )
        out.append(f"{ind}}}")
        return out + self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)

    def web_request(self, key: str, opts: dict, ind: str) -> list[str]:
        """The server reading the request it serves (IBM CICS TS, EXEC CICS WEB EXTRACT, WEB RECEIVE, WEB READ HTTPHEADER,
        WEB WRITE HTTPHEADER; register X38) on the request the run states (CicsTask.withHttpRequest). EXTRACT: each piece
        asked for, its length option read before it is written (the area's size is the cap); on NORMAL the pieces' bytes,
        their lengths, the port, SCHEME's CVDA and REQUESTTYPE's HTTPYES. RECEIVE INTO: the body (at most MAXLENGTH) at
        INTO's start, LENGTH, MEDIATYPE blank-padded to 56. READ HTTPHEADER: the value at VALUE's start, VALUELENGTH.
        WRITE HTTPHEADER: the header recorded as WEB-HEADER. Every other option is refused by name (check_options)."""
        g = self.g
        r = g.tmpname("web")

        def req(o: str) -> str:
            if not opts.get(o):
                raise CicsError(_msg(key, "required", o))
            return _arg(opts[o])

        def text(o: str) -> str:
            return f"Cobol.text({self.read_field(req(o))}, CS)"

        def store(o: str, value: str) -> str:
            return f"{ind}    " + g.store_into(self.ref(_arg(opts[o])), f"BigDecimal.valueOf({value})", False)

        def put(area: str, data: str, what: str) -> str:
            """A piece at the area's start (the rest left alone); more bytes than the area holds refused (PastFrom)."""
            f = self.field(area)
            return (f'{ind}    if ({data}.length > {f}.length()) throw new DetCics.PastFrom("{what} beyond its area: '
                    f'not modelled"); DetCics.put({f}, {data});')  # fmt: skip

        if (
            key == "WEB RETRIEVE"
        ):  # #4941 (X41): the DOCTOKEN of the last EVENTUAL document send, written on NORMAL only
            area = self.field(req("DOCTOKEN"))
            return [f"{ind}CicsTask.DocumentCreated {r} = task.webRetrieve();",
                    f"{ind}if ({r}.resp() == 0) DetCics.putText({area}, {r}.doctoken(), CS);",
                    *self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)]  # fmt: skip
        if key.startswith(
            ("WEB READ FORMFIELD", "WEB READ QUERYPARM", "WEB STARTBROWSE ", "WEB READNEXT ", "WEB ENDBROWSE ")
        ):
            return self.web_forms(key, opts, ind, text, req, store, put)
        if key == "WEB WRITE HTTPHEADER":
            call = f"task.webWriteHeader({text('HTTPHEADER')}, {self.int_(req('NAMELENGTH'))}, {text('VALUE')}, {self.int_(req('VALUELENGTH'))})"
            return [f"{ind}int[] {r} = {call};", *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]
        if key == "WEB READ HTTPHEADER":
            vl = req("VALUELENGTH")
            call = (f"task.webReadHeader({text('HTTPHEADER')}, {self.int_(req('NAMELENGTH'))}, {self.int_(vl)}, "
                    f"{self.size(req('VALUE'))})")  # fmt: skip
            return [f"{ind}CicsTask.WebHeader {r} = {call};", f"{ind}if ({r}.resp() == 0) {{",
                    put(req("VALUE"), f"{r}.value().getBytes(CS)", "WEB READ HTTPHEADER VALUE"),
                    store("VALUELENGTH", f"{r}.value().length()"), f"{ind}}}",
                    *self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)]  # fmt: skip
        if key == "WEB RECEIVE":
            if ("INTO" in opts) == ("SET" in opts) or not (opts.get("INTO") or opts.get("SET")):
                raise CicsError(_msg(key, "one_of", "INTO"))
            if "INTO" in opts and not opts.get("MAXLENGTH"):
                raise CicsError(_requires(key, "INTO", "MAXLENGTH"))
            if "SET" in opts and not opts.get("LENGTH"):
                raise CicsError(_requires(key, "SET", "LENGTH"))
            if "SRVCONVERT" in opts and "NOSRVCONVERT" in opts:
                raise CicsError(_msg(key, "at_most_one", "SRVCONVERT"))
            conv = 1 if "SRVCONVERT" in opts else 2 if "NOSRVCONVERT" in opts else 0
            if "SET" in opts:  # #4771 (X47): the body in a new block of task storage the pointer addresses
                ptr = self.pointer(opts["SET"])
                most = self.int_(req("MAXLENGTH")) if opts.get("MAXLENGTH") else "Integer.MAX_VALUE"
                out = [f"{ind}CicsTask.WebReceived {r} = task.webReceive({most}, Integer.MAX_VALUE, {conv});",
                       f"{ind}if ({r}.body() != null) {{",
                       f"{ind}    DetCics.receivedBlock(task, {ptr}, {r}.body(), CS);"]  # fmt: skip
            else:
                into = req("INTO")
                call = f"task.webReceive({self.int_(req('MAXLENGTH'))}, {self.size(into)}, {conv})"
                out = [f"{ind}CicsTask.WebReceived {r} = {call};", f"{ind}if ({r}.body() != null) {{",
                       put(into, f"{r}.body().getBytes(CS)", "WEB RECEIVE INTO")]  # fmt: skip
            if "LENGTH" in opts:
                out.append(store("LENGTH", f"{r}.body().length()"))
            if "MEDIATYPE" in opts:
                out.append(f"{ind}    DetCics.putText({self.field(req('MEDIATYPE'))}, "
                           f'String.format("%-56s", {r}.mediaType()), CS);')  # fmt: skip
            out.append(f"{ind}}}")
            return out + self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)
        pieces = (("HOST", "HOSTLENGTH", "host"), ("HTTPMETHOD", "METHODLENGTH", "method"),
                  ("HTTPVERSION", "VERSIONLEN", "version"), ("PATH", "PATHLENGTH", "path"),
                  ("QUERYSTRING", "QUERYSTRLEN", "query"))  # fmt: skip
        for a, n, _ in pieces:
            if (a in opts) != (n in opts):
                raise CicsError(_requires(key, a, n))

        def length(n: str) -> str:
            return f"Integer.valueOf({self.int_(_arg(opts[n]))})" if n in opts else "null"

        def cap(a: str) -> str:
            return str(self.size(_arg(opts[a]))) if a in opts else "0"

        call = "task.webExtract(" + ", ".join(f"{length(n)}, {cap(a)}" for a, n, _ in pieces) + ")"
        out = [f"{ind}CicsTask.WebExtracted {r} = {call};", f"{ind}if ({r}.resp() == 0) {{"]
        for a, n, piece in pieces:
            if a in opts:
                out.append(put(_arg(opts[a]), f"{r}.{piece}().getBytes(CS)", f"WEB EXTRACT {a}"))
                out.append(store(n, f"{r}.{piece}().length()"))
        if "PORTNUMBER" in opts:
            out.append(store("PORTNUMBER", f"{r}.port()"))
        if "SCHEME" in opts:
            out.append(store("SCHEME", f"{r}.scheme()"))
        if "REQUESTTYPE" in opts:
            out.append(store("REQUESTTYPE", "1033"))
        out.append(f"{ind}}}")
        return out + self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)

    def extract_tcpip(self, key: str, opts: dict, ind: str) -> list[str]:
        """#4972 (register X38): EXTRACT TCPIP (IBM CICS TS, EXEC CICS EXTRACT TCPIP) over the connection the run states
        (CicsTask.withTcpip). CicsTask.extractTcpip takes each address / name area's length option (an area asked for whose
        length option is missing: 0, LENGERR RESP2 1) and its size; on NORMAL the bytes at each area's start (the rest left
        alone), the lengths, the address numbers, the IPv4 CVDA (300), the port and the SSL type's CVDA."""
        g = self.g
        r = g.tmpname("tcp")
        pieces = (("CLIENTADDR", "CADDRLENGTH", "clientAddr"), ("CLIENTNAME", "CNAMELENGTH", "clientName"),
                  ("SERVERADDR", "SADDRLENGTH", "serverAddr"), ("SERVERNAME", "SNAMELENGTH", "serverName"))  # fmt: skip
        for a, n, _ in pieces:
            if n in opts and a not in opts:
                raise CicsError(_requires(key, n, a))

        def length(a: str, n: str) -> str:
            if a not in opts:
                return "null"
            return f"Integer.valueOf({self.int_(_arg(opts[n]))})" if n in opts else "Integer.valueOf(0)"

        def cap(a: str) -> str:
            return str(self.size(_arg(opts[a]))) if a in opts else "0"

        def store(o: str, value: str) -> str:
            return f"{ind}    " + g.store_into(self.ref(_arg(opts[o])), f"BigDecimal.valueOf({value})", False)

        args = ", ".join(f"{length(a, n)}, {cap(a)}" for a, n, _ in pieces)
        flags = ", ".join(
            str(o in opts).lower() for o in ("CLIENTADDRNU", "SERVERADDRNU", "CLNTIPFAMILY", "SRVRIPFAMILY")
        )
        out = [
            f"{ind}CicsTask.TcpipExtracted {r} = task.extractTcpip({args}, {flags});",
            f"{ind}if ({r}.resp() == 0) {{",
        ]
        for a, n, piece in pieces:
            if a in opts:
                f = self.field(_arg(opts[a]))
                data = f"{r}.{piece}().getBytes(CS)"
                out.append(f'{ind}    if ({data}.length > {f}.length()) throw new DetCics.PastFrom("EXTRACT TCPIP {a} beyond '
                           f'its area: not modelled"); DetCics.put({f}, {data});')  # fmt: skip
                if n in opts:
                    out.append(store(n, f"{r}.{piece}().length()"))
        for o, value in (("CLIENTADDRNU", f"{r}.clientNu()"), ("SERVERADDRNU", f"{r}.serverNu()"), ("CLNTIPFAMILY", "300"),
                         ("SRVRIPFAMILY", "300"), ("PORTNUMNU", f"{r}.port()"), ("SSLTYPE", f"{r}.ssl()")):  # fmt: skip
            if o in opts:
                out.append(store(o, value))
        out.append(f"{ind}}}")
        return out + self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)

    def web_forms(self, key: str, opts: dict, ind: str, text, req, store, put) -> list[str]:
        """#4940 (register X38): WEB READ FORMFIELD / QUERYPARM and the WEB browse forms (IBM CICS TS, EXEC CICS WEB READ
        FORMFIELD, WEB READ QUERYPARM, WEB STARTBROWSE / READNEXT / ENDBROWSE HTTPHEADER, FORMFIELD, QUERYPARM) on the stated
        request (CicsTask.webReadParam / webStartBrowse / webReadNext / webEndBrowse). A read: the value at VALUE's start
        (cut to VALUELENGTH, LENGERR RESP2 5) and VALUELENGTH its whole length. READNEXT: the pair's name and value at the
        areas' starts and their whole lengths (also when cut, LENGERR RESP2 4 / 5)."""
        g = self.g
        r = g.tmpname("web")
        form, kind = key.split()[1], key.split()[2]
        ok = f"{ind}if ({r}.value() != null) {{"
        if form == "READ":
            call = (f'task.webReadParam("{kind}", {text(kind)}, {self.int_(req("NAMELENGTH"))}, '
                    f"{self.int_(req('VALUELENGTH'))}, {self.size(req('VALUE'))})")  # fmt: skip
            return [f"{ind}CicsTask.WebParam {r} = {call};", ok,
                    put(req("VALUE"), f"{r}.value().getBytes(CS)", f"{key} VALUE"),
                    store("VALUELENGTH", f"{r}.length()"), f"{ind}}}",
                    *self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)]  # fmt: skip
        if form == "READNEXT":
            for o in (kind, "NAMELENGTH", "VALUE", "VALUELENGTH"):
                req(o)
            call = (f'task.webReadNext("{kind}", {self.int_(req("NAMELENGTH"))}, {self.size(req(kind))}, '
                    f"{self.int_(req('VALUELENGTH'))}, {self.size(req('VALUE'))})")  # fmt: skip
            return [f"{ind}CicsTask.WebNext {r} = {call};", f"{ind}if ({r}.name() != null) {{",
                    put(req(kind), f"{r}.name().getBytes(CS)", f"{key} {kind}"), store("NAMELENGTH", f"{r}.nameLength()"),
                    put(req("VALUE"), f"{r}.value().getBytes(CS)", f"{key} VALUE"),
                    store("VALUELENGTH", f"{r}.valueLength()"), f"{ind}}}",
                    *self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)]  # fmt: skip
        if form == "ENDBROWSE":
            return [f'{ind}int[] {r} = task.webEndBrowse("{kind}");', *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]
        named = bool(opts.get(kind))  # STARTBROWSE
        if kind == "HTTPHEADER" and named:
            raise CicsError("WEB STARTBROWSE HTTPHEADER: a name to start at is not documented: not modelled")
        if named and not opts.get("NAMELENGTH"):
            raise CicsError(f"WEB STARTBROWSE {kind}(name) without NAMELENGTH (IBM: it is required with a name)")
        if "NAMELENGTH" in opts and not named:
            raise CicsError(f"WEB STARTBROWSE {kind} NAMELENGTH without a name")
        if named:
            call = f'task.webStartBrowse("{kind}", {text(kind)}, Integer.valueOf({self.int_(req("NAMELENGTH"))}))'
        else:
            call = f'task.webStartBrowse("{kind}", null, null)'
        return [f"{ind}int[] {r} = {call};", *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]
