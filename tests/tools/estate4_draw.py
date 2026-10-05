#!/usr/bin/env python3
"""Blind candidate list and verifiable draw for the 4th CICS estate trial.

Subcommands
  inputs  Collect the exclusion inputs (development-data repos, burned-estate
          file basenames) from OUR local corpora. Names only.
  build   Metadata-only crawl of GitHub. Every HTTP call goes through
          ``ApiClient``, which enforces an allow-list and logs the request.
  draw    Fetch a drand round and pick the winner (run on the target round).

Blindness rule: no candidate code or README is ever read. Allowed endpoints:
  GET /search/repositories
  GET /repos/{o}/{r}
  GET /repos/{o}/{r}/languages
  GET /repos/{o}/{r}/license        (only the SPDX id is used)
  GET /repos/{o}/{r}/git/trees/{ref}?recursive=1   (paths only)
  GET /users/{owner}
  GET /repos/{o}/{r}/git/ref/heads/{branch}   (commit sha)
  GET /repos/{o}/{r}/git/commits/{sha}        (ONLY tree.sha is kept; nothing else stored)
Pre-registration: docs/language_status/estate4_preregistration.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gitgalaxy.core.source_text import read_source  # noqa: E402
DOCS = ROOT / "docs" / "language_status"
CANDIDATES_JSON = DOCS / "estate4_candidates.json"
CANDIDATES_MD = DOCS / "estate4_candidates.md"
REQUEST_LOG = DOCS / "estate4_candidates_requests.json"
DEVDATA_JSON = DOCS / "estate4_devdata_repos.json"
BURNED_JSON = DOCS / "estate4_burned_basenames.json"

API = "https://api.github.com"
DEFAULT_CACHE = Path("/tmp/estate4_build_cache.json")

# ---- allow-list -----------------------------------------------------------
SEG = r"[A-Za-z0-9_.-]+"
ALLOWED = [
    re.compile(r"^/search/repositories\?"),
    re.compile(rf"^/repos/{SEG}/{SEG}$"),
    re.compile(rf"^/repos/{SEG}/{SEG}/languages$"),
    re.compile(rf"^/repos/{SEG}/{SEG}/license$"),
    re.compile(rf"^/repos/{SEG}/{SEG}/git/trees/[A-Za-z0-9_./-]+\?recursive=1$"),
    re.compile(rf"^/users/{SEG}$"),
    # commit-id pinning (owner-approved): ref -> commit sha; commit -> only tree.sha is used
    re.compile(rf"^/repos/{SEG}/{SEG}/git/ref/heads/[A-Za-z0-9_./-]+$"),
    re.compile(rf"^/repos/{SEG}/{SEG}/git/commits/[0-9a-f]{{40}}$"),
]
FORBIDDEN_FRAGMENTS = (
    "/contents",
    "/readme",
    "/git/blobs",
    "raw.githubusercontent.com",
    "/search/code",
    "/zipball",
    "/tarball",
    "/archive/",
)


def is_allowed(method: str, url: str) -> bool:
    """True only for a GET to an allow-listed GitHub API endpoint."""
    if method != "GET" or not url.startswith(API):
        return False
    path = url[len(API):]
    low = path.lower()
    base = low.split("?", 1)[0]
    if any(f in base for f in FORBIDDEN_FRAGMENTS):
        return False
    return any(p.match(path) for p in ALLOWED)


def forbidden_in_log(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Entries of a request log that are not allow-listed."""
    return [e for e in entries if not is_allowed(str(e.get("method")), str(e.get("url")))]


class ApiClient:
    """GitHub GET client: allow-list enforced, every request logged, cached."""

    def __init__(self, token: str, cache_path: Path = DEFAULT_CACHE) -> None:
        self.token = token
        self.cache_path = cache_path
        self.log: list[dict[str, Any]] = []
        self.cache: dict[str, dict[str, Any]] = {}
        self._last_search = 0.0
        if cache_path.exists():
            blob = json.loads(cache_path.read_text())
            self.log = blob["log"]
            self.cache = blob["cache"]

    def save(self) -> None:
        self.cache_path.write_text(json.dumps({"log": self.log, "cache": self.cache}))

    def get(self, path: str) -> tuple[int, Any]:
        url = API + path
        if not is_allowed("GET", url):
            raise PermissionError(f"blocked by allow-list: GET {url}")
        if url in self.cache:
            c = self.cache[url]
            return c["status"], c["body"]
        for attempt in range(8):
            if path.startswith("/search/"):
                wait = 2.2 - (time.time() - self._last_search)
                if wait > 0:
                    time.sleep(wait)
                self._last_search = time.time()
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": "gitgalaxy-estate4-draw",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    status, body = r.status, json.loads(r.read())
                    remaining = r.headers.get("X-RateLimit-Remaining")
                    reset = r.headers.get("X-RateLimit-Reset")
            except urllib.error.HTTPError as e:
                status = e.code
                raw = e.read()
                try:
                    body = json.loads(raw)
                except ValueError:
                    body = {}
                remaining = e.headers.get("X-RateLimit-Remaining")
                reset = e.headers.get("X-RateLimit-Reset")
                retry = e.headers.get("Retry-After")
                self.log.append({"method": "GET", "url": url, "status": status})
                if status in (403, 429) and (remaining == "0" or retry):
                    sleep = int(retry) if retry else max(5, int(reset or 0) - int(time.time()) + 2)
                    print(f"rate limited; sleeping {sleep}s", file=sys.stderr)
                    time.sleep(min(sleep, 3700))
                    continue
                if status >= 500:
                    time.sleep(5 * (attempt + 1))
                    continue
                if status not in (403, 429):
                    self.cache[url] = {"status": status, "body": body}
                return status, body
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                time.sleep(5 * (attempt + 1))
                continue
            self.log.append({"method": "GET", "url": url, "status": status})
            if "/git/commits/" in path and status == 200:
                body = {"tree": {"sha": body["tree"]["sha"]}}  # drop message/author
            self.cache[url] = {"status": status, "body": body}
            if remaining is not None and int(remaining) < 3 and reset:
                time.sleep(max(1, int(reset) - int(time.time()) + 2))
            return status, body
        raise RuntimeError(f"giving up on {url}")


