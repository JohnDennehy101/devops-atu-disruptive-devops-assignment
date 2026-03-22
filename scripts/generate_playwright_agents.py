import argparse
import json
import re
import shutil
import subprocess
import time
from datetime import datetime

from shared import (
    APP_DIR_PATH,
    CHANGE_TYPE_MAP,
    DEV_SERVER_URL,
    HOME_TSX_PATH,
    ITERATION_MAP,
    MODEL_OUTPUTS_PATH,
    REPO_ROOT_PATH,
    VERSIONS_ROOT_PATH,
    collect_unique_prompts,
    resolve_file_path_for_code_change,
    start_dev_server,
    stop_dev_server,
    uncomment_file,
)

# Directories used by the Playwright agents pipeline
SPECS_DIRECTORY = APP_DIR_PATH / "specs"
TESTS_DIRECTORY = APP_DIR_PATH / "e2e" / "generated"
AGENT_NODE_MODULES = APP_DIR_PATH / "e2e" / "node_modules"


def clean_agent_outputs() -> None:
    """
    Remove generated specs and tests from previous agent runs
    to ensure clean state for each test run.
    """

    # Remove all markdown plans from specs directory but keep README
    for md_file in SPECS_DIRECTORY.glob("*.md"):
        if md_file.name != "README.md":
            md_file.unlink()

    # Remove all generated test files from tests directory
    if TESTS_DIRECTORY.exists():
        shutil.rmtree(TESTS_DIRECTORY)

    # Recreate it ahead of next run
    TESTS_DIRECTORY.mkdir(exist_ok=True)

    # Remove any node_modules created by agent runs to avoid conflicts
    if AGENT_NODE_MODULES.exists():
        shutil.rmtree(AGENT_NODE_MODULES)


