import json
import re
from collections import defaultdict
from pathlib import Path
from sys import stderr, stdout

from shared import EVAL_OUTPUTS_DIR_PATH

# Output path for the error analysis JSON file
ERROR_ANALYSIS_PATH = EVAL_OUTPUTS_DIR_PATH / "error_analysis_2.json"

# Map from sub-directory names in eval_outputs directory name to model name used in results.jsonl
DIRECTORY_TO_MODEL_MAP = {
    "claude": "claude-sonnet-4-20250514",
    "copilot": "gpt-4o",
    "deepseek": "DeepSeek-Coder-V2-Lite-Instruct",
    "deepseek_api": "deepseek-chat",
    "google": "gemma-3-12b-it",
    "mcp_claude": "mcp-claude-sonnet-4-20250514",
    "mistral": "Mistral-Nemo-Instruct-2407",
    "playwright_agents": "playwright-agents-claude-sonnet-4-20250514",
    "qwen": "Qwen2.5-Coder-14B-Instruct",
    # Recent model runs stored in subdirectories
    "gpt-5-4": "gpt-5.4",
    "32_B_Model": "Qwen2.5-Coder-32B-Instruct",
    "24_B_Model": "Mistral-Small-24B-Instruct-2501",
    "27_B_Model": "gemma-3-27b-it",
}

# Detailed descriptions for each identified error category
CATEGORY_DESCRIPTIONS = {
    "syntax_error_markdown_fences": "Model left markdown code fences (```) in the generated code",
    "missing_import_test": "Model did not include 'import { test } from @playwright/test', so 'test' is undefined",
    "missing_import_expect": "Model did not include 'import { expect } from @playwright/test', so 'expect' is undefined",
    "invalid_playwright_import": "Model tried to import a non-existent export from @playwright/test (e.g., getByRole)",
    "module_not_found": "Model imported a module that does not exist in the project",
    "wrong_url_connection_refused": "Model used wrong URL (e.g., localhost:3000 instead of localhost:5175)",
    "syntax_error_other": "Generated code has a syntax error",
    "type_error": "Runtime TypeError in the generated test code",
    "test_timeout": "Test execution timed out",
    "no_tests_found": "Playwright could not find any valid tests in the generated file",
    "empty_generated_code": "Model returned empty output or no code found",
    "missing_version_file": "Internal error: version-specific Home.tsx file not found",
    "locator_mismatch": "Playwright locator resolved to wrong number of elements",
    "element_not_found_timeout": "Test timed out waiting for an element that was never found on the page",
    "assertion_failure": "Test ran but an assertion (expect) did not match the actual page state",
    "strict_mode_violation": "Locator matched multiple elements when only one was expected",
    "runtime_test_failure": "Test executed but failed at runtime (general failure not matching other categories)",
    "other": "Error that does not match any known category",
}

# Map from eval_outputs scenario directory name to scenario label in results.jsonl
SCENARIO_DIR_MAP = {
    "diff_only": "diff-only",
    "diff_and_source_code": "diff-and-source-code",
    "diff_and_source_code_and_tests": "diff-and-source-code-and-tests",
}