# ---- eligibility constants ------------------------------------------------
OK_LICENSES = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "0BSD", "EPL-2.0"}
EXCLUDED_OWNERS = {"squid-protocol", "jmesquib"}
INELIGIBLE_LIST = sorted(
    {
        "cicsdev/cics-java-recgen",
        "cicsdev/cics-async-api-redbooks",
        "cicsdev/cics-async-api-credit-card-application-example",
        "cicsdev/cics-java-liberty-loans-and-scoring",
        "zosconnect/zosconnect-sample-cobol-apirequester",
        "graziano10/nexusbank_v1.2_cobol",
        "thisouza01/cobol-db2-refatorado",
        "martinluc/cobol-db2-cursor",
        "martinluc/cobol_db2_stringsearch",
        # the 5 burned estates
        "aws/aws-mainframe-modernization-carddemo",
        "cicsdev/cics-banking-sample-application-cbsa",
        "cicsdev/cics-genapp",
        "walmartlabs/zecs",
        "ibm/dbb",
    }
)
# repo-name (not owner) match for the burned estates, whichever fork/owner hosts them
BURNED_NAMES = {
    "aws-mainframe-modernization-carddemo",
    "cics-banking-sample-application-cbsa",
    "cics-genapp",
    "zecs",
    "dbb",
    "mortgageapplication",
    "dbb-mortgage-application",
}
COPY_NAME_RE = re.compile(r"carddemo|genapp|cbsa|zecs|mortgage", re.I)
COPY_BASENAME_FRACTION = 0.30
MIN_COBOL_BYTES = 20_000
MIN_PROGRAMS, MAX_PROGRAMS = 5, 300
PROGRAM_EXT = (".cbl", ".cob", ".cobol")
BASENAME_EXT = PROGRAM_EXT + (".cpy",)

# ---- foreign heuristic ----------------------------------------------------
EN_WORDS = set(
    "the a an and of for to in on with is are this that from by as it its or be "
    "your you our using use sample samples example examples code application "
    "app demo project projects programs program support simple system data file "
    "files tool tools library based into test tests cics cobol mainframe".split()
)
FOREIGN_WORDS = {
    "pt": "de do da dos das para com uma um em os as e que sistema cadastro programa exemplo aplicacao projeto estudo cobol".split(),
    "es": "de del la las los el para con una un en y que sistema ejemplo aplicacion proyecto programa".split(),
    "fr": "de du la le les des pour avec une un et dans sur application exemple projet programme systeme".split(),
    "de": "der die das und fuer mit eine ein von zu im den beispiel anwendung projekt programm".split(),
    "it": "di del della il lo la le gli per con una un e che esempio applicazione progetto programma".split(),
    "nl": "de het een en van voor met toepassing voorbeeld".split(),
    "tr": "ve ile bir icin uygulama ornek".split(),
    "pl": "i w z na dla do aplikacja przyklad".split(),
}
# words shared with English or too short to be evidence on their own
FOREIGN_STOP = {"a", "e", "i", "w", "z", "de", "la", "le", "un", "do", "na", "es", "cobol", "en", "as", "os", "di", "il", "lo", "el", "in"}


def non_english(text: str) -> bool:
    """Deterministic heuristic: >= 2 distinctive non-English words, and more
    of them than English function words, in the lowercased ASCII-folded text."""
    words = re.findall(r"[a-z]+", text.lower())
    if not words:
        return False
    en = sum(1 for w in words if w in EN_WORDS)
    best = 0
    for vocab in FOREIGN_WORDS.values():
        vs = set(vocab) - FOREIGN_STOP
        best = max(best, sum(1 for w in words if w in vs))
    return best >= 2 and best > en


def has_non_ascii_letter(text: str) -> bool:
    return any(ord(c) > 127 and c.isalpha() for c in text)


