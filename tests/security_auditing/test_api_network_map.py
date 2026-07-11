import json
import yaml
import pytest
from unittest.mock import patch

from gitgalaxy.tools.network_auditing.full_api_network_map import (
    run_api_audit,
    main,
    auto_discover_swagger,
    parse_official_swagger,
    map_physical_codebase,
    normalize_endpoint,
    calculate_api_drift
)


# ==============================================================================
# TEST 1: Framework Regex Extraction (All Supported Languages)
# ==============================================================================
def test_framework_regex_extraction(tmp_path):
    """Verifies the physical mapper correctly extracts endpoints from all supported backends."""
    repo_dir = tmp_path / "all_frameworks_repo"
    repo_dir.mkdir()

    # Create dummy files for every supported framework
    (repo_dir / "app.py").write_text('@app.get("/api/py")', encoding="utf-8")
    (repo_dir / "server.js").write_text('router.post("/api/js")', encoding="utf-8")
    (repo_dir / "Controller.java").write_text(
        '@DeleteMapping("/api/java")', encoding="utf-8"
    )
    (repo_dir / "main.go").write_text('.PUT("/api/go")', encoding="utf-8")
    (repo_dir / "Api.cs").write_text('[HttpPatch("/api/cs")]', encoding="utf-8")
    (repo_dir / "MinApi.cs").write_text('.MapGet("/api/csmin")', encoding="utf-8")
    (repo_dir / "routes.php").write_text('Route::delete("/api/php")', encoding="utf-8")
    (repo_dir / "main.rs").write_text('#[post("/api/rs")]', encoding="utf-8")
    (repo_dir / "routes.rb").write_text('get "/api/rb"', encoding="utf-8")

    physical_apis, frameworks = map_physical_codebase(repo_dir)

    # Verify all frameworks were successfully detected
    assert len(frameworks) == 9, (
        "Not all frameworks were detected by the extraction rules!"
    )
    endpoints = set(physical_apis.keys())
    assert "GET /api/py" in endpoints
    assert "POST /api/js" in endpoints
    assert "DELETE /api/java" in endpoints
    assert "PUT /api/go" in endpoints
    assert "PATCH /api/cs" in endpoints
    assert "GET /api/csmin" in endpoints
    assert "DELETE /api/php" in endpoints
    assert "POST /api/rs" in endpoints
    assert "GET /api/rb" in endpoints


# ==============================================================================
# TEST 2: Path Variable Extraction
# ==============================================================================
def test_endpoint_variable_extraction(tmp_path):
    """Verifies that different framework syntaxes for path variables are extracted as-is."""
    repo_dir = tmp_path / "normalization_repo"
    repo_dir.mkdir()

    # Different frameworks use different variable syntaxes (Flask: <id>, Express: :id, Spring: {id})
    (repo_dir / "app.py").write_text(
        '@app.get("/api/users/<user_id>")', encoding="utf-8"
    )
    (repo_dir / "server.js").write_text(
        'router.get("/api/users/:userId")', encoding="utf-8"
    )
    (repo_dir / "Controller.java").write_text(
        '@GetMapping("/api/users/{id}")', encoding="utf-8"
    )

    physical_apis, _ = map_physical_codebase(repo_dir)
    endpoints = set(physical_apis.keys())

    # The engine retains the normalized syntax from the new normalize_endpoint logic
    assert "GET /api/users/{var}" in endpoints, "Variable normalization failed!"
    assert len(endpoints) == 1, "Variable routes were incorrectly segregated!"


