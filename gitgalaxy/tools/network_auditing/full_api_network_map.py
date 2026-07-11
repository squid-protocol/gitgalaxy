#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: Full API Network Map
#
# PURPOSE:
# Detects undocumented "Shadow APIs" and missing "Ghost APIs" by comparing
# physical source code routing signatures against official OpenAPI/Swagger
# documentation.
#
# ARCHITECTURAL DECISION:
# API documentation frequently drifts from the compiled reality of the codebase.
# This module performs AST-free structural signature identification to map 
# actual, executable endpoints across multiple frameworks (Spring, Express, 
# FastAPI) and enforces strict parity with declared specifications, exposing 
# hidden attack surfaces.
# ==============================================================================
import argparse
import sys
import re
import json
from pathlib import Path
from collections import defaultdict

try:
    import yaml
except ImportError:
    yaml = None

# ==============================================================================
# 1. ROUTER STRUCTURAL SIGNATURES (EXPANDED FRAMEWORK REGEX PATTERNS)
# ==============================================================================
FRAMEWORK_SIGNATURES = {
    "Python (FastAPI/Flask/Django)": {
        "ext": [".py"],
        "regex": re.compile(
            r'@(?:app|router|bp)\.(get|post|put|delete|patch)\s*\(\s*["\'](.*?)["\']',
            re.IGNORECASE,
        ),
    },
    "Node.js (Express/Fastify/Koa)": {
        "ext": [".js", ".ts"],
        "regex": re.compile(
            r'(?:app|router|server)\.(get|post|put|delete|patch)\s*\(\s*["\'](.*?)["\']',
            re.IGNORECASE,
        ),
    },
    "Java (Spring Boot)": {
        "ext": [".java"],
        "regex": re.compile(
            r'@(Get|Post|Put|Delete|Patch)Mapping\s*\(\s*(?:value\s*=\s*)?["\'](.*?)["\']\)',
            re.IGNORECASE,
        ),
    },
    "Golang (Gorilla/Mux/Gin/Fiber)": {
        "ext": [".go"],
        "regex": re.compile(r'\.(GET|POST|PUT|DELETE|PATCH)\s*\(\s*["\'](.*?)["\']', re.IGNORECASE),
    },
    "C# (.NET Controllers)": {
        "ext": [".cs"],
        "regex": re.compile(
            r'\[Http(Get|Post|Put|Delete|Patch)\s*\(\s*["\'](.*?)["\']\s*\)\]',
            re.IGNORECASE,
        ),
    },
    "C# (.NET Minimal APIs)": {
        "ext": [".cs"],
        "regex": re.compile(r'\.Map(Get|Post|Put|Delete|Patch)\s*\(\s*["\'](.*?)["\']', re.IGNORECASE),
    },
    "PHP (Laravel/Symfony)": {
        "ext": [".php"],
        "regex": re.compile(r'Route::(get|post|put|delete|patch)\s*\(\s*["\'](.*?)["\']', re.IGNORECASE),
    },
    "Rust (Actix/Rocket)": {
        "ext": [".rs"],
        "regex": re.compile(
            r'#\[(get|post|put|delete|patch)\s*\(\s*["\'](.*?)["\']\s*\)\]',
            re.IGNORECASE,
        ),
    },
    "Ruby (Rails/Sinatra)": {
        "ext": [".rb"],
        "regex": re.compile(
            r'^\s*(get|post|put|delete|patch)\s+["\'](.*?)["\']',
            re.IGNORECASE | re.MULTILINE,
        ),
    },
}


def normalize_endpoint(method: str, path: str) -> str:
    """
    Normalizes endpoints to fix REST Path Parameter Collisions, Query String 
    Contamination, and Whitespace artifacts.
    """
    # Fix #166: Strip Query Strings and Whitespace
    path = path.split('?')[0].strip()
    
    # Fix #164: Normalize Dynamic REST Parameters to a universal {var} token
    # Express/Fastify (e.g., /users/:userId)
    path = re.sub(r':[a-zA-Z0-9_]+', '{var}', path)
    # Flask (e.g., /users/<int:user_id>)
    path = re.sub(r'<[^>]+>', '{var}', path)
    # Swagger/OpenAPI/Laravel/Spring (e.g., /users/{userId})
    path = re.sub(r'\{[^}]+\}', '{var}', path)
    
    # Clean trailing slashes for uniformity
    if path != '/' and path.endswith('/'):
        path = path.rstrip('/')
        
    # Ensure root slash
    if not path.startswith('/'):
        path = '/' + path
        
    return f"{method.upper()} {path}"


