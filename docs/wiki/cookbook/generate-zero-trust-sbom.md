# How to Generate a Zero-Trust SBOM (Software Bill of Materials)

In modern enterprise compliance (like SOC2 or Executive Order 14028), generating a Software Bill of Materials (SBOM) is mandatory. However, standard SBOM generators are fundamentally flawed: they blindly trust manifest files (`package.json`, `requirements.txt`, `Cargo.toml`). 

If a malicious actor alters a dependency inside `node_modules` or a Python `venv` after installation, standard tools will still report the package as safe because they only read the manifest. 

GitGalaxy shifts this paradigm using the **Universal Zero-Trust SBOM Generator**. It physically verifies the existence and structural integrity of every declared dependency on disk before sealing the cryptographic manifest.

## The Zero-Trust Verification Engine

The GitGalaxy generator supports NPM, Packagist (PHP), PyPI, and Cargo ecosystems. It performs a multi-stage physical audit to map the delta between what is declared and what actually exists in memory.

### 1. Execute the Generation
Point the generator at the root directory of your project. SBOM generation is a native
exclusive mode of the main orchestrator — there is no separate SBOM binary to install.

```bash
galaxyscope /path/to/target_project --sbom-only
```

### 2. The Physical Integrity Audit
As the engine parses the manifest, it hunts down the physical location of the package on disk (e.g., scanning virtual environments or `vendor/` folders). It then subjects the core files to the GitGalaxy `SecurityLens`.

Every dependency is tagged with one of three Zero-Trust statuses:
* **`VERIFIED_SAFE`**: The package exists on disk and passes baseline mathematical structural integrity.
* **`UNVERIFIED_MISSING_ON_DISK`**: The manifest claims the package is installed, but the physical files are missing. (Indicates broken builds or phantom dependencies).
* **`SPOOF_DETECTED`**: The package exists, but the structural engine detected extreme mathematical anomalies (e.g., Shannon Entropy > 4.8 or Language Spoofing), indicating the dependency has been hijacked, packed, or poisoned.

### 3. Review the Output & CycloneDX Standard
The engine exports a strictly formatted **CycloneDX 1.4 JSON** file, ensuring seamless integration with enterprise vulnerability scanners (like Dependency-Track or Snyk). The proprietary GitGalaxy threat telemetry is safely injected into the CycloneDX `properties` array.

```text
==========================================================
 📦 SBOM GENERATOR: MISSION REPORT
==========================================================
 Dependencies Claimed : 145
 Standard Export      : CycloneDX 1.4 JSON
 Output Location      : /path/to/target_project_galaxy_sbom.json
----------------------------------------------------------
 Verified Safe        : 142
 Missing on Disk      : 2
 Spoofed / Infected   : 1
----------------------------------------------------------
   ⚠️  [MISSING] left-pad@1.3.0
   🚨 [SPOOF DETECTED] colors@1.4.1

 ❌ ALERT: 1 dependencies failed physical structural verification.
==========================================================
```

By shifting to a Zero-Trust SBOM, your security teams are no longer auditing assumptions—they are auditing mathematical reality.

> **Read the full technical specification:** [SBOM Generator](../04-02-sbom-generator.md)

---

**[⬅️ Back to Master Index](../index.md)**
