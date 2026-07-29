# Software Bill of Materials (SBOM) Generator

> **File Reference:** [gitgalaxy/recorders/sbom_recorder.py](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/recorders/sbom_recorder.py)

The `SbomRecorder` module in `gitgalaxy/recorders/sbom_recorder.py` generates enterprise-compliant CycloneDX 1.4 Software Bill of Materials (SBOM) documents backed by physical verification of installed third-party dependencies. Rather than relying solely on declarative package manifests, the recorder inspects installed packages on disk (`node_modules`, `vendor`, Python `venv`/`.venv`) to verify component integrity and flag potential package spoofing or hidden malware payloads.

---

## Universal Manifest Parsing

The generator delegates manifest extraction to `UniversalManifestSlicer` (`gitgalaxy/security/manifest_parser.py`), supporting multiple package manager ecosystems within polyglot repositories:

* **NPM (JavaScript / TypeScript):** Extracts production and development dependencies from `package.json`.
* **Packagist (PHP Composer):** Extracts required packages from `composer.json`.
* **PyPI (Python):** Parses `requirements.txt` declarations and version bounds.
* **Cargo (Rust):** Extracts dependency blocks from `Cargo.toml`.

Manifest locations are ingested directly from the core pipeline census (`manifest_paths`), ensuring that excluded directories (such as vendor locks or distribution builds) are ignored during manifest discovery.

---

## Physical Dependency Verification Pipeline

For every dependency declared in a manifest, `SbomRecorder` attempts to locate the physical package on disk and evaluate its code integrity:

### 1. Package Location & Verification Status
The engine searches local project paths (e.g., `./node_modules/<package>`, `./vendor/<package>`, `venv/lib/python*/site-packages/<package>`).
* **Installed Packages:** Evaluated through integrity inspection routines.
* **Missing Packages (`UNVERIFIED_MISSING_ON_DISK`):** Flagged when declared in manifests but absent from local disk storage.

### 2. Candidate Sampling & Entry Point Prioritization (`_iter_candidate_files`)
To ensure high-risk entry points are inspected first under time or budget constraints, candidate files (`.js`, `.py`, `.ts`, `.php`, `.rs`) are ordered by risk priority:
1. Common entry point stems (`index`, `main`, `__init__`, `app`, `setup`).
2. Shallow path depth before deep nested subdirectories.
3. Lexicographical sorting.

### 3. Structural Anomaly & Spoofing Inspection (`_scan_single_file`)
Scanned candidate files undergo dual evaluation using core GitGalaxy sensors:
* **High-Entropy Payload Check (`SecurityLens`):** Identifies mathematically dense or obfuscated string blobs (Shannon Entropy > 4.8), flagging potential hidden binaries or encrypted payloads.
* **Language Anomaly Verification (`LanguageDetector`):** Verifies file extension against structural heuristics. Mismatches (e.g., JavaScript extensions containing non-JS structures) trigger `SPOOF_DETECTED` warnings.

### 4. Stateful Caching (`_audit_with_cache`)
When a `DependencyAuditCache` instance is provided, file contents are hashed (`SHA-256`). Verdicts are cached per file hash across scan sessions, allowing instant lookup on hits while restricting fresh scans to configured budgets (`fresh_scan_budget`).

---

## CycloneDX 1.4 Serialization

The final report is emitted as a fully compliant **CycloneDX 1.4 JSON** document. To provide security teams with deep visibility, GitGalaxy enriches the standard component metadata with custom property key-value pairs:

```json
{
  "type": "library",
  "name": "lodash",
  "version": "4.17.21",
  "purl": "pkg:npm/lodash@4.17.21",
  "properties": [
    { "name": "gitgalaxy:trust_status", "value": "VERIFIED_SAFE" },
    { "name": "gitgalaxy:anomaly_notes", "value": "None" },
    { "name": "gitgalaxy:audit_coverage", "value": "12/12 files (12 cached, 0 fresh)" }
  ]
}
```

### Trust Status Classifications

| Status Value | Condition |
| :--- | :--- |
| `VERIFIED_SAFE` | All inspected package files passed entropy and language signature checks. |
| `SPOOF_DETECTED` | One or more files contained high entropy (> 4.8) or language structural anomalies. |
| `UNVERIFIED_MISSING_ON_DISK` | Package declared in manifest but directory could not be located on disk. |
| `PARTIALLY_VERIFIED` | Package files were deferred to future runs due to fresh scan budget limits. |

---

## Programmatic Execution & Telemetry

`SbomRecorder` integrates into the pipeline via `generate_report()`:

```python
recorder = SbomRecorder(version="2.4.0", dependency_cache=cache)
recorder.generate_report(
    parsed_files=parsed_files,
    summary=summary,
    session_meta=session_meta,
    output_path="bom.json",
    manifest_paths=manifest_paths
)
```

The emitted JSON payload includes root metadata, tools telemetry, project context, and the verified array of CycloneDX components.

---

### Ecosystem References

* **[GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** - Source module for `sbom_recorder.py`.
* **[GitGalaxy Platform](https://gitgalaxy.io/)** - Interactive WebGPU visualization dashboard.

---

**[⬅️ Back to Master Index](index.md)**

