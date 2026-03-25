import json
from collections import defaultdict

from shared import EVAL_OUTPUTS_DIR_PATH


# Path to the results file outputted by run_ai_model_output_playwright_tests.py
RESULTS_JSONL_PATH = EVAL_OUTPUTS_DIR_PATH / "results.jsonl"

# Path where generated summary JSON will be written
SUMMARY_JSON_PATH = EVAL_OUTPUTS_DIR_PATH / "summary_2.json"

# Constants at top of file for easy ref
BASE_PROMPT_TYPES = ["zero-shot", "few-shot", "instruction", "chain-of-thought"]
REFINED_PROMPT_TYPES = [f"refined_{pt}" for pt in BASE_PROMPT_TYPES]
PROMPT_TYPES = BASE_PROMPT_TYPES + REFINED_PROMPT_TYPES
SCENARIOS = ["diff-only", "diff-and-source-code", "diff-and-source-code-and-tests"]
ITERATIONS = ["first", "second", "third", "fourth"]
CHANGE_TYPES = ["code_change", "code_change_and_test_change"]


def safe_numeric_value(value, default=0):
    """
    Return value if it is a number, otherwise return default (0)
    """
    # Check type, accept if int or float type
    if value is not None and isinstance(value, (int, float)):
        return value

    # Otherwise revert to default of 0
    return default


def load_unique_results() -> list[dict]:
    """
    Noticed duplicated entries in the results file.
    This function removes duplicate entries.
    """

    # Start with empty list
    results = []

    # Load the file
    with open(RESULTS_JSONL_PATH) as f:
        # Loop over each line
        for line in f:
            # Stip whitepace and skip empty lines
            line = line.strip()

            # Only include non-empty lines
            if line:
                results.append(json.loads(line))

    # A set is used to ensure uniqueness
    seen = set()

    # List where unique records will be stored
    unique = []

    # Keep count of duplicates for logging
    duplicates = 0

    # Loop over all results
    for record in results:
        # Key for set uses a number of values to ensure uniqueness of the record
        key = (
            record["model"],
            record["prompt_type"],
            record["scenario"],
            record["iteration"],
            record["change_type"],
        )

        # If already in seen set, duplicate row, increment variable value and skip
        if key in seen:
            duplicates += 1
            continue

        # Otherwise, add key to seen set for future iteraitons
        seen.add(key)

        # Add record to list
        unique.append(record)

    # Print statement for logging.
    print(
        f"Loaded {len(results)} records, removed {duplicates} duplicates, {len(unique)} unique."
    )

    # Write unique results back to the JSONL file
    with open(RESULTS_JSONL_PATH, "w") as f:
        for record in unique:
            f.write(json.dumps(record) + "\n")

    # Finally, return the unique records list
    return unique


def calculate_summary_stats(records: list[dict]) -> dict | None:
    """
    Calculate summary statistics for the provided records list.
    None returned if empty list of records provided.
    """

    # First check to see if records is empty
    total = len(records)
    if total == 0:
        return None

    # Identify total number of passed runs.
    passed = sum(1 for r in records if r["passed"])

    # Calculate average execution time over runs
    average_execuction_time = (
        sum(safe_numeric_value(r.get("execution_time_s")) for r in records) / total
    )

    # Calculate average inference time over runs
    average_inference_time = (
        sum(safe_numeric_value(r.get("inference_time_s")) for r in records) / total
    )

    # Calculate average output token count over runs (note not available for all models)
    average_output_tokens = (
        sum(safe_numeric_value(r.get("output_token_count")) for r in records) / total
    )

    # Tokens per second only available for some models
    tps_records = [r for r in records if r.get("tokens_per_sec") is not None]

    # Calculate average tokens per second if records have the value
    # Otherwise default to None
    average_tokens_per_second = (
        round(sum(r["tokens_per_sec"] for r in tps_records) / len(tps_records), 2)
        if tps_records
        else None
    )

    # Return dictionary with all calculated summary statistics
    return {
        "total_runs": total,
        "passed_runs": passed,
        "failed_runs": total - passed,
        "pass_rate": round(passed / total, 4),
        "avg_execution_time_s": round(average_execuction_time, 2),
        "avg_inference_time_s": round(average_inference_time, 2),
        "avg_output_tokens": round(average_output_tokens, 1),
        "avg_tokens_per_sec": average_tokens_per_second,
        "total_tests_passed": sum(
            safe_numeric_value(r.get("passed_count")) for r in records
        ),
        "total_tests_failed": sum(
            safe_numeric_value(r.get("failed_count")) for r in records
        ),
    }