ANGLO = (
    "usa united states u.s. america uk united kingdom england scotland wales northern ireland great britain "
    "canada australia ireland new zealand london manchester edinburgh glasgow dublin cork toronto vancouver "
    "montreal ottawa calgary sydney melbourne brisbane perth auckland wellington nyc new york san francisco "
    "los angeles seattle boston chicago austin dallas houston denver atlanta portland washington dc silicon valley"
).split(" ")
ANGLO_PHRASES = [
    "united states", "united kingdom", "northern ireland", "great britain", "new zealand", "new york",
    "san francisco", "los angeles", "silicon valley", "washington dc",
]
US_STATE_RE = re.compile(
    r"(?:,\s*|\s)(al|ak|az|ar|ca|co|ct|de|fl|ga|hi|id|il|in|ia|ks|ky|la|me|md|ma|mi|mn|ms|mo|mt|ne|nv|nh|nj|nm|ny|nc|nd|oh|ok|or|pa|ri|sc|sd|tn|tx|ut|vt|va|wa|wv|wi|wy)$",
    re.I,
)
ANGLO_WORDS = {"usa", "us", "uk", "canada", "australia", "ireland", "england", "scotland", "wales",
               "london", "dublin", "toronto", "sydney", "melbourne", "auckland", "california", "texas",
               "florida", "ontario", "colorado", "virginia", "massachusetts", "illinois", "oregon"}
FOREIGN_PLACES = (
    "india bangalore bengaluru mumbai delhi hyderabad chennai pune kolkata noida gurgaon gurugram pakistan karachi "
    "lahore bangladesh dhaka sri lanka colombo nepal china beijing shanghai shenzhen guangzhou hangzhou chengdu "
    "hong kong taiwan taipei japan tokyo osaka kyoto korea seoul singapore malaysia kuala lumpur indonesia jakarta "
    "vietnam hanoi thailand bangkok philippines manila brazil brasil sao paulo rio de janeiro brasilia belo horizonte "
    "porto alegre curitiba argentina buenos aires chile santiago colombia bogota medellin peru lima mexico "
    "uruguay montevideo venezuela ecuador quito bolivia costa rica panama cuba spain espana madrid barcelona "
    "valencia sevilla portugal lisboa lisbon porto france paris lyon marseille toulouse germany deutschland berlin "
    "munich muenchen münchen hamburg frankfurt cologne koeln köln stuttgart dusseldorf düsseldorf italy italia "
    "rome roma milan milano turin torino netherlands nederland amsterdam rotterdam utrecht belgium belgique "
    "brussels bruxelles switzerland schweiz suisse zurich zürich geneva genf austria österreich vienna wien "
    "sweden sverige stockholm gothenburg norway norge oslo denmark danmark copenhagen finland helsinki iceland "
    "poland polska warsaw warszawa krakow kraków wroclaw czech prague praha slovakia bratislava hungary budapest "
    "romania bucharest bulgaria sofia serbia belgrade croatia zagreb slovenia ljubljana greece athens turkey "
    "türkiye istanbul ankara russia moscow saint petersburg ukraine kyiv kiev belarus minsk lithuania vilnius "
    "latvia riga estonia tallinn israel tel aviv jerusalem egypt cairo morocco nigeria lagos kenya nairobi "
    "south africa johannesburg cape town ghana uae dubai abu dhabi saudi arabia riyadh qatar iran tehran "
    "iraq lebanon beirut jordan amman kazakhstan uzbekistan georgia tbilisi armenia"
).split()
FOREIGN_PHRASES = [
    "sri lanka", "hong kong", "kuala lumpur", "sao paulo", "são paulo", "rio de janeiro", "belo horizonte",
    "porto alegre", "buenos aires", "costa rica", "saint petersburg", "tel aviv", "south africa", "cape town",
    "abu dhabi", "saudi arabia", "south korea", "united arab emirates",
]


def location_foreign(location: str | None) -> bool:
    """True when the profile location names a place outside US/UK/CA/AU/IE/NZ.

    Anglo keywords win. Empty or unrecognised locations count as not foreign.
    """
    if not location:
        return False
    low = location.lower()
    for ph in ANGLO_PHRASES:
        if ph in low:
            return False
    tokens = re.findall(r"[^\W\d_]+", low)
    if any(t in ANGLO_WORDS for t in tokens):
        return False
    if US_STATE_RE.search(low.strip()) and "," in low:
        return False
    for ph in FOREIGN_PHRASES:
        if ph in low:
            return True
    foreign_single = set(FOREIGN_PLACES) - {"de", "rio", "porto", "south", "cape", "town", "saint", "tel", "sri",
                                            "lanka", "hong", "kong", "kuala", "lumpur", "sao", "paulo", "belo",
                                            "horizonte", "alegre", "buenos", "aires", "costa", "rica", "abu",
                                            "dhabi", "saudi", "arabia", "janeiro", "africa", "aviv", "petersburg"}
    return any(t in foreign_single for t in tokens)


