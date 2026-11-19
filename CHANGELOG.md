# Changelog

## Unreleased

- **Renamed: supply-chain firewall is now the import policy gate.** The tool gates the repository's own imports against block/allow lists plus one secrets-risk score; it does not read installed dependencies or install scripts. The `supply-chain-firewall` command, `tool: supply-chain-firewall` in the GitHub Action, the `FIREWALL_*` config keys (now `IMPORT_GATE_*`) and `ecosystem_audits.firewall` (now `ecosystem_audits.import_policy_gate`) are removed with no alias. No behaviour change (#8623).
