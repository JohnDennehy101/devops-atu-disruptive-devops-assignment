"""
Shared constants and utility functions used across evaluation and generation scripts.
"""

import json
import re
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