def compute_foreign(description: str | None, topics: list[str], paths: list[str], location: str | None) -> int:
    meta = " ".join([description or ""] + list(topics))
    s = 0
    if has_non_ascii_letter(meta) or non_english(meta):
        s += 1
    if any(not p.isascii() for p in paths):
        s += 1
    if location_foreign(location):
        s += 1
    return s


def compute_hard(paths: list[str], programs: int) -> int:
    low = [p.lower() for p in paths]
    comps = [p.split("/") for p in low]
    jcl = any(p.endswith(".jcl") for p in low) or any("jcl" in c[:-1] for c in comps)
    pli = any(p.endswith((".pli", ".pl1")) for p in low)
    asm_dirs = {"asm", "assembler", "assembly", "hlasm"}
    asm = any(p.endswith((".asm", ".mac")) for p in low) or any(
        p.endswith(".s") and asm_dirs & set(c[:-1]) for p, c in zip(low, comps)  # comps is built from low: same length
    )
    db2 = any(p.endswith((".dcl", ".sql", ".dbd", ".psb")) for p in low)
    return int(jcl) + int(pli) + int(asm) + int(db2) + int(programs >= 50)


def tree_stats(paths: list[str]) -> dict[str, Any]:
    low = [p.lower() for p in paths]
    stems = {
        p.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        for p in low
        if p.endswith(BASENAME_EXT)
    }
    return {
        "bms": sum(1 for p in low if p.endswith(".bms")),
        "csd": sum(1 for p in low if p.endswith(".csd")),
        "programs": sum(1 for p in low if p.endswith(PROGRAM_EXT)),
        "cobol_files": sum(1 for p in low if p.endswith(BASENAME_EXT)),
        "stems": stems,
    }


def burned_overlap(stems_by_file: list[str], burned: dict[str, list[str]]) -> tuple[float, str]:
    """Max fraction of this repo's COBOL file basenames (stem, lowercase)
    found in any one burned estate. Returns (fraction, estate)."""
    if not stems_by_file:
        return 0.0, ""
    best = (0.0, "")
    for estate, names in burned.items():
        ns = set(names)
        frac = sum(1 for s in stems_by_file if s in ns) / len(stems_by_file)
        if frac > best[0]:
            best = (frac, estate)
    return best


# ---- drand / selection ----------------------------------------------------
DRAND_BASE = "https://api.drand.sh"
CHAIN_HASH = "8990e7a9aaed2ffed73dbd7092123d6f289930540d7651336225dc172e51b2ce"
DRAND_PERIOD = 30
DRAND_GENESIS = 1595431050
TARGET_TIME = dt.datetime(2026, 10, 7, 12, 0, 0, tzinfo=dt.timezone.utc)


def round_for_time(t: dt.datetime, genesis: int = DRAND_GENESIS, period: int = DRAND_PERIOD) -> int:
    """First round whose time (genesis + (r-1)*period) is at or after t."""
    delta = int(t.timestamp()) - genesis
    return 1 if delta <= 0 else -(-delta // period) + 1


def round_time(r: int, genesis: int = DRAND_GENESIS, period: int = DRAND_PERIOD) -> dt.datetime:
    return dt.datetime.fromtimestamp(genesis + (r - 1) * period, tz=dt.timezone.utc)


def compute_seed(randomness_hex: str, candidates_bytes: bytes) -> str:
    return hashlib.sha256((randomness_hex + hashlib.sha256(candidates_bytes).hexdigest()).encode()).hexdigest()


def select(candidates: list[dict[str, Any]], seed_hex: str) -> tuple[int, int, dict[str, Any]]:
    """Weighted pick: walk the list with cumulative weights.
    Returns (index_value, total_weight, winner)."""
    total = sum(int(c["weight"]) for c in candidates)
    idx = int(seed_hex, 16) % total
    acc = 0
    for c in candidates:
        acc += int(c["weight"])
        if idx < acc:
            return idx, total, c
    raise AssertionError("unreachable")


def http_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=30) as r:  # drand only; not a candidate repo
        return json.loads(r.read())


def cmd_draw(args: argparse.Namespace) -> int:
    info = http_json(f"{DRAND_BASE}/info")
    if info.get("hash") != CHAIN_HASH:
        print("chain hash mismatch:", info.get("hash"), file=sys.stderr)
        return 2
    genesis, period = int(info["genesis_time"]), int(info["period"])
    if (genesis, period) != (DRAND_GENESIS, DRAND_PERIOD):
        print("genesis/period mismatch", genesis, period, file=sys.stderr)
        return 2
    rnd = http_json(f"{DRAND_BASE}/{CHAIN_HASH}/public/{args.round}")
    randomness = rnd["randomness"]
    if hashlib.sha256(bytes.fromhex(rnd["signature"])).hexdigest() != randomness:
        print("randomness != sha256(signature)", file=sys.stderr)
        return 2
    data = CANDIDATES_JSON.read_bytes()
    cands = json.loads(data)["candidates"]
    seed = compute_seed(randomness, data)
    idx, total, win = select(cands, seed)
    print(f"drand chain hash   : {CHAIN_HASH}")
    print(f"genesis / period   : {genesis} / {period}s")
    print(f"round              : {args.round}  ({round_time(args.round).isoformat()})")
    print(f"randomness         : {randomness}")
    print(f"candidates sha256  : {hashlib.sha256(data).hexdigest()}")
    print(f"seed               : {seed}")
    print(f"total weight       : {total}")
    print(f"index              : {idx}  (= int(seed,16) mod {total})")
    print(f"winner             : {win['full_name']}  weight={win['weight']}  sha={win['default_branch_sha']}")
    return 0


