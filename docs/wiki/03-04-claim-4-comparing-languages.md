---
description: "If I have an engine that can scan and compare codebases across time and language, independent of compilation, I don't know about you, but I want to..."
---
# Claim 4 (Comparing Languages)

If I have an engine that can scan and compare codebases across time and language, independent of compilation, I don't know about you, but I want to take it for a spin! What patterns will emerge as we compare repositories of Python, COBOL, and TypeScript at a massive scale? 

This is my current validation and proof-of-principle dataset. I have scaled the pipeline up to analyze over **14,000 repositories** encompassing **2.57 million files** across 50+ languages. The engine scores them according to GitGalaxy's physical risk exposure metrics and structural DNA, and I am presenting it publicly for validation and criticism. Openness and public input are the only ways forward with a system like this. 

The following ridge line plots visualize the distribution of these risk exposures and other metrics across the language ecosystem. I currently have the security measures set to be highly sensitive, meaning normal (but risky) coding practices are being listed as security warnings. The sensitivity of these detections can be tuned down for a less annoying daily workflow, and then cranked back to `--paranoid` for your final sanity check before pushing a release live.

*Click on any image to view it at full resolution.*

## Architectural Risk Exposures

<table style="width:100%; text-align:center;">
  <tr>
    <td>
      <a href="../assets/analyses_ridgeplots/risk_cognitive_load_exposure_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/risk_cognitive_load_exposure_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Cognitive Load Exposure"/><br/>
        <b>Cognitive Load Exposure</b>
      </a>
    </td>
    <td>
      <a href="../assets/analyses_ridgeplots/risk_tech_debt_exposure_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/risk_tech_debt_exposure_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Tech Debt Exposure"/><br/>
        <b>Tech Debt Exposure</b>
      </a>
    </td>
    <td>
      <a href="../assets/analyses_ridgeplots/risk_error_and_exception_exposure_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/risk_error_and_exception_exposure_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Error & Exception Exposure"/><br/>
        <b>Error & Exception Exposure</b>
      </a>
    </td>
  </tr>
  <tr>
    <td>
      <a href="../assets/analyses_ridgeplots/risk_api_exposure_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/risk_api_exposure_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on API Exposure"/><br/>
        <b>API Exposure</b>
      </a>
    </td>
    <td>
      <a href="../assets/analyses_ridgeplots/risk_state_flux_exposure_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/risk_state_flux_exposure_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on State Flux Exposure"/><br/>
        <b>State Flux Exposure</b>
      </a>
    </td>
    <td>
      <a href="../assets/analyses_ridgeplots/risk_concurrency_exposure_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/risk_concurrency_exposure_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Concurrency Exposure"/><br/>
        <b>Concurrency Exposure</b>
      </a>
    </td>
  </tr>
  <tr>
    <td>
      <a href="../assets/analyses_ridgeplots/risk_testing_exposure_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/risk_testing_exposure_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Testing Exposure"/><br/>
        <b>Testing Exposure</b>
      </a>
    </td>
    <td>
      <a href="../assets/analyses_ridgeplots/risk_documentation_exposure_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/risk_documentation_exposure_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Documentation Exposure"/><br/>
        <b>Documentation Exposure</b>
      </a>
    </td>
    <td>
      <a href="../assets/analyses_ridgeplots/risk_specification_exposure_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/risk_specification_exposure_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Specification Exposure"/><br/>
        <b>Specification Exposure</b>
      </a>
    </td>
  </tr>
  <tr>
    <td>
      <a href="../assets/analyses_ridgeplots/risk_graveyard_exposure_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/risk_graveyard_exposure_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Graveyard Exposure"/><br/>
        <b>Graveyard Exposure</b>
      </a>
    </td>
    <td>
      <a href="../assets/analyses_ridgeplots/risk_civil_war_exposure_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/risk_civil_war_exposure_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Civil War Formatting Exposure"/><br/>
        <b>Civil War Exposure</b>
      </a>
    </td>
    <td></td>
  </tr>
</table>

## Structural Physics & DNA

