"""
Shared constants and utility functions used across evaluation and generation scripts.
"""

import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


# Common paths - variables defined for reuse across scripts
REPO_ROOT_PATH = Path(__file__).parent.parent
MODEL_OUTPUTS_PATH = REPO_ROOT_PATH / "model_outputs"
VERSIONS_ROOT_PATH = REPO_ROOT_PATH / "versions"
APP_DIR_PATH = REPO_ROOT_PATH / "app"
HOME_TSX_PATH = APP_DIR_PATH / "src" / "pages" / "Home.tsx"
E2E_DIR_PATH = APP_DIR_PATH / "e2e"
EVAL_OUTPUTS_DIR_PATH = REPO_ROOT_PATH / "eval_outputs"
DEV_SERVER_URL = "http://localhost:5175"


# Map from change_type (MODEL_OUTPUTS_PATH path segment) to versions/ subdirectory
CHANGE_TYPE_MAP = {
    "code_change_and_test_change": "code_change_and_tests",
    "code_change": "code_change_only",
}

# Map from iteration keyword to target directory in versions/
ITERATION_MAP = {
    "first": "changes_1",
    "second": "changes_2",
    "third": "changes_3",
    "fourth": "changes_4",
}


def extract_typescript(raw: str) -> str:
    """
    Try extract the Playwright test code from a model response.
    """
    # First look for code blocks identified by ```
    blocks = re.findall(r"```(\w*)\s*\n(.*?)```", raw, re.DOTALL)

    # If code block found and test within it, return immediately
    for language, content in blocks:
        if language in ("typescript", "ts") and re.search(r"\btest\s*\(", content):
            return content.strip()

    # No test block found but typescript or ts block found - returned as should be able to run
    for language, content in blocks:
        if language in ("typescript", "ts"):
            return content.strip()

    # No typescript block found but test block found so again should be usable
    for language, content in blocks:
        if re.search(r"\btest\s*\(", content):
            return content.strip()

    # If no match for others, revert to regex scans for import statements, test blocks, test defintions
    for item in [
        r"(import\s+\{[^}]*test[^}]*\}.*)",
        r"(test\.describe\s*\(.*)",
        r"(test\s*\(.*)",
    ]:
        match = re.search(item, raw, re.DOTALL)
        if match:
            return match.group(1).strip()

    # If no match for any, just return the raw response
    return raw


def collect_unique_prompts() -> list[dict]:
    """
    Scan model outputs and collect unique (prompt, scenario,
    prompt_type, iteration, change_type) combinations. Only need one
    run per unique prompt — no need to duplicate across models.
    """

    # Set used to ensure unique entries
    seen = set()

    # List of dicts which will store prompts
    prompts = []

    # Extract all model output JSON files
    for json_file in sorted(MODEL_OUTPUTS_PATH.rglob("*.json")):
        # Load the JSON file
        with open(json_file) as f:
            entries = json.load(f)

        # Extract scenario_dir, change_type, iteration from the file path structure
        parts = json_file.relative_to(MODEL_OUTPUTS_PATH).parts

        # Check for consistent path structure: scenario_dir/change_type/iteration/model/filename.json
        if len(parts) < 4:
            continue

        # Extract scenario from path
        scenario_directory = parts[0]

        # Extract change type from path
        change_type = parts[1]

        # Extract iteration from path
        iteration = parts[2]

        # Loop through entries in the file
        for entry in entries:
            # Extract prompt text
            prompt_text = entry.get("content", {}).get("prompt", "")

            # Extract prompt type
            prompt_type = entry.get("prompt_type", "")

            # Extract scenario
            scenario = entry.get("scenario", "")

            # Create key tuple to store in seen set for uniqueness check
            key = (scenario, change_type, iteration, prompt_type)

            # If that tuple already within set, don't add, continue to next iteration
            if key in seen or not prompt_text.strip():
                continue

            # Otherwise, add to set and append to prompts
            seen.add(key)

            # Append dict with list of relevant info for target prompt
            prompts.append(
                {
                    "prompt": prompt_text,
                    "prompt_type": prompt_type,
                    "scenario": scenario,
                    "scenario_dir": scenario_directory,
                    "change_type": change_type,
                    "iteration": iteration,
                }
            )

    # Return the list of unique prompts
    return prompts


def resolve_file_path_for_code_change(iteration: str, change_type: str) -> Path | None:
    """
    Determine the path to the version-specific Home.tsx for the given iteration
    and change type. Returns None if the file is missing.
    """

    # Look up the version subdirectory and changes directory
    changes_dir = ITERATION_MAP.get(iteration)
    versions_dir = CHANGE_TYPE_MAP.get(change_type)

    # Validate that both mappings exist
    if not changes_dir or not versions_dir:
        return None

    # Construct path to the version specific Home.tsx
    version_home = VERSIONS_ROOT_PATH / versions_dir / changes_dir / "Home.tsx"

    # Return the path only if the file exists on disk
    return version_home if version_home.exists() else None


def uncomment_file(src: Path, dst: Path) -> None:
    """
    To avoid linting errors in version specific tsx files, they are commented out with '//'.
    This function removes the leading '// ' from every line and writes to the destination path
    I.E so that the version specific file is written to actual Home.tsx file for the Playwright test run
    """

    # Read the source file
    raw = src.read_text()

    # Regex check to remove the comments
    lines = [re.sub(r"^// ?", "", line) for line in raw.splitlines()]

    # Write the uncommented content to the destination file
    dst.write_text("\n".join(lines))


def start_dev_server() -> subprocess.Popen:
    """
    Start the Vite dev server and block until it responds on DEV_SERVER_URL.
    This is necessary to ensure the app is running, ready to serve the test page
    against which the Playwright tests will run.
    """
    # Use a sub process to start the actual web app
    proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=APP_DIR_PATH,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Debug statement
    print(f"Starting dev server (pid {proc.pid})...", end=" ", flush=True)

    # Allow up to 30 seconds for the dev server to be up and responsive
    for _ in range(30):
        try:
            urllib.request.urlopen(DEV_SERVER_URL, timeout=2)
            print("ready.")
            return proc
        except (urllib.error.URLError, OSError):
            time.sleep(1)

    # If not running within 30 seconds, terminate the process and raise an error
    proc.terminate()
    raise RuntimeError(
        f"Dev server did not become ready at {DEV_SERVER_URL} within 30s"
    )


def stop_dev_server(proc: subprocess.Popen) -> None:
    """
    This function ensures server stops after each test finishes to ensure
    a clean run for each test.
    """

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("Dev server stopped.")
