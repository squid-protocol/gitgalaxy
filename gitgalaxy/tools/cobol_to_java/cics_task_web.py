#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: CicsTask's web support (#4767, #4940, #4972, split out by #5274)
#
# PURPOSE:
# The web family of the CICS task runtime the transaction forge emits (CICS_TASK_JAVA), in two parts that
# sat on either side of the task-storage block: WEB_SESSION_JAVA (WEB OPEN / CONVERSE / CLOSE, the server side
# WEB SEND and EXTRACT, EXTRACT TCPIP, WEB RECEIVE) and WEB_REQUEST_JAVA (WEB READ / WRITE HTTPHEADER,
# WEB RETRIEVE, FORMFIELD / QUERYPARM and the browse forms, WEB PARSE URL). The forge splices them into
# CicsTask where they always sat, so the class is byte-identical.
# ==============================================================================

WEB_SESSION_JAVA = """\
    // #4767 zECS (register X35): CICS web support as an HTTP client -- WEB OPEN, WEB CONVERSE, WEB CLOSE (IBM CICS TS,
    // EXEC CICS WEB OPEN, WEB CONVERSE, WEB CLOSE). The server is not part of the region: the peers (scheme, host, port,
    // the CLIENT URIMAP naming one, and the response each gives, request by request) are a fact whoever runs the task
    // states, never guessed. The exchange is in the program's characters (`cs`): conversion changes nothing here.
    /** One stated response: the request it answers (method, path, query string without its '?', "" for none) and what
     *  the server sends back (status code, reason phrase, media type, body text). Each answers one request, in order. */
    public record HttpExchange(String method, String path, String query, int status, String statusText,
                               String mediaType, String body) {
    }

    /** One stated server: scheme (HTTP / HTTPS), host, port, the CLIENT URIMAP that names it and that URIMAP's path
     *  (null: none), and its responses. */
    public record HttpPeer(String scheme, String host, int port, String urimap, String path,
                           java.util.List<HttpExchange> exchanges) {
    }

    /** WEB OPEN's outcome: RESP, RESP2 and the SESSTOKEN (null unless NORMAL). */
    public record WebOpened(int resp, int resp2, String sesstoken) {
    }

    /** WEB CONVERSE's outcome: RESP, RESP2 and, when a response came back (NORMAL, LENGERR 57), the bytes for INTO,
     *  TOLENGTH, STATUSCODE, the reason phrase and the media type (blank-padded to 56); else body null. */
    public record WebResponse(int resp, int resp2, byte[] body, int toLength, int status, String statusText,
                              String mediaType) {
    }

    private record WebSession(HttpPeer peer, boolean byUrimap) {
    }

    private java.util.List<HttpPeer> httpPeers;
    private final java.util.Map<String, WebSession> webSessions = new LinkedHashMap<>();
    private final java.util.Set<HttpExchange> webAnswered =
            java.util.Collections.newSetFromMap(new java.util.IdentityHashMap<>());
    private int webSeq;
    private static final java.util.Map<Integer, String> WEB_METHODS = java.util.Map.of(
            748, "GET", 750, "HEAD", 292, "DELETE", 636, "POST", 749, "PUT", 1220, "PATCH");
    private static final java.util.Set<String> WEB_BODY = java.util.Set.of("POST", "PUT", "PATCH");

    /** The HTTP servers the task can reach. Not stated (never called), every WEB command is refused. */
    public CicsTask withHttpPeers(java.util.List<HttpPeer> peers) {
        this.httpPeers = peers;
        return this;
    }

    // #4767 zECS (register X37): the server side. The task is the response to one inbound HTTP request that whoever runs it
    // STATES (never guessed); WEB SEND's response is recorded as an event and compared.
    /** The inbound request the task serves: scheme, host, port, method, HTTP version, path, query string (without its
     *  '?', "" for none), headers (name, value), the body's media type and body (null: none). WEB SEND, WEB RECEIVE,
     *  WEB EXTRACT and WEB READ / WRITE HTTPHEADER need it stated (X37, X38). */
    public record HttpRequest(String scheme, String host, int port, String method, String version, String path,
                              String query, java.util.List<String[]> headers, String mediaType, String body) {
    }

    private HttpRequest httpRequest;
    private boolean webSent;  // an ACTION(IMMEDIATE) response was sent
    private boolean webSendFailed;  // #4941: the last WEB SEND ended in a condition (IBM: whether it was issued is not stated)
    private boolean webIssued;  // a WEB SEND was accepted (IMMEDIATE or EVENTUAL)
    private Object[] webHeld;  // #4941 (X37): the ACTION(EVENTUAL) response held for the end of the task (WEB-SEND's fields)
    private byte[] webHeldDoc;  // the document an EVENTUAL DOCTOKEN send (not DOCDELETE) sent, as it was sent
    private String webHeldToken;  // the DOCTOKEN WEB RETRIEVE gave for webHeldDoc (null: not retrieved yet)
    private int webReceived;  // 0 none yet, 1 a receive that was not SRVCONVERT, 2 NOSRVCONVERT, 3 a SRVCONVERT pass after it

    /** The HTTP request this task serves (a web-attached task). Not stated (never called), WEB SEND is refused. */
    public CicsTask withHttpRequest(HttpRequest request) {
        this.httpRequest = request;
        return this;
    }

    private java.util.List<HttpPeer> statedPeers() {
        java.util.List<HttpPeer> p = root().httpPeers;
        if (p == null) {
            throw refused("the HTTP peers are not stated (withHttpPeers)");
        }
        return p;
    }

    private WebOpened webSession(HttpPeer peer, boolean byUrimap) {
        CicsTask r = root();
        if (r.webSeq >= 9999) {
            throw refused("WEB OPEN: more than 9999 sessions in one task");
        }
        String token = String.format(java.util.Locale.ROOT, "GGWS%04d", ++r.webSeq);
        r.webSessions.put(token, new WebSession(peer, byUrimap));
        return new WebOpened(0, 0, token);
    }

    /** WEB OPEN HOST(host) HOSTLENGTH(n) [PORTNUMBER(port)] SCHEME(cvda): `host` is the HOST area's text; PORTNUMBER
     *  omitted (portGiven false) is 80 for HTTP, 443 for HTTPS. LENGERR 21 (HOSTLENGTH not above zero), INVREQ 40 (a
     *  scheme other than HTTP / HTTPS), INVREQ 138 (a port above 65535). Refused: two conditions at once, a port below 1,
     *  a HOSTLENGTH past HOST, a server the run does not state. */
    public WebOpened webOpenHost(String host, int hostLength, int port, boolean portGiven, int scheme) {
        WebOpened o = webOpenHostChecked(host, hostLength, port, portGiven, scheme);
        event("WEB-OPEN", "host", hostLength > 0 && hostLength <= host.length() ? host.substring(0, hostLength) : "",
                "scheme", scheme == 1096 ? "HTTP" : scheme == 1029 ? "HTTPS" : null, "resp", o.resp(), "resp2", o.resp2());
        return o;
    }

    private WebOpened webOpenHostChecked(String host, int hostLength, int port, boolean portGiven, int scheme) {
        java.util.List<HttpPeer> peers = statedPeers();
        java.util.List<int[]> c = new java.util.ArrayList<>();
        if (hostLength <= 0) {
            c.add(new int[] {22, 21});
        } else if (hostLength > host.length()) {
            throw refused("WEB OPEN HOSTLENGTH beyond HOST");
        }
        String sch = scheme == 1096 ? "HTTP" : scheme == 1029 ? "HTTPS" : null;
        if (sch == null) {
            c.add(new int[] {16, 40});
        }
        if (portGiven && port > 65535) {
            c.add(new int[] {16, 138});
        } else if (portGiven && port < 1) {
            throw refused("WEB OPEN PORTNUMBER below 1");
        }
        if (c.size() > 1) {
            throw refused("WEB OPEN with more than one condition at once");
        }
        if (c.size() == 1) {
            return new WebOpened(c.get(0)[0], c.get(0)[1], null);
        }
        String h = host.substring(0, hostLength);
        int p = portGiven ? port : "HTTPS".equals(sch) ? 443 : 80;
        for (HttpPeer peer : peers) {
            if (peer.scheme().equals(sch) && peer.host().equalsIgnoreCase(h) && peer.port() == p) {
                return webSession(peer, false);
            }
        }
        throw refused("WEB OPEN of a peer the run does not state");
    }

    /** WEB OPEN URIMAP(name): the stated server whose CLIENT URIMAP that is; another is refused. */
    public WebOpened webOpenUrimap(String name) {
        String n = name == null ? "" : name.strip();
        for (HttpPeer peer : statedPeers()) {
            if (n.equals(peer.urimap())) {
                event("WEB-OPEN", "host", peer.host(), "scheme", peer.scheme(), "resp", 0, "resp2", 0);
                return webSession(peer, true);
            }
        }
        throw refused("WEB OPEN of a peer the run does not state");
    }

    /** WEB CONVERSE on SESSTOKEN `token`: one request and its stated response. Each text argument is its area's text
     *  (null: the option is not given) and each length its value; mediaType is MEDIATYPE's area (null: not given),
     *  maxLength MAXLENGTH (INTO's length when omitted), statusLength STATUSLEN (-1: no STATUSTEXT). The conditions IBM
     *  lists for what the program gives (NOTOPEN 27; INVREQ 33 / 34 / 54 / 76; LENGERR 5 / 8 / 16 / 50 / 59) come back
     *  with nothing sent; a response longer than MAXLENGTH is truncated (LENGERR 57). The request sent is recorded
     *  (WEB-CONVERSE). Refused: two conditions at once, TRACE / OPTIONS, MAXLENGTH 0, no PATH on a session opened by
     *  HOST, a body with a blank MEDIATYPE, a length past its area, a request the peer states no response to, a reason
     *  phrase longer than STATUSLEN. */
    public WebResponse webConverse(String token, int method, String path, int pathLength, String query, int queryLength,
                                   String from, int fromLength, String mediaType, int maxLength, int statusLength,
                                   java.nio.charset.Charset cs) {
        CicsTask r = root();
        r.statedPeers();
        java.util.List<int[]> c = new java.util.ArrayList<>();
        WebSession s = r.webSessions.get(token);
        if (s == null) {
            c.add(new int[] {19, 27});
        }
        if (method == 760 || method == 759) {
            throw refused("WEB CONVERSE METHOD TRACE / OPTIONS");
        }
        String m = WEB_METHODS.get(method);
        if (m == null) {
            c.add(new int[] {16, 54});
        } else if (from != null && !WEB_BODY.contains(m)) {
            c.add(new int[] {16, 33});
        } else if (from == null && WEB_BODY.contains(m)) {
            c.add(new int[] {16, 34});
        }
        if (from != null && mediaType == null) {
            c.add(new int[] {16, 76});
        } else if (from != null && mediaType.isBlank()) {
            throw refused("WEB CONVERSE body with a blank MEDIATYPE");
        }
        if (path != null && pathLength <= 0) {
            c.add(new int[] {22, 5});
        }
        if (query != null && queryLength <= 0) {
            c.add(new int[] {22, 8});
        }
        if (maxLength < 0) {
            c.add(new int[] {22, 16});
        } else if (maxLength == 0) {
            throw refused("WEB CONVERSE MAXLENGTH 0");
        }
        if (from != null && fromLength <= 0) {
            c.add(new int[] {22, 50});
        }
        if (statusLength == 0 || statusLength < -1) {
            c.add(new int[] {22, 59});
        }
        if ((path != null && pathLength > path.length()) || (query != null && queryLength > query.length())
                || (from != null && fromLength > from.length())) {
            throw refused("WEB CONVERSE length beyond its area");
        }
        if (c.size() > 1) {
            throw refused("WEB CONVERSE with more than one condition at once");
        }
        if (c.size() == 1) {
            return new WebResponse(c.get(0)[0], c.get(0)[1], null, -1, -1, null, null);
        }
        if (path == null && !s.byUrimap()) {
            throw refused("WEB CONVERSE with no PATH on a session opened by HOST");
        }
        String p = path != null ? path.substring(0, pathLength) : s.peer().path();
        String q = query == null ? "" : query.substring(0, queryLength);
        q = q.startsWith("?") ? q.substring(1) : q;
        String body = from == null ? null : from.substring(0, fromLength);
        String mt = from == null ? null : mediaType.length() > 56 ? mediaType.substring(0, 56).stripTrailing()
                : mediaType.stripTrailing();
        HttpExchange x = null;
        for (HttpExchange e : s.peer().exchanges()) {
            if (!r.webAnswered.contains(e) && e.method().equals(m) && e.path().equals(p) && e.query().equals(q)) {
                x = e;
                break;
            }
        }
        if (x == null) {
            throw refused("WEB CONVERSE request the peer states no response to");
        }
        if (statusLength > 0 && x.statusText().length() > statusLength) {
            throw refused("WEB CONVERSE status text longer than STATUSLEN");
        }
        r.webAnswered.add(x);
        byte[] data = x.body().getBytes(cs);
        int resp = data.length > maxLength ? 22 : 0;
        int resp2 = resp == 0 ? 0 : 57;
        byte[] into = resp == 0 ? data : java.util.Arrays.copyOf(data, maxLength);
        event("WEB-CONVERSE", "host", s.peer().host(), "method", m, "path", p, "query", q, "mediatype", mt,
                "body", body, "resp", resp, "resp2", resp2, "status", x.status(),  // #4767: the response given
                "tolength", into.length, "into", new String(into, cs));
        return new WebResponse(resp, resp2, into, into.length, x.status(), x.statusText(),
                String.format(java.util.Locale.ROOT, "%-56.56s", x.mediaType()));
    }

    /** WEB CLOSE SESSTOKEN(token): {RESP, RESP2} -- NOTOPEN 27 for a token that is not an open session's. */
    public int[] webClose(String token) {
        CicsTask r = root();
        r.statedPeers();
        int[] out = r.webSessions.remove(token) != null ? new int[] {0, 0} : new int[] {19, 27};
        event("WEB-CLOSE", "resp", out[0], "resp2", out[1]);
        return out;
    }

    /** WEB SEND FROM(area) FROMLENGTH(n) [MEDIATYPE(area)] ACTION(cvda) [STATUSCODE(n)] [STATUSTEXT(area) [STATUSLEN(n)]]
     *  [SRVCONVERT | NOSRVCONVERT] (IBM CICS TS, EXEC CICS WEB SEND, server; register X37): the response to the stated
     *  request, recorded as WEB-SEND (status -- 200 when STATUSCODE is not given --, reason phrase (null: not given),
     *  media type (null: not given), body, action). `from` is FROM's area text, mediaType MEDIATYPE's area text (null: not
     *  given), action ACTION's value (0: not given), status STATUSCODE (-1: not given), statusText STATUSTEXT's area text
     *  (null: not given), statusLength STATUSLEN (-1: not given: the whole area, ASSUMED), conv 0 / 1 / 2 for neither /
     *  SRVCONVERT / NOSRVCONVERT. INVREQ 11 (an action that is neither IMMEDIATE nor EVENTUAL), INVREQ 72 (status 204 /
     *  205 / 304 with a body). Refused: no request stated, ACTION not IMMEDIATE (an EVENTUAL or omitted action sends at
     *  the end of the task and a second send replaces it), a second send after IMMEDIATE, FROMLENGTH or STATUSLEN not
     *  above zero, a length past its area, a blank or malformed MEDIATYPE, a status
     *  code outside 100-599, SRVCONVERT on a media type that is not text/*, two conditions at once. */
    public int[] webSend(String from, int fromLength, String mediaType, int action, int status, String statusText,
                         int statusLength, int conv) {
        CicsTask r = root();
        if (r.httpRequest == null) {
            throw refused("the HTTP request is not stated (withHttpRequest)");
        }
        if (r.webSent) {
            throw refused("WEB SEND after a response was sent");
        }
        if (fromLength <= 0 || (statusText != null && statusLength == 0) || statusLength < -1) {
            throw refused("WEB SEND FROMLENGTH or STATUSLEN not above zero");
        }
        if (fromLength > from.length() || (statusText != null && statusLength > statusText.length())) {
            throw refused("WEB SEND length beyond its area");
        }
        return webSendBody(from.substring(0, fromLength), mediaType, action, status, statusText, statusLength, conv, false,
                null, 0, null);
    }

    /** WEB SEND CONTAINER(container) [CHANNEL(channel)] [MEDIATYPE(area)] ACTION(cvda) [STATUSCODE(n)] [STATUSTEXT(area)
     *  [STATUSLEN(n)]] [SRVCONVERT | NOSRVCONVERT] (IBM CICS TS, EXEC CICS WEB SEND, server; register X37): the response body
     *  is the container's data as it is now, recorded as WEB-SEND. IBM: "If the CONTAINER option is specified, CHANNEL is
     *  optional" (omitted: the current channel); CONTAINERERR RESP2 2 (container not found), CHANNELERR RESP2 2 (channel not
     *  found), INVREQ RESP2 145 (no CHANNEL and no current channel), INVREQ RESP2 150 (conversion requested of a DATATYPE BIT
     *  container). Refused: an empty container, and a BIT container sent as it is (IBM does not say what an empty body
     *  is, and a body of bytes is not compared as text); `cs` is the program's character set. */
    public int[] webSendContainer(String channel, String container, String mediaType, int action, int status,
                                  String statusText, int statusLength, int conv, java.nio.charset.Charset cs) {
        CicsTask r = root();
        if (r.httpRequest == null) {
            throw refused("the HTTP request is not stated (withHttpRequest)");
        }
        if (r.webSent) {
            throw refused("WEB SEND after a response was sent");
        }
        if ((statusText != null && statusLength == 0) || statusLength < -1) {
            throw refused("WEB SEND FROMLENGTH or STATUSLEN not above zero");
        }
        if (statusText != null && statusLength > statusText.length()) {
            throw refused("WEB SEND length beyond its area");
        }
        Channel ch = channel == null ? currentChannel : scopeChannel(channel, false);
        String name = channelName(container, "container");
        int[] pre = null;
        Container k = null;
        if (ch == null) {
            pre = channel == null ? new int[] {16, 145} : new int[] {122, 2};
        } else if ((k = ch.containers.get(name)) == null) {
            pre = new int[] {110, 2};
        } else if (conv != 0 && k.bit) {
            pre = new int[] {16, 150};
        } else if (k.data.length == 0) {
            throw refused("WEB SEND of an empty container");
        } else if (k.bit) {
            throw refused("WEB SEND of a DATATYPE BIT container");
        } else if (k.ccsid != REGION_CCSID) {
            throw refused("WEB SEND of a container in a CCSID other than the region's");
        }
        return webSendBody(pre != null ? "" : new String(k.data, cs), mediaType, action, status, statusText, statusLength,
                conv, false, null, 0, pre);
    }

    /** WEB SEND DOCTOKEN(token) [MEDIATYPE(area)] ACTION(cvda) [STATUSCODE(n)] [STATUSTEXT(area) [STATUSLEN(n)]] [SRVCONVERT |
     *  NOSRVCONVERT] (IBM CICS TS, EXEC CICS WEB SEND, server; register X37): the response is the document `token` names -- one
     *  the task created (DOCUMENT CREATE) -- as it is now, recorded as WEB-SEND with the document's text as the body. An empty
     *  document is no message body (ASSUMED: IBM does not say, and lists INVREQ RESP2 72 for 204 / 205 / 304 "with a body"), so
     *  a 204 may send one; `cs` is the program's character set. Refused as webSend does, and a token that names no document of the task. */
    public int[] webSendDocument(String doctoken, String mediaType, int action, int status, String statusText,
                                 int statusLength, int conv, int docStatus, java.nio.charset.Charset cs) {
        CicsTask r = root();
        if (r.httpRequest == null) {
            throw refused("the HTTP request is not stated (withHttpRequest)");
        }
        if (r.webSent) {
            throw refused("WEB SEND after a response was sent");
        }
        byte[] doc = r.documents.get(doctoken.stripTrailing());
        if ((statusText != null && statusLength == 0) || statusLength < -1) {
            throw refused("WEB SEND FROMLENGTH or STATUSLEN not above zero");
        }
        if (statusText != null && statusLength > statusText.length()) {
            throw refused("WEB SEND length beyond its area");
        }
        r.webDocToken = doctoken.stripTrailing();
        return webSendBody(doc == null ? "" : new String(doc, cs), mediaType, action, status,
                statusText, statusLength, conv, true, doc, docStatus, null);
    }

    private String webDocToken;  // (the token webSendDocument is sending: webSendBody deletes its document on DOCDELETE)

    private int[] webSendBody(String body, String mediaType, int action, int status, String statusText,
                              int statusLength, int conv, boolean ofDocument, byte[] doc, int docStatus, int[] pre) {
        CicsTask r = root();
        if (status != -1 && (status < 100 || status > 599)) {
            throw refused("WEB SEND STATUSCODE outside 100-599");
        }
        String mt = null;
        if (mediaType != null) {
            mt = mediaType.length() > 56 ? mediaType.substring(0, 56) : mediaType;
            int pad = mt.indexOf('\0');  // #6839 (X37): an area padded to its end with X'00' is the type before the padding
            if (pad >= 0 && mt.substring(pad).chars().allMatch(c -> c == 0)) {
                mt = mt.substring(0, pad);
            }
            mt = mt.stripTrailing();
            int slash = mt.indexOf('/');
            if (slash < 1 || slash == mt.length() - 1 || mt.chars().anyMatch(c -> c <= ' ' || c > '~')) {
                throw refused("WEB SEND MEDIATYPE blank or not type/subtype");
            }
        }
        if (conv == 1 && (mt == null || !mt.toLowerCase(java.util.Locale.ROOT).startsWith("text/"))) {
            throw refused("WEB SEND SRVCONVERT on a media type that is not text/*");
        }
        java.util.List<int[]> c = new java.util.ArrayList<>();
        if (pre != null) {
            c.add(pre);  // a container send's own conditions (CONTAINERERR / CHANNELERR / INVREQ 145 / 150)
        }
        if (ofDocument && doc == null) {
            c.add(new int[] {13, 1});  // the document has not been created, or has been deleted, or the name is wrong
        }
        if (action != 0 && action != 2 && action != 3) {
            c.add(new int[] {16, 11});
        }
        if (ofDocument && docStatus != 0 && docStatus != 295 && docStatus != 296) {
            c.add(new int[] {16, 143});
        }
        if ((status == 204 || status == 205 || status == 304) && !body.isEmpty()) {
            c.add(new int[] {16, 72});
        }
        if (c.size() > 1) {
            throw refused("WEB SEND with more than one condition at once");
        }
        if (c.size() == 1) {
            r.webSendFailed = true;
            return c.get(0);
        }
        boolean eventual = action != 2;  // (an omitted ACTION is EVENTUAL for a send that is not chunked: IBM)
        if (!eventual && r.webHeld != null) {
            throw refused("WEB SEND ACTION(IMMEDIATE) after an ACTION(EVENTUAL) send");
        }
        String st = statusText == null ? null : statusText.substring(0, statusLength < 0 ? statusText.length() : statusLength);
        Object[] fields = {"status", status == -1 ? 200 : status, "statustext", st, "mediatype", mt, "body", body,
                "action", eventual ? "EVENTUAL" : "IMMEDIATE", "resp", 0, "resp2", 0};
        r.webSendFailed = false;
        r.webIssued = true;
        if (ofDocument && docStatus == 295) {
            r.documents.remove(r.webDocToken);  // DOCDELETE: deleted once its contents are saved for sending
        }
        if (eventual) {
            r.webHeld = fields;  // sent at the end of the task; a second send replaces it
            r.webHeldDoc = ofDocument && docStatus != 295 ? doc.clone() : null;
            r.webHeldToken = null;
            return new int[] {0, 0};
        }
        r.webSent = true;
        r.webHeldDoc = null;
        event("WEB-SEND", fields);
        return new int[] {0, 0};
    }

    // #4767 zECS (register X38): the server reading the request it serves, which whoever runs the task STATES.
    private CicsTask statedRequest() {
        CicsTask r = root();
        if (r.httpRequest == null) {
            throw refused("the HTTP request is not stated (withHttpRequest)");
        }
        return r;
    }

    /** WEB EXTRACT's outcome: RESP, RESP2 and, on NORMAL, the request's pieces as stated (the HTTP version as the run
     *  states it, ASSUMED: IBM does not say whether it is "HTTP/1.1" or "1.1"), the scheme's CVDA (1096 HTTP, 1029
     *  HTTPS) and the port; else the strings are null. */
    public record WebExtracted(int resp, int resp2, int scheme, String host, int port, String method, String version,
                               String path, String query) {
    }

    /** WEB EXTRACT (server form; IBM CICS TS, EXEC CICS WEB EXTRACT; register X38). Each *Length is the option's value
     *  (null: the piece is not asked for) and each cap its area's size. LENGERR 21 / 5 / 7 for a HOSTLENGTH / PATHLENGTH /
     *  VERSIONLEN not above zero. A query string the request does not have: length 0, the area left alone (ASSUMED: IBM
     *  does not say). Refused: no request stated, a piece longer than its length (LENGERR 4 / 6 / 8 / 29 / 30: what the
     *  length then holds is not stated), a METHODLENGTH or QUERYSTRLEN not above zero (no condition is listed), a length
     *  past its area, two conditions at once. */
    public WebExtracted webExtract(Integer hostLength, int hostCap, Integer methodLength, int methodCap,
                                   Integer versionLength, int versionCap, Integer pathLength, int pathCap,
                                   Integer queryLength, int queryCap) {
        HttpRequest q = statedRequest().httpRequest;
        if ((hostLength != null && hostLength > hostCap) || (methodLength != null && methodLength > methodCap)
                || (versionLength != null && versionLength > versionCap) || (pathLength != null && pathLength > pathCap)
                || (queryLength != null && queryLength > queryCap)) {
            throw refused("WEB EXTRACT length beyond its area");
        }
        if ((methodLength != null && methodLength <= 0) || (queryLength != null && queryLength <= 0)) {
            throw refused("WEB EXTRACT METHODLENGTH or QUERYSTRLEN not above zero");
        }
        java.util.List<int[]> c = new java.util.ArrayList<>();
        if (hostLength != null && hostLength <= 0) {
            c.add(new int[] {22, 21});
        }
        if (pathLength != null && pathLength <= 0) {
            c.add(new int[] {22, 5});
        }
        if (versionLength != null && versionLength <= 0) {
            c.add(new int[] {22, 7});
        }
        if (c.size() > 1) {
            throw refused("WEB EXTRACT with more than one condition at once");
        }
        if (c.size() == 1) {
            return new WebExtracted(c.get(0)[0], c.get(0)[1], 0, null, -1, null, null, null, null);
        }
        if ((hostLength != null && q.host().length() > hostLength) || (methodLength != null && q.method().length() > methodLength)
                || (versionLength != null && q.version().length() > versionLength)
                || (pathLength != null && q.path().length() > pathLength)
                || (queryLength != null && q.query().length() > queryLength)) {
            throw refused("WEB EXTRACT piece longer than its length");
        }
        return new WebExtracted(0, 0, "HTTPS".equals(q.scheme()) ? 1029 : 1096, q.host(), q.port(), q.method(),
                q.version(), q.path(), q.query());
    }

    // #4972 (register X38): EXTRACT TCPIP, the connection the task was started on, which whoever runs the task STATES.
    /** The TCP/IP connection the task serves: the client's and the server's IPv4 address (dotted decimal), the client's and
     *  the server's name as the DNS knows it (null: the DNS knows none), the port that received the request and the SSL
     *  type (SSL, NOSSL, CLIENTAUTH or ATTLSAWARE). EXTRACT TCPIP needs it stated (X38). */
    public record Tcpip(String clientAddr, String clientName, String serverAddr, String serverName, int port,
                        String sslType) {
    }

    private Tcpip tcpip;

    /** The TCP/IP connection this task serves. Not stated (never called), EXTRACT TCPIP is refused. */
    public CicsTask withTcpip(Tcpip connection) {
        this.tcpip = connection;
        return this;
    }

    /** EXTRACT TCPIP's outcome: RESP, RESP2 and, on NORMAL, what the stated connection holds (names null when the DNS
     *  knows none); the address numbers are the IPv4 address as a signed fullword. */
    public record TcpipExtracted(int resp, int resp2, String clientAddr, String clientName, String serverAddr,
                                 String serverName, int clientNu, int serverNu, int port, int ssl) {
    }

    /** An IPv4 address in dotted decimal as a number (-1: it is not one; four decimal parts 0-255 without a leading zero). */
    private static long ipv4Value(String addr) {
        String[] part = addr == null ? new String[0] : addr.split("[.]", -1);
        long value = 0;
        if (part.length != 4) {
            return -1;
        }
        for (String p : part) {
            if (p.isEmpty() || p.length() > 3 || (p.length() > 1 && p.charAt(0) == '0')) {
                return -1;
            }
            int n = 0;
            for (int i = 0; i < p.length(); i++) {
                int d = p.charAt(i) - '0';
                if (d < 0 || d > 9) {
                    return -1;
                }
                n = n * 10 + d;
            }
            if (n > 255) {
                return -1;
            }
            value = value * 256 + n;
        }
        return value;
    }

    /** EXTRACT TCPIP (IBM CICS TS, EXEC CICS EXTRACT TCPIP; register X38) over the stated connection. Each *Length is the
     *  option's value (null: the area is not asked for; 0 for an area asked for whose length option is missing) and each cap
     *  its area's size. LENGERR RESP2 1 when an area asked for has a length not above zero. The client name: the DNS knows
     *  none, length 0 and the area left alone (IBM: "zero if the DNS does not know the client"). Refused: no connection
     *  stated, an address that is not IPv4 dotted decimal, an address number past a signed fullword, a server name the
     *  connection does not state, a name or address longer than its length (LENGERR RESP2 3 / 4 / 6 / 7: IBM does not say what
     *  the length or the area then holds), a length past its area, two conditions at once. */
    public TcpipExtracted extractTcpip(Integer cAddrLength, int cAddrCap, Integer cNameLength, int cNameCap,
                                       Integer sAddrLength, int sAddrCap, Integer sNameLength, int sNameCap,
                                       boolean clientNu, boolean serverNu, boolean clientFamily, boolean serverFamily) {
        CicsTask r = root();
        if (r.tcpip == null) {
            throw refused("the TCP/IP connection is not stated (withTcpip)");
        }
        Tcpip t = r.tcpip;
        if ((cAddrLength != null && cAddrLength > cAddrCap) || (cNameLength != null && cNameLength > cNameCap)
                || (sAddrLength != null && sAddrLength > sAddrCap) || (sNameLength != null && sNameLength > sNameCap)) {
            throw refused("EXTRACT TCPIP length beyond its area");
        }
        long cNum = ipv4Value(t.clientAddr());
        long sNum = ipv4Value(t.serverAddr());
        if (((cAddrLength != null || clientNu || clientFamily) && cNum < 0)
                || ((sAddrLength != null || serverNu || serverFamily) && sNum < 0)
                || (clientNu && cNum > Integer.MAX_VALUE) || (serverNu && sNum > Integer.MAX_VALUE)) {
            throw refused("EXTRACT TCPIP address");
        }
        if (sNameLength != null && t.serverName() == null) {
            throw refused("EXTRACT TCPIP");
        }
        boolean badLength = (cAddrLength != null && cAddrLength <= 0) || (cNameLength != null && cNameLength <= 0)
                || (sAddrLength != null && sAddrLength <= 0) || (sNameLength != null && sNameLength <= 0);
        String clientName = t.clientName() == null ? "" : t.clientName();
        String serverName = t.serverName() == null ? "" : t.serverName();
        boolean tooSmall = (cAddrLength != null && cAddrLength > 0 && t.clientAddr().length() > cAddrLength)
                || (cNameLength != null && cNameLength > 0 && clientName.length() > cNameLength)
                || (sAddrLength != null && sAddrLength > 0 && t.serverAddr().length() > sAddrLength)
                || (sNameLength != null && sNameLength > 0 && serverName.length() > sNameLength);
        if (badLength && tooSmall) {
            throw refused("EXTRACT TCPIP with more than one condition at once");
        }
        if (badLength) {
            return new TcpipExtracted(22, 1, null, null, null, null, 0, 0, 0, 0);
        }
        if (tooSmall) {
            throw refused("EXTRACT TCPIP");
        }
        int ssl = "SSL".equals(t.sslType()) ? 1030 : "NOSSL".equals(t.sslType()) ? 1031
                : "CLIENTAUTH".equals(t.sslType()) ? 1032 : 1205;  // (ATTLSAWARE)
        return new TcpipExtracted(0, 0, t.clientAddr(), clientName, t.serverAddr(), serverName, (int) cNum, (int) sNum,
                t.port(), ssl);
    }

    /** WEB RECEIVE's outcome: RESP, RESP2 and, on NORMAL / LENGERR 57, the body returned (at most MAXLENGTH) and its media
     *  type, else null. */
    public record WebReceived(int resp, int resp2, String body, String mediaType) {
    }

    /** WEB RECEIVE INTO(area) LENGTH(area) MAXLENGTH(n) [MEDIATYPE(area)] [SRVCONVERT | NOSRVCONVERT] (server form; IBM
     *  CICS TS, EXEC CICS WEB RECEIVE; register X38). LENGERR 16 for a MAXLENGTH not above zero; a body longer than
     *  MAXLENGTH is cut there with LENGERR 57 (without NOTRUNCATE "the remainder was discarded"; LENGTH then holds the
     *  bytes returned). The body is in the program's characters whatever the conversion option (ASSUMED, as X37).
     *  Recorded as WEB-RECEIVE (the request's media type and the body returned, null on LENGERR 16; RESP, RESP2) --
     *  the crucible SPEC's event, so a runner can tell what the program read. Refused: no request stated, a request with no body, a second receive, a MAXLENGTH past INTO. */
    public WebReceived webReceive(int maxLength, int intoCap) {
        return webReceive(maxLength, intoCap, 0);
    }

    /** As above with the conversion option: conv 0 neither, 1 SRVCONVERT, 2 NOSRVCONVERT. A second receive is allowed only as
     *  SRVCONVERT after a NOSRVCONVERT one (ZECS001's text/* pass; ASSUMED, register X38: IBM does not say what a body already
     *  received returns again; the model returns the same body and media type, as conversion changes nothing); any other
     *  repeat, and a third receive, is refused. */
    public WebReceived webReceive(int maxLength, int intoCap, int conv) {
        CicsTask r = statedRequest();
        HttpRequest q = r.httpRequest;
        if (q.body() == null) {
            throw refused("WEB RECEIVE of a request with no body");
        }
        if (r.webReceived != 0 && !(r.webReceived == 2 && conv == 1)) {
            throw refused("a second WEB RECEIVE");
        }
        if (maxLength > intoCap) {
            throw refused("WEB RECEIVE length beyond its area");
        }
        if (maxLength <= 0) {
            event("WEB-RECEIVE", "mediatype", null, "body", null, "resp", 22, "resp2", 16);
            return new WebReceived(22, 16, null, null);
        }
        r.webReceived = r.webReceived == 2 ? 3 : conv == 2 ? 2 : 1;
        boolean cut = q.body().length() > maxLength;
        WebReceived got = new WebReceived(cut ? 22 : 0, cut ? 57 : 0, cut ? q.body().substring(0, maxLength) : q.body(), q.mediaType());
        event("WEB-RECEIVE", "mediatype", got.mediaType(), "body", got.body(), "resp", got.resp(), "resp2", got.resp2());
        return got;
    }

"""