<table style="width:100%; text-align:center;">
  <tr>
    <td>
      <a href="../assets/analyses_ridgeplots/structural_mass_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/structural_mass_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Structural Mass"/><br/>
        <b>Structural Mass</b>
      </a>
    </td>
    <td>
      <a href="../assets/analyses_ridgeplots/control_flow_ratio_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/control_flow_ratio_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Control Flow Ratio"/><br/>
        <b>Control Flow Ratio</b>
      </a>
    </td>
    <td>
      <a href="../assets/analyses_ridgeplots/hit_control_flow_branches_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/hit_control_flow_branches_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Control Flow Branches"/><br/>
        <b>Control Flow Branches</b>
      </a>
    </td>
  </tr>
  <tr>
    <td>
      <a href="../assets/analyses_ridgeplots/max_func_complexity_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/max_func_complexity_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Max Function Complexity"/><br/>
        <b>Max Function Complexity</b>
      </a>
    </td>
    <td>
      <a href="../assets/analyses_ridgeplots/avg_func_args_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/avg_func_args_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Avg Function Arguments"/><br/>
        <b>Avg Function Arguments</b>
      </a>
    </td>
    <td>
      <a href="../assets/analyses_ridgeplots/import_count_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/import_count_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Outbound Imports"/><br/>
        <b>Outbound Imports</b>
      </a>
    </td>
  </tr>
  <tr>
    <td>
      <a href="../assets/analyses_ridgeplots/hit_i_o_and_network_boundaries_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/hit_i_o_and_network_boundaries_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on I/O & Network Boundaries"/><br/>
        <b>I/O & Network Boundaries</b>
      </a>
    </td>
    <td></td>
    <td></td>
  </tr>
</table>

## Volatility & Authorship

<table style="width:100%; text-align:center;">
  <tr>
    <td>
      <a href="../assets/analyses_ridgeplots/risk_volatility_exposure_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/risk_volatility_exposure_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Volatility Exposure (Churn)"/><br/>
        <b>Volatility Exposure (Churn)</b>
      </a>
    </td>
    <td>
      <a href="../assets/analyses_ridgeplots/risk_instability_exposure_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/risk_instability_exposure_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Instability Exposure (Age)"/><br/>
        <b>Instability Exposure (Age)</b>
      </a>
    </td>
    <td>
      <a href="../assets/analyses_ridgeplots/silo_risk_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/silo_risk_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Silo Risk (Bus Factor)"/><br/>
        <b>Silo Risk (Bus Factor)</b>
      </a>
    </td>
  </tr>
  <tr>
    <td>
      <a href="../assets/analyses_ridgeplots/ownership_entropy_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/ownership_entropy_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Ownership Entropy"/><br/>
        <b>Ownership Entropy</b>
      </a>
    </td>
    <td></td>
    <td></td>
  </tr>
</table>

## Core Security & Vulnerability Risks

<table style="width:100%; text-align:center;">
  <tr>
    <td>
      <a href="../assets/analyses_ridgeplots/risk_hardcoded_payload_artifacts_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/risk_hardcoded_payload_artifacts_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Hardcoded Payload Artifacts"/><br/>
        <b>Hardcoded Payload Artifacts</b>
      </a>
    </td>
    <td>
      <a href="../assets/analyses_ridgeplots/risk_obfuscation_and_evasion_surface_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/risk_obfuscation_and_evasion_surface_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Obfuscation & Evasion Surface"/><br/>
        <b>Obfuscation & Evasion Surface</b>
      </a>
    </td>
    <td>
      <a href="../assets/analyses_ridgeplots/risk_exploit_generation_surface_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/risk_exploit_generation_surface_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Exploit Generation Surface"/><br/>
        <b>Exploit Generation Surface</b>
      </a>
    </td>
  </tr>
  <tr>
    <td>
      <a href="../assets/analyses_ridgeplots/risk_weaponizable_injection_vectors_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/risk_weaponizable_injection_vectors_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Weaponizable Injection Vectors"/><br/>
        <b>Weaponizable Injection Vectors</b>
      </a>
    </td>
    <td>
      <a href="../assets/analyses_ridgeplots/risk_raw_memory_manipulation_ridgeplot.png">
        <img src="../assets/analyses_ridgeplots/risk_raw_memory_manipulation_ridgeplot.png" width="300" loading="lazy" alt="Ridge plot comparing different programming languages based on Raw Memory Manipulation"/><br/>
        <b>Raw Memory Manipulation</b>
      </a>
    </td>
    <td></td>
  </tr>
</table>

<br><br>

---

### 🌌 Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* 🪐 **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* 🔭 **[Visualize your own repository at GitGalaxy.io](https://gitgalaxy.io/)** using our interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**