# ==============================================================================
# TEST 3: Swagger Parser (YAML, JSON, and Corruption)
# ==============================================================================
def test_swagger_parser_yaml_and_corruption(tmp_path, capsys):
    """Verifies the parser handles YAML specs and correctly raises RuntimeErrors on corruption."""
    # 1. Valid YAML
    yaml_file = tmp_path / "openapi.yaml"
    yaml_data = {"paths": {"/api/yaml": {"get": {}}}}
    yaml_file.write_text(yaml.dump(yaml_data), encoding="utf-8")

    routes = parse_official_swagger(yaml_file)
    assert "GET /api/yaml" in routes

    # 2. Corrupted File Check (Pipeline Assassin patch changes this to RuntimeError)
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{ CORRUPTED JSON", encoding="utf-8")

    with pytest.raises(RuntimeError) as exc_info:
        parse_official_swagger(bad_file)
    assert "Error parsing Swagger file" in str(exc_info.value)


# ==============================================================================
# TEST 4: Swagger Parser (Empty Paths & Greedy Key Extraction)
# ==============================================================================
def test_swagger_parser_edge_cases(tmp_path):
    """Verifies the parser survives schemas without paths and grabs all path keys."""
    # 1. Missing "paths" object
    empty_file = tmp_path / "empty_spec.json"
    empty_file.write_text(
        '{"openapi": "3.0.0", "info": {"title": "Empty"}}', encoding="utf-8"
    )
    routes_empty = parse_official_swagger(empty_file)
    assert len(routes_empty) == 0, "Parser failed to handle missing 'paths' object!"

    # 2. Greedy Key Extraction
    invalid_methods_file = tmp_path / "vendor_spec.json"
    spec_data = {
        "openapi": "3.0.0",
        "paths": {
            "/api/data": {
                "get": {},
                "parameters": [],
                "x-internal-routing": {},
                "servers": [],
            }
        },
    }
    invalid_methods_file.write_text(json.dumps(spec_data), encoding="utf-8")
    routes_invalid = parse_official_swagger(invalid_methods_file)

    # The parser grabs everything under the path and uppercases it
    assert "GET /api/data" in routes_invalid
    assert "PARAMETERS /api/data" in routes_invalid
    assert "X-INTERNAL-ROUTING /api/data" in routes_invalid
    assert len(routes_invalid) == 4, "Parser failed to extract all path keys!"


# ==============================================================================
# TEST 5: Auto-Discovery Engine (Detection & Deep Grep)
# ==============================================================================
def test_auto_discover_files(tmp_path):
    """Verifies the engine finds exact filenames OR deep-greps for OpenAPI signatures."""
    # 1. Fast Path (Exact name match)
    (tmp_path / "swagger.json").write_text("{}", encoding="utf-8")

    # 2. Deep Grep (Unconventional name, but contains OpenAPI signature)
    (tmp_path / "hidden_spec.yml").write_text(
        'openapi: "3.0.0"\npaths: {}', encoding="utf-8"
    )

    # 3. Decoy (Valid extension, no signature)
    (tmp_path / "package.json").write_text('{"name": "app"}', encoding="utf-8")

    candidates = auto_discover_swagger(tmp_path)
    names = [c.name for c in candidates]

    assert "swagger.json" in names
    assert "hidden_spec.yml" in names
    assert "package.json" not in names


# ==============================================================================
# TEST 6: Auto-Discovery Engine (Recursive Greediness)
# ==============================================================================
def test_auto_discover_directories(tmp_path):
    """Verifies that the auto-discovery engine recursively searches all directories."""
    test_dir = tmp_path / "tests"
    mock_dir = tmp_path / "mock"
    docs_dir = tmp_path / "docs"
    node_dir = tmp_path / "node_modules"

    for d in [test_dir, mock_dir, docs_dir, node_dir]:
        d.mkdir()
        (d / "swagger.json").write_text(
            '{"openapi": "3.0.0", "paths": {}}', encoding="utf-8"
        )

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "openapi.json").write_text(
        '{"openapi": "3.0.0", "paths": {}}', encoding="utf-8"
    )

    candidates = auto_discover_swagger(tmp_path)
    paths = [str(c.relative_to(tmp_path)).replace("\\", "/") for c in candidates]

    assert len(paths) == 5, "Engine failed to recursively locate all Swagger files!"
    assert "src/openapi.json" in paths
    assert "node_modules/swagger.json" in paths


# ==============================================================================
# TEST 7: Physical Codebase I/O Exception Handling
# ==============================================================================
def test_physical_mapper_exception_handling(tmp_path):
    """Verifies the physical mapper skips unreadable or corrupted files without crashing."""
    (tmp_path / "app.py").write_text('@app.get("/api/test")', encoding="utf-8")

    with patch("pathlib.Path.read_text", side_effect=PermissionError("Locked file!")):
        apis, frameworks = map_physical_codebase(tmp_path)

    assert len(apis) == 0, "The engine failed to safely catch and ignore the I/O exception!"


