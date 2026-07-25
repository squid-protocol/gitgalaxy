#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: Pipeline Validation Harness
#
# PURPOSE:
# Stress-tests the entire Cloud Modernization Pathway (Structural Extraction ->
# Spring Boot Scaffolding -> Maven Compilation) across 'n' legacy repositories.
# Captures granular debugging logs for CI/CD auditing.
#
# ARCHITECTURAL DECISION:
# In enterprise migrations, translating thousands of COBOL programs introduces
# compounding points of failure. This harness isolates each translation phase,
# enforcing strict dependency bounds and execution timeouts to guarantee
# deterministic batch validation without pipeline stalling.
# ==============================================================================
import argparse
import os
import subprocess
import time
from pathlib import Path


def run_command(command: list, cwd: Path) -> tuple[bool, str, str]:
    """Executes a shell command and returns success status + logs."""

    # ==========================================================================
    # DEFENSIVE DESIGN (ENVIRONMENT PARITY):
    # Compiling generated code across different developer machines or CI/CD runners
    # invites "it works on my machine" failures. We clone the environment and
    # forcefully inject a specific JDK path to guarantee deterministic compilation.
    # ==========================================================================
    custom_env = os.environ.copy()
    custom_env["JAVA_HOME"] = "/usr/lib/jvm/java-17-openjdk-amd64"

    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=custom_env,
            capture_output=True,
            text=True,
            # DEFENSIVE DESIGN: 5-minute timeout per command to prevent zombie
            # processes from hanging the entire batch run if a regex loops infinitely.
            timeout=300,
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired as e:
        return (
            False,
            e.stdout.decode("utf-8") if e.stdout else "",
            "TIMEOUT: Command exceeded 5 minutes.",
        )
    except Exception as e:
        return False, "", str(e)


def main():
    parser = argparse.ArgumentParser(description="GitGalaxy Pipeline Validation Harness")
    parser.add_argument("corpus_dir", help="Path to the directory containing legacy COBOL repos")
    parser.add_argument("--n", type=int, default=0, help="Number of repositories to process (0 for all)")
    args = parser.parse_args()

    corpus_path = Path(args.corpus_dir).resolve()
    v6_dir = corpus_path.parents[1] / "v6" / "gitgalaxy"

    reports_dir = corpus_path / "batch_test_reports"
    reports_dir.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    master_log_path = reports_dir / f"master_batch_run_{timestamp}.txt"

    all_dirs = [d for d in corpus_path.iterdir() if d.is_dir()]
    target_repos = [d for d in all_dirs if not ("_gitgalaxy_" in d.name or "batch_test" in d.name)]
    if args.n > 0:
        target_repos = target_repos[: args.n]

    print("\n" + "=" * 70)
    print(" 🧪 PIPELINE VALIDATION HARNESS ENGAGED")
    print(f" Target Corpus : {corpus_path.name}")
    print(f" Sample Size   : n = {len(target_repos)}")
    print("=" * 70 + "\n")

    summary = {
        "passed": 0,
        "failed_refractor": 0,  # Preserved dictionary key
        "failed_java_forge": 0,  # Preserved dictionary key
        "failed_maven": 0,
    }

    with open(master_log_path, "w", encoding="utf-8") as master_log:
        master_log.write(f"GITGALAXY BATCH RUN - {timestamp}\nSample Size: {len(target_repos)}\n\n")

        for repo in target_repos:
            print(f"⚙️  Processing: {repo.name} ... ", end="", flush=True)
            master_log.write(f"--- REPO: {repo.name} ---\n")
            repo_error_log = reports_dir / f"{repo.name}_error_{timestamp}.log"

            # STEP 1: Structural Extraction
            cmd1 = ["python", str(v6_dir / "cobol_refractor_controller.py"), repo.name]
            success1, out1, err1 = run_command(cmd1, cwd=corpus_path)
            if not success1:
                print("❌ FAILED (Structural Extraction Phase)")
                print("\n" + "-" * 40 + " LAST 15 LINES OF STDERR " + "-" * 40)
                print("\n".join(err1.splitlines()[-15:]))
                print("-" * 105 + "\n")
                summary["failed_refractor"] += 1
                repo_error_log.write_text(f"--- EXTRACTION STDERR ---\n{err1}\n\n--- STDOUT ---\n{out1}")
                continue

            clean_dirs = sorted(
                corpus_path.glob(f"{repo.name}_gitgalaxy_clean_*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not clean_dirs:
                continue
            clean_room = clean_dirs[0]

            # STEP 2: Spring Boot Scaffolding
            cmd2 = [
                "python",
                str(v6_dir / "cobol_to_java_controller.py"),
                clean_room.name,
            ]
            success2, out2, err2 = run_command(cmd2, cwd=corpus_path)
            if not success2:
                print("❌ FAILED (Spring Boot Scaffolding Phase)")
                print("\n" + "-" * 40 + " LAST 15 LINES OF STDERR " + "-" * 40)
                print("\n".join(err2.splitlines()[-15:]))
                print("-" * 105 + "\n")
                summary["failed_java_forge"] += 1
                repo_error_log.write_text(f"--- SCAFFOLDING STDERR ---\n{err2}\n\n--- STDOUT ---\n{out2}")
                continue

            java_dirs = sorted(
                corpus_path.glob(f"{repo.name}_gitgalaxy_java_spring_*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not java_dirs:
                continue
            java_dir = java_dirs[0]

            # STEP 3: Maven Compilation
            cmd3 = ["mvn", "clean", "compile"]
            success3, out3, err3 = run_command(cmd3, cwd=java_dir)
            if not success3:
                print("❌ FAILED (Maven Compilation)")
                print("\n" + "-" * 40 + " LAST 15 LINES OF MAVEN LOG " + "-" * 40)
                # Maven puts compilation errors in stdout, not stderr!
                print("\n".join(out3.splitlines()[-15:]))
                print("-" * 105 + "\n")
                summary["failed_maven"] += 1
                repo_error_log.write_text(f"--- MAVEN STDERR/STDOUT ---\n{out3}\n{err3}")
                continue

            print("✅ SUCCESS (Fully Compiled)")
            summary["passed"] += 1

        print("\n" + "=" * 70)
        print(" 🏁 BATCH TEST COMPLETE")
        print("----------------------------------------------------------------------")
        print(f"  • Perfect Successes    : {summary['passed']}/{len(target_repos)}")
        print(f" 📁 Master Log  : {master_log_path}")
        print("======================================================================\n")


if __name__ == "__main__":
    main()