# ---- inputs (our own corpora; names only) ---------------------------------
GH_URL_RE = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")


def cmd_inputs(args: argparse.Namespace) -> int:
    gg = Path(args.gitgalaxy_root)
    sources = [
        ROOT / "tests/cobol_mainframe/corpora.json",
        ROOT / "tests/cobol_mainframe/field_testing.json",
        ROOT / "tests/cobol_mainframe/ground_truth_ledger.json",
    ]
    lc = gg / "language-crucible"
    sources += sorted(lc.rglob("SOURCES.md")) + sorted(lc.rglob("PROVENANCE.json"))
    for extra in ("cics-crucible-pin", "estate-crucible"):
        sources += sorted((gg / extra).rglob("SOURCES.md"))
    repos: dict[str, set[str]] = {}
    for f in sources:
        if not f.exists():
            continue
        for o, r in GH_URL_RE.findall(read_source(f).text):
            r = r.removesuffix(".git").rstrip(".")
            repos.setdefault(f"{o}/{r}".lower(), set()).add(str(f).replace(str(gg) + "/", "").replace(str(ROOT) + "/", ""))
    DEVDATA_JSON.write_text(
        json.dumps({"about": "GitHub repos cited by our own corpora (rule 7). Over-inclusive on purpose.",
                    "repos": {k: sorted(v) for k, v in sorted(repos.items())}}, indent=1) + "\n"
    )
    burned: dict[str, list[str]] = {}
    mc = Path(args.corpora_dir)
    for d in sorted(mc.iterdir()):
        if d.name in {"aws-mainframe-modernization-carddemo", "cics-banking-sample-application-cbsa",
                      "cics-genapp", "zecs", "dbb-mortgage-application"}:
            burned[d.name] = sorted(
                {p.name.lower().rsplit(".", 1)[0] for p in d.rglob("*") if p.is_file() and p.suffix.lower() in BASENAME_EXT}
            )
    BURNED_JSON.write_text(json.dumps({"about": "Lowercase COBOL file stems (.cbl/.cob/.cobol/.cpy) of the burned estates (rule 8).",
                                       "estates": burned}, indent=1) + "\n")
    print(f"devdata repos: {len(repos)}; burned stems: { {k: len(v) for k, v in burned.items()} }")
    return 0


# ---- build ----------------------------------------------------------------
def shards(client: ApiClient, lo: dt.date, hi: dt.date) -> list[tuple[dt.date, dt.date, int]]:
    q = f"language:COBOL fork:false is:public created:{lo}..{hi}"
    status, body = client.get("/search/repositories?" + urllib.parse.urlencode({"q": q, "per_page": 1}))
    if status != 200:
        raise RuntimeError(f"search failed {status}: {body}")
    n = int(body["total_count"])
    if n == 0:
        return []
    if n < 1000 or lo == hi:
        if n >= 1000:
            raise RuntimeError(f"single day {lo} has {n} >= 1000 results; add a size shard")
        return [(lo, hi, n)]
    mid = lo + (hi - lo) // 2
    return shards(client, lo, mid) + shards(client, mid + dt.timedelta(days=1), hi)


