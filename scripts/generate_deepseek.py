import argparse
import json
import os
import re
import time
from datetime import datetime

from openai import OpenAI

from shared import (
    ITERATION_MAP,
    MODEL_OUTPUTS_PATH,
    collect_unique_prompts,
    extract_typescript,
)

# Open AI package works with Deepseek API as well
CLIENT = None


def get_client() -> OpenAI:
    """
    Initialise OpenAI client pointed at DeepSeek API.
    """

    # Avoid re-initialising client on every call, cache in global var
    global CLIENT

    if CLIENT is None:
        # Extract API key from env variable
        token = os.environ.get("DEEPSEEK_API_KEY")

        # If not found, inform user as it is required
        if not token:
            raise RuntimeError(
                "DEEPSEEK_API_KEY env var not set. Run: export DEEPSEEK_API_KEY=sk-..."
            )

        # Initialise OpenAI client pointed at DeepSeek API
        CLIENT = OpenAI(
            base_url="https://api.deepseek.com",
            api_key=token,
        )

    # Return configured client
    return CLIENT


def call_deepseek(prompt: str, model: str = "deepseek-chat") -> tuple[str, float, dict]:
    """
    Call DeepSeek API and return (response, duration, metrics).
    """

    # Get configured client for API calls
    client = get_client()

    # Measure inference time per request
    time_start = time.time()

    # Call API with the prompt and hyperparameters
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=1024,
    )

    # Measure total duration taken for response from API
    duration = round(time.time() - time_start, 3)

    # Extract raw response and usage metrics from the API response
    raw_response = response.choices[0].message.content or ""
    usage = response.usage

    # Build dict with metrics info
    metrics = {
        "inference_time_s": duration,
        "input_token_count": usage.prompt_tokens if usage else 0,
        "output_token_count": usage.completion_tokens if usage else 0,
        "total_token_count": usage.total_tokens if usage else 0,
    }

    # Calculate tokens per second if info is available
    if usage and duration > 0:
        metrics["tokens_per_sec"] = round((usage.completion_tokens or 0) / duration, 2)

    # Return raw response, duration, metrics
    return raw_response, duration, metrics


def main():
    # Argument parser in place for optional filtering (to filter runs)
    parser = argparse.ArgumentParser(
        description="Generate Playwright tests via DeepSeek API"
    )
    parser.add_argument("--filter-scenario", help="Filter by scenario type")
    parser.add_argument("--filter-prompt", help="Filter by prompt type")
    parser.add_argument(
        "--filter-iteration",
        choices=list(ITERATION_MAP.keys()),
        help="Filter by iteration",
    )
    parser.add_argument(
        "--model",
        default="deepseek-chat",
        help="DeepSeek model name",
    )
    parser.add_argument(
        "--refined",
        action="store_true",
        help="Only run prompt-engineered prompts - second pass",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be run without calling the API - useful for debugging",
    )
    args = parser.parse_args()

    # Initialise API client early so auth errors are raised before anything else
    get_client()

    print("Collecting unique prompts from model_outputs/...", end=" ", flush=True)

    # Call helper function to get the prompts in use
    prompts = collect_unique_prompts()
    print(f"{len(prompts)} found.")

    # Apply filters
    if args.filter_scenario:
        prompts = [p for p in prompts if args.filter_scenario in p["scenario"]]
    if args.filter_prompt:
        prompts = [p for p in prompts if p["prompt_type"] == args.filter_prompt]
    if args.filter_iteration:
        prompts = [p for p in prompts if p["iteration"] == args.filter_iteration]
    if args.refined:
        prompts = [p for p in prompts if p.get("refined")]
    else:
        prompts = [p for p in prompts if not p.get("refined")]

    if not prompts:
        print("No prompts match the given filters.")
        return

    print(f"Will generate {len(prompts)} DeepSeek outputs using {args.model}.\n")

    # Loop over prompts and call API for each
    for i, p in enumerate(prompts, 1):
        label = f"{p['scenario']} / {p['change_type']} / {p['iteration']} / {p['prompt_type']}"
        print(f"[{i}/{len(prompts)}] {label}", end=" ", flush=True)

        # Build output path under deepseek_api model directory
        output_directory = (
            MODEL_OUTPUTS_PATH
            / p["scenario_dir"]
            / p["change_type"]
            / p["iteration"]
            / "deepseek_api"
        )

        # Ensure the target output directory actually exists
        output_directory.mkdir(parents=True, exist_ok=True)

        # Determine file prefix based on whether first pass or refined prompt
        file_prefix = "refined_deepseek-api" if p.get("refined") else "deepseek-api"

        # Skip if output already exists
        existing = list(
            output_directory.glob(
                f"{file_prefix}_{p['prompt_type']}_{p['scenario']}_*.json"
            )
        )
        if existing:
            print("(already exists, skipping)")
            continue

        # Timestamp for unique file name
        timestamp = datetime.now().isoformat()

        # Construct file name
        filename = f"{file_prefix}_{p['prompt_type']}_{p['scenario']}_{timestamp.replace(':', '_')}.json"

        # If dry run, just print the output path, don't call API
        if args.dry_run:
            print(f"-> {output_directory / filename} (dry run)")
            continue

        # Call DeepSeek API
        raw_response, duration, metrics = call_deepseek(p["prompt"], model=args.model)

        # Extract code from raw response using the helper function
        extracted = extract_typescript(raw_response)

        # Build record matching existing format
        record = [
            {
                "timestamp": timestamp,
                "model_id": f"deepseek-api/{args.model}",
                "prompt_type": p["prompt_type"],
                "scenario": p["scenario"],
                "metrics": metrics,
                "content": {
                    "prompt": p["prompt"],
                    "raw_response": raw_response,
                    "extracted_code": extracted,
                },
                "hyperparameters": {
                    "max_new_tokens": 1024,
                    "do_sample": False,
                    "temperature": 0,
                    "note": "DeepSeek API (deepseek-chat = DeepSeek-V3)",
                },
            }
        ]

        # Construct output path and save contents to a JSON file
        # at that path
        output_path = output_directory / filename
        with open(output_path, "w") as f:
            json.dump(record, f, indent=4)

        # Check to see if extraction generated a test
        status = "ok" if re.search(r"\btest\s*\(", extracted) else "no test() found"
        print(f"({duration}s) [{status}]")

        # Small delay to avoid rate limits on the API
        time.sleep(2)

    print("\nDone.")


if __name__ == "__main__":
    main()
