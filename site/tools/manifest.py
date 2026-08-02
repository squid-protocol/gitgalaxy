# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
import os
import json

MUSEUM_DIR = "/srv/storage_16tb/projects/gitgalaxy/museum"


def build_manifest():
    manifest_data = []

    # Scan for all base galaxy files
    for filename in os.listdir(MUSEUM_DIR):
        if filename.endswith("_galaxy.json"):
            # Extract the base project name (e.g., "django" from "django_galaxy.json")
            project_name = filename.replace("_galaxy.json", "")

            # Construct expected filenames for the payloads
            audit_filename = f"{project_name}_galaxy_audit.json"
            llm_filename = f"{project_name}_galaxy_llm.md"

            # Check if they actually exist in the museum folder
            has_audit = os.path.exists(os.path.join(MUSEUM_DIR, audit_filename))
            has_llm = os.path.exists(os.path.join(MUSEUM_DIR, llm_filename))

            # Build the payload for the frontend (Mapped for Nginx /data/ folder)
            entry = {
                "id": project_name,
                "name": project_name.replace("-", " ").title(),
                "file": f"/data/{filename}",
                "auditUrl": f"/data/{audit_filename}" if has_audit else "",
                "llmUrl": f"/data/{llm_filename}" if has_llm else "",
            }
            manifest_data.append(entry)

    # Sort alphabetically by project name
    manifest_data = sorted(manifest_data, key=lambda x: x["name"].lower())

    # Write the new manifest.json directly to the museum folder
    manifest_path = os.path.join(MUSEUM_DIR, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f, indent=4)

    print(f"✅ Manifest successfully generated at: {manifest_path}")
    print(f"✅ Total galaxies indexed: {len(manifest_data)}")


if __name__ == "__main__":
    build_manifest()