def auto_discover_swagger(target_dir: Path) -> list:
    """Scans for OpenAPI/Swagger specifications via filename and internal structural signatures."""
    candidates = set()
    common_names = {
        "swagger.json",
        "swagger.yaml",
        "swagger.yml",
        "openapi.json",
        "openapi.yaml",
        "openapi.yml",
    }

    for filepath in target_dir.rglob("*"):
        if not filepath.is_file() or filepath.suffix not in [".json", ".yaml", ".yml"]:
            continue

        # 1. Check filename first (Fast Path)
        if filepath.name.lower() in common_names:
            candidates.add(filepath)
            continue

        # ==============================================================================
        # DEFENSIVE DESIGN (I/O OPTIMIZATION & MEMORY SHIELD):
        # Reading entire JSON/YAML files just to check if they are valid Swagger specs 
        # can cause OOM crashes on massive declarative data blobs. We restrict the read 
        # buffer to the first 1000 characters to achieve O(1) memory validation while 
        # maintaining extreme pipeline velocity.
        # ==============================================================================
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                head = f.read(1000)
                # Extra validation to ensure it's a real spec, not just a package.json mentioning swagger
                if re.search(
                    r'("swagger"\s*:\s*"2\.\d"|"openapi"\s*:\s*"3\.\d\.\d"|swagger\s*:\s*["\']?2\.\d|openapi\s*:\s*["\']?3\.\d\.\d)',
                    head,
                ):
                    candidates.add(filepath)
        except Exception:
            pass

    return list(candidates)


def parse_official_swagger(swagger_path: Path) -> set:
    """Parses the official security documentation to extract a baseline of approved APIs."""
    approved_apis = set()
    try:
        with open(swagger_path, "r", encoding="utf-8") as f:
            if swagger_path.suffix.lower() in [".yaml", ".yml"]:
                if yaml is None:
                    # Fix #165: Pipeline Assassin. Raise exception instead of sys.exit()
                    raise RuntimeError(f"PyYAML is required to parse .yaml Swagger files ({swagger_path.name}).")
                swagger_data = yaml.safe_load(f)
            else:
                swagger_data = json.load(f)

        paths = swagger_data.get("paths", {})
        for api_path, methods in paths.items():
            for method in methods.keys():
                approved_apis.add(normalize_endpoint(method, api_path))
    except Exception as e:
        # Fix #165: Pipeline Assassin. Raise exception instead of sys.exit()
        raise RuntimeError(f"Error parsing Swagger file {swagger_path.name}: {e}")

    return approved_apis


def map_physical_codebase(target_dir: Path) -> tuple:
    """
    Analyzes the source code to extract every executable API endpoint.
    
    ARCHITECTURAL DECISION (REGEX OVER AST):
    Relying on language-specific ASTs requires compiling the code and supporting 
    dozens of parsers. By using bounded regex structural signatures, we can 
    deterministically identify framework routing intents (e.g., @GetMapping, 
    app.post) at high speed, regardless of language or compilation status.
    """
    physical_apis = defaultdict(list)
    frameworks_detected = set()

    for filepath in target_dir.rglob("*"):
        if not filepath.is_file():
            continue

        for framework, config in FRAMEWORK_SIGNATURES.items():
            if filepath.suffix in config["ext"]:
                try:
                    content = filepath.read_text(encoding="utf-8", errors="ignore")
                    hits = config["regex"].findall(content)
                    if hits:
                        frameworks_detected.add(framework)

                    for method, api_path in hits:
                        endpoint = normalize_endpoint(method, api_path)
                        physical_apis[endpoint].append(filepath.name)
                except Exception:
                    pass

    return physical_apis, frameworks_detected