def build_records_index(records: list[dict]) -> dict:
    """
    This function buildsindex of records grouped by different properties
    for easier lookups when calculating stats.
    """

    # Default dict used to automatically create empty lists for new keys
    record_index = defaultdict(list)

    # Loop over records and add to index
    # under different keys for different analysis
    # such as model, prompt, scenario, iteration, change type
    for r in records:
        record_index[("model", r["model"])].append(r)
        record_index[("prompt", r["prompt_type"])].append(r)
        record_index[("scenario", r["scenario"])].append(r)
        record_index[("iteration", r["iteration"])].append(r)
        record_index[("model_prompt", r["model"], r["prompt_type"])].append(r)
        record_index[("model_scenario", r["model"], r["scenario"])].append(r)
        record_index[("model_iter", r["model"], r["iteration"])].append(r)
        record_index[("model_change", r["model"], r["change_type"])].append(r)
        record_index[
            (
                "detail",
                r["model"],
                r["prompt_type"],
                r["scenario"],
                r["iteration"],
                r["change_type"],
            )
        ].append(r)

    # Return the completed index
    return record_index


def generate_summary(records: list[dict]) -> dict:
    """
    This function generate a full summary from the records.
    """

    # Sort models and use a set to ensure uniqueness
    models = sorted(set(r["model"] for r in records))

    # Call utility function to build the records index for easier lookups
    full_records_index = build_records_index(records)

    # This is simplified as the reports index makes it easy
    # to lookup records for each model for different scenarios.
    summary = {
        "metadata": {
            "total_unique_runs": len(records),
            "models": models,
            "prompt_types": PROMPT_TYPES,
            "scenarios": SCENARIOS,
            "iterations": ITERATIONS,
            "change_types": CHANGE_TYPES,
        },
        "overall_by_model": {
            model: calculate_summary_stats(full_records_index[("model", model)])
            for model in models
        },
        "by_prompt_type": {
            prompt_type: calculate_summary_stats(
                full_records_index[("prompt", prompt_type)]
            )
            for prompt_type in PROMPT_TYPES
        },
        "by_scenario": {
            scenario: calculate_summary_stats(
                full_records_index[("scenario", scenario)]
            )
            for scenario in SCENARIOS
        },
        "by_iteration": {
            iteration: calculate_summary_stats(
                full_records_index[("iteration", iteration)]
            )
            for iteration in ITERATIONS
        },
        "by_model_and_prompt_type": {},
        "by_model_and_scenario": {},
        "by_model_and_iteration": {},
        "by_model_and_change_type": {},
        "detailed_breakdown": [],
    }

    # Build stats for each model by looping over each
    # model and calculating stats for each based on prompt types, scenarios, actual change, iteration
    for model in models:
        # Calculate stats for each model by prompt type
        summary["by_model_and_prompt_type"][model] = {
            prompt_type: summary_stats
            for prompt_type in PROMPT_TYPES
            if (
                summary_stats := calculate_summary_stats(
                    full_records_index[("model_prompt", model, prompt_type)]
                )
            )
        }

        # Calculate stats for each model by scenario (diff-only, diff-and-code, diff-and-code-and-tests)
        summary["by_model_and_scenario"][model] = {
            scenario: summary_stats
            for scenario in SCENARIOS
            if (
                summary_stats := calculate_summary_stats(
                    full_records_index[("model_scenario", model, scenario)]
                )
            )
        }

        # Calculate stats for each model by iteration (first change, second change, third change, fourth change)
        summary["by_model_and_iteration"][model] = {
            iteration: summary_stats
            for iteration in ITERATIONS
            if (
                summary_stats := calculate_summary_stats(
                    full_records_index[("model_iter", model, iteration)]
                )
            )
        }

        # Calculate stats for each model by change type (code change only vs code change and test changes)
        summary["by_model_and_change_type"][model] = {
            change_type: summary_stats
            for change_type in CHANGE_TYPES
            if (
                summary_stats := calculate_summary_stats(
                    full_records_index[("model_change", model, change_type)]
                )
            )
        }

    # Build original prompts vs refined prompts (after early analysis of errors)
    summary["refined_vs_unrefined"] = {}
    for model in models:
        model_records = full_records_index[("model", model)]

        # Extract 'refined' vs 'unrefined' prompts
        unrefined = [
            r for r in model_records if not r["prompt_type"].startswith("refined_")
        ]
        refined = [r for r in model_records if r["prompt_type"].startswith("refined_")]

        # Call helper function to generate the stats
        unrefined_stats = calculate_summary_stats(unrefined)
        refined_stats = calculate_summary_stats(refined)

        # Include in summary
        if unrefined_stats or refined_stats:
            summary["refined_vs_unrefined"][model] = {
                "unrefined": unrefined_stats,
                "refined": refined_stats,
            }

    # Nested loop to build a detailed calculation of each individual record for each model
    # To identify performance and trends
    for model in models:
        for prompt_type in PROMPT_TYPES:
            for scenario in SCENARIOS:
                for iteration in ITERATIONS:
                    for change_type in CHANGE_TYPES:
                        # Extract records for the current iteration of the loop
                        record_index = full_records_index[
                            (
                                "detail",
                                model,
                                prompt_type,
                                scenario,
                                iteration,
                                change_type,
                            )
                        ]

                        # Check to ensure the records exist
                        if record_index:
                            # Should be only one so extracting first index
                            record = record_index[0]

                            # Adding detailed breakdown entry to summary for current iteration values
                            summary["detailed_breakdown"].append(
                                {
                                    "model": model,
                                    "prompt_type": prompt_type,
                                    "scenario": scenario,
                                    "iteration": iteration,
                                    "change_type": change_type,
                                    "passed": record["passed"],
                                    "passed_count": safe_numeric_value(
                                        record.get("passed_count")
                                    ),
                                    "failed_count": safe_numeric_value(
                                        record.get("failed_count")
                                    ),
                                    "execution_time_s": safe_numeric_value(
                                        record.get("execution_time_s")
                                    ),
                                    "inference_time_s": safe_numeric_value(
                                        record.get("inference_time_s")
                                    ),
                                    "output_token_count": safe_numeric_value(
                                        record.get("output_token_count")
                                    ),
                                }
                            )

    # Finally return the completed summary
    return summary