def classify_error(stdout: str, stderr: str) -> str:
    """
    Playwright log files contain standard output and standard error
    section from running the generated tests. This function analyses
    the files to identify common patterns of errors across runs.
    """

    # Combine standard output and standard error for
    # a full search
    combined = stdout + "\n" + stderr

    # Check for missed markdown symbols in the extracted code
    if re.search(r"Unterminated template.*```", combined, re.DOTALL) or re.search(
        r"```", combined
    ):
        if "Unterminated template" in combined or "SyntaxError" in combined:
            return "syntax_error_markdown_fences"

    # Check for missing playwright imports (test is not defined)
    # Visual check of logs suggests this is very common
    if "ReferenceError: test is not defined" in combined:
        return "missing_import_test"

    # Check for missing expect import
    # Visual check of logs suggests this is very common
    if "ReferenceError: expect is not defined" in combined:
        return "missing_import_expect"

    # Check for invalid imports from @playwright/test
    if "does not provide an export named" in combined:
        return "invalid_playwright_import"

    # Check for module not found errors
    # Would indicate hallucinated imports
    if "Cannot find module" in combined:
        return "module_not_found"

    # Check for wrong localhost port (3000 instead of 5175)
    # Another very common error from visual scan of the logs
    if "net::ERR_CONNECTION_REFUSED" in combined:
        return "wrong_url_connection_refused"

    # Check for general syntax errors in generated code
    # Maybe extracted code was cut off or model generation
    # was cut off
    if "SyntaxError" in combined:
        return "syntax_error_other"

    # Check for TypeScript compilation errors
    if "TypeError" in combined:
        return "type_error"

    # Check for timeout during test execution
    if "TIMEOUT" in combined or "Test timeout" in combined:
        return "test_timeout"

    # Check for no tests found
    if "No tests found" in combined:
        return "no_tests_found"

    # Check for empty generated code
    if "empty generated code" in combined:
        return "empty_generated_code"

    # Check for missing version Home.tsx
    if "missing version Home.tsx" in combined:
        return "missing_version_file"

    # Check for element not specific enough
    # Locator resolved to 0 or more than 1 element
    # A common failure pattern in Playwright tests
    if re.search(r"(locator|getBy\w+).*resolved to \d+ element", combined):
        return "locator_mismatch"

    # Another check for element not found but with timeout
    if "waiting for locator" in combined.lower() or "Timeout" in combined:
        return "element_not_found_timeout"

    # Check for assertion failures
    if re.search(
        r"expect\(.*\)\.(toBeVisible|toHaveText|toBe|toContain|toEqual|toHaveCount)",
        combined,
    ):
        return "assertion_failure"

    # Check for strict mode violations (locator matched multiple elements)
    if "strict mode violation" in combined:
        return "strict_mode_violation"

    # If tests ran but failed, classify as runtime test failure
    if re.search(r"\d+ failed", combined):
        return "runtime_test_failure"

    # Fallback for any errors that didn't match any of the above patterns
    return "other"


def extract_error_message(stdout: str, stderr: str) -> str:
    """
    Extract the error message from the log output.
    Returns the first error line, truncated.
    """

    # Combine standard output and standard error for
    # a full search
    combined = stdout + "\n" + stderr

    # Look for common error patterns and extract the relevant line
    # Looping over each to find the first match
    for pattern in [
        r"(ReferenceError:.*)",
        r"(SyntaxError:.*)",
        r"(TypeError:.*)",
        r"(Error:.*)",
        r"(ERROR:.*)",
    ]:
        # Use regex to find first occurrence of current iteration
        match = re.search(pattern, combined)

        # If a match found return first 200 characters after it
        if match:
            return match.group(1).strip()[:200]

    # Fallback in case no error pattern found:
    # returns first non-empty line from stdout
    for line in combined.splitlines():
        stripped = line.strip()
        if stripped and stripped != "=== STDOUT ===" and stripped != "=== STDERR ===":
            return stripped[:200]

    # If no match found, return default message
    return "unknown error"


def parse_log_file(log_path: Path) -> dict | None:
    """
    This function parses a generated .log file and obtains return code, stdout, stderr sections from the file.
    Returns None if the file doesn't match expected format.
    """

    # Reads the log file
    content = log_path.read_text()

    # Checks for a return code to determine pass/fail
    # using regex
    return_code_match = re.search(r"RETURN CODE: (\d+)", content)

    # Handles special cases
    if not return_code_match:
        # Check for timeout
        if "TIMEOUT" in content:
            return {"return_code": -1, "stdout": content, "stderr": ""}
        # Check fo error
        if "ERROR:" in content:
            return {"return_code": 1, "stdout": content, "stderr": ""}
        return None

    # Use the extracted return code
    return_code = int(return_code_match.group(1))

    # Extract standard output section within the log file using regex
    standard_output_match = re.search(
        r"=== STDOUT ===\n(.*?)(?:\n=== STDERR ===|\Z)", content, re.DOTALL
    )

    # Strip whitespace from standard output
    standard_output = (
        standard_output_match.group(1).strip() if standard_output_match else ""
    )

    # Extract standard error section
    standard_error_match = re.search(r"=== STDERR ===\n(.*)", content, re.DOTALL)

    # Strip whitespace from standard error
    standard_error = (
        standard_error_match.group(1).strip() if standard_error_match else ""
    )

    # Return return code, standard output, standard error
    return {
        "return_code": return_code,
        "stdout": standard_output,
        "stderr": standard_error,
    }


