# File Filtering and Ingestion Shield

> **File Reference:** [`gitgalaxy/core/aperture.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/core/aperture.py)

The `ApertureFilter` module in `gitgalaxy/core/aperture.py` serves as the primary file filtering and perimeter security gate for the GitGalaxy analysis engine. Prior to sending files to heavy regular expression parsing and metric evaluation, the filter strips out noise such as compiled binaries, minified bundles, vendor packages (`node_modules`), and excluded directories (`.git`). By enforcing strict ingestion boundaries, the engine focuses computational resources strictly on actionable source code logic.

---

## Multilevel Ingestion Rules

The filter enforces a multi-tiered evaluation hierarchy to determine file processing eligibility:

* **Existence Verification (Phantom Check):** Executes zero-overhead filesystem checks to ensure files exist on disk, instantly dropping dangling symlinks or deleted file references.
* **File Size Guarding:** Measures file byte size against max threshold limits. Files exceeding size thresholds are excluded from full parsing to prevent worker memory allocation failures.
* **Folder Micro-File Quota:** Tracks the frequency of micro-files (< 50 bytes) within individual directories. If a directory exceeds its micro-file limit, subsequent tiny files are suppressed from primary analysis. (Legacy mainframe files, such as COBOL copybooks, are explicitly exempted).
* **Secrets Detection Radar (Priority Gate):** Inspects filenames and extensions against high-risk security registries prior to path checks. If a file matches credential patterns (e.g., `.pem`, `.key`, `id_rsa`, `.env`), it triggers a high-severity leak alert and is flagged for security highlights.
* **Directory Blacklisting & GitIgnore Integration:** Integrates project `.gitignore` rules and a built-in `BLACK_HOLES` directory registry (`node_modules`, `.git`, `.vscode`, `dist`, `build`). System administrative folders and hidden directories starting with dots are excluded by default.
* **Stateful Caching & Intent Locks:** Preserves file whitelist locks registered by project manifests (`package.json`, `Cargo.toml`) or `.gitattributes` via `guidestar_lens.py`, allowing explicitly referenced configuration assets (e.g., custom hooks or build scripts) to bypass standard exclusion filters.

---

## Asset Classification & Inspection Gates

Files surviving path blacklists pass through secondary content gates:

* **Missing Extensions & Shebang Processing:** Files lacking traditional extensions (e.g., executable scripts without `.sh` or `.py`) are passed to the language detection engine (`language_lens.py`) for shebang header evaluation (`#!/bin/bash`).
* **Binary File Header Inspection (X-Ray Gate):** Intercepts the initial 8KB chunk of binary assets. Inspects binary magic bytes, execution headers (e.g., ELF, PE, Mach-O), and Shannon entropy to detect weaponized payloads or embedded AI model weights (`.safetensors`, `.gguf`).
* **Minified Code & Vendor Library Shield:** Analyzes line length density. If average line length breaches compression thresholds (> 250 characters per line) or matches vendor patterns (e.g., `.min.js`, `/vendor/`), regular expression parsing is bypassed. The asset is registered as a static dependency footprint without incurring heavy parsing latency.

---

## Ingestion Classification Matrix

The filter categorizes repository assets into operational ingestion buckets based on file content and security status:

| Ingestion Category | Target File Types | Filter Handling | Pipeline Output |
| :--- | :--- | :--- | :--- |
| **Security Risk (Leaked Credential)** | Private keys, `.env` files, credentials, DB dumps | Flag Leak Alert | Injected as High-Severity Security Alert |
| **Binary Vulnerability / ML Model** | Weaponized executables, ML weight binaries (`.safetensors`) | Flag Binary Threat | Injected as Model/Threat Highlight |
| **Excluded Directory Noise** | `.gitignore` matches, `node_modules`, `.git` | Block Path | Excluded from scan inventory |
| **Inert Media Asset** | Compiled binaries, image assets, fonts, null byte files | Discard File | Routed to Unclassified Asset Store |
| **Minified / Vendor Library** | Minified JavaScript (`.min.js`), vendor bundles | Bypass Regex | Registered as Inert Dependency Footprint |
| **Valid Source Code** | Whitelisted language source files | Full Processing | Active Repository Node in Graph |

---

### Ecosystem References

* **[GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** - Source module for `aperture.py`.
* **[GitGalaxy Platform](https://gitgalaxy.io/)** - Interactive repository visualization engine.

---

**[⬅️ Back to Master Index](index.md)**

