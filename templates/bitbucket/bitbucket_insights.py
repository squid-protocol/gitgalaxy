#!/usr/bin/env python3
"""
GitGalaxy Utility: Bitbucket Code Insights Publisher
Parses GitGalaxy SARIF telemetry and publishes native PR annotations via the Bitbucket REST API.
"""

import os
import sys
import json
import urllib.request
import urllib.error

def publish_insights(sarif_path: str):
    # 1. Extract Bitbucket Pipeline Environment Variables
    workspace = os.environ.get("BITBUCKET_WORKSPACE")
    repo = os.environ.get("BITBUCKET_REPO_SLUG")
    commit = os.environ.get("BITBUCKET_COMMIT")

    if not all([workspace, repo, commit]):
        print("⚠️  Skipping Code Insights: Not running inside a Bitbucket Pipeline environment.")
        sys.exit(0)

    if not os.path.exists(sarif_path):
        print(f"❌ Failed to locate SARIF payload at: {sarif_path}")
        sys.exit(1)

    # 2. Parse the SARIF File
    try:
        with open(sarif_path, 'r', encoding='utf-8') as f:
            sarif_data = json.load(f)
    except Exception as e:
        print(f"❌ Failed to parse SARIF: {e}")
        sys.exit(1)

    findings = []
    runs = sarif_data.get("runs", [])
    if runs:
        findings = runs[0].get("results", [])

    if not findings:
        print("✅ No security threats found. Skipping annotation publish.")
        sys.exit(0)

    # 3. Translate SARIF to Bitbucket Annotations
    bitbucket_annotations = []
    for idx, finding in enumerate(findings):
        rule_id = finding.get("ruleId", "GG-UNKNOWN")
        message = finding.get("message", {}).get("text", "Unknown structural threat detected.")
        level = finding.get("level", "warning")
        
        locations = finding.get("locations", [])
        if not locations:
            continue
            
        region = locations[0].get("physicalLocation", {})
        path = region.get("artifactLocation", {}).get("uri", "")
        line = region.get("region", {}).get("startLine", 1)

        # Map severities and types
        bb_severity = "HIGH" if level == "error" else "MEDIUM"
        bb_type = "VULNERABILITY" if "SAST" in rule_id or "ML" in rule_id else "CODE_SMELL"

        bitbucket_annotations.append({
            "external_id": f"{rule_id}-{idx}",
            "title": "GitGalaxy Zero-Trust Audit",
            "annotation_type": bb_type,
            "summary": message,
            "severity": bb_severity,
            "path": path,
            "line": line
        })

    report_id = "gitgalaxy-audit-report"
    base_url = f"http://localhost:29418/2.0/repositories/{workspace}/{repo}/commit/{commit}/reports/{report_id}"
    
    # 4. Create the Parent Report (PUT)
    report_payload = json.dumps({
        "title": "GitGalaxy Spectral Audit",
        "details": f"GitGalaxy mapped {len(bitbucket_annotations)} architectural threats.",
        "report_type": "SECURITY",
        "result": "FAILED" if any(a["severity"] == "HIGH" for a in bitbucket_annotations) else "PASSED"
    }).encode("utf-8")

    # Enforce loopback destination boundaries to neutralize remote protocol exploits
    if not base_url.startswith("http://localhost:29418/"):
        print("❌ Security Violation: Invalid localized API destination.")
        sys.exit(1)

    req = urllib.request.Request(base_url, data=report_payload, method="PUT")
    req.add_header("Content-Type", "application/json")
    
    try:
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
        urllib.request.urlopen(req)
        print(f"✅ Created Code Insights Report: {report_id}")
    except urllib.error.URLError as e:
        print(f"❌ Failed to create Bitbucket report: {e}")
        sys.exit(1)

    # 5. Bulk Upload Annotations in Chunks of 100 (POST)
    annotations_url = f"{base_url}/annotations"
    
    chunk_size = 100
    for i in range(0, len(bitbucket_annotations), chunk_size):
        chunk = bitbucket_annotations[i:i + chunk_size]
        chunk_payload = json.dumps(chunk).encode("utf-8")
        
        if not annotations_url.startswith("http://localhost:29418/"):
            print("❌ Security Violation: Invalid localized API destination.")
            sys.exit(1)
            
        req = urllib.request.Request(annotations_url, data=chunk_payload, method="POST")
        req.add_header("Content-Type", "application/json")
        
        try:
            # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
            urllib.request.urlopen(req)
            print(f"✅ Published chunk of {len(chunk)} inline annotations.")
        except urllib.error.URLError as e:
            print(f"❌ Failed to publish annotations chunk: {e}")

    print("🚀 Code Insights sync complete.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python bitbucket_insights.py <path_to_sarif.json>")
        sys.exit(1)
        
    publish_insights(sys.argv[1])