def format_stats_line(label: str, stats: dict, label_width: int = 45) -> str:
    """
    This function formats line of text for easier readability.
    Note label width can be adjusted to ensure alignment of values.
    """

    # Format line with label (using passed label_width), passed runs to 3 digits,
    # total runs to 3 digits, pass rate one decimal place.
    line = (
        f"  {label:{label_width}s} {stats['passed_runs']:3d}/{stats['total_runs']:3d} "
        f"({stats['pass_rate'] * 100:5.1f}%)"
    )

    # Include average inference time if available in the record
    if stats.get("avg_inference_time_s") is not None:
        line += f"  avg_inference={stats['avg_inference_time_s']:6.1f}s"

    # Finally return the formatted line
    return line


def print_generated_summary(summary: dict) -> None:
    """
    Print a quick overview of results to the console for visualisation
    """

    print("\nOVERALL PASS RATE BY MODEL:")
    # Loop over models, sort by pass rate and print out summary stats for each
    for model in sorted(
        summary["overall_by_model"],
        key=lambda x: summary["overall_by_model"][x]["pass_rate"],
        reverse=True,
    ):
        print(format_stats_line(model, summary["overall_by_model"][model]))

    print("\nREFINED vs UNREFINED BY MODEL:")
    # Loop over models and show initial prompt performance vs refined prompts comparison
    for model in sorted(summary.get("refined_vs_unrefined", {})):
        # Extract summary stats
        comparison = summary["refined_vs_unrefined"][model]

        # Extract initial prompt stats and refined prompt stats
        unrefined = comparison.get("unrefined")
        refined = comparison.get("refined")

        if unrefined and refined:
            # Calculate difference in pass rate between first and second runs of prompts
            diff = (refined["pass_rate"] - unrefined["pass_rate"]) * 100
            print(f"{model}:")
            print(
                f"Initial: {unrefined['passed_runs']:3d}/{unrefined['total_runs']:3d} ({unrefined['pass_rate']*100:5.1f}%)"
            )
            print(
                f"Refined: {refined['passed_runs']:3d}/{refined['total_runs']:3d} ({refined['pass_rate']*100:5.1f}%)  ({diff:+.1f}%)"
            )
        elif unrefined:
            print(
                f"{model}: Initial only — {unrefined['passed_runs']}/{unrefined['total_runs']} ({unrefined['pass_rate']*100:.1f}%)"
            )
        elif refined:
            print(
                f"{model}: refined only — {refined['passed_runs']}/{refined['total_runs']} ({refined['pass_rate']*100:.1f}%)"
            )

    print("\nPASS RATE BY PROMPT TYPE:")
    # Loop over prompt types and print out summary stats for each
    for prompt_type in PROMPT_TYPES:
        prompt_type_stat = summary["by_prompt_type"].get(prompt_type)
        if prompt_type_stat:
            print(format_stats_line(prompt_type, prompt_type_stat, label_width=25))

    print("\nPASS RATE BY SCENARIO:")
    # Loop over scenarios and print out summary stats for each
    for scenario in SCENARIOS:
        scenario_stat = summary["by_scenario"].get(scenario)
        if scenario_stat:
            print(format_stats_line(scenario, scenario_stat, label_width=35))

    print("\nPASS RATE BY ITERATION:")
    # Loop over iterations and print out summary stats for each (to see performance across changes)
    for iteration in ITERATIONS:
        iteration_stat = summary["by_iteration"].get(iteration)
        if iteration_stat:
            print(format_stats_line(iteration, iteration_stat, label_width=10))


def main() -> None:
    print("Loading results")

    # Load results from the file, ensuring no duplicates
    records = load_unique_results()

    print("Generating summary")

    # Generate summary from the records
    summary = generate_summary(records)

    # Write summary to the output JSON file
    with open(SUMMARY_JSON_PATH, "w") as f:
        json.dump(summary, f, indent=2)

    # Also output to console for users
    print(f"Summary written to {SUMMARY_JSON_PATH}")
    print(f"Detailed breakdown entries: {len(summary['detailed_breakdown'])}")

    # Detailed breakdown also outputted
    print_generated_summary(summary)


if __name__ == "__main__":
    main()