def resolve_metadata_from_path(log_path: Path) -> dict | None:
    """
    With log file path, extract metdata about run such as model,
    prompt, scenario, iteration, change type by parsing the file path.
    """

    # Get path relative to eval_outputs directory
    # If error, return None by default
    try:
        relative_path = log_path.relative_to(EVAL_OUTPUTS_DIR_PATH)
    except ValueError:
        return None

    # Get path parts
    path_parts = relative_path.parts

    # Validate the expected path structure
    # Note two valid paths here (as some models are within subdirectories)
    # 5 parts: scenario/change_type/iteration/model/prompt.log
    # 6 parts: scenario/change_type/iteration/model/subdir/prompt.log
    if len(path_parts) not in (5, 6):
        return None

    # Extract scenario, change type, iteration from the path
    scenario_directory = path_parts[0]
    change_type = path_parts[1]
    iteration = path_parts[2]

    # Handle both model directories type based on length (6 is if additional sub-directory)
    if len(path_parts) == 6:
        # For sub-directories within models e.g. copilot/gpt-5-4/ or qwen/32_B_Model/
        model_directory = path_parts[4]
        prompt_type = path_parts[5].replace(".log", "")
    else:
        # For models without sub-directories e.g. google/ or deepseek_api/
        model_directory = path_parts[3]
        prompt_type = path_parts[4].replace(".log", "")

    # Both model and scenario need to be mapped for valid values
    model = DIRECTORY_TO_MODEL_MAP.get(model_directory)
    scenario = SCENARIO_DIR_MAP.get(scenario_directory)

    # If either of those don't find a match, return None
    if not model or not scenario:
        return None

    # Return extracted metadata as a dict
    return {
        "model": model,
        "scenario": scenario,
        "change_type": change_type,
        "iteration": iteration,
        "prompt_type": prompt_type,
    }


def analyse_all_logs() -> list[dict]:
    """
    Find and analyse all .log files under eval_outputs/.
    These were generated by test runner and contain standard output,
    standard error, and return code for each test run.
    """

    # Initialise empty list
    failures = []

    # Find all log files using rglob and sort for consistent processing
    for log_path in sorted(EVAL_OUTPUTS_DIR_PATH.rglob("*.log")):
        # Extract metadata from the file path by calling the helper function
        metadata = resolve_metadata_from_path(log_path)

        # If this was not successful, skip the current file and continue to next
        if not metadata:
            continue

        # Parse the log file contents
        parsed = parse_log_file(log_path)

        # Again, if not successful, skip and continue to next file
        if not parsed:
            continue

        # Only analyse failures (return code != 0)
        if parsed["return_code"] == 0:
            continue

        # Classify the error by calling the helper function
        error_category = classify_error(parsed["stdout"], parsed["stderr"])

        # Get the error message by calling the helper function
        error_message = extract_error_message(parsed["stdout"], parsed["stderr"])

        # Append failure to list with metadata, error category, and
        # error message
        failures.append(
            {
                **metadata,
                "error_category": error_category,
                "error_message": error_message,
            }
        )

    # Once all log files have been processed, return final list
    return failures