def run_agent(agent_name: str, prompt: str, timeout: int = 600) -> dict:
    """
    Run a named Playwright agent via the Claude Code cli.
    Returns a dict with full output details for reporting.
    """

    # Get start time for duration calculation
    timestamp_start = time.time()

    # Using Popen to stream stdout as it occurs and capture output
    # subprocess.run used previously with capture_output=True buffered everything
    # meaning on timeout all output was lost and couldn't see any progress
    # Added as the generator is taking a long time to run
    process = subprocess.Popen(
        [
            "claude",
            "-p",
            prompt,
            "--agent",
            agent_name,
            "--allowedTools",
            "mcp__playwright-test__*,Write,Edit,Read,Glob,Grep",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Read standard output line by line so progress is visible in terminal
    stdout_lines = []
    try:
        # Loops to read standard output as it is produced
        for line in process.stdout:
            print(f"{line}", end="", flush=True)
            stdout_lines.append(line)

        # Wait for process to finish and capture stderr
        process.wait(timeout=timeout)

        # Capture standard error output after process finish
        stderr_output = process.stderr.read()

        # Calculate duration of agent run
        duration = round(time.time() - timestamp_start, 3)

        # Validation check - warn user if error
        if process.returncode != 0:
            print(f"\n    Warning: {agent_name} exited with code {process.returncode}")
            if stderr_output:
                print(f"    stderr: {stderr_output[:300]}")

        # Return dict with details of agent run
        return {
            "stdout": "".join(stdout_lines).strip(),
            "stderr": stderr_output.strip(),
            "return_code": process.returncode,
            "duration_s": duration,
            "timed_out": False,
            "prompt": prompt,
        }

    # Handle timeout scenario. Kills existing process but keeps any output
    except subprocess.TimeoutExpired:
        # Kill the process
        process.kill()

        # Capture the standard error output
        stderr_output = process.stderr.read()

        # Determine the duration until timeout
        duration = round(time.time() - timestamp_start, 3)

        # Print for user visiblity
        print(f"\nWarning: {agent_name} timed out after {timeout}s")

        # Return dict with as much output as possible
        return {
            "stdout": "".join(stdout_lines).strip(),
            "stderr": stderr_output.strip()
            if stderr_output
            else f"Process timed out after {timeout}s",
            "return_code": -1,
            "duration_s": duration,
            "timed_out": True,
            "prompt": prompt,
        }


def run_planner(change_description: str) -> dict:
    """
    Run the Playwright test planner agent.
    It uses the running app to produce a test plan in specs directory.
    """

    # Construct prompt for planner agent
    # Note: limit to 5 scenarios max to avoid generator timeouts
    # as each scenario requires multiple MCP tool calls
    # First runs were timing out as agent was generating too many
    # tests and tokens cost could explode across many runs.
    prompt = f"""The app is running at {DEV_SERVER_URL}

    Explore the application and create a test plan focused on the following changes:

    {change_description}

    IMPORTANT CONSTRAINTS:
    - Create a MAXIMUM of 3 test scenarios (focus on the most critical paths only)
    - All test files should be placed under app/e2e/generated/
    - The seed file is at app/e2e/seed.spec.ts

    Save the plan to app/specs/."""

    return run_agent("playwright-test-planner", prompt)


def run_generator() -> dict:
    """
    Run the Playwright test generator agent.
    It reads test plans from specs/ and generates test files in tests/.
    """

    # Find all spec plans excluding README
    # Build the prompt with references to all
    # plans generated from planner agent.
    plan_files = [f for f in SPECS_DIRECTORY.glob("*.md") if f.name != "README.md"]

    # Validation check - if no plans found, return empty result
    if not plan_files:
        return {
            "stdout": "No test plans found in specs/",
            "stderr": "",
            "return_code": -1,
            "duration_s": 0.0,
            "timed_out": False,
            "prompt": "",
        }

    # Load into string that can be injected into prompt
    plan_references = "\n".join(
        f"- {f.relative_to(REPO_ROOT_PATH)}" for f in plan_files
    )

    # Construct prompt including the plan files
    prompt = f"""Generate Playwright tests from the following test plan(s):

    {plan_references}

    The app is running at {DEV_SERVER_URL}
    The seed file is at app/e2e/seed.spec.ts.
    Generate tests into the app/e2e/generated/ directory."""

    # Run generator agent with longer timeout as it interacts
    # with the app for each test scenario via MCP tools
    return run_agent("playwright-test-generator", prompt, timeout=900)


def run_healer() -> dict:
    """
    Run the Playwright test healer agent.
    It runs the generated tests and automatically fixes any failures.
    """

    # Construct prompt mentioning the generated files
    prompt = """Run all tests in the app/e2e/generated/ directory.
    If any tests fail, debug and fix them.
    Continue until all tests pass or are marked as fixme."""

    # Run healer agent with the prompt
    # Note longer timeout as it may need multiple test runs
    # to actually fix the tests
    return run_agent("playwright-test-healer", prompt, timeout=600)


def collect_generated_plans() -> str:
    """
    Read generated test plan markdown files from specs directory.
    Return plan content as a single string.
    """

    # Collect all plan files excluding README
    plan_files = sorted(
        f for f in SPECS_DIRECTORY.glob("*.md") if f.name != "README.md"
    )

    # If none found, default to empty string
    if not plan_files:
        return ""

    # Combine all plans into a single string
    parts = []
    for pf in plan_files:
        parts.append(f"<!-- File: {pf.relative_to(REPO_ROOT_PATH)} -->")
        parts.append(pf.read_text())
        parts.append("")

    # Combine with new line separators
    return "\n".join(parts)


def collect_generated_tests() -> tuple[str, list[dict]]:
    """
    Read generated test files from tests directory.
    """

    # Collect generated spec files from the expected directory
    # Also check repo root e2e/generated/ as the MCP tool may write there instead
    fallback_dir = REPO_ROOT_PATH / "e2e" / "generated"
    test_files = sorted(TESTS_DIRECTORY.rglob("*.spec.ts"))
    if not test_files and fallback_dir.exists():
        test_files = sorted(fallback_dir.rglob("*.spec.ts"))

    # If none found in either location, default to empty
    if not test_files:
        return "", []

    # Combined parts list will be joined into single string
    # to match format of other model outputs
    combined_parts = []

    # File records is for capturing files that were generated
    # Easier to analyse after the run
    file_records = []

    # Loop over test files
    for tf in test_files:
        # Get relative path to include for auditing
        relative_path = str(tf.relative_to(REPO_ROOT_PATH))

        # Read the file content
        content = tf.read_text()

        # Add to combined parts with comment for file separation
        combined_parts.append(f"// File: {relative_path}")
        combined_parts.append(content)
        combined_parts.append("")

        # Add to file records for capturing each individually
        file_records.append(
            {
                "file": relative_path,
                "content": content,
            }
        )

    # Combine with newline separators for the combined_parts
    # Leave file_records as list for easier analysis of individual
    # generated files after the run
    return "\n".join(combined_parts), file_records


def build_change_description(prompt_entry: dict) -> str:
    """
    Make a description of the change from the prompt.
    Use the context.md file, if not present
    fall back to the original prompt.
    """

    # Extract iteration from entry
    iteration = prompt_entry["iteration"]

    # Extract change type from entry
    change_type = prompt_entry["change_type"]

    # Try to load the context.md for this change
    changes_dir = ITERATION_MAP.get(iteration)
    versions_dir = CHANGE_TYPE_MAP.get(change_type)

    # If both directories exist,
    # try read context.md file and return content
    if changes_dir and versions_dir:
        context_file = VERSIONS_ROOT_PATH / versions_dir / changes_dir / "context.md"
        if context_file.exists():
            return context_file.read_text()

    # Fallback to original prompt if it doesn't exist
    return prompt_entry["prompt"]


def main():
    # Argument parser to enable optional filtering for debugging
    parser = argparse.ArgumentParser(
        description="Generate Playwright tests via Playwright's built-in AI agents"
    )
    parser.add_argument("--filter-scenario", help="Filter by scenario type")
    parser.add_argument("--filter-prompt", help="Filter by prompt type")
    parser.add_argument(
        "--filter-iteration",
        choices=list(ITERATION_MAP.keys()),
        help="Filter by iteration",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be run without calling agents",
    )
    args = parser.parse_args()

    print("Collecting unique prompts from model_outputs/...", end=" ", flush=True)

    # Extract unique prompts - only need one per iteration and change_type
    # as the agents explore the app rather than using the text prompt
    prompts = collect_unique_prompts()
    print(f"{len(prompts)} found.")

    # Apply filters
    if args.filter_scenario:
        prompts = [p for p in prompts if args.filter_scenario in p["scenario"]]
    if args.filter_prompt:
        prompts = [p for p in prompts if p["prompt_type"] == args.filter_prompt]
    if args.filter_iteration:
        prompts = [p for p in prompts if p["iteration"] == args.filter_iteration]

    # Deduplicate by iteration and change type as agents explore the app
    # rather than using the text prompt. The scenario and prompt type dimensions
    # produce identical runs for agents, so only one is needed per change.

    # Using a set to track already seen combinations of iteration and
    # change typ
    seen_combinations = set()

    # List to contain unique prompts
    unique_prompts = []

    # Loop over prompts
    for p in prompts:
        key = (p["iteration"], p["change_type"])
        if key not in seen_combinations:
            seen_combinations.add(key)
            unique_prompts.append(p)

    # Set prompts to the calculated unique prompts
    prompts = unique_prompts

    # Validation check if no prompts remain after filtering
    if not prompts:
        print("No prompts match the given filters.")
        return

    print(f"Will generate {len(prompts)} Playwright agent outputs.\n")

    # Start the dev server so agents can interact with the running app
    if not args.dry_run:
        dev_server = start_dev_server()
    else:
        dev_server = None

    try:
        # Loop over prompts
        for i, p in enumerate(prompts, 1):
            # Debug label to show progress
            label = f"{p['scenario']} / {p['change_type']} / {p['iteration']} / {p['prompt_type']}"
            print(f"[{i}/{len(prompts)}] {label}", end=" ", flush=True)

            # Build output path under playwright_agents model directory
            output_directory = (
                MODEL_OUTPUTS_PATH
                / p["scenario_dir"]
                / p["change_type"]
                / p["iteration"]
                / "playwright_agents"
            )

            # Ensure output directory exists
            output_directory.mkdir(parents=True, exist_ok=True)

            # Skip if output already exists for this prompt combination
            existing = list(
                output_directory.glob(
                    f"playwright_agents_{p['prompt_type']}_{p['scenario']}_*.json"
                )
            )

            if existing:
                print("(already exists, skipping)")
                continue

            # Timestamp used for unique file name and record
            timestamp = datetime.now().isoformat()

            # File name generation
            filename = f"playwright_agents_{p['prompt_type']}_{p['scenario']}_{timestamp.replace(':', '_')}.json"

            # If dry run, just print what would be done and skip
            if args.dry_run:
                print(f"-> {output_directory / filename} (dry run)")
                continue

            # Determine the correct version of Home.tsx for this iteration
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

                # Clean previous agent outputs to ensure clean run
                clean_agent_outputs()

                # Get description of change for the planner
                change_description = build_change_description(p)

                # Step 1: Planner - looks at the app and creates a test plan
                print("\n[planner agent]", end=" ", flush=True)
                planner_result = run_planner(change_description)
                print(f"({planner_result['duration_s']}s)", end="", flush=True)

                # Step 2: Generator - reads the agent plan, generates test files
                print("\n[generator agent]", end=" ", flush=True)
                generator_result = run_generator()
                print(f"({generator_result['duration_s']}s)", end="", flush=True)

                # Step 3: Healer - runs tests from the generator agent, fixes failures
                print("\n[healer agent]", end=" ", flush=True)
                healer_result = run_healer()
                print(f"({healer_result['duration_s']}s)", end="", flush=True)

                # Collect all generated plans and test code
                total_duration = round(
                    planner_result["duration_s"]
                    + generator_result["duration_s"]
                    + healer_result["duration_s"],
                    3,
                )
                generated_plan = collect_generated_plans()
                generated_code, test_files = collect_generated_tests()

                # Build output record, note this includes outputs per agent
                record = [
                    {
                        "timestamp": timestamp,
                        "model_id": "anthropic/playwright-agents-claude-sonnet-4-20250514",
                        "prompt_type": p["prompt_type"],
                        "scenario": p["scenario"],
                        "metrics": {
                            "inference_time_s": total_duration,
                            "planner_time_s": planner_result["duration_s"],
                            "generator_time_s": generator_result["duration_s"],
                            "healer_time_s": healer_result["duration_s"],
                        },
                        "content": {
                            "prompt": change_description,
                            "test_plan": generated_plan,
                            "extracted_code": generated_code,
                            "test_files": test_files,
                        },
                        "agent_outputs": {
                            "planner": {
                                "stdout": planner_result["stdout"],
                                "stderr": planner_result["stderr"],
                                "return_code": planner_result["return_code"],
                                "timed_out": planner_result["timed_out"],
                                "prompt": planner_result["prompt"],
                            },
                            "generator": {
                                "stdout": generator_result["stdout"],
                                "stderr": generator_result["stderr"],
                                "return_code": generator_result["return_code"],
                                "timed_out": generator_result["timed_out"],
                                "prompt": generator_result["prompt"],
                            },
                            "healer": {
                                "stdout": healer_result["stdout"],
                                "stderr": healer_result["stderr"],
                                "return_code": healer_result["return_code"],
                                "timed_out": healer_result["timed_out"],
                                "prompt": healer_result["prompt"],
                            },
                        },
                        "hyperparameters": {
                            "note": "Playwright built-in AI agents (planner, generator, healer)",
                        },
                    }
                ]

                # Save output in a JSON file
                output_path = output_directory / filename
                with open(output_path, "w") as f:
                    json.dump(record, f, indent=4)

                # Quick status check to see if the test was successfully generated
                status = (
                    "ok"
                    if re.search(r"\btest\s*\(", generated_code)
                    else "no test() found"
                )
                print(f" ({total_duration}s total) [{status}]")

            finally:
                # Restore original Home.tsx after each prompt
                HOME_TSX_PATH.write_text(backup)

            # Small delay between runs
            time.sleep(2)

    finally:
        # Stop the dev server when done
        if dev_server:
            stop_dev_server(dev_server)

    print("\nDone.")


if __name__ == "__main__":
    main()