# ==============================================================================
# TEST 8: CLI Main - Missing Target Directory
# ==============================================================================
def test_cli_missing_target(capsys):
    """Verifies the CLI aborts gracefully if the target directory doesn't exist."""
    with patch("sys.argv", ["api_map", "missing_repo_12345"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1
    assert "Error: Target source directory" in capsys.readouterr().out


# ==============================================================================
# TEST 9: CLI Main - No Swagger Found Error
# ==============================================================================
def test_cli_no_swagger_found(tmp_path, capsys):
    """Verifies the CLI aborts gracefully if auto-discovery finds zero schemas."""
    repo_dir = tmp_path / "empty_repo"
    repo_dir.mkdir()

    with patch("sys.argv", ["api_map", str(repo_dir)]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1
    assert "[ABORT] No OpenAPI/Swagger specifications found" in capsys.readouterr().out


# ==============================================================================
# TEST 10: CLI Main - Ambiguous Swaggers (Requires Intervention)
# ==============================================================================
def test_cli_ambiguous_swaggers(tmp_path, capsys):
    """Verifies the CLI halts and requires intervention if multiple primary schemas exist."""
    repo_dir = tmp_path / "multi_repo"
    repo_dir.mkdir()

    (repo_dir / "api_v1").mkdir()
    (repo_dir / "api_v2").mkdir()

    (repo_dir / "api_v1" / "swagger.json").write_text('{"paths":{}}', encoding="utf-8")
    (repo_dir / "api_v2" / "swagger.json").write_text('{"paths":{}}', encoding="utf-8")

    with patch("sys.argv", ["api_map", str(repo_dir)]):
        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "[AMBIGUITY] Multiple OpenAPI/Swagger specifications found" in captured.out
    assert "OR use the --merge-all flag" in captured.out


# ==============================================================================
# TEST 11: CLI Main - Ambiguous Swaggers WITH --merge-all
# ==============================================================================
def test_cli_ambiguous_merge_all(tmp_path, capsys):
    """Verifies the --merge-all flag unifies multiple schemas into one verified state."""
    repo_dir = tmp_path / "multi_repo_merge"
    repo_dir.mkdir()

    (repo_dir / "swagger1.json").write_text(
        '{"openapi": "3.0.0", "paths":{"/api/one":{"get":{}}}}', encoding="utf-8"
    )
    (repo_dir / "swagger2.json").write_text(
        '{"openapi": "3.0.0", "paths":{"/api/two":{"post":{}}}}', encoding="utf-8"
    )

    (repo_dir / "app.py").write_text(
        '@app.get("/api/one")\n@app.post("/api/two")', encoding="utf-8"
    )

    with patch("sys.argv", ["api_map", str(repo_dir), "--merge-all"]):
        main()

    captured = capsys.readouterr()
    assert "--merge-all active. Unioning 2 discovered specifications" in captured.out
    assert "Documented Endpoints (Swagger) : 2" in captured.out
    assert "No Shadow APIs detected" in captured.out


# ==============================================================================
# TEST 12: CLI Main - Explicit --swagger Flag
# ==============================================================================
def test_cli_explicit_swagger_flag(tmp_path, capsys):
    """Verifies the --swagger flag bypasses discovery, handling both valid and invalid paths."""
    repo_dir = tmp_path / "explicit_repo"
    repo_dir.mkdir()

    spec_path = repo_dir / "custom_spec.json"
    spec_path.write_text('{"paths":{"/api/explicit":{"get":{}}}}', encoding="utf-8")

    with patch("sys.argv", ["api_map", str(repo_dir), "--swagger", str(repo_dir / "missing.json")]):
        with pytest.raises(SystemExit):
            main()
    assert "Error: Provided Swagger file" in capsys.readouterr().out

    with patch("sys.argv", ["api_map", str(repo_dir), "--swagger", str(spec_path)]):
        main()

    assert "Documented Endpoints (Swagger) : 1" in capsys.readouterr().out


# ==============================================================================
# TEST 13: ISSUE #166 - Whitespace and Query String Contamination
# ==============================================================================
def test_whitespace_and_query_string_contamination(tmp_path):
    """Proves the normalizer safely removes query parameters and trailing whitespace."""
    repo_dir = tmp_path / "whitespace_repo"
    repo_dir.mkdir()
    
    # Simulate a developer accidentally adding a query parameter and trailing whitespace
    (repo_dir / "app.py").write_text('@app.get("/api/users?status=active ")\n@app.post(" /api/clean/   ")', encoding="utf-8")
    (repo_dir / "openapi.json").write_text('{"openapi": "3.0.0", "paths":{"/api/users":{"get":{}}, "/api/clean":{"post":{}}}}', encoding="utf-8")
    
    result = run_api_audit(repo_dir)
    assert result["status"] == "success"
    assert result["shadow_count"] == 0, "Query string contamination caused a false Shadow API!"
    assert result["ghost_count"] == 0, "Query string contamination caused a false Ghost API!"


# ==============================================================================
# TEST 14: ISSUE #164 - REST Path Parameter Collisions
# ==============================================================================
def test_rest_path_parameter_collisions(tmp_path):
    """Proves the normalizer converts all framework-specific dynamic variables into a universal {var} token."""
    repo_dir = tmp_path / "param_collision_repo"
    repo_dir.mkdir()
    
    # Different frameworks use entirely different routing variable syntaxes
    (repo_dir / "app.py").write_text('@app.get("/api/users/<int:user_id>")', encoding="utf-8")
    (repo_dir / "server.js").write_text('router.post("/api/users/:userId/docs/:docId")', encoding="utf-8")
    
    # Swagger exclusively uses {id} syntax
    (repo_dir / "openapi.json").write_text('{"openapi": "3.0.0", "paths":{"/api/users/{id}":{"get":{}}, "/api/users/{userId}/docs/{docId}":{"post":{}}}}', encoding="utf-8")
    
    result = run_api_audit(repo_dir)
    assert result["status"] == "success"
    assert result["shadow_count"] == 0, "REST parameter collision caused a false Shadow API!"
    assert result["ghost_count"] == 0, "REST parameter collision caused a false Ghost API!"


# ==============================================================================
# TEST 15: ISSUE #163 - Router Prefix Blindspot (Suffix Topological Matching)
# ==============================================================================
def test_router_prefix_blindspot(tmp_path):
    """Proves physical endpoints properly align with Swagger using topological suffix matching."""
    repo_dir = tmp_path / "prefix_blindspot_repo"
    repo_dir.mkdir()
    
    # Physical code just says /profile (because it's in a controller mapped to /api/v1/users)
    (repo_dir / "Controller.java").write_text('@GetMapping("/profile")', encoding="utf-8")
    
    # Swagger has the fully qualified path
    (repo_dir / "openapi.json").write_text('{"openapi": "3.0.0", "paths":{"/api/v1/users/profile":{"get":{}}}}', encoding="utf-8")
    
    result = run_api_audit(repo_dir)
    assert result["status"] == "success"
    assert result["shadow_count"] == 0, "Router prefix blindspot caused a false Shadow API!"
    assert result["ghost_count"] == 0, "Router prefix blindspot caused a false Ghost API!"


# ==============================================================================
# TEST 16: ISSUE #165 - The Pipeline Assassin (Graceful Parse Failures)
# ==============================================================================
def test_pipeline_assassin_graceful_exit(tmp_path):
    """Proves the programmatic API safely catches parsing errors without calling sys.exit()."""
    repo_dir = tmp_path / "assassin_repo"
    repo_dir.mkdir()
    
    # Corrupt YAML format to induce a parse failure
    (repo_dir / "openapi.yaml").write_text('openapi: 3.0.0\npaths: *unresolved_alias', encoding="utf-8")
    
    # Verify the orchestrator does not crash and instead returns the error schema
    result = run_api_audit(repo_dir)
    assert result["status"] == "swagger_parse_error", "The pipeline assassin struck again! Expected safe error status."
    assert result["shadow_count"] == 0