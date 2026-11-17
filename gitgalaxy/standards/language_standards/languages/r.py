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
from gitgalaxy.standards.language_standards.identifiers import ID_CONTINUE

from .._shared_patterns import CALLS_OUT_UNSUPPORTED, GLOBAL_FRAGILE_DEBT, GLOBAL_PLANNED_DEBT

# An R name: a letter, or a `.` not followed by a digit, then word characters and `.`.
_NAME = r"(?:[^\W\d_]|\.(?![0-9]))[" + ID_CONTINUE + r".]*"
# An assignment operator that binds a name to a function: `<-`, `<<-` or `=` (not `==`).
_ASSIGN = r"(?:<<-|<-|=(?!=))"
# `obj$method <- function`, `self@slot = function`: the receiver chain before the bound name.
_RECEIVER = r"(?:" + _NAME + r"[$@])*"
# A call's parameter list: one level of nested parentheses (`function(x = c(1, 2))`), no newline.
_PARAMS = r"(?:[^()\n]|\([^()\n]*\))*"
# A package attach call: `library(x)`, `require(x)`, `requireNamespace("x")`, `loadNamespace("x")`.
_ATTACH = r"(?:library|require|requireNamespace|loadNamespace)"

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "R 4.x (functions, S3 / S4 / R5 / R6 classes, packages, tidyverse, Shiny, testthat)",
        "last_updated": "2026-11-11",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # The language lens lowercases an extension, so `.r` also routes `analysis.R`.
    "extensions": [".r"],
    "exact_matches": [],
    "discriminators": [],
    "shebangs": ["Rscript"],
    # `#` line comments (roxygen `#'` lines are comments too); R has no block comment.
    "lexical_family": "line_exclusive",
    # #6572: a `#` comment, and a "..." or '...' string (R strings may span lines), hold no imports. The pattern
    # walks the one-line strings too, so a quote inside one never shifts the pairing, and only a string spanning
    # lines is blanked: a one-line `library("dplyr")` keeps its quoted package name. A `#` comment is consumed
    # first so a stray quote in it cannot pair with a later one. Capped, so linear.
    "import_capture_blank": r"#[^\n]*" + r'|"(?:[^"\\]|\\[\s\S]){0,20000}"' + r"|'(?:[^'\\]|\\[\s\S]){0,20000}'",
    "import_capture_multiline_only": True,
    "rules": {
        # A call-graph extractor is not built yet (#6572 sibling): declare it unsupported rather than guess.
        "calls_out": CALLS_OUT_UNSUPPORTED,
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        "branch": re.compile(r"(?<![\w.$@])(?:if|else|for|while|repeat|switch|ifelse)\b(?![\w.])|&&|\|\|"),
        # args: group 1 is the parameter list of a `function(...)` header.
        "args": re.compile(r"\bfunction[ \t]*\((" + _PARAMS + r")\)"),
        "structural_boundaries": re.compile(
            r"(?<![\w.$@])(?:function|setClass|setRefClass|setClassUnion|R6Class|setGeneric|setMethod|library|require)\b"
        ),
        # func_start: `name <- function(`, `name <<- function(`, `name = function(`, `` `my name` <- function( ``
        # and the R 4.1 lambda `name <- \(x)`. Group 1 is the name, group 2 a backticked name.
        "func_start": re.compile(
            r"^[ \t]*"
            + _RECEIVER
            + r"(?:("
            + _NAME
            + r")|`([^`\n]+)`)[ \t]*"
            + _ASSIGN
            + r"[ \t]*(?:function[ \t]*\(|\\\()",
            re.M,
        ),
        # class_start: `setClass("X"`, `setRefClass("X"`, `setClassUnion("X"` (group 1) or `X <- R6Class(` /
        # `X <- setClass(` (group 2).
        "class_start": re.compile(
            r"^[ \t]*(?:(?:setClass|setRefClass|setClassUnion)\([ \t]*[\"'](" + _NAME + r")[\"']"
            r"|(" + _NAME + r")[ \t]*" + _ASSIGN + r"[ \t]*(?:R6::)?(?:R6Class|setRefClass|setClass)\()",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        "safety": re.compile(
            r"(?<![\w.])(?:tryCatch|try|stopifnot|withCallingHandlers|inherits)\(|\bis\.(?:null|na|nan|finite)\("
            r"|\bon\.exit\("
        ),
        "safety_bypasses": re.compile(
            r"(?<![\w.])(?:suppressWarnings|suppressMessages|suppressPackageStartupMessages|unlockBinding"
            r"|assignInNamespace)\(|\b\w+:::\w+|\.Internal\("
        ),
        "high_risk_execution": re.compile(
            r"(?<![\w.$@])(?:eval|evalq|system|system2|shell|shell\.exec|source|sys\.source|do\.call)\("
        ),
        "io": re.compile(
            r"(?<![\w.$@])(?:read\.(?:csv|csv2|table|delim|fwf)|write\.(?:csv|csv2|table)|readRDS|saveRDS|readLines"
            r"|writeLines|file|readr::\w+|read_(?:csv|tsv|delim|excel|rds|file)|write_(?:csv|tsv|delim|rds|file)"
            r"|fread|fwrite|load|save|scan|download\.file|dir\.create|file\.(?:remove|copy|rename|create|exists)"
            r"|unlink|list\.files|dbConnect|dbGetQuery|dbExecute|dbWriteTable|dbReadTable)\("
        ),
        "api": re.compile(r"(?<![\w.])(?:plumb|pr_get|pr_post|pr_put|pr_delete|pr_handle)\(|\bRestRserve::\w+"),
        "state_mutation": re.compile(r"<<-|(?<![\w.$@])assign\(|\$[A-Za-z.][\w.]*[ \t]*<-|\[\[?[^\]\n]*\]\]?[ \t]*<-"),
        "dead_code": re.compile(r"^[ \t]*#[ \t]*(?:library|require|function|print|cat|source|browser)[ \t(]", re.M),
        "doc": re.compile(r"^[ \t]*#'", re.M),
        "test": re.compile(
            r"(?<![\w.$@])(?:test_that|expect_[a-z_]+|context|describe|test_check|test_dir|test_file)\("
            r"|\blibrary\([ \t]*testthat[ \t]*\)"
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        "concurrency": re.compile(
            r"(?<![\w.$@])(?:mclapply|parLapply|parSapply|parApply|clusterApply|clusterExport|clusterEvalQ|makeCluster"
            r"|stopCluster|mcparallel|mccollect|foreach|future|future_map|future_lapply|plan|registerDoParallel)\("
            r"|%dopar%|%dofuture%|\b(?:parallel|future|furrr|promises|doParallel|mirai|callr)::\w+"
        ),
        "ui_framework": re.compile(
            r"(?<![\w.$@])(?:shinyApp|fluidPage|navbarPage|dashboardPage|bootstrapPage|renderPlot|renderTable|renderUI"
            r"|renderText|plotOutput|tableOutput|uiOutput|textOutput|ggplot|plot_ly|leaflet)\(|\bshiny::\w+"
            r"|\blibrary\([ \t]*(?:shiny|shinydashboard|bslib|ggplot2|plotly|leaflet)[ \t]*\)"
        ),
        "closures": re.compile(r"\\\([^)\n]*\)|~[ \t]*\.|[(,][ \t]*function[ \t]*\("),
        "globals": re.compile(r"<<-|\bglobalenv\(|\.GlobalEnv\b|(?<![\w.$@])(?:Sys\.getenv|options|getOption)\("),
        "decorators": re.compile(
            r"^[ \t]*#'[ \t]*@(?:export|param|return|importFrom|import|examples|rdname|inheritParams|keywords"
            r"|exportMethod|exportClass|describeIn)\b",
            re.M,
        ),
        "generics": re.compile(
            r"(?<![\w.$@])(?:setGeneric|setMethod|setValidity|UseMethod|NextMethod|standardGeneric|callNextMethod)\("
        ),
        "comprehensions": re.compile(
            r"(?<![\w.$@])(?:lapply|sapply|vapply|mapply|Map|Filter|Reduce|Position|Find|apply|tapply|rapply|outer"
            r"|map|map_[a-z]+|walk|keep|discard|reduce)\("
        ),
        "scientific": re.compile(
            r"(?<![\w.$@])(?:lm|glm|nls|anova|t\.test|wilcox\.test|chisq\.test|cor|rnorm|runif|rbinom|set\.seed|optim"
            r"|predict|aov|prcomp|kmeans|hclust)\(|\b(?:dplyr|tidyr|data\.table|caret|Matrix|survival|lme4|MASS|mgcv"
            r"|glmnet|xgboost|randomForest|tidymodels|forecast|Seurat|DESeq2|limma|edgeR|BiocManager)\b"
        ),
        "reflection_metaprogramming": re.compile(
            r"(?<![\w.$@])(?:substitute|quote|bquote|deparse|body|formals|match\.call|sys\.call|sys\.function"
            r"|environment|get|mget|exists|getAnywhere|match\.arg|expression|as\.name|as\.call|Recall|eval|parse"
            r"|getMethod|slotNames|getSlots|attributes)\("
        ),
        "import": re.compile(r"^[ \t]*" + _ATTACH + r"[ \t]*\(", re.M),
        # Group 1 is the package: `library(dplyr)`, `library("dplyr")`, `require(x, quietly = TRUE)` and
        # `library(package = "x")` name it; `requireNamespace("x")` inside a condition names nothing.
        "_dependency_capture": re.compile(
            r"^[ \t]*" + _ATTACH + r"[ \t]*\([ \t]*(?:package[ \t]*=[ \t]*)?[\"']?(" + _NAME + r")", re.M
        ),
        "ownership": re.compile(
            r"^[ \t]*#+[ \t]*(?:Authors?|Created[ \t]+by|Maintainers?|Owners?|Contact)[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)[ \t]*$",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
        "ssr_boundaries": re.compile(r"(?<![\w.$@])(?:shinyApp|shinyServer|htmlTemplate|runApp)\(|\bshiny::\w+"),
        "events": re.compile(
            r"(?<![\w.$@])(?:observe|observeEvent|eventReactive|reactive|isolate|invalidateLater|reactiveVal"
            r"|reactiveValues|updateSelectInput|showNotification)\("
        ),
        "dependency_injection": re.compile(
            r"(?<![\w.$@])(?:with_options|with_envvar|local_options|local_mocked_bindings|with_mocked_bindings"
            r"|with_dir|local_dir|stub|mock)\("
        ),
        "macros": re.compile(r"\{\{[ \t]*[\w.]+[ \t]*\}\}|(?<![\w.$@])(?:enquo|enquos|enexpr|quo|quos|bquote)\("),
        "pointers": re.compile(r"(?<![\w.$@])\.(?:Call|External|C|Fortran)\(|\bexternalptr\b"),
        "memory_alloc": re.compile(
            r"(?<![\w.$@])(?:vector|numeric|integer|character|logical|double)\([ \t]*(?:\d|length\(|[\"']"
            r"|mode)|(?<![\w.$@])(?:object\.size|tracemem|mem_used)\("
        ),
        "inline_asm": re.compile(r"(?<![\w.$@])(?:cppFunction|sourceCpp|evalCpp|cfunction)\("),
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        "telemetry": re.compile(
            r"(?<![\w.$@])(?:message|warning|packageStartupMessage|log_(?:info|warn|error|debug|trace|fatal)"
            r"|flog\.\w+|loginfo|logwarn|logerror)\("
        ),
        "debug_prints": re.compile(r"(?<![\w.$@])(?:print|cat|str|browser|debug|debugonce|dput|View)\("),
        "explicit_casts": re.compile(
            r"(?<![\w$@])as\.[A-Za-z]\w*\(|(?<![\w.$@])(?:as_(?:tibble|date|datetime|integer|numeric|character)"
            r"|storage\.mode|type\.convert|parse_number|parse_integer)\("
        ),
        "panics_and_aborts": re.compile(r"(?<![\w.$@])(?:stop|quit|abort|stopifnot|cli_abort|stop_custom)\("),
        "thread_sleeps": re.compile(r"\bSys\.sleep\([ \t]*[0-9.]+"),
        "bitwise_ops": re.compile(r"\b(?:bitw(?:And|Or|Xor|Not|ShiftL|ShiftR)|xor)\(|\bbitops::\w+"),
        "sync_locks": re.compile(r"(?<![\w.$@])(?:lock|unlock|trylock|mutex)\(|\b(?:filelock|synchronicity|ipc)::\w+"),
        "immutability_locks": re.compile(r"(?<![\w.$@])(?:lockBinding|lockEnvironment|makeActiveBinding)\("),
        "cleanup": re.compile(
            r"\bon\.exit\(|(?<![\w.$@])(?:close|unlink|rm|gc|dbDisconnect|sink|stopCluster|closeAllConnections"
            r"|dev\.off|file\.remove)\("
        ),
        "encapsulation": re.compile(r"^[ \t]*(?:private|public|active)[ \t]*=[ \t]*list\(", re.M),
        "listeners": re.compile(
            r"(?<![\w.$@])(?:serverSocket|socketAccept|startServer|runServer|runApp|later|run_now)\(|\bhttpuv::\w+"
        ),
        "test_skip": re.compile(
            r"(?<![\w.$@])skip(?:_if|_if_not|_on_cran|_on_os|_on_ci|_if_offline|_on_bioc|_if_not_installed)?\("
        ),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (R specifics) ---
        "auth_middleware": re.compile(
            r"\b(?:oauth_app|oauth_endpoint|oauth_token|jwt_claim|jwt_encode_\w+|jwt_decode_\w+|shinymanager"
            r"|shinyauthr|auth_basic|authenticate|authorize|keyring::\w+)\b"
        ),
        "serialization_parsing": re.compile(
            r"(?<![\w.$@])(?:fromJSON|toJSON|read_json|write_json|stream_in|stream_out|read_xml|read_html|xmlParse"
            r"|read_yaml|write_yaml|serialize|unserialize|read_parquet|write_parquet|read_feather|write_feather"
            r"|read_sas|read_spss|read_dta)\(|\b(?:jsonlite|xml2|arrow|haven)::\w+"
        ),
        "regex_execution": re.compile(
            r"(?<![\w.$@])(?:grepl|regexpr|gregexpr|regexec|gregexec|sub|gsub|grep|regmatches|str_detect|str_extract"
            r"|str_extract_all|str_replace|str_replace_all|str_match|str_match_all|str_split)\("
        ),
        "time_date_logic": re.compile(
            r"(?<![\w.$@])(?:Sys\.(?:time|Date|timezone)|as\.(?:Date|POSIXct|POSIXlt)|strptime|strftime|difftime"
            r"|ISOdate|ISOdatetime|ymd|mdy|dmy|ymd_hms|today|now|system\.time|proc\.time|weekdays|months)\("
        ),
        "ipc_rpc_bridges": re.compile(
            r"\b(?:reticulate|rJava|httr2?|curl|RCurl|processx|rzmq|mirai|crew)::\w+"
            r"|(?<![\w.$@])(?:\.jcall|\.jnew|socketConnection|py_run_string|py_run_file|GET|POST|PUT|DELETE|PATCH"
            r"|system2?)\("
        ),
        "system_config_mutation": re.compile(
            r"(?<![\w.$@])(?:Sys\.setenv|Sys\.unsetenv|Sys\.setlocale|Sys\.chmod|Sys\.umask|setwd|options|file\.chmod)\("
        ),
    },
}
