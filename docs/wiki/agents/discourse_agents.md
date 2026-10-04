---
description: "You are operating within `discourse`, a massive, widely-adopted community discussion platform. The repository is a heavily intertwined monolith..."
---
# AGENTS.md: discourse Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `discourse`, a massive, widely-adopted community discussion platform. The repository is a heavily intertwined monolith composed primarily of Ruby (38.1%), YAML configurations (35.4%), and JavaScript/Ember.js (21.6%) for the frontend.
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 5.452. The network topology demonstrates completely flat Modularity (0.0) and extreme negative Assortativity (-0.593). This indicates a fragile, highly centralized "hub-and-spoke" architecture where a few massive God Nodes (like `User`, `Topic`, and `ApplicationController`) govern almost all execution logic.
* **Core Rule:** Do NOT attempt to decouple core Rails models or introduce isolated micro-services. The architecture fundamentally relies on tight, synchronous coupling between the Ruby backend state and the Ember.js frontend components. 

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core backend controllers and background jobs (`ApplicationController`, `TopicsController`, `Jobs::CreateLinkedTopic`, `Jobs::MergeUser`) operate at extreme recursive time complexities (O(2^N) in static analysis) due to deep callback chains, active record callbacks, and nested rendering. You MUST NOT introduce unbounded loops, deep recursive iterations, or N+1 query patterns in the `app/controllers/` or `app/jobs/` directories.
* **Orchestrator Fragility:** Frontend orchestrators such as `frontend/discourse/tests/helpers/qunit-helpers.js` (84 outbound dependencies), `topic.gjs` (49 outbound), and `topic.js` (46 outbound) are highly fragile. Altering component lifecycles or test harness initializations requires immediate verification against the massive QUnit and RSpec test suites.
* **Avoid Dead Code Pruning:** Files like `frontend/discourse/app/models/user.js` (89 orphaned functions) and `topic.js` (74 orphaned functions) contain logic that static analysis tools flag as "dead code." DO NOT autonomously attempt to prune, format, or clean up these files. Discourse uses dynamic injection, Ember observers, and metaprogramming that bypasses static dependency resolution.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream integration testing before modifying the structural signatures, database queries, or public APIs of these files:
* `frontend/discourse/app/models/post-stream.js` (Highest Cumulative Risk: 715.22, 100% Logic Bomb Exposure, manages the core timeline state).
* `frontend/discourse/app/controllers/topic.js` (Extremely High Cognitive Load: 98.7%, highly volatile).
* `config/routes.rb` (Massive Structural Mass: 5819.24, DB Complexity: 602. The absolute routing core).
* `app/models/user.rb` & `app/models/topic.rb` (Massive Data Gravity and structural pillars of the database schema).
* `app/services/post_alerter.rb` & `app/models/color_scheme.rb` (Key Person Silos - 100% isolated ownership by specific maintainers like Jake Goldsborough and Kris).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Files such as `app/controllers/search_controller.rb`, `app/controllers/application_controller.rb`, and `app/models/theme.rb` possess 100% Exposure scores for Exploit Generation. You MUST ensure strict input sanitization (strong parameters) and strict XSS escaping when handling user search queries or theme/CSS uploads.
2. **Weaponizable Injection Vectors:** Database migrations (e.g., `db/migrate/20170313192741_add_themes.rb`) and the custom proxy (`frontend/custom-proxy/index.js`) exhibit 100% Injection Surface risk. Never use string interpolation for SQL queries; always utilize ActiveRecord's parameterized queries. 
3. **Supply Chain:** There are over 9,100 unknown dependencies bypassing the Zero-Trust whitelist across RubyGems and NPM. Do not add or bump external packages in `Gemfile` or `package.json` without explicit architectural and security review.

## 5. Environmental Tooling (The Oracle)
Do not guess Ember.js component resolutions, hallucinate ActiveRecord associations, or rely on generalized Rails knowledge to determine blast radius within this 600k+ LOC application. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