def build_error_analysis(failures: list[dict]) -> dict:
    """
    Build a summary of errors from the list of classified failures.
    Note: imperfect as this was conducted from visual analysis but
    sufficient for this limited run.
    """

    # Overall error category counts
    # Using defaultdict for easier counting
    # as don't need to check if key exists before incrementing
    category_counts = defaultdict(int)

    # Loop over failures and count quantity of each error category
    for individual_failure in failures:
        category_counts[individual_failure["error_category"]] += 1

    # Error categories by model
    # Using nested defaultdict to count categories within each model
    by_model = defaultdict(lambda: defaultdict(int))

    # Again loop over failures and count quantiy of each error category per model
    for individual_failure in failures:
        by_model[individual_failure["model"]][individual_failure["error_category"]] += 1

    # Error categories by prompt type
    # Nested defaultdict to count categories within each prompt type
    by_prompt = defaultdict(lambda: defaultdict(int))
    for individual_failure in failures:
        by_prompt[individual_failure["prompt_type"]][
            individual_failure["error_category"]
        ] += 1

    # Error categories by scenario
    # Nested deafultdict to count categories within each scenarios
    by_scenario = defaultdict(lambda: defaultdict(int))
    for individual_failure in failures:
        by_scenario[individual_failure["scenario"]][
            individual_failure["error_category"]
        ] += 1

    # Error categories by iteration
    # Nested defaultdict to count categories within each iteration
    by_iteration = defaultdict(lambda: defaultdict(int))
    for individual_failure in failures:
        by_iteration[individual_failure["iteration"]][
            individual_failure["error_category"]
        ] += 1

    # Collect sample error messages for each category
    # Using defaultdict of lists to store multiple examples per category
    category_examples = defaultdict(list)
    for individual_failure in failures:
        # Limit to 3 examples per category to avoid too much info
        # in result file
        category = individual_failure["error_category"]
        if len(category_examples[category]) < 3:
            category_examples[category].append(
                {
                    "model": individual_failure["model"],
                    "prompt_type": individual_failure["prompt_type"],
                    "scenario": individual_failure["scenario"],
                    "iteration": individual_failure["iteration"],
                    "error_message": individual_failure["error_message"],
                }
            )

    # Sort error categories by count with the most common first
    sorted_categories = sorted(
        category_counts.items(), key=lambda x: x[1], reverse=True
    )

    # Sort models, prompt types, scenarios and iterations for consistent output
    return {
        "total_failures_analysed": len(failures),
        "error_category_summary": [
            {
                "category": category,
                "count": count,
                "percentage": round(count / len(failures) * 100, 1) if failures else 0,
                "description": CATEGORY_DESCRIPTIONS.get(category, ""),
            }
            for category, count in sorted_categories
        ],
        "by_model": {
            model: dict(sorted(categories.items(), key=lambda x: x[1], reverse=True))
            for model, categories in sorted(by_model.items())
        },
        "by_prompt_type": {
            prompt: dict(sorted(categories.items(), key=lambda x: x[1], reverse=True))
            for prompt, categories in sorted(by_prompt.items())
        },
        "by_scenario": {
            scenario: dict(sorted(categories.items(), key=lambda x: x[1], reverse=True))
            for scenario, categories in sorted(by_scenario.items())
        },
        "by_iteration": {
            iteration: dict(
                sorted(categories.items(), key=lambda x: x[1], reverse=True)
            )
            for iteration, categories in sorted(by_iteration.items())
        },
        "category_examples": dict(category_examples),
        "refined_vs_unrefined": build_refined_comparison(failures),
        "all_failures": failures,
    }


def build_refined_comparison(failures: list[dict]) -> dict:
    """
    This function compares error types between initial and refined prompt runs.
    Shows which error categories were reduced or introduced by prompt refinement.
    """

    # Split failures into unrefined and refined based on prompt_type prefix
    unrefined = [f for f in failures if not f["prompt_type"].startswith("refined_")]
    refined = [f for f in failures if f["prompt_type"].startswith("refined_")]

    # Count error categories for each group
    unrefined_counts = defaultdict(int)
    for f in unrefined:
        unrefined_counts[f["error_category"]] += 1

    refined_counts = defaultdict(int)
    for f in refined:
        refined_counts[f["error_category"]] += 1

    # Get all categories across both groups
    all_categories = sorted(
        set(list(unrefined_counts.keys()) + list(refined_counts.keys()))
    )

    # Build comparison showing change per category
    category_comparison = []
    for category in all_categories:
        unrefined_count = unrefined_counts.get(category, 0)
        refined_count = refined_counts.get(category, 0)
        category_comparison.append(
            {
                "category": category,
                "unrefined_count": unrefined_count,
                "refined_count": refined_count,
                "change": refined_count - unrefined_count,
                "description": CATEGORY_DESCRIPTIONS.get(category, ""),
            }
        )

    # Sort by categories that saw greatest reduction
    # I.e. improvement
    category_comparison.sort(key=lambda x: x["change"])

    # Comparison of total failure counts across models
    models = sorted(set(f["model"] for f in failures))
    model_comparison = {}
    for model in models:
        unrefined_total = sum(1 for f in unrefined if f["model"] == model)
        refined_total = sum(1 for f in refined if f["model"] == model)
        model_comparison[model] = {
            "unrefined_failures": unrefined_total,
            "refined_failures": refined_total,
            "change": refined_total - unrefined_total,
        }

    # Return comparison data in dict
    return {
        "total_unrefined_failures": len(unrefined),
        "total_refined_failures": len(refined),
        "category_comparison": category_comparison,
        "model_comparison": model_comparison,
    }


