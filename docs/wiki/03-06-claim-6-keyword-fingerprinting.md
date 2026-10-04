---
description: "If we have lists of keywords per file we can do something very similar to DNA finger print matching. This implementation took the lowest hanging fruit..."
---
# Claim 6 -- DNA/Keyword Fingerprinting: An "NCBI BLAST" for Code

If we have lists of keywords per file we can do something very similar to DNA finger print matching. This implementation took the lowest hanging fruit method and just used a ratiometric DNA fingerprint system to attempt to normalize out LOC. What the data suggests is wild. 

### The Methodology: Sequencing Code
By extracting pure structural keywords (control flow branches, memory allocations, network I/O, defensive nets, and state mutations), we can convert any script into a multi-dimensional mathematical vector. We are effectively sequencing the structural DNA of the file. 

With this sequenced genome, we built the software equivalent of an NCBI BLAST search. Using a hyper-optimized, multi-threaded vector search engine, we take a target file's DNA vector and instantly calculate its **Cosine Similarity** against a global population of 1.25 million files. The engine completely ignores the industry domain, the repository name, and the file extension, hunting purely for matching execution geometry. 

### Easing In: The Universal Boilerplate
Before looking at the extremes, the engine immediately highlights the mundane reality of enterprise software: we copy and paste structural patterns constantly. 

When we scanned standard repositories, the engine easily identified internal deduplication targets. For example, in the **Elasticsearch** repository, the engine found that `NerConfig.java` and `ZeroShotClassificationConfig.java` were a 99.6% structural match. Different machine learning features, but the exact same physical blueprint. 

When we looked across repository boundaries, we found that a unit test in **Jenkins** (`FileParameterValueTest.java`) matched a test file in **Spring Boot** (`DockerComposeFileTests.java`) at 99.1%. The engine didn't care about the variables or the strings; it saw the dense concentration of setup, teardown, and mock annotations and recognized the universal blueprint: *tests look like tests, no matter who writes them.*

### Convergent Evolution: Cross-Company Solutions
As we loosened the similarity threshold slightly, we moved past copy-pasting and entered the zone of *convergent evolution*—independent developers arriving at the exact same structural solution to a problem.

For example, we targeted a 256-line Java file in the **Selenium** repository (`RemoteValue.java`). The engine scanned the global database and found its closest evolutionary twin was an 874-line C# file inside Microsoft's **PowerToys** repository (`ShellPage.xaml.cs`), matching at 98.4%. 

The engine jumped across language boundaries (Java to C#), repository boundaries (Selenium to Microsoft), and scale boundaries to find a near-perfect structural match. It recognized that a Java Remote Object and a C# UI ViewModel share the exact same physical blueprint: heavily encapsulated properties, getter/setter fluxes, and rigid class structures. The syntax was just paint; the plumbing was identical.

### The Mainframe Time Machine
When we ran this engine against the heaviest, most complex files in the galaxy, the results shattered the myth of "unique" code entirely. 

In one scan, we targeted a massive, 3,264-line COBOL mainframe file. The engine searched the cosmos and found its closest structural twins:
* **Match 1 (99.00% DNA Match):** An 80-line **SQL** data import script from Grafana.
* **Match 2 (98.68% DNA Match):** A 3,943-line **Fortran** weather modeling script from the WRF physics engine.

The math proved some problems wether solved in 1970's business logic (COBOL), 1980s scientific computing (Fortran), and modern data ingestion (SQL) are all using the exact same structural blueprint. The engine ignored decades of syntax differences and saw that all three files were simply giant, rigid data-shuffling pipelines. Furthermore, it proved the *fractal* nature of code: an 80-line file can share the exact same structural ratio of control flow and memory usage as a 3,000-line file.

### The Global Clone Audit
When we expanded the scan to a random global sample of 2,000 files to track architectural reuse, the data revealed a staggering reality about how the world writes software:

* **Exact Clones (≥99% Match): 83.0%** of files are identical blueprints; mostly boilerplate or copy-paste architecture.
* **Close Relatives (95% - 98.9%): 8.2%** of files feature minor developer tweaks, but use the same underlying engine.
* **Convergent Design (85% - 94.9%): 0.8%** of files represent independent developers solving the same problem the in slightly different ways.
* **Highly Unique (<85% Match): 0.0%**. Across millions of lines of code, the engine could not find out of the 2000 randomly tested files, that those files doing something structurally unique!

Most profoundly, the engine proved that architectural intent transcends the compiler. In our cross-pollination audit, **18.2% of architectural patterns were reused across completely different repositories**, and **7.4% of files shared their closest structural twin with a completely different programming language**.

By proving that these universal, cross-language blueprints exist, we can move beyond standard refactoring. We can begin applying *directed evolution*—using AI to adapt legacy spaghetti code into the exact genetic sequence of a highly evolved, battle-tested survivor.

<br><br>

---

### 🌌 Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* 🪐 **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* 🔭 **[Visualize your own repository at GitGalaxy.io](https://gitgalaxy.io/)** using our interactive 3D WebGPU dashboard.



---

**[⬅️ Back to Master Index](index.md)**