WEB_REQUEST_JAVA = """\
    /** WEB READ HTTPHEADER's outcome: RESP, RESP2 and, on NORMAL, the header's value, else null. */
    public record WebHeader(int resp, int resp2, String value) {
    }

    /** WEB READ HTTPHEADER HTTPHEADER(name) NAMELENGTH(n) VALUE(area) VALUELENGTH(area) (server form; IBM CICS TS, EXEC
     *  CICS WEB READ HTTPHEADER; register X38): `name` is the name area's text. INVREQ 43 when the request has no
     *  headers, NOTFND 1 when none has that name, LENGERR 1 for a VALUELENGTH not above zero. Refused: no request stated,
     *  a header found only when the names are compared without case (IBM does not say), two headers of the name, a
     *  NAMELENGTH not above zero or past its area, a value longer than VALUELENGTH (LENGERR 2: what VALUELENGTH then holds
     *  is not stated), a VALUELENGTH past VALUE's area, two conditions at once. */
    public WebHeader webReadHeader(String name, int nameLength, int valueLength, int valueCap) {
        HttpRequest q = statedRequest().httpRequest;
        if (nameLength <= 0 || nameLength > name.length()) {
            throw refused("WEB READ HTTPHEADER NAMELENGTH not above zero or past its area");
        }
        if (valueLength > valueCap) {
            throw refused("WEB READ HTTPHEADER length beyond its area");
        }
        String n = name.substring(0, nameLength);
        java.util.List<String[]> exact = q.headers().stream().filter(h -> h[0].equals(n)).toList();
        if (exact.isEmpty() && q.headers().stream().anyMatch(h -> h[0].equalsIgnoreCase(n))) {
            throw refused("WEB READ HTTPHEADER header name found only without case");
        }
        if (exact.size() > 1) {
            throw refused("WEB READ HTTPHEADER two headers of the name");
        }
        java.util.List<int[]> c = new java.util.ArrayList<>();
        if (q.headers().isEmpty()) {
            c.add(new int[] {16, 43});
        } else if (exact.isEmpty()) {
            c.add(new int[] {13, 1});
        }
        if (valueLength <= 0) {
            c.add(new int[] {22, 1});
        }
        if (c.size() > 1) {
            throw refused("WEB READ HTTPHEADER with more than one condition at once");
        }
        if (c.size() == 1) {
            return new WebHeader(c.get(0)[0], c.get(0)[1], null);
        }
        if (exact.get(0)[1].length() > valueLength) {
            throw refused("WEB READ HTTPHEADER value longer than VALUELENGTH");
        }
        return new WebHeader(0, 0, exact.get(0)[1]);
    }

    /** WEB WRITE HTTPHEADER HTTPHEADER(name) NAMELENGTH(n) VALUE(area) VALUELENGTH(n) (server form; IBM CICS TS, EXEC CICS
     *  WEB WRITE HTTPHEADER; register X38): one header added to the response, recorded as WEB-HEADER (name, value) and
     *  compared; a header written twice is two headers (IBM: "in addition to the existing header"). LENGERR 35 for a
     *  NAMELENGTH not above zero, 55 for a VALUELENGTH not above zero or above 32000. Refused: no request stated, a header
     *  after the response was sent, a name that is blank or holds a blank or a colon, a length past its area, two
     *  conditions at once. */
    public int[] webWriteHeader(String name, int nameLength, String value, int valueLength) {
        CicsTask r = statedRequest();
        if (r.webSent || r.webHeld != null) {
            throw refused("WEB WRITE HTTPHEADER after the response was sent");
        }
        java.util.List<int[]> c = new java.util.ArrayList<>();
        if (nameLength <= 0) {
            c.add(new int[] {22, 35});
        }
        if (valueLength <= 0 || valueLength > 32000) {
            c.add(new int[] {22, 55});
        }
        if (c.size() > 1) {
            throw refused("WEB WRITE HTTPHEADER with more than one condition at once");
        }
        if (c.size() == 1) {
            return c.get(0);
        }
        if (nameLength > name.length() || valueLength > value.length()) {
            throw refused("WEB WRITE HTTPHEADER length beyond its area");
        }
        String n = name.substring(0, nameLength);
        if (n.isBlank() || n.chars().anyMatch(ch -> ch == ' ' || ch == ':')) {
            throw refused("WEB WRITE HTTPHEADER name blank or holding a blank or a colon");
        }
        event("WEB-HEADER", "name", n, "value", value.substring(0, valueLength), "resp", 0, "resp2", 0);
        return new int[] {0, 0};
    }

    /** WEB RETRIEVE DOCTOKEN(area) (IBM CICS TS, EXEC CICS WEB RETRIEVE; register X41): the document of the last WEB SEND.
     *  NORMAL (resp 0, the DOCTOKEN): the last WEB SEND was a document send with ACTION(EVENTUAL) and no DOCDELETE; the token
     *  names a copy of the document as it was sent (IBM: later changes are not in it; ASSUMED: a new document of the task,
     *  the same token for every retrieve of that send). INVREQ RESP2 2: no WEB SEND has been issued; NOTFND RESP2 1: the last
     *  WEB SEND was DOCDELETE or not an EVENTUAL document send. Refused: no request stated (IBM's INVREQ RESP2 1, a non-web
     *  task, cannot be told from it), a retrieve after a WEB SEND that ended in a condition (IBM does not say whether it was
     *  issued). The outcome is a DocumentCreated (resp, resp2, the token: null unless NORMAL). */
    public DocumentCreated webRetrieve() {
        CicsTask r = statedRequest();
        if (r.webSendFailed) {
            throw refused("WEB RETRIEVE after a WEB SEND that ended in a condition");
        }
        if (!r.webIssued) {
            return new DocumentCreated(16, 2, null);
        }
        if (r.webHeldDoc == null) {
            return new DocumentCreated(13, 1, null);
        }
        if (r.webHeldToken == null) {
            r.webHeldToken = newDocument(r.webHeldDoc).doctoken();
        }
        return new DocumentCreated(0, 0, r.webHeldToken);
    }

    // #4940 (register X38): WEB READ FORMFIELD / QUERYPARM and the WEB browse forms (STARTBROWSE / READNEXT / ENDBROWSE of
    // HTTPHEADER, FORMFIELD, QUERYPARM) on the stated request. FORMFIELD reads the name=value pairs of the body (a form,
    // application/x-www-form-urlencoded), QUERYPARM those of the query string (both unescaped, %XX only), HTTPHEADER the
    // headers; a browse's position is the task's (kind -> {next pair, 1 once ENDFILE was returned}).
    private final java.util.Map<String, int[]> webBrowses = new java.util.HashMap<>();

    private static String webPlain(String kind, String s) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char ch = s.charAt(i);
            if (ch == '+' || ch == ';' || ch <= ' ' || ch > '~') {
                throw refused("WEB " + kind + " data outside the modelled name=value form");
            }
            if (ch == '%') {
                if (i + 2 >= s.length() || !webHexAny(s.charAt(i + 1)) || !webHexAny(s.charAt(i + 2))) {
                    throw refused("WEB " + kind + " data outside the modelled name=value form");
                }
                int hi = webHexValue(s.charAt(i + 1));
                int lo = webHexValue(s.charAt(i + 2));
                if (hi * 16 + lo < 32 || hi * 16 + lo > 126) {
                    throw refused("WEB " + kind + " data outside the modelled name=value form");
                }
                b.append((char) (hi * 16 + lo));
                i += 2;
            } else {
                b.append(ch);
            }
        }
        return b.toString();
    }

    /** The pairs a form's data holds (null: the request has none), unescaped. */
    private static java.util.List<String[]> webPairs(HttpRequest q, String kind) {
        if (kind.equals("HTTPHEADER")) {
            return q.headers().isEmpty() ? null : q.headers();
        }
        String data = kind.equals("QUERYPARM") ? q.query() : q.body();
        if (kind.equals("FORMFIELD") && data != null && !data.isEmpty()
                && !"application/x-www-form-urlencoded".equalsIgnoreCase(q.mediaType())) {
            throw refused("WEB FORMFIELD body not application/x-www-form-urlencoded");
        }
        if (data == null || data.isEmpty()) {
            return null;
        }
        java.util.List<String[]> pairs = new java.util.ArrayList<>();
        for (String piece : data.split("&", -1)) {
            int eq = piece.indexOf('=');
            if (eq <= 0 || piece.indexOf('%') >= 0 && piece.indexOf('%') < eq) {
                throw refused("WEB " + kind + " data outside the modelled name=value form");
            }
            pairs.add(new String[] {webPlain(kind, piece.substring(0, eq)), webPlain(kind, piece.substring(eq + 1))});
        }
        return pairs;
    }

    /** WEB READ FORMFIELD / QUERYPARM's outcome: RESP, RESP2 and, on NORMAL or LENGERR 5 (a value longer than VALUELENGTH:
     *  cut to it), the value; `length` is the value's whole length (what VALUELENGTH then holds). Else value is null. */
    public record WebParam(int resp, int resp2, String value, int length) {
    }

    /** WEB READ FORMFIELD(name) / QUERYPARM(name) NAMELENGTH(n) VALUE(area) VALUELENGTH(area) (server form; IBM CICS TS, EXEC
     *  CICS WEB READ FORMFIELD, WEB READ QUERYPARM; register X38). `kind` FORMFIELD or QUERYPARM. The name is not case
     *  sensitive (IBM); the value is unescaped (IBM). INVREQ 13 (no forms data / keyword parameters), NOTFND 1, LENGERR 1
     *  (NAMELENGTH or VALUELENGTH not above zero), LENGERR 5 (the value cut, VALUELENGTH its real length). Refused: no
     *  request stated, data outside the modelled name=value form, two pairs of the name (IBM does not say), a length past
     *  its area, two conditions at once. */
    public WebParam webReadParam(String kind, String name, int nameLength, int valueLength, int valueCap) {
        HttpRequest q = statedRequest().httpRequest;
        if (nameLength > name.length() || valueLength > valueCap) {
            throw refused("WEB READ " + kind + " length beyond its area");
        }
        java.util.List<String[]> pairs = webPairs(q, kind);
        java.util.List<int[]> c = new java.util.ArrayList<>();
        String[] hit = null;
        if (pairs == null) {
            c.add(new int[] {16, 13});
        } else if (nameLength > 0) {
            String n = name.substring(0, nameLength);
            java.util.List<String[]> found = pairs.stream().filter(p -> p[0].equalsIgnoreCase(n)).toList();
            if (found.size() > 1) {
                throw refused("WEB READ " + kind + " two pairs of the name");
            }
            if (found.isEmpty()) {
                c.add(new int[] {13, 1});
            } else {
                hit = found.get(0);
            }
        }
        if (nameLength <= 0 || valueLength <= 0) {
            c.add(new int[] {22, 1});
        }
        if (c.size() > 1) {
            throw refused("WEB READ " + kind + " with more than one condition at once");
        }
        if (c.size() == 1) {
            return new WebParam(c.get(0)[0], c.get(0)[1], null, 0);
        }
        int n = hit[1].length();
        return n > valueLength ? new WebParam(22, 5, hit[1].substring(0, valueLength), n) : new WebParam(0, 0, hit[1], n);
    }

    /** WEB STARTBROWSE HTTPHEADER | FORMFIELD [(name) NAMELENGTH(n)] | QUERYPARM [(name) NAMELENGTH(n)] (server form; IBM CICS
     *  TS; register X38). `name` null: from the first pair (HTTPHEADER has no name); else from the pair of that name. ILLOGIC
     *  5 (10 for HTTPHEADER) when a browse of the kind is already in progress, INVREQ 13 (43 for HTTPHEADER) when there is
     *  nothing to browse, NOTFND 1, LENGERR 1. A start that raises a condition starts no browse (ASSUMED). Refused: no
     *  request stated, a name found only without case or twice (IBM does not say), data outside the modelled form, a
     *  length past its area, two conditions at once. */
    public int[] webStartBrowse(String kind, String name, Integer nameLength) {
        CicsTask r = statedRequest();
        boolean header = kind.equals("HTTPHEADER");
        if (nameLength != null && nameLength > name.length()) {
            throw refused("WEB STARTBROWSE " + kind + " length beyond its area");
        }
        java.util.List<String[]> pairs = webPairs(r.httpRequest, kind);
        java.util.List<int[]> c = new java.util.ArrayList<>();
        int start = 0;
        if (r.webBrowses.containsKey(kind)) {
            c.add(new int[] {21, header ? 10 : 5});
        }
        if (nameLength != null && nameLength <= 0) {
            c.add(new int[] {22, 1});
        }
        if (pairs == null) {
            c.add(new int[] {16, header ? 43 : 13});
        } else if (nameLength != null && nameLength > 0) {
            String n = name.substring(0, nameLength);
            java.util.List<Integer> at = new java.util.ArrayList<>();
            for (int i = 0; i < pairs.size(); i++) {
                if (pairs.get(i)[0].equalsIgnoreCase(n)) {
                    at.add(i);
                }
            }
            if (at.size() > 1) {
                throw refused("WEB STARTBROWSE " + kind + " two pairs of the name");
            }
            if (at.isEmpty()) {
                c.add(new int[] {13, 1});
            } else if (!pairs.get(at.get(0))[0].equals(n)) {
                throw refused("WEB STARTBROWSE " + kind + " name found only without case");
            } else {
                start = at.get(0);
            }
        }
        if (c.size() > 1) {
            throw refused("WEB STARTBROWSE " + kind + " with more than one condition at once");
        }
        if (c.size() == 1) {
            return c.get(0);
        }
        r.webBrowses.put(kind, new int[] {start, 0});
        return new int[] {0, 0};
    }

    /** WEB READNEXT's outcome: RESP, RESP2 and, on NORMAL or a truncation (LENGERR 4 / 5), the pair's name and value (cut to
     *  the lengths the program gave) and their whole lengths; else the strings are null. */
    public record WebNext(int resp, int resp2, String name, String value, int nameLength, int valueLength) {
    }

    /** WEB READNEXT HTTPHEADER | FORMFIELD | QUERYPARM (name) NAMELENGTH(area) VALUE(area) VALUELENGTH(area) (server form; IBM
     *  CICS TS; register X38): the next pair in the order the request states them; each length is the area's size in and the
     *  pair's whole length out. INVREQ 4 before a start, ENDFILE (RESP2 0: IBM lists none) at the end, LENGERR 1 (a length
     *  not above zero: nothing is read, the browse stays), LENGERR 4 / 5 for a FORMFIELD / QUERYPARM name / value that does
     *  not fit (cut; the same pair is returned again, IBM). Refused: no request stated, a READNEXT after ENDFILE, a name and
     *  a value both too long, a header that does not fit (IBM does not say what the lengths hold or whether the browse
     *  moves on), data outside the modelled form, a length past its area, two conditions at once. */
    public WebNext webReadNext(String kind, int nameLength, int nameCap, int valueLength, int valueCap) {
        CicsTask r = statedRequest();
        if (nameLength > nameCap || valueLength > valueCap) {
            throw refused("WEB READNEXT " + kind + " length beyond its area");
        }
        int[] st = r.webBrowses.get(kind);
        if (st == null) {
            return new WebNext(16, 4, null, null, 0, 0);
        }
        java.util.List<String[]> pairs = webPairs(r.httpRequest, kind);
        boolean end = st[0] >= pairs.size();
        if (end && st[1] != 0) {
            throw refused("WEB READNEXT " + kind + " after ENDFILE");
        }
        java.util.List<int[]> c = new java.util.ArrayList<>();
        if (nameLength <= 0 || valueLength <= 0) {
            c.add(new int[] {22, 1});
        }
        if (end) {
            c.add(new int[] {20, 0});
        }
        if (c.size() > 1) {
            throw refused("WEB READNEXT " + kind + " with more than one condition at once");
        }
        if (c.size() == 1) {
            st[1] = end ? 1 : st[1];
            return new WebNext(c.get(0)[0], c.get(0)[1], null, null, 0, 0);
        }
        String[] p = pairs.get(st[0]);
        boolean cutName = p[0].length() > nameLength;
        boolean cutValue = p[1].length() > valueLength;
        if (cutName && cutValue) {
            throw refused("WEB READNEXT " + kind + " name and value both truncated");
        }
        if ((cutName || cutValue) && kind.equals("HTTPHEADER")) {
            throw refused("WEB READNEXT HTTPHEADER truncated");
        }
        String name = cutName ? p[0].substring(0, nameLength) : p[0];
        String value = cutValue ? p[1].substring(0, valueLength) : p[1];
        if (!cutName && !cutValue) {
            st[0]++;
        }
        return new WebNext(cutName ? 22 : cutValue ? 22 : 0, cutName ? 4 : cutValue ? 5 : 0, name, value, p[0].length(),
                p[1].length());
    }

    /** WEB ENDBROWSE HTTPHEADER | FORMFIELD | QUERYPARM (server form; IBM CICS TS; register X38): INVREQ 4 before a start. */
    public int[] webEndBrowse(String kind) {
        CicsTask r = statedRequest();
        return r.webBrowses.remove(kind) == null ? new int[] {16, 4} : new int[] {0, 0};
    }

    // #4767 zECS (register X36): WEB PARSE URL (IBM CICS TS, EXEC CICS WEB PARSE URL) -- pure: no peer is involved.
    /** WEB PARSE URL's outcome: RESP, RESP2 and, on NORMAL, the scheme (upper case, blank-padded to SCHEMENAME's area),
     *  host, port (explicit, else 80 for HTTP / 443 for HTTPS), path (with its leading '/') and query string (without
     *  its '?', still escaped); else the strings are null and the port -1. */
    public record WebParsed(int resp, int resp2, String scheme, String host, int port, String path, String query) {
    }

    /** An ASCII hex digit of either case (never another script's digits). */
    private static boolean webHexAny(char c) {
        return webHex(c) || (c >= 'a' && c <= 'f');
    }

    /** The value of an ASCII hex digit of either case (callers check webHexAny first). */
    private static int webHexValue(char c) {
        return c <= '9' ? c - '0' : (c & 0x5f) - 'A' + 10;
    }

    private static boolean webHex(char c) {
        return (c >= '0' && c <= '9') || (c >= 'A' && c <= 'F');
    }

    /** WEB PARSE URL: `url` is the URL area's text and urlLength URLLENGTH; hostLength / pathLength / queryLength are the
     *  HOSTLENGTH / PATHLENGTH / QUERYSTRLEN values (null: the option is not given) and the caps the areas' sizes (the
     *  length options are read here, written by the caller to the piece's length). INVREQ 28 (no "scheme://", an empty
     *  scheme or host, a port that is not 1-5 digits or above 65535: ASSUMED), INVREQ 65 (a "%" not followed by two of
     *  0-9 A-F), LENGERR 22 (RESP2 29 host, 30 path, 8 query string longer than its length; the areas and lengths are
     *  left alone: ASSUMED, IBM says the data is truncated but not what the length then holds). An IPv6 host is written
     *  in brackets and returned without them. Refused: a scheme other than HTTP / HTTPS, a user-info part, a fragment, an
     *  IPv6 host that is not [hex:colons] or [hex:colons]:port, an empty port or port 0, a lowercase hex digit in an
     *  escape, a URLLENGTH not above zero, a length past its area, a PATH or QUERYSTRING asked for when the URL has none,
     *  two conditions (INVREQ and LENGERR, or two pieces too long). */
    public WebParsed webParse(String url, int urlLength, int schemeCap, Integer hostLength, int hostCap,
                              Integer pathLength, int pathCap, Integer queryLength, int queryCap) {
        if (urlLength <= 0 || urlLength > url.length()) {
            throw refused(urlLength <= 0 ? "WEB PARSE URL URLLENGTH not above zero" : "WEB PARSE URL length beyond its area");
        }
        if ((hostLength != null && hostLength > hostCap) || (pathLength != null && pathLength > pathCap)
                || (queryLength != null && queryLength > queryCap)) {
            throw refused("WEB PARSE URL length beyond its area");
        }
        String u = url.substring(0, urlLength);
        boolean bad28 = false;
        boolean bad65 = false;
        for (int i = 0; i < u.length(); i++) {
            if (u.charAt(i) == '%') {
                boolean ok = i + 2 < u.length() && webHex(u.charAt(i + 1)) && webHex(u.charAt(i + 2));
                boolean lower = i + 2 < u.length() && webHexAny(u.charAt(i + 1)) && webHexAny(u.charAt(i + 2));
                if (!ok && lower) {
                    throw refused("WEB PARSE URL lowercase hex digit in an escape");
                }
                bad65 |= !ok;
            }
        }
        if (u.indexOf('#') >= 0) {
            throw refused("WEB PARSE URL fragment");
        }
        int sep = u.indexOf("://");
        String scheme = sep < 0 ? "" : u.substring(0, sep).toUpperCase(java.util.Locale.ROOT);
        if (sep <= 0) {
            bad28 = true;
        } else if (!scheme.equals("HTTP") && !scheme.equals("HTTPS")) {
            throw refused("WEB PARSE URL scheme other than HTTP / HTTPS");
        }
        String host = "";
        String path = "";
        String query = "";
        int port = -1;
        if (!bad28) {
            String rest = u.substring(sep + 3);
            int e = rest.length();
            for (int i = 0; i < rest.length(); i++) {
                if (rest.charAt(i) == '/' || rest.charAt(i) == '?') {
                    e = i;
                    break;
                }
            }
            String auth = rest.substring(0, e);
            if (auth.indexOf('@') >= 0) {
                throw refused("WEB PARSE URL user-info");
            }
            String ps = null;
            if (auth.startsWith("[")) {
                int close = auth.indexOf(']');
                boolean shaped = close >= 2 && (close + 1 == auth.length() || auth.charAt(close + 1) == ':')
                        && auth.indexOf('[', 1) < 0 && auth.indexOf(']', close + 1) < 0
                        && auth.substring(1, close).chars().allMatch(c -> webHexAny((char) c) || c == ':' || c == '.');
                if (!shaped) {
                    throw refused("WEB PARSE URL IPv6 host that is not [hex:colons] or [hex:colons]:port");
                }
                host = auth.substring(1, close);
                ps = close + 1 == auth.length() ? null : auth.substring(close + 2);
            } else {
                if (auth.indexOf('[') >= 0 || auth.indexOf(']') >= 0) {
                    throw refused("WEB PARSE URL IPv6 host that is not [hex:colons] or [hex:colons]:port");
                }
                int colon = auth.lastIndexOf(':');
                host = colon < 0 ? auth : auth.substring(0, colon);
                ps = colon < 0 ? null : auth.substring(colon + 1);
            }
            if (ps != null) {
                if (ps.isEmpty()) {
                    throw refused("WEB PARSE URL empty port");
                }
                if (!ps.chars().allMatch(c -> c >= '0' && c <= '9') || ps.length() > 5 || Integer.parseInt(ps) > 65535) {
                    bad28 = true;
                } else if (Integer.parseInt(ps) == 0) {
                    throw refused("WEB PARSE URL port 0");
                } else {
                    port = Integer.parseInt(ps);
                }
            } else {
                port = scheme.equals("HTTPS") ? 443 : 80;
            }
            bad28 |= host.isEmpty();
            String tail = rest.substring(e);
            int q = tail.indexOf('?');
            path = q < 0 ? tail : tail.substring(0, q);
            query = q < 0 ? "" : tail.substring(q + 1);
        }
        boolean hostLong = hostLength != null && host.length() > hostLength;
        boolean pathLong = pathLength != null && path.length() > pathLength;
        boolean queryLong = queryLength != null && query.length() > queryLength;
        if ((bad28 ? 1 : 0) + (bad65 ? 1 : 0) + (hostLong ? 1 : 0) + (pathLong ? 1 : 0) + (queryLong ? 1 : 0) > 1) {
            throw refused("WEB PARSE URL with more than one condition at once");
        }
        if (bad28 || bad65) {
            return new WebParsed(16, bad28 ? 28 : 65, null, null, -1, null, null);
        }
        if (schemeCap > 0 && scheme.length() > schemeCap) {
            throw refused("WEB PARSE URL length beyond its area");
        }
        if ((pathLength != null && path.isEmpty()) || (queryLength != null && query.isEmpty())) {
            throw refused("WEB PARSE URL PATH or QUERYSTRING the URL has none of");
        }
        if (hostLong || pathLong || queryLong) {
            return new WebParsed(22, hostLong ? 29 : pathLong ? 30 : 8, null, null, -1, null, null);
        }
        String padded = schemeCap > 0 ? String.format(java.util.Locale.ROOT, "%-" + schemeCap + "s", scheme) : scheme;
        return new WebParsed(0, 0, padded, host, port, path, query);
    }

"""