def print_error_summary(analysis: dict) -> None:
    """
    Print a summary of the error analysis to the console.
    """

    # Separator header and footer for easier readability
    print(f"\n{'='*50}")
    print(
        f"Error Analysis — {analysis['total_failures_analysed']} failed runs analysed"
    )
    print(f"{'='*50}")

    print("\nError Categories (with most common first):")
    for entry in analysis["error_category_summary"]:
        # Format to readable values for numeric values
        print(
            f"  {entry['count']:4d} ({entry['percentage']:5.1f}%)  {entry['category']}"
        )
        # Also include description if present
        if entry["description"]:
            print(f"  {entry['description']}")

    print(f"\n{'─'*50}")
    print("Errors by model:")
    # Loop over models and show error category breakdown
    for model, categories in sorted(analysis["by_model"].items()):
        total = sum(categories.values())
        print(f"\n  {model} ({total} failures):")
        for individual_category, count in categories.items():
            print(f"  {count:4d}  {individual_category}")

    print(f"\n{'─'*50}")
    print("Errors by prompt type:")
    # Loop over prompt types and show error category breakdown
    for prompt, categories in sorted(analysis["by_prompt_type"].items()):
        total = sum(categories.values())
        print(f"\n  {prompt} ({total} failures):")
        for individual_category, count in categories.items():
            print(f"  {count:4d}  {individual_category}")

    print(f"\n{'─'*50}")
    print("Errors by scenario:")
    # Loop over scenarios and show error category breakdown
    for scenario, categories in sorted(analysis["by_scenario"].items()):
        total = sum(categories.values())
        print(f"\n  {scenario} ({total} failures):")
        for individual_category, count in categories.items():
            print(f"  {count:4d}  {individual_category}")

    print(f"\n{'─'*50}")
    print("Errors by iteration:")
    # Loop over iterations and show error category breakdown
    for iteration, categories in sorted(analysis["by_iteration"].items()):
        total = sum(categories.values())
        print(f"\n  {iteration} ({total} failures):")
        for individual_category, count in categories.items():
            print(f"  {count:4d}  {individual_category}")

    # Print errors from initial runs against the second runs
    # where prompts had been refined based on initial error analysis
    comparison = analysis.get("refined_vs_unrefined", {})
    if comparison:
        print(f"\n{'-'*50}")
        print("First Pass (unrefined) vs Second Pass (refined) comparison")
        print(f"{'-'*50}")
        print(
            f"Total failures — Initial Run: {comparison['total_unrefined_failures']}, "
            f"Total failures - Second Run: {comparison['total_refined_failures']}"
        )

        print("\nError category changes (negative = improvement):")
        for entry in comparison.get("category_comparison", []):
            # Get change in count of error category between runs
            change = entry["change"]

            # It has improved if fewer failures of that category in second run
            indicator = "improved" if change < 0 else "worse" if change > 0 else "same"
            print(
                f"  {change:+4d}  {entry['category']}"
                f" {entry['unrefined_count']} -> {entry['refined_count']}) [{indicator}]"
            )

        print("\nFailure count change by model:")
        for model, data in sorted(comparison.get("model_comparison", {}).items()):
            # Get change in count of error category between runs
            change = data["change"]

            # It has improved if fewer failures of that category in second run
            indicator = "improved" if change < 0 else "worse" if change > 0 else "same"
            print(
                f"  {model}: {data['unrefined_failures']} -> {data['refined_failures']}"
                f"  ({change:+d}) [{indicator}]"
            )


def main() -> None:
    print("Scanning log files for failed runs")

    # Analyse all log files and classify errors using helper function
    failures = analyse_all_logs()
    print(f"Found {len(failures)} failed runs with log files.")

    # Validation check to ensure there are actual failure files
    if not failures:
        print("No failures to analyse.")
        return

    # Build the error analysis by calling the helper function
    analysis = build_error_analysis(failures)

    # Write the results to the output JSON file
    with open(ERROR_ANALYSIS_PATH, "w") as f:
        json.dump(analysis, f, indent=2)
    print(f"\nError analysis written to {ERROR_ANALYSIS_PATH}")

    # Print results to console
    print_error_summary(analysis)


if __name__ == "__main__":
    main()
