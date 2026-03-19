import argparse
import json
import re
import subprocess
import time
from datetime import datetime

from shared import (
    ITERATION_MAP,
    MODEL_OUTPUTS_PATH,
    collect_unique_prompts,
    extract_typescript,
)


def call_claude(prompt: str) -> tuple[str, float]:
    """
    Call claude -p and return (response, duration_seconds).
    """

    # Use subprocess to call the Claude Code CLI with prompt,
    # capture the output and measure inference time.
    test_start = time.time()
    result = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=120,
    )
    duration = round(time.time() - test_start, 3)

    # Check for non-zero exit code
    if result.returncode != 0:
        print(f"  WARNING: claude exited with code {result.returncode}")
        if result.stderr:
            print(f"  stderr: {result.stderr[:200]}")

    # Return raw response and duration
    return result.stdout.strip(), duration


def main():
    # Argument parser in place for optional filtering
    # Dry run option to test what would be run without actually calling.
    parser = argparse.ArgumentParser(
        description="Generate Playwright tests via Claude Code CLI"
    )
    parser.add_argument("--filter-scenario", help="Filter by scenario slug")
    parser.add_argument("--filter-prompt", help="Filter by prompt type")
    parser.add_argument(
        "--filter-iteration",
        choices=list(ITERATION_MAP.keys()),
        help="Filter by iteration",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be run without calling Claude",
    )
    args = parser.parse_args()

    print("Collecting unique prompts from model_outputs/...", end=" ", flush=True)

    # Extract unique prompts used for open-source models
    # so that claude can be called on the same set for comparison.
    prompts = collect_unique_prompts()
    print(f"{len(prompts)} found.")

    # Apply filters
    if args.filter_scenario:
        prompts = [p for p in prompts if args.filter_scenario in p["scenario"]]
    if args.filter_prompt:
        prompts = [p for p in prompts if p["prompt_type"] == args.filter_prompt]
    if args.filter_iteration:
        prompts = [p for p in prompts if p["iteration"] == args.filter_iteration]

    # Validation check if no prompt remain after filtering exit
    if not prompts:
        print("No prompts match the given filters.")
        return

    print(f"Will generate {len(prompts)} Claude outputs.\n")

    # Loop over prompts and call claude code cli for each
    for i, p in enumerate(prompts, 1):

        # Debug label to show progress in UI
        label = f"{p['scenario']} / {p['change_type']} / {p['iteration']} / {p['prompt_type']}"
        print(f"[{i}/{len(prompts)}] {label}", end=" ", flush=True)

        # Build output path
        output_directory = (
            MODEL_OUTPUTS_PATH
            / p["scenario_dir"]
            / p["change_type"]
            / p["iteration"]
            / "claude"
        )

        # Ensure output directory exists
        output_directory.mkdir(parents=True, exist_ok=True)

        # Timestamp used for unique file name and record
        timestamp = datetime.now().isoformat()

        # File name defined by prompt type, scenario, and timestamp
        # Same format used for other open-source model outputs
        # for consistency
        filename = f"claude_{p['prompt_type']}_{p['scenario']}_{timestamp.replace(':', '_')}.json"

        # If dry run, just print what would be done and exit
        if args.dry_run:
            print(f"-> {output_directory / filename} (dry run)")
            continue

        # Call Claude Code CLI
        raw_response, duration = call_claude(p["prompt"])

        # Extract code from raw response
        extracted = extract_typescript(raw_response)

        # Build output record matching existing format
        record = [
            {
                "timestamp": timestamp,
                "model_id": "anthropic/claude-sonnet-4-20250514",
                "prompt_type": p["prompt_type"],
                "scenario": p["scenario"],
                "metrics": {
                    "inference_time_s": duration,
                },
                "content": {
                    "prompt": p["prompt"],
                    "raw_response": raw_response,
                    "extracted_code": extracted,
                },
                "hyperparameters": {
                    "note": "Claude Code CLI (claude -p), Max subscription",
                },
            }
        ]

        # Construct output path and save the JSON to that path
        output_path = output_directory / filename
        with open(output_path, "w") as f:
            json.dump(record, f, indent=4)

        # Quick status check to see if extraction generated a test
        status = "ok" if re.search(r"\btest\s*\(", extracted) else "no test() found"
        print(f"({duration}s) [{status}]")

        # Small delay to be respectful of rate limits
        time.sleep(2)

    print("\nDone.")


if __name__ == "__main__":
    main()
