# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

from typing import Any

from gitgalaxy.standards.language_standards import _lazy_re as re  # #3914: compiled on first use

from .._shared_patterns import CALLS_OUT_UNSUPPORTED, GLOBAL_FRAGILE_DEBT, GLOBAL_PLANNED_DEBT

# A quoted block label: `"aws_instance"`, `"web"`. No newline, no escape handling needed for a header.
_LABEL = r'"[^"\n]*"'
# A top-level block header at column 0 (`terraform fmt` never indents one): the block type, up to two labels and `{`.
# `resource "t" "n" {`, `variable "x" {`, `locals {`, `terraform {`. The type is a whole word, so `resources {` is not one.
_UNIT_TYPES = (
    r"(?:resource|data|module|variable|output|provider|locals|terraform|check|moved|import|removed"
    r"|run|mock_provider|override_resource|override_data|override_module)"
)
# A module call header, whose `source` attribute names the dependency.
_MODULE = r"^module[ \t]+" + _LABEL + r"[ \t]*\{"
# One nesting level of braces inside a body (`providers = { aws = aws.east }`), disjoint from the plain run so the
# repetition never backtracks across the same character two ways.
_BODY = r"(?:[^{}]|\{[^{}]{0,300}\}){0,3000}?"

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "HCL2 (Terraform / OpenTofu, Packer, Nomad, Vault, Consul; terraform test files)",
        "last_updated": "2026-11-11",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # `.tf` / `.tfvars` (Terraform, OpenTofu) and `.hcl` (Packer, Nomad, Terragrunt, `.tftest.hcl`, lock files).
    "extensions": [".tf", ".tfvars", ".hcl"],
    "exact_matches": [],
    "discriminators": [],
    "shebangs": [],
    # `#` line comments are stripped. `//` line and `/* */` block comments are legal HCL but rare (Terraform's style
    # guide and `terraform fmt` use `#`): a block header inside one is not removed from the logic text (#6572 sibling).
    "lexical_family": "line_exclusive",
    # #6572: a `#`, `//` or `/* */` comment and a quoted string spanning lines hold no module call, and neither does a
    # `<<EOT` heredoc body (user_data scripts, JSON policies). The pattern walks the one-line strings too so a quote
    # never shifts the pairing, and only a span crossing lines is blanked: a one-line `source = "./modules/vpc"` keeps
    # its quoted path. Every alternative is length-capped, so it is linear.
    "import_capture_blank": (
        r"#[^\n]*|//[^\n]*|/\*[\s\S]{0,20000}?\*/"
        r"|<<-?[ \t]*([A-Za-z_]\w{0,40})[ \t]*\r?\n[\s\S]{0,50000}?\r?\n[ \t]*\1(?![\w])"
        r'|"(?:[^"\\\n]|\\.){0,2000}"'
    ),
    "import_capture_multiline_only": True,
    "rules": {
        # A call-graph extractor is not built yet (#6572 sibling): declare it unsupported rather than guess.
        "calls_out": CALLS_OUT_UNSUPPORTED,
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # A conditional `a ? b : c`, a `for x in xs` / `if cond` clause of a for-expression, and the `count` /
        # `for_each` meta-arguments that make a block conditional or repeated. `for_each` is one word, so `for` does not hit.
        "branch": re.compile(
            r"(?<![\w.-])(?:for|if)(?=[ \t]+[\w(!\[])|[ \t]\?[ \t]|^[ \t]*(?:count|for_each)[ \t]*=(?!=)", re.M
        ),
        "structural_boundaries": re.compile(r"^" + _UNIT_TYPES + r"\b", re.M),
        # func_start: every column-0 block header, up to two labels. The match ends at the last label (or the type
        # for `locals {`), so the unit's name is the resource name / variable name.
        "func_start": re.compile(r"^" + _UNIT_TYPES + r"(?:[ \t]+" + _LABEL + r"){0,2}(?=[ \t]*\{)", re.M),
        # class_start: the typed infrastructure entities, `resource "type" "name"` and `data "type" "name"`.
        "class_start": re.compile(r"^(?:resource|data)(?:[ \t]+" + _LABEL + r"){2}(?=[ \t]*\{)", re.M),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # A guard the plan enforces: `validation`, `precondition`, `postcondition` blocks, `prevent_destroy`,
        # `sensitive` / `nullable` markers and `try()` / `can()`.
        "safety": re.compile(
            r"^[ \t]*(?:validation|precondition|postcondition)[ \t]*\{|\bprevent_destroy[ \t]*=[ \t]*true\b"
            r"|\bsensitive[ \t]*=[ \t]*true\b|\bdeletion_protection[ \t]*=[ \t]*true\b|(?<![\w.])(?:try|can)\(",
            re.M,
        ),
        # A switch that turns a protection off: `prevent_destroy = false`, `skip_*validation = true`, `insecure = true`,
        # `ignore_changes`, `force_destroy = true`, `deletion_protection = false`, a public bucket or database.
        "safety_bypasses": re.compile(
            r"\bprevent_destroy[ \t]*=[ \t]*false\b|\bdeletion_protection[ \t]*=[ \t]*false\b"
            r"|\bskip_[a-z_]*(?:validation|check|verification)[ \t]*=[ \t]*true\b"
            r"|\b(?:insecure|insecure_skip_verify|skip_tls_verify)[ \t]*=[ \t]*true\b"
            r"|\b(?:verify_ssl|ssl_verify|enable_https|encrypted|storage_encrypted)[ \t]*=[ \t]*false\b"
            r"|\bforce_destroy[ \t]*=[ \t]*true\b|\bpublicly_accessible[ \t]*=[ \t]*true\b"
            r"|\bignore_changes[ \t]*=|\bignore_public_acls[ \t]*=[ \t]*false\b|\bblock_public_(?:acls|policy)[ \t]*=[ \t]*false\b"
        ),
        # Code run on the operator's machine or a guest during apply: provisioners, `external` data, null / terraform_data.
        "high_risk_execution": re.compile(
            r"^[ \t]*provisioner[ \t]+|\binterpreter[ \t]*=|\bprogram[ \t]*=[ \t]*\[|\bnull_resource\b|\bterraform_data\b"
            r"|\b(?:user_data|custom_data|startup_script|user_data_base64)[ \t]*=",
            re.M,
        ),
        "io": re.compile(
            r"(?<![\w.])(?:file|filebase64|filebase64sha256|filemd5|filesha1|filesha256|fileexists|fileset"
            r"|templatefile|abspath|pathexpand|dirname|basename)\("
            r"|\b(?:path\.(?:module|root|cwd)|local_file|local_sensitive_file|archive_file)\b"
        ),
        "api": re.compile(
            r"\b(?:aws_api_gateway_\w+|aws_apigatewayv2_\w+|azurerm_api_management\w*|google_api_gateway_\w+"
            r"|google_endpoints_service|aws_lambda_function_url|aws_appsync_\w+|cloudflare_(?:record|worker_route))\b"
        ),
        "state_mutation": re.compile(
            r"^[ \t]*(?:moved|import|removed|backend)[ \t]*(?:" + _LABEL + r"[ \t]*)?\{|\bterraform_remote_state\b"
            r"|\bterraform_data\b|\bnull_resource\b|\blifecycle[ \t]*\{",
            re.M,
        ),
        "dead_code": re.compile(
            r"^[ \t]*(?:#|//)[ \t]*(?:resource|data|module|variable|output|provider|locals)\b[ \t]*(?:"
            + _LABEL
            + r"|\{)",
            re.M,
        ),
        # A `description` attribute is the language's own documentation of a variable, output or block.
        "doc": re.compile(r"^[ \t]*description[ \t]*=", re.M),
        "test": re.compile(
            r"^[ \t]*(?:run|assert|mock_provider|mock_resource|mock_data|override_resource|override_data|override_module)"
            r"\b[ \t]*(?:" + _LABEL + r"[ \t]*)?\{|\bexpect_failures\b|\.tftest\.hcl\b",
            re.M,
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        "concurrency": re.compile(
            r"\b(?:parallelism|max_concurrency|reserved_concurrent_executions|provisioned_concurrent_executions"
            r"|max_parallel|concurrency_limit)[ \t]*="
        ),
        "ui_framework": re.compile(
            r"\b(?:grafana_dashboard|aws_cloudwatch_dashboard|datadog_dashboard\w*|azurerm_portal_dashboard"
            r"|google_monitoring_dashboard|kibana_\w+dashboard\w*)\b"
        ),
        # HCL has no closures, decorators, generics or comprehension-as-function; `for` expressions are the branch rule.
        "closures": None,
        "globals": re.compile(
            r"(?<![\w.])(?:var|local)\.[A-Za-z_]\w*|\bterraform\.workspace\b|(?<![\w.])(?:getenv|environ)\("
        ),
        "decorators": None,
        "generics": None,
        "comprehensions": re.compile(r"[\[{][ \t]*for[ \t]+[A-Za-z_]\w*(?:[ \t]*,[ \t]*[A-Za-z_]\w*)?[ \t]+in\b"),
        "scientific": None,
        "reflection_metaprogramming": re.compile(
            r"^[ \t]*dynamic[ \t]+" + _LABEL + r"[ \t]*\{|(?<![\w.])(?:jsondecode|yamldecode|tolist|tomap|toset"
            r"|try|can|lookup|merge|flatten|zipmap|coalesce|one)\(|\bprovider[ \t]*=[ \t]*[A-Za-z_]\w*\.",
            re.M,
        ),
        # A module call, the unit of reuse. Its `source` is the dependency (`_dependency_capture`).
        "import": re.compile(_MODULE, re.M),
        # Group 1 is the module source: `module "vpc" { source = "./modules/vpc" }`, a registry address or a
        # `git::https://...` URL. A `source` attribute of any other block (`aws_s3_object`) is not a dependency, so the
        # match must start at a module header and stay inside its body (one nested brace level allowed).
        "_dependency_capture": re.compile(
            _MODULE + _BODY + r"^[ \t]*source[ \t]*=[ \t]*\"([^\"\n]+)\"",
            re.M,
        ),
        "ownership": re.compile(
            r"^[ \t]*(?:#|//)+[ \t]*(?:Authors?|Created[ \t]+by|Maintainers?|Owners?|Contact)[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)[ \t]*$",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
        "ssr_boundaries": None,
        "events": re.compile(
            r"\b(?:aws_cloudwatch_event_\w+|aws_sns_topic\w*|aws_sqs_queue\w*|aws_eventbridge_\w+|azurerm_eventgrid_\w+"
            r"|google_pubsub_\w+|aws_lambda_event_source_mapping)\b"
        ),
        "dependency_injection": re.compile(
            r"^[ \t]*providers[ \t]*=[ \t]*\{|\bdepends_on[ \t]*=|^[ \t]*(?:required_providers|required_version)\b"
            r"|\bprovider[ \t]*=[ \t]*[A-Za-z_]\w*\.[A-Za-z_]\w*",
            re.M,
        ),
        "macros": re.compile(r"\$\{[^}\n]{1,300}\}|%\{[^}\n]{1,300}\}"),
        "pointers": None,
        "memory_alloc": re.compile(
            r"\b(?:memory_size|memory|memory_mb|ram|storage|disk_size_gb|allocated_storage|volume_size|size_gb)[ \t]*="
        ),
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        "telemetry": re.compile(
            r"\b(?:aws_cloudwatch_log_\w+|aws_cloudwatch_metric_alarm|azurerm_monitor_\w+|google_logging_\w+"
            r"|google_monitoring_\w+|datadog_monitor|aws_xray_\w+|enable_logging|logging)\b[ \t]*(?:=|\"|\{)"
        ),
        "debug_prints": re.compile(r"\bTF_LOG\b|(?<![\w.])nonsensitive\("),
        "explicit_casts": re.compile(
            r"(?<![\w.])(?:tostring|tonumber|tobool|tolist|tomap|toset|parseint|floor|ceil)\("
        ),
        "panics_and_aborts": re.compile(r"\berror_message[ \t]*=|\bcondition[ \t]*=|\bexpect_failures\b"),
        "thread_sleeps": re.compile(r"\b(?:create_duration|destroy_duration|wait_for_(?:seconds|ready)|time_sleep)\b"),
        "bitwise_ops": None,
        "sync_locks": re.compile(
            r"\b(?:dynamodb_table|use_lockfile|lock_table|lock_timeout|lock_id|skip_lock)\b[ \t]*(?:=|\{)"
        ),
        "immutability_locks": re.compile(
            r"\b(?:prevent_destroy|create_before_destroy|replace_triggered_by|retain_on_delete|object_lock_\w+)[ \t]*="
        ),
        "cleanup": re.compile(
            r"\b(?:when[ \t]*=[ \t]*destroy|force_destroy|delete_on_termination|skip_final_snapshot|destroy_duration"
            r"|auto_delete|lifecycle_rule|expiration)\b"
        ),
        "encapsulation": re.compile(r"^[ \t]*(?:nullable|sensitive|ephemeral)[ \t]*=", re.M),
        "listeners": re.compile(
            r"\b(?:aws_lb_listener\w*|aws_alb_listener\w*|google_compute_(?:forwarding_rule|global_forwarding_rule)"
            r"|azurerm_lb_rule|aws_lb_target_group\w*)\b|^[ \t]*(?:listener|ingress)[ \t]*\{",
            re.M,
        ),
        "test_skip": re.compile(r"\bskip_cleanup[ \t]*=|\bskip[ \t]*=[ \t]*true\b|\bcommand[ \t]*=[ \t]*plan\b"),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (HCL specifics) ---
        "auth_middleware": re.compile(
            r"\b(?:aws_iam_\w+|azurerm_role_\w+|azuread_\w+|google_(?:project|service_account|iam)_\w*iam\w*|vault_(?:auth|policy|jwt)\w*"
            r"|aws_cognito_\w+|aws_lambda_permission|assume_role(?:_policy)?|oidc_provider|kubernetes_(?:role|cluster_role)\w*)\b"
        ),
        "serialization_parsing": re.compile(
            r"(?<![\w.])(?:jsonencode|jsondecode|yamlencode|yamldecode|base64encode|base64decode|csvdecode|textencodebase64"
            r"|textdecodebase64|urlencode|tobase64)\("
        ),
        "regex_execution": re.compile(r"(?<![\w.])(?:regex|regexall|replace|startswith|endswith|strcontains)\("),
        "time_date_logic": re.compile(
            r"(?<![\w.])(?:timestamp|timeadd|timecmp|formatdate|plantimestamp)\(|\b(?:time_rotating|time_static|time_offset"
            r"|time_sleep)\b|\b(?:schedule_expression|cron_schedule|rotation_days|expiration_days)[ \t]*="
        ),
        "ipc_rpc_bridges": re.compile(
            r"\b(?:aws_lambda_invocation|aws_sfn_state_machine|aws_vpc_endpoint\w*|aws_vpc_peering_connection\w*"
            r"|google_service_networking_connection|azurerm_private_endpoint|azurerm_virtual_network_peering)\b"
        ),
        "system_config_mutation": re.compile(
            r"\b(?:aws_ssm_parameter|aws_ssm_document|aws_appconfig_\w+|azurerm_app_configuration\w*|kubernetes_config_map\w*"
            r"|google_runtimeconfig_\w+|consul_keys|vault_generic_secret)\b|^[ \t]*(?:environment|env)[ \t]*(?:=|\{)",
            re.M,
        ),
    },
}
