import argparse
import json
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

from shared import (
    DEV_SERVER_URL,
    HOME_TSX_PATH,
    ITERATION_MAP,
    MODEL_OUTPUTS_PATH,
    collect_unique_prompts,
    extract_typescript,
    resolve_file_path_for_code_change,
    start_dev_server,
    stop_dev_server,
    uncomment_file,
)


# Define MCP server config for Playwright as constant
MCP_CONFIG = {
    "mcpServers": {"playwright": {"command": "npx", "args": ["@playwright/mcp@latest"]}}
}


def build_mcp_prompt(prompt_entry: dict) -> str:
    """
    This function constructs the prompt that tells Claude to use MCP tools to inspect
    the running app before generating tests.
    The original diff/source context is still provided,
    but Claude can also browse the app.
    """

    # Extract original prompt
    original_prompt = prompt_entry["prompt"]

    # Construct MCP prompt
    return f"""You have access to a Playwright MCP server that lets you interact with a running web app.
    
    The app is running at {DEV_SERVER_URL}
    
    TASK: Generate Playwright e2e tests for the following code change. 
    Before writing any tests, use your Playwright tools to:
    1. Navigate to {DEV_SERVER_URL}
    2. Take a snapshot to see the current UI structure  
    3. Interact with the changed functionality to understand how it works
    4. Then write comprehensive Playwright test code

    {original_prompt}

    IMPORTANT: Return ONLY the Playwright test code (TypeScript) in a ```typescript code block.
    Use @playwright/test imports. The tests should be runnable with 'npx playwright test'.
    """


def call_claude_with_mcp(prompt: str, mcp_config_path: Path) -> tuple[str, float]:
    """
    Call Claude CLI with MCP server config enabled.
    """

    # Get start time for duration calculation
    t_start = time.time()

    # Use subprocess to call Claude Code CLI
    # Note use of --mcp-config to point
    # to configured MCP server
    result = subprocess.run(
        [
            "claude",
            "-p",
            prompt,
            "--mcp-config",
            str(mcp_config_path),
            "--allowedTools",
            "mcp__playwright__*",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )

    # Measure duration of inference
    duration = round(time.time() - t_start, 3)

    # Validation check - warn user if error
    if result.returncode != 0:
        print(f"  WARNING: claude exited with code {result.returncode}")
        if result.stderr:
            print(f"  stderr: {result.stderr[:200]}")

    # Return raw response from model as well as inference duration
    return result.stdout.strip(), duration


def main():
    # Argument parser to enable optional filtering for debugging
    # And dry run option to see what would be done without
    # actually running the code generation
    parser = argparse.ArgumentParser(
        description="Generate Playwright tests via Claude with MCP tools"
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
    # so that MCP claude can be called on the same set for comparison.
    prompts = collect_unique_prompts()
    print(f"{len(prompts)} found.")

    # Apply filters
    if args.filter_scenario:
        prompts = [p for p in prompts if args.filter_scenario in p["scenario"]]
    if args.filter_prompt:
        prompts = [p for p in prompts if p["prompt_type"] == args.filter_prompt]
    if args.filter_iteration:
        prompts = [p for p in prompts if p["iteration"] == args.filter_iteration]

    # Validation check if no prompts remain after filtering
    if not prompts:
        print("No prompts match the given filters.")
        return

    print(f"Will generate {len(prompts)} MCP Claude outputs.\n")

    # Write MCP config to a temp file for the Claude cli
    mcp_config_path = Path(__file__).parent / "mcp_config.json"
    with open(mcp_config_path, "w") as f:
        json.dump(MCP_CONFIG, f, indent=2)

    # Start the dev server so Claude can interact with the running app via MCP
    dev_server = start_dev_server()

    try:
        # Loop over prompts, swapping Home.tsx per iteration and calling Claude with MCP
        for i, p in enumerate(prompts, 1):
            # Debug label to show progress
            label = f"{p['scenario']} / {p['change_type']} / {p['iteration']} / {p['prompt_type']}"
            print(f"[{i}/{len(prompts)}] {label}", end=" ", flush=True)

            # Build output path under mcp_claude model directory
            output_directory = (
                MODEL_OUTPUTS_PATH
                / p["scenario_dir"]
                / p["change_type"]
                / p["iteration"]
                / "mcp_claude"
            )

            # Ensure output directory exists
            output_directory.mkdir(parents=True, exist_ok=True)

            # Skip if an mcp_claude output already exists for this prompt combination
            existing = list(
                output_directory.glob(
                    f"mcp_claude_{p['prompt_type']}_{p['scenario']}_*.json"
                )
            )

            if existing:
                print("(already exists, skipping)")
                continue

            # Timestamp used for unique file name and record
            timestamp = datetime.now().isoformat()

            # File name matching existing convention
            filename = f"mcp_claude_{p['prompt_type']}_{p['scenario']}_{timestamp.replace(':', '_')}.json"

            # If dry run, just print what would be done and skip
            if args.dry_run:
                print(f"-> {output_directory / filename} (dry run)")
                continue

            # Resolve the correct version of Home.tsx for this iteration
            version_home = resolve_file_path_for_code_change(
                p["iteration"], p["change_type"]
            )
            if not version_home:
                print("skipping due to (missing version Home.tsx)")
                continue

            # Backup current Home.tsx before overwriting
            backup = HOME_TSX_PATH.read_text() if HOME_TSX_PATH.exists() else ""

            try:
                # Uncomment and write the version specific file to the actual Home.tsx
                uncomment_file(version_home, HOME_TSX_PATH)

                # Build the MCP-enhanced prompt
                mcp_prompt = build_mcp_prompt(p)

                # Call Claude with MCP server enabled
                raw_response, duration = call_claude_with_mcp(
                    mcp_prompt, mcp_config_path
                )

                # Extract code from raw response
                extracted = extract_typescript(raw_response)

                # Build output record matching existing format
                record = [
                    {
                        "timestamp": timestamp,
                        "model_id": "anthropic/mcp-claude-sonnet-4-20250514",
                        "prompt_type": p["prompt_type"],
                        "scenario": p["scenario"],
                        "metrics": {
                            "inference_time_s": duration,
                        },
                        "content": {
                            "prompt": mcp_prompt,
                            "raw_response": raw_response,
                            "extracted_code": extracted,
                        },
                        "hyperparameters": {
                            "note": "Claude Code CLI with Playwright MCP server",
                        },
                    }
                ]

                # Save the JSON output
                output_path = output_directory / filename
                with open(output_path, "w") as f:
                    json.dump(record, f, indent=4)

                # Quick status check to see if extraction generated a test
                status = (
                    "ok" if re.search(r"\btest\s*\(", extracted) else "no test() found"
                )
                print(f"({duration}s) [{status}]")

            finally:
                # Restore original Home.tsx after each prompt
                HOME_TSX_PATH.write_text(backup)

            # Small delay to be respectful of rate limits
            time.sleep(2)

    finally:
        # Stop the dev server when done
        stop_dev_server(dev_server)

        # Clean up the temp MCP config file
        if mcp_config_path.exists():
            mcp_config_path.unlink()

    print("\nDone.")


if __name__ == "__main__":
    main()
