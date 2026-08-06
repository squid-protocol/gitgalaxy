#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: AI Application Security (AppSec) Sensor
#
# PURPOSE:
# Scans the repository for AI architectures built by developers that bind an
# LLM to raw state-mutation capability (network/disk IO) with weak defensive
# programming density.
#
# ARCHITECTURAL DECISION (#1102):
# This sensor used to also flag "Autonomous Execution Vector" and "Agentic
# Exfiltration Vector" whenever unrelated regex categories (an LLM import, a
# public-API regex, an eval/subprocess regex) merely co-occurred anywhere in
# the same file -- the same "hallucinated" pattern epic #1025/#1020 already
# removed from RISK_SCHEMA/SIGNAL_SCHEMA, just reimplemented here under
# different names, so it evaded that sweep's blast-radius grep (this module
# never touches those schemas). An AST-free, taint-tracking-free engine has
# no way to prove the data actually flows between those co-occurring hits, so
# both checks were removed in #1102. `over_permissioned_agent` survives: it
# gates on `ai_orchestrator` (a library-*import* signal, i.e. framework
# identity, not a behavioral claim), the same "identity not behavior"
# standard the epic already established as honest for a regex-only engine.
# ==============================================================================
import logging
from typing import Any


class AIAppSecSensor:
    """
    AI Application Security (AppSec) Threat Sensor.
    """

    def __init__(self, parent_logger=None):
        self.logger = parent_logger.getChild("appsec_sensor") if parent_logger else logging.getLogger("appsec_sensor")

    def hunt_threats(self, parsed_files: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.logger.info("AI AppSec Sensor: Scanning for Agentic Vulnerabilities...")

        for file_data in parsed_files:
            # Extract the raw structural signatures. These are tallied in 'equations'
            # (raw_signals keyed by SIGNAL_SCHEMA name), not 'telemetry' -- 'telemetry'
            # only holds derived/computed metrics (network stats, popularity, etc.).
            equations = file_data.get("equations", {})

            # Extract specific architectural signals
            ai_orchestrator = equations.get("llm_orchestrator", 0) > 0

            arch_io = (equations.get("io", 0) + equations.get("sec_io", 0)) > 0  # Network/Disk I/O

            # Defensive programming density (try/catch, guards, regex validation) per LOC.
            # No existing schema signal captures this ratio directly, so it's derived here
            # from the raw 'safety' hit count, using the same doc_mult-style scaling
            # SignalProcessor._calc_cog_load uses to turn sparse per-LOC hit counts into a
            # meaningful 0-1 density.
            safe_loc = max(file_data.get("coding_loc", 1), 1)
            safety_density = min(1.0, (equations.get("safety", 0) * 10.0) / safe_loc)

            appsec_report: dict[str, Any] = {
                "over_permissioned_agent": False,
                "critical_warnings": [],
            }

            # Over-Permissioned Agent Binding (Autonomous Escalation)
            # Agent Orchestration Framework + State Mutation (DB or Disk) + Low Defensive Safety
            #
            # #365/#323: this used to gate on "ai_tools", a SIGNAL_SCHEMA category
            # removed in #323 because agent tool-CALLING is behavior, not library
            # identity -- a regex-based structural signature engine can't reliably
            # detect it, so the category was deliberately dropped rather than left
            # as a permanent false negative. That silently broke this rule (it
            # could never fire again) until #365 found it via #325's dead key audit.
            #
            # ai_orchestrator (langchain/llama_index imports) is the closest thing
            # this engine CAN honestly detect: those are specifically the frameworks
            # whose entire purpose is binding an LLM to tools/actions, so "this file
            # imports an agent orchestration framework" is a reasonable, lexically-
            # detectable proxy for "this file has agentic tool-binding capability" --
            # library-identity detection, exactly the kind of signal #323 said this
            # engine is good at, not the behavioral one it isn't.
            #
            # #1013: this used to also gate on `db_complexity >= 2`, a per-function
            # score removed engine-wide because it just summed unrelated io/
            # serialization_parsing/state_mutation hits and called it "database
            # complexity" -- it fired on any IO-heavy or mutation-heavy function
            # regardless of whether a database was involved. `arch_io` alone
            # already covers the "raw IO write access" signal this rule needs.
            if ai_orchestrator and arch_io and safety_density < 0.5:
                appsec_report["over_permissioned_agent"] = True
                appsec_report["critical_warnings"].append(
                    "CRITICAL [Over-Permissioned Agent]: AI is bound to tools with raw Network/Disk IO write access and < 50% safety density. High risk of autonomous data corruption."
                )

            # Inject the AppSec report back into the file's telemetry
            file_data["telemetry"]["ai_appsec"] = appsec_report

        return parsed_files