def search_all(client: ApiClient, lo: dt.date, hi: dt.date, n: int) -> list[dict[str, Any]]:
    q = f"language:COBOL fork:false is:public created:{lo}..{hi}"
    out: list[dict[str, Any]] = []
    for page in range(1, (n + 99) // 100 + 1):
        status, body = client.get(
            "/search/repositories?" + urllib.parse.urlencode({"q": q, "per_page": 100, "page": page, "sort": "created", "order": "asc"})
        )
        if status != 200:
            raise RuntimeError(f"search page failed {status}")
        out += body["items"]
    return out


def cmd_build(args: argparse.Namespace) -> int:
    token = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    client = ApiClient(token, Path(args.cache))
    devdata = set(json.loads(DEVDATA_JSON.read_text())["repos"])
    burned = json.loads(BURNED_JSON.read_text())["estates"]
    counts: dict[str, int] = {}

    today = dt.date.today()
    sh = shards(client, dt.date(2008, 1, 1), today)
    client.save()
    found: dict[str, dict[str, Any]] = {}
    for lo, hi, n in sh:
        for it in search_all(client, lo, hi, n):
            found[it["full_name"].lower()] = it
        client.save()
    n_search_total = sum(n for _, _, n in sh)
    counts["search_shards"] = len(sh)
    counts["search_reported_total"] = n_search_total
    counts["S0_unique_public_nonfork_cobol_repos"] = len(found)

    items = {k: v for k, v in found.items() if not v["fork"] and not v["private"]}
    counts["R1a_public_nonfork"] = len(items)
    items = {k: v for k, v in items.items() if v["owner"]["login"].lower() not in EXCLUDED_OWNERS}
    counts["R1_owner_not_excluded"] = len(items)
    items = {k: v for k, v in items.items() if ((v.get("license") or {}).get("spdx_id") in OK_LICENSES)}
    counts["R2_license_in_set_(search metadata)"] = len(items)

    repos: dict[str, dict[str, Any]] = {}
    for i, (k, v) in enumerate(sorted(items.items())):
        o, r = v["full_name"].split("/")
        st, meta = client.get(f"/repos/{o}/{r}")
        if st != 200 or meta.get("fork") or meta.get("private"):
            continue
        st, lic = client.get(f"/repos/{o}/{r}/license")
        spdx = (lic.get("license") or {}).get("spdx_id") if st == 200 else None
        if spdx not in OK_LICENSES:
            continue
        st, langs = client.get(f"/repos/{o}/{r}/languages")
        repos[k] = {"meta": meta, "license": spdx, "cobol_bytes": int((langs or {}).get("COBOL", 0)) if st == 200 else 0}
        if i % 50 == 0:
            client.save()
    client.save()
    counts["R2b_license_confirmed_via_/license_and_repo_still_public_nonfork"] = len(repos)

    pool = {k: v for k, v in repos.items() if v["cobol_bytes"] >= MIN_COBOL_BYTES}
    counts["R3_cobol_bytes_ge_20000"] = len(pool)

    for i, (k, v) in enumerate(sorted(pool.items())):
        o, r = v["meta"]["full_name"].split("/")
        br = v["meta"]["default_branch"]
        st, tree = client.get(f"/repos/{o}/{r}/git/trees/{urllib.parse.quote(br, safe='/')}?recursive=1")
        if st == 200:
            v["paths"] = [e["path"] for e in tree.get("tree", []) if e.get("type") == "blob"]
            v["tree_sha"] = tree["sha"]
            v["truncated"] = bool(tree.get("truncated"))
        else:
            v["paths"], v["tree_sha"], v["truncated"] = [], "", False
        v["stats"] = tree_stats(v["paths"])
        if i % 25 == 0:
            client.save()
    client.save()

    s4 = {k: v for k, v in pool.items() if v["stats"]["bms"] + v["stats"]["csd"] >= 1}
    counts["R4_has_bms_or_csd"] = len(s4)
    s5 = {k: v for k, v in s4.items() if MIN_PROGRAMS <= v["stats"]["programs"] <= MAX_PROGRAMS}
    counts["R5_programs_5_to_300"] = len(s5)
    s6 = {k: v for k, v in s5.items() if k not in set(INELIGIBLE_LIST) and v["meta"]["name"].lower() not in BURNED_NAMES}
    counts["R6_not_on_ineligible_list"] = len(s6)
    s7 = {k: v for k, v in s6.items() if k not in devdata}
    counts["R7_not_development_data"] = len(s7)
    s8: dict[str, dict[str, Any]] = {}
    for k, v in s7.items():
        m = v["meta"]
        if COPY_NAME_RE.search(m["name"]) or COPY_NAME_RE.search(m.get("description") or ""):
            continue
        frac, est = burned_overlap(sorted(v["stats"]["stems"]), burned)
        v["burned_overlap"], v["burned_overlap_estate"] = round(frac, 4), est
        if frac >= COPY_BASENAME_FRACTION:
            continue
        s8[k] = v
    counts["R8_not_copy_of_burned_estate"] = len(s8)

    out: list[dict[str, Any]] = []
    for k, v in sorted(s8.items()):
        m = v["meta"]
        o, r = m["full_name"].split("/")
        st, ref = client.get(f"/repos/{o}/{r}/git/ref/heads/{urllib.parse.quote(m['default_branch'], safe='/')}")
        commit_sha = ref["object"]["sha"] if st == 200 else ""
        st, com = client.get(f"/repos/{o}/{r}/git/commits/{commit_sha}") if commit_sha else (0, {})
        # `git/trees/{branch}` reports the resolved commit's sha as `sha`; it must equal the ref's commit.
        if commit_sha != v["tree_sha"] or st != 200:
            print(f"BRANCH MOVED since crawl: {k}; invalidate its cache entries and re-run", file=sys.stderr)
            client.save()
            return 5
        root_tree = com["tree"]["sha"]
        st, user = client.get(f"/users/{m['owner']['login']}")
        loc = user.get("location") if st == 200 else None
        topics = m.get("topics") or []
        foreign = compute_foreign(m.get("description"), topics, v["paths"], loc)
        hard = compute_hard(v["paths"], v["stats"]["programs"])
        out.append({
            "full_name": k,
            "default_branch": m["default_branch"],
            "default_branch_sha": commit_sha,
            "root_tree_sha": root_tree,
            "license": v["license"],
            "cobol_bytes": v["cobol_bytes"],
            "cobol_programs": v["stats"]["programs"],
            "bms_files": v["stats"]["bms"],
            "csd_files": v["stats"]["csd"],
            "tree_truncated": v["truncated"],
            "burned_overlap": v["burned_overlap"],
            "foreign": foreign,
            "hard": hard,
            "weight": 1 + foreign + hard,
            "size_kb": m["size"],
            "created_at": m["created_at"],
            "pushed_at": m["pushed_at"],
            "archived": m["archived"],
            "owner_location": loc,
            "description": m.get("description"),
            "topics": topics,
        })
    client.save()
    counts["eligible"] = len(out)

    # always write the log (shows what was requested even if we stop)
    REQUEST_LOG.write_text(json.dumps(client.log, indent=0) + "\n")
    bad = forbidden_in_log(client.log)
    if bad:
        print("FORBIDDEN requests in log:", bad[:5], file=sys.stderr)
        return 3
    if len(out) < 5:
        print("FEWER THAN 5 ELIGIBLE; stopping. Counts:", json.dumps(counts, indent=1))
        (DOCS / "estate4_candidates_counts_partial.json").write_text(json.dumps(counts, indent=1) + "\n")
        return 4
    doc = {
        "about": "Blind candidate list for the 4th CICS estate trial. Metadata only; no code or README read.",
        "built_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "filter_counts": counts,
        "total_weight": sum(c["weight"] for c in out),
        "candidates": out,
    }
    CANDIDATES_JSON.write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    write_md(doc, len(client.log))
    print(json.dumps(counts, indent=1))
    return 0


RULES_MD = """\
1. Public, `fork == false`, not owned by `squid-protocol` or `jmesquib`.
2. License SPDX id in {MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, 0BSD, EPL-2.0}. No license or anything else means excluded.
3. GitHub language stats: COBOL >= 20,000 bytes.
4. CICS evidence from file names only: >= 1 file ending `.bms` or `.csd` (case-insensitive).
5. 5-300 COBOL program files (`.cbl`, `.cob`, `.cobol`; case-insensitive).
6. Not on the ineligible list (the 5 burned estates: aws-mainframe-modernization-carddemo, cics-banking-sample-application-cbsa, cics-genapp, zecs, dbb / MortgageApplication; plus the 9 census repos in `census/INELIGIBLE_FOR_BLIND_ESTATE.md`).
7. Not development data: exclude any repo that our own corpora were sourced from (`tests/cobol_mainframe/corpora.json`, the language-crucible `SOURCES.md` / `PROVENANCE.json` files, and the CICS / estate crucibles if they cite external sources).
8. Not a copy of a burned estate: exclude if the name or description matches (case-insensitive) `carddemo|genapp|cbsa|zecs|mortgage`, or if >= 30% of its COBOL file basenames match basenames in any burned estate.
"""

STAGES = [
    ("S0_unique_public_nonfork_cobol_repos", "Search pool: public, non-fork repos GitHub classifies as COBOL (`language:COBOL fork:false`), unique across date shards"),
    ("R1_owner_not_excluded", "Rule 1: public, non-fork, owner not squid-protocol / jmesquib"),
    ("R2_license_in_set_(search metadata)", "Rule 2 (search metadata): license in the allowed SPDX set"),
    ("R2b_license_confirmed_via_/license_and_repo_still_public_nonfork", "Rule 2 (confirmed): `/license` SPDX id in set, `/repos` still public and non-fork"),
    ("R3_cobol_bytes_ge_20000", "Rule 3: COBOL >= 20,000 bytes"),
    ("R4_has_bms_or_csd", "Rule 4: >= 1 `.bms` or `.csd` file name"),
    ("R5_programs_5_to_300", "Rule 5: 5-300 COBOL program files"),
    ("R6_not_on_ineligible_list", "Rule 6: not on the ineligible list"),
    ("R7_not_development_data", "Rule 7: not development data"),
    ("R8_not_copy_of_burned_estate", "Rule 8: not a copy of a burned estate"),
    ("eligible", "Eligible"),
]


def write_md(doc: dict[str, Any], n_requests: int) -> None:
    tr = round_for_time(TARGET_TIME)
    c = doc["filter_counts"]
    L = [
        "# 4th CICS estate: blind candidate list and draw method",
        "",
        "Pre-registration: [`estate4_preregistration.md`](estate4_preregistration.md) (section 2, target selection).",
        "",
        "> **Candidate repos must not be opened by anyone until the trial ends.** This file holds metadata only: no code, no README text. Descriptions appear only because the foreign heuristic reads them.",
        "",
        "## Eligibility rules (verbatim)",
        "",
        RULES_MD,
        "Implementation notes (declared, deterministic):",
        "- The search pool is `GET /search/repositories?q=language:COBOL fork:false is:public created:A..B`, sharded by `created:` ranges until each shard had fewer than 1000 results. GitHub's search matches a repo's *primary* language, so a repo whose top language is not COBOL is outside the pool.",
        "- Rule 5/4 counts come from the default-branch git tree (paths only). If GitHub truncated a tree (`tree_truncated` in the JSON), counts are lower bounds.",
        "- Rule 7 input: `estate4_devdata_repos.json` (every GitHub repo cited by our corpora provenance files, deliberately over-inclusive).",
        "- Rule 8 basenames: lowercase file stem of `.cbl/.cob/.cobol/.cpy` files; the fraction is matches / the candidate's such files, against each burned estate separately (`estate4_burned_basenames.json`, names only). A repo named after a burned estate (`dbb`, `zecs`, ...) at any owner is also excluded under rule 6.",
        "- `default_branch_sha` is the default-branch **commit SHA** (`git/ref/heads/{branch}`); `git/commits/{sha}` was read only for `tree.sha`, which is recorded as `root_tree_sha`; the commit SHA was checked to equal the SHA the crawl's tree read resolved to, so the counted tree is the pinned commit's. Those two endpoints are the only additions to the allow-list.",
        "- **Known limit:** the search pool covers only repos whose GitHub *primary* language is COBOL, so a repo where another language dominates is out of reach of `/search/repositories`.",
        "",
        "## Weighting (declared before the draw)",
        "",
        "`weight = 1 + foreign + hard`.",
        "- `foreign` (0-3): +1 if description/topics contain a non-ASCII letter or `non_english()` is true (>= 2 distinctive words from a small Portuguese/Spanish/French/German/Italian/Dutch/Turkish/Polish word list and more of them than English function words); +1 if any file path has a non-ASCII character; +1 if the owner's profile `location` names a place outside US/UK/Canada/Australia/Ireland/NZ (keyword tables `ANGLO_*` and `FOREIGN_*` in `tests/tools/estate4_draw.py`; empty or unrecognised locations score 0).",
        "- `hard` (0-5): +1 each for JCL (`.jcl` or a `jcl/` folder), PL/I (`.pli`, `.pl1`), assembler (`.asm`, `.mac`, or `.s` under an `asm`/`assembler`/`assembly`/`hlasm` folder), Db2/IMS (`.dcl`, `.sql`, `.dbd`, `.psb`); +1 if COBOL programs >= 50.",
        "",
        "## Filter stages",
        "",
        "| stage | count |",
        "|---|---|",
    ]
    for key, label in STAGES:
        if key in c:
            L.append(f"| {label} | {c[key]} |")
    L += [
        "",
        f"Total weight: **{doc['total_weight']}**.",
        "",
        "## The draw",
        "",
        "Run on the target round, not before: `python tests/tools/estate4_draw.py draw --round R`.",
        "",
        f"- drand chain: League of Entropy default chain, hash `{CHAIN_HASH}`, period {DRAND_PERIOD} s, genesis {DRAND_GENESIS} (`{round_time(1).isoformat()}`); `draw` re-verifies these against `https://api.drand.sh/info`.",
        f"- Target time: first round at or after **{TARGET_TIME.strftime('%Y-%m-%d %H:%M:%S')} UTC**. Round r is published at `genesis + (r-1)*period`.",
        f"- **Target round R = {tr}**, published at **{round_time(tr).strftime('%Y-%m-%d %H:%M:%S')} UTC**.",
        "- `seed = sha256(randomness_hex + sha256(estate4_candidates.json bytes))` (hex strings concatenated as ASCII, then hashed); `index = int(seed, 16) mod total_weight`.",
        "- Walk the list below (sorted by lowercase `owner/name`) adding weights; the winner is the first repo whose cumulative weight exceeds `index`.",
        "- The candidates file hash is fixed by the merged commit of `estate4_candidates.json`.",
        "",
        "## Request log",
        "",
        f"`estate4_candidates_requests.json` lists every GitHub request made by `build` ({n_requests} requests: method, URL, status). It contains no content endpoints (`/contents`, `/readme`, `/git/blobs`, `raw.githubusercontent.com`, `/search/code`); `tests/cobol_mainframe/test_estate4_draw.py` fails if any appear.",
        "",
        "## Eligible candidates",
        "",
        "| repo | commit sha | license | COBOL bytes | programs | bms | csd | foreign | hard | weight |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for x in doc["candidates"]:
        L.append(
            f"| {x['full_name']} | `{x['default_branch_sha']}` | {x['license']} | {x['cobol_bytes']} | "
            f"{x['cobol_programs']} | {x['bms_files']} | {x['csd_files']} | {x['foreign']} | {x['hard']} | {x['weight']} |"
        )
    CANDIDATES_MD.write_text("\n".join(L) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inputs")
    p.add_argument("--gitgalaxy-root", default="/srv/storage_16tb/projects/gitgalaxy")
    p.add_argument("--corpora-dir", default="/srv/storage_16tb/projects/gitgalaxy/v6/.mainframe_corpora")
    p.set_defaults(fn=cmd_inputs)
    p = sub.add_parser("build")
    p.add_argument("--cache", default=str(DEFAULT_CACHE))
    p.set_defaults(fn=cmd_build)
    p = sub.add_parser("draw")
    p.add_argument("--round", type=int, required=True)
    p.set_defaults(fn=cmd_draw)
    args = ap.parse_args()
    return int(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())
