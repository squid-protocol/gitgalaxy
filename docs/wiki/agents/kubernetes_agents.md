---
description: "You are operating within `kubernetes`, a massive (1.9M+ LOC) and highly complex container orchestration platform. The repository is predominantly Go..."
---
# AGENTS.md: kubernetes Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `kubernetes`, a massive (1.9M+ LOC) and highly complex container orchestration platform. The repository is predominantly Go (55.2%) and YAML (30.9%), heavily utilizing code generation, reflection-based API machinery, and deeply layered networking/storage abstractions.
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 4.724. The network topology demonstrates a completely flat Modularity (0.0) and negative Assortativity (-0.3704). This indicates a highly coupled, monolithic core structure where API definitions, core controllers, and staging repositories (`staging/src/k8s.io/*`) act as single-points-of-failure with immense inbound connectivity.
* **AI & Machine Learning Topology:** The repository contains a "Local Sovereignty" integration representing isolated, heavy compute tasks (likely related to resource allocation and tensor/GPU scheduling). Do not modify these components without rigorous verification.
* **Core Rule:** Maintain strict adherence to the existing `k8s.io/apimachinery` and `client-go` interfaces. Do NOT attempt to decouple foundational orchestrators or bypass code-generation pipelines (`zz_generated.*`); the architecture relies heavily on tightly synchronized API validation and conversion logic.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core validation functions (`ValidateCustomResourceDefinitionOpenAPIS` in `validation.go`) and code-generation scripts (`kube_codegen.sh`) operate at extreme recursive time complexities (O(2^N) in static analysis) due to deep AST traversal and schema validation. You MUST NOT introduce unbounded recursive loops, synchronous blocking operations, or excessive object allocations on the critical path of API validation, pod allocation (`pod_workers.go`), or networking proxies.
* **Orchestrator Fragility:** Central orchestrators such as `kubelet.go` (128 outbound dependencies), `allocator_testing.go` (239 outbound), and `validation_test.go` are highly fragile. Modifying Kubelet sync loops, resource allocation logic, or Custom Resource Definition (CRD) validation requires immediate, comprehensive verification via the Kubernetes E2E integration test suites.
* **Avoid Dead Code Pruning:** The repository contains massive volumes of logic flagged as "dead code" or "orphaned functions" (e.g., `zz_generated.conversion.go` with 96 orphaned functions). DO NOT autonomously attempt to prune, format, or clean up these files. Kubernetes relies entirely on code generators (`k8s.io/code-generator`) which produce structs and functions that static dependency analysis tools interpret as unused.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or represent 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream integration testing before modifying the structural signatures, API definitions, or public methods of these files:
* `staging/src/k8s.io/apiserver/pkg/warning/context.go` & `staging/src/k8s.io/apimachinery/pkg/apis/meta/v1/time.go` (Severe Load-Bearers: 1964 and 1384 inbound connections respectively. Foundational data types).
* `staging/src/k8s.io/apiextensions-apiserver/pkg/apis/apiextensions/validation/validation.go` & `validation_test.go` (Key Person Silo - 100% isolated ownership by Jordan Liggitt. The core engine for CRD schema validation).
* `pkg/kubelet/kubelet.go` & `pkg/kubelet/pod_workers.go` (Core node execution boundaries; modifications here carry high operational risk for cluster stability).
* `staging/src/k8s.io/apimachinery/pkg/util/proxy/upgradeaware_test.go` (Highest Cumulative Risk: 716.94. Verifies critical HTTP/WebSocket proxy upgrades).
* `staging/src/k8s.io/code-generator/cmd/validation-gen/validators/testing.go` (Severe Blind Bottleneck - extremely high blast radius with 66% Doc Risk).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH CRITICAL EXPLOIT/INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface & Weaponizable Injection:** Files managing pod execution, proxy upgrades, and authentication (`pod_workers.go`, `upgradeaware_test.go`, `authentication_test.go`) possess 100% Exposure for Exploit Generation and Weaponizable Injection. Because Kubernetes manages isolated container execution and request proxying, you MUST ensure that privilege escalation boundaries are never breached. Any modifications to API filters, impersonation handlers (`impersonation_test.go`), or proxy streams must rigorously sanitize headers and paths to prevent Server-Side Request Forgery (SSRF) and unauthenticated Remote Code Execution (RCE).
2. **Hardcoded Payload Artifacts:** Several `.crt`, `.key`, and `.pem` files in `testdata/` directories (e.g., `cmd/kubeadm/app/util/pkiutil/testing/testdata/`) tripped hardcoded payload signatures. DO NOT flag these as leaked secrets; they are explicit cryptographic test fixtures required for verifying PKI operations, TLS, and Service Account signing.
3. **Supply Chain:** There are 497 unknown dependencies bypassing the Zero-Trust whitelist and 73 binary anomalies (mostly test fixtures/images). Do not add or bump external packages in `go.mod` without explicit architectural review, as Kubernetes strictly vendors and manages its dependencies.

## 5. Environmental Tooling (The Oracle)
Do not guess API machinery conversion semantics, hallucinate Kubelet sync loop mechanisms, or rely on generalized Go knowledge to determine blast radius within this 1.9M+ LOC orchestration engine. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