def calculate_api_drift(physical_endpoints: set, approved_apis: set) -> tuple:
    """
    Fixes #163: The Router Prefix Blindspot.
    Uses suffix topological matching to align physical endpoints (which may be missing 
    their class/router-level prefixes) with fully qualified Swagger endpoints.
    """
    shadow_apis = set()
    matched_approved = set()
    
    for phys in physical_endpoints:
        phys_meth, phys_path = phys.split(" ", 1)
        found = False
        
        for app in approved_apis:
            app_meth, app_path = app.split(" ", 1)
            
            if phys_meth == app_meth:
                # Suffix Match: Physical '/profile' aligns with Swagger '/api/v1/users/profile'
                # Because our normalizer guarantees phys_path starts with a '/', 
                # .endswith(phys_path) naturally prevents partial word bleeding.
                if app_path == phys_path or app_path.endswith(phys_path):
                    found = True
                    matched_approved.add(app)
                    break
        
        if not found:
            shadow_apis.add(phys)
            
    ghost_apis = approved_apis - matched_approved
    
    return shadow_apis, ghost_apis


def main():
    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("Full API Network Map")

    parser = argparse.ArgumentParser(description="GitGalaxy Full API Network Map")
    parser.add_argument("source", help="Directory containing the application source code")
    parser.add_argument(
        "--swagger",
        required=False,
        help="Optional: Path to a specific official swagger.json/yaml file",
    )
    parser.add_argument(
        "--merge-all",
        action="store_true",
        help="Merge all discovered Swagger files together (useful for Microservice Monorepos)",
    )
    args = parser.parse_args()

    source_path = Path(args.source).resolve()

    if not source_path.exists():
        print(f"Error: Target source directory '{source_path}' does not exist.")
        sys.exit(1)

    print(f"🗺️  GitGalaxy API Network Mapper analyzing physical endpoints in: {source_path.name}...\n")

    # ==============================================================================
    # AUTO-DISCOVERY INITIALIZATION & AUDIT
    # ==============================================================================
    approved_apis = set()

    if not args.swagger:
        print(" 🔍 No --swagger file provided. Initiating auto-discovery...")
        candidates = auto_discover_swagger(source_path)

        if not candidates:
            print(" ❌ [ABORT] No OpenAPI/Swagger specifications found in the repository.")
            print("    Please provide one manually using the --swagger flag.")
            sys.exit(1)

        # Segregate testing schemas from primary production schemas
        primary_cands = []
        test_cands = []
        for c in candidates:
            parts = [p.lower() for p in c.relative_to(source_path).parts]
            if "test" in parts or "tests" in parts or "__tests__" in parts or "testing" in parts:
                test_cands.append(c)
            else:
                primary_cands.append(c)

        if len(primary_cands) == 1 and not args.merge_all:
            swagger_path = primary_cands[0]
            print(f" [DISCOVERY] Primary Swagger specification identified: {swagger_path.relative_to(source_path)}")
            if test_cands:
                print(f" 🛡️  Safely excluded {len(test_cands)} schemas detected in test directories (Test-Schema Pollution Mitigation):")
                for tc in test_cands:
                    print(f"    - [Assumed Test] {tc.relative_to(source_path)}")
            print("")
            try:
                approved_apis = parse_official_swagger(swagger_path)
            except RuntimeError as e:
                print(f" ❌ {e}")
                sys.exit(1)

        elif len(candidates) > 1 and not args.merge_all:
            print(f" ⚠️  [AMBIGUITY] Multiple OpenAPI/Swagger specifications found ({len(candidates)}).")
            print("    To prevent test-schema pollution, automatic merging is disabled.")
            print("\n    Discovered Files (By Endpoint Count):")

            preview_stats = []
            for c in candidates:
                try:
                    routes = parse_official_swagger(c)
                    preview_stats.append((c, len(routes), c in test_cands))
                except Exception:
                    preview_stats.append((c, 0, c in test_cands))

            preview_stats.sort(key=lambda x: x[1], reverse=True)

            for c, count, is_test in preview_stats:
                badge = "[TEST DIR]" if is_test else "[PRIMARY]"
                print(f"    - {badge.ljust(11)} [{count} routes] {c.relative_to(source_path)}")

            print("\n    Please specify the authoritative schema using the --swagger flag,")
            print("    OR use the --merge-all flag to union all of them together.")
            sys.exit(1)

        elif len(candidates) > 1 and args.merge_all:
            print(f" [DISCOVERY] --merge-all active. Unioning {len(candidates)} discovered specifications...\n")
            for c in candidates:
                try:
                    approved_apis.update(parse_official_swagger(c))
                except RuntimeError as e:
                    print(f" ⚠️  [SKIP] Failed to parse discovered specification '{c.relative_to(source_path)}': {e}")
        else:
            swagger_path = candidates[0]
            print(f" [DISCOVERY] Auto-discovered Swagger specification: {swagger_path.relative_to(source_path)}\n")
            try:
                approved_apis = parse_official_swagger(swagger_path)
            except RuntimeError as e:
                print(f" ❌ {e}")
                sys.exit(1)
    else:
        swagger_path = Path(args.swagger).resolve()
        if not swagger_path.exists():
            print(f" ❌ Error: Provided Swagger file '{swagger_path}' does not exist.")
            sys.exit(1)
        try:
            approved_apis = parse_official_swagger(swagger_path)
        except RuntimeError as e:
            print(f" ❌ {e}")
            sys.exit(1)
        
    physical_apis_map, frameworks_detected = map_physical_codebase(source_path)
    physical_endpoints = set(physical_apis_map.keys())

    # Map the drift using the topological suffix matcher
    shadow_apis, ghost_apis = calculate_api_drift(physical_endpoints, approved_apis)

    # ==============================================================================
    # PRESENTATION DASHBOARD
    # ==============================================================================
    print("==========================================================")
    print(" 📡 SHADOW API SECURITY AUDIT")
    print("==========================================================")
    framework_str = ", ".join(frameworks_detected) if frameworks_detected else "None Detected"
    print(f" Physical Frameworks Tracked    : {framework_str}")
    print(f" Documented Endpoints (Swagger) : {len(approved_apis)}")
    print(f" Physical Endpoints (Source)    : {len(physical_endpoints)}")
    print("-" * 58)

    if shadow_apis:
        print(f" 🚨 SHADOW APIs DETECTED: {len(shadow_apis)} (Critical Risk)")
        for api in sorted(shadow_apis):
            files = ", ".join(set(physical_apis_map[api]))
            print(f"    ↳ {api.ljust(25)} [Found in: {files}]")
    else:
        print(" ✅ No Shadow APIs detected. Codebase strictly matches documentation.")

    print("\n----------------------------------------------------------")
    if ghost_apis:
        print(f" 👻 GHOST APIs DETECTED: {len(ghost_apis)} (Documentation Bloat)")
        for api in sorted(ghost_apis):
            print(f"    ↳ {api.ljust(25)} [Missing from executable source code]")
    else:
        print(" ✅ No Ghost APIs detected.")

    print("==========================================================\n")


def run_api_audit(source_path: Path) -> dict:
    """Programmatic entry point for GalaxyScope."""
    candidates = auto_discover_swagger(source_path)
    if not candidates:
        return {"status": "no_swagger", "shadow_count": 0, "ghost_count": 0}

    primary_cands = [c for c in candidates if "test" not in [p.lower() for p in c.relative_to(source_path).parts]]
    if len(primary_cands) != 1:
        return {"status": "ambiguous", "shadow_count": 0, "ghost_count": 0}

    try:
        approved_apis = parse_official_swagger(primary_cands[0])
    except RuntimeError:
        # Fails securely without terminating the pipeline
        return {"status": "swagger_parse_error", "shadow_count": 0, "ghost_count": 0}

    physical_apis_map, frameworks = map_physical_codebase(source_path)
    physical_endpoints = set(physical_apis_map.keys())

    shadow_apis, ghost_apis = calculate_api_drift(physical_endpoints, approved_apis)

    return {
        "status": "success",
        "frameworks": list(frameworks),
        "shadow_count": len(shadow_apis),
        "ghost_count": len(ghost_apis),
        "shadow_apis": list(shadow_apis),
    }


if __name__ == "__main__":
    main()