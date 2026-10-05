---
description: "These files aren't your standard, manually written documentation. We used data from our proprietary **blAST engine**—powered by a custom AST-free,..."
---
# GitGalaxy Agent Directives (agents.md)

## How These Are Generated (The blAST Engine)
These files aren't your standard, manually written documentation. We used data from our proprietary **blAST engine**—powered by a custom AST-free, NON-LLM determinstic knowledge graph generator. This is fast and light enough to be in the CI pipeline and updated every push and then re-referenced. 

Currently our system is setup to give a slightly more opinionated and detailed report on the repo. So we created these by taking our LLM_reports and asking an   to: *Convert this to a standard `agents.md` engagement file.* The result is a highly actionable guide that prevents downstream AI from hallucinating architecture or violating security perimeters. 

*Note: If there's interest, we can directly build a custom data flow specific to having an LLM dynamically create and maintain the `agents.md` for your organization.*

---

## Directory Index

### 🤖 Standard Repositories Used to Test LLMs
*These are the highly requested, massively complex open-source ecosystems that researchers and engineers are really interested in having AI-agents benchmarked against.*
* [django](django_agents.md)
* [flask](flask_agents.md)
* [kubernetes](kubernetes_agents.md)
* [linux](linux_agents.md)
* [Python](Python_agents.md)
* [react](react_agents.md)
* [rust](rust_agents.md)
* [tensorflow](tensorflow_agents.md)
* [TypeScript](TypeScript_agents.md)
* [vscode](vscode_agents.md)

### ⚙️ Operating Systems & Low-Level
* [BareMetal-OS](BareMetal-OS_agents.md)
* [bootloader](bootloader_agents.md)
* [bootOS](bootOS_agents.md)
* [ChrysaLisp](ChrysaLisp_agents.md)
* [cosmopolitan](cosmopolitan_agents.md)
* [cpm65](cpm65_agents.md)
* [darwin-xnu](darwin-xnu_agents.md)
* [freebsd-src](freebsd-src_agents.md)
* [x86-bare-metal-examples](x86-bare-metal-examples_agents.md)

### 🗣️ Languages, Compilers & Runtimes
* [asm](asm_agents.md)
* [assemblyscript](assemblyscript_agents.md)
* [berry](berry_agents.md)
* [bog](bog_agents.md)
* [bun](bun_agents.md)
* [capy](capy_agents.md)
* [Carbon](Carbon_agents.md)
* [cpython](cpython_agents.md)
* [cyber](cyber_agents.md)
* [cython](cython_agents.md)
* [deno](deno_agents.md)
* [go](go_agents.md)
* [kotlin](kotlin_agents.md)
* [livecode](livecode_agents.md)
* [roslyn](roslyn_agents.md)
* [wasmtime](wasmtime_agents.md)
* [zig](zig_agents.md)

### 🌐 Web Frameworks & Libraries
* [actix-web](actix-web_agents.md)
* [angular](angular_agents.md)
* [ant-design](ant-design_agents.md)
* [bootstrap](bootstrap_agents.md)
* [cakephp](cakephp_agents.md)
* [CodeIgniter](CodeIgniter_agents.md)
* [Dancer2](Dancer2_agents.md)
* [fastapi](fastapi_agents.md)
* [laravel](laravel_agents.md)
* [rails](rails_agents.md)
* [symfony](symfony_agents.md)
* [tailwindcss](tailwindcss_agents.md)
* [trpc](trpc_agents.md)

### 🧠 Data, AI & Scientific Computing
* [airflow](airflow_agents.md)
* [alphafold_2018](alphafold_2018_agents.md)
* [biopython](biopython_agents.md)
* [blast](blast_agents.md)
* [Chart.js](Chart.js_agents.md)
* [cytoscape.js](cytoscape.js_agents.md)
* [d3](d3_agents.md)
* [eeglab](eeglab_agents.md)

### 💾 COBOL, Mainframe & Enterprise
* [abap2xlsx](abap2xlsx_agents.md)
* [abap-cleaner](abap-cleaner_agents.md)
* [abapGit](abapGit_agents.md)
* [awesome-cobol](awesome-cobol_agents.md)
* [cash-account-cobol](cash-account-cobol_agents.md)
* [cics-banking-sample-application-cbsa](cics-banking-sample-application-cbsa_agents.md)
* [cobrix](cobrix_agents.md)
* [fineract](fineract_agents.md)
* [gnucobol](gnucobol_agents.md)
* [vscode_cobol](vscode_cobol_agents.md)

### 🛠️ DevOps, Infrastructure & Tooling
* [ack3](ack3_agents.md)
* [alacritty](alacritty_agents.md)
* [ansible](ansible_agents.md)
* [black](black_agents.md)
* [brew](brew_agents.md)
* [cargo](cargo_agents.md)
* [curl](curl_agents.md)
* [cypress](cypress_agents.md)
* [desktop](desktop_agents.md)
* [diff-so-fancy](diff-so-fancy_agents.md)
* [docker-py](docker-py_agents.md)
* [elasticsearch](elasticsearch_agents.md)
* [exiftool](exiftool_agents.md)
* [ghostty](ghostty_agents.md)
* [gradle](gradle_agents.md)
* [jenkins](jenkins_agents.md)
* [sqlite](sqlite_agents.md)

### 🎮 Game Engines & 3D Graphics
* [Babylon.js](Babylon.js_agents.md)
* [bevy](bevy_agents.md)
* [cesium](cesium_agents.md)
* [DOOM](DOOM_agents.md)
* [godot](godot_agents.md)
* [three.js](three.js_agents.md)

### 📱 Mobile, Hardware & IoT
* [Adafruit_CircuitPython_Bundle](Adafruit_CircuitPython_Bundle_agents.md)
* [AFNetworking](AFNetworking_agents.md)
* [Alamofire](Alamofire_agents.md)
* [catalyst-runtime](catalyst-runtime_agents.md)
* [circuitpython](circuitpython_agents.md)
* [flutter](flutter_agents.md)
* [micropython](micropython_agents.md)

### 🏢 CMS, Platforms & Applications
* [apex-recipes](apex-recipes_agents.md)
* [AppFlowy](AppFlowy_agents.md)
* [bugzilla](bugzilla_agents.md)
* [canvas-lms](canvas-lms_agents.md)
* [discourse](discourse_agents.md)
* [jellyfin](jellyfin_agents.md)
* [mediawiki](mediawiki_agents.md)
* [WordPress](WordPress_agents.md)

### 🔒 Security, Cryptography & Blockchain
* [angr](angr_agents.md)
* [bitcoin-0.1.0](bitcoin-0.1.0_agents.md)
* [blst](blst_agents.md)
* [capstone](capstone_agents.md)
* [curve25519-dalek](curve25519-dalek_agents.md)
* [gnupg](gnupg_agents.md)
* [solana](solana_agents.md)

### 🧩 Uncategorized / Core
* [Apollo-11](Apollo-11_agents.md)
* [arktype](arktype_agents.md)
* [content](content_agents.md)
* [core](core_agents.md)
* [iwubi](iwubi_agents.md)
* [nvda](nvda_agents.md)

---

### 🌌 Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* 🪐 **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* 🔭 **[Visualize your own repository at GitGalaxy.io](https://gitgalaxy.io/)** using our interactive 3D WebGPU dashboard.