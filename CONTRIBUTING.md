# 🤝 Contributing to GitGalaxy

First off, thank you for considering contributing to GitGalaxy! The blAST engine is a highly calibrated, deterministic mathematical instrument. Calibrating it across the vast ecosystem of open-source software requires a dedicated community of systems engineers.

Whether you are reporting a taxonomic discrepancy, refining the parsing engine, or expanding the documentation, your input helps map the architectural physics of software more accurately.

---

## ⚙️ The blAST Philosophy (Physics over ASTs)

Before diving in, please remember that GitGalaxy treats code as a physical structure governed by thermodynamic laws. The blAST engine evaluates structural logic, algorithmic complexity, and calculated **risk exposures**—not just rigid syntax. 

Sometimes, what appears to be a traditional parsing error might actually be the blAST engine intentionally flagging a structural anomaly or a dense risk exposure. Please keep this in mind when reporting issues or proposing changes to the extraction heuristics.

---

## 🌐 Expanding the blAST Engine (Adding Languages)

GitGalaxy uses an AST-free, mathematical heuristics engine to build a comparative lexical taxonomical map across all programming languages. We do not write traditional parsers; we map thermodynamic language physics using bounded regular expressions. 

If you want to add native support for a new language (e.g., Lua, Haskell, or a proprietary DSL), do not start writing regex from scratch. We use a strict LLM-driven calibration protocol to guarantee ReDoS immunity. 

**Please read the strict engine calibration guide here:** **[Architecting a New Language (Extending the blAST Engine)](gitgalaxy/standards/how_to_add_a_language.md)**

---

## 🔬 The Differential Scan (Our PR Protocol)

We do not merge structural backend changes based solely on subjective code review. GitGalaxy operates at planetary scale, and every change to the parsing logic has cascading effects.

When you submit a Pull Request that alters the blAST engine, your candidate changes will be subjected to a **Full Differential Scan**. 

* **The Control + Variable Test:** We run your branch against our calibrated baseline of ~80 massive open-source repositories, **plus** the specific repository your PR is designed to address.
* **Before and After:** We perform a strict mathematical comparison of the engine's output before and after your rule update across this entire dataset. This ensures your addition resolves the target discrepancy without degrading the established baseline or triggering Catastrophic Backtracking (ReDoS).
* **The Metrics:** The output is assessed strictly on four vectors: **Accuracy, Speed, Utility, and Ethos.**
* Only changes that are mathematically and practically *measurably better* across the broader ecosystem will be incorporated into the `main` branch.

---

## 🛠️ Submitting Pull Requests

To ensure your contribution integrates smoothly into the Zero-Trust ecosystem:

1. **Fork and Branch:** Create a feature branch from `main` (`git checkout -b feature/your-feature-name`).
2. **Maintain the Contract:** Ensure that any backend changes to the CLI do not break the universal JSON schema contract expected by the frontend Observatory. 
3. **Test Visually:** Run your newly generated `_galaxy.json` through either **[GitGalaxy.io](https://gitgalaxy.io)** or your local **Airgap Observatory** to verify that 3D WebGPU rendering and visual physics constraints remain intact. 
4. **Document:** If you are adding new language phenotypes or altering the parsing logic, please update the [Language Lens](docs/wiki/02-05-language-lens.md) documentation in the wiki.
5. **Submit:** Open a PR with a clear title. Explain the *why* behind your structural changes, not just the *what*. Be sure to include the link to the target repository so we can include it in the Differential Scan.

---

## 🔒 Updating the Golden Crucible Baseline

`tests/golden_master_audit.json` and `tests/golden_master_zero_dep_audit.json` are the accepted-good snapshots that every PR's output is diffed against (see the `crucible-audit` check). A failing diff means GitGalaxy's output changed -- that's either a bug you should fix, or an intentional improvement whose new baseline needs to be deliberately re-blessed.

**Never** hand-copy fresh output over these files. Always use:

```
python tests/tools/update_golden_master.py
```

It shows you exactly what's about to change before writing anything, and requires explicit confirmation. If your PR touches either fixture, **explain why in the PR description** (e.g. "improved the Rust parser, now correctly detects async trait bounds") -- a CI check flags any PR that modifies these files so it's never invisible in a large diff.

---

## 🐛 Reporting Discrepancies

If the GalaxyScope CLI misidentifies a repository's structure or fails to parse a specific file phenotype, please use our **[Parsing Discrepancy Form](https://github.com/squid-protocol/gitgalaxy/issues/new/choose)**. 

To help us reproduce the issue with quantitative precision, you will be asked to provide:
* A direct link to the public repository being scanned.
* The Observatory viewer you were using ([GitGalaxy.io](https://gitgalaxy.io) or Airgap Observatory).
* A clear description of the expected vs. actual output.
* The contents of your custom `gitgalaxy_config.py` file (if applicable).
* Contact information for follow-up questions.

---

## 🛡️ Security Vulnerabilities

If you discover a vulnerability within GitGalaxy itself (e.g., a way to bypass the local sandbox, a ReDoS vector, or an issue in the Airgap Observatory), **do not open a public issue.** Please reach out directly via the contact portal at [GitGalaxy.io](https://gitgalaxy.io) so the vulnerability can be patched securely before public disclosure.

---

## 📜 Licensing Reminder

GitGalaxy is released under the **PolyForm Noncommercial License 1.0.0**. By contributing to this repository, you agree that your contributions will be licensed under these same terms. 

*Note: This tool is free for research, education, testing, and hobby projects. Any commercial use or integration into commercial SaaS products or corporate CI/CD pipelines requires a separate commercial license.*