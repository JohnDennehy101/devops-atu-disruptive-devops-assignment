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

# GitHub Models endpoint — OpenAI-compatible, uses GitHub Personal Access Token
# Available as part of GitHub student developer pack
CLIENT = None


def get_client(use_openai: bool = False) -> OpenAI:
    """
    Initialise OpenAI client pointed at GitHub Models API or OpenAI directly.
    """

    # Avoid re-initialiing client on every call, cache in global var
    global CLIENT

    if CLIENT is None:
        if use_openai:
            # Use OpenAI API directly, extract API key from env variable
            token = os.environ.get("OPENAI_API_KEY")
            if not token:
                raise RuntimeError(
                    "OPENAI_API_KEY env var not set. Run: export OPENAI_API_KEY=sk-..."
                )
            CLIENT = OpenAI(api_key=token)
        else:
            # Use GitHub Models API with GITHUB_TOKEN
            token = os.environ.get("GITHUB_TOKEN")
            if not token:
                raise RuntimeError(
                    "GITHUB_TOKEN env var not set. Run: export GITHUB_TOKEN=$(gh auth token)"
                )
            CLIENT = OpenAI(
                base_url="https://models.inference.ai.azure.com",
                api_key=token,
            )

    # Return configured client
    return CLIENT


def call_copilot(prompt: str, model: str = "gpt-4o") -> tuple[str, float, dict]:
    """
    Call GitHub Models API and return (response, duration, usage_metrics).
    """

    # Get configured client for API calls
    client = get_client()

    # Measure inference time per request
    t_start = time.time()

    # Call API with the prompt and hyperparams
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=1024,
    )

    # Measure total duration taken for response from API
    duration = round(time.time() - t_start, 3)

    raw = response.choices[0].message.content or ""
    usage = response.usage

    # Construct metrics dictionary
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
    return raw, duration, metrics


def main():
    # Argument parser in place for optional filtering
    # Dry run option to test what would be run without actually calling.
    parser = argparse.ArgumentParser(
        description="Generate Playwright tests via GitHub Copilot (GPT-4o)"
    )
    parser.add_argument("--filter-scenario", help="Filter by scenario slug")
    parser.add_argument("--filter-prompt", help="Filter by prompt type")
    parser.add_argument(
        "--filter-iteration",
        choices=list(ITERATION_MAP.keys()),
        help="Filter by iteration",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o",
        help="GitHub Models model name (default: gpt-4o)",
    )
    parser.add_argument(
        "--openai",
        action="store_true",
        help="Use OpenAI API directly instead of GitHub Models - requires Open AI API key",
    )
    parser.add_argument(
        "--refined",
        action="store_true",
        help="Only run prompt-engineered prompts (second pass)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be run without calling the API",
    )
    args = parser.parse_args()

    # Initialise API client
    get_client(use_openai=args.openai)

    print("Collecting unique prompts from model_outputs/...", end=" ", flush=True)
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

    print(f"Will generate {len(prompts)} Copilot outputs using {args.model}.\n")

    # Loop over prompt and call API for each
    for i, p in enumerate(prompts, 1):
        label = f"{p['scenario']} / {p['change_type']} / {p['iteration']} / {p['prompt_type']}"
        print(f"[{i}/{len(prompts)}] {label}", end=" ", flush=True)

        # Build output path
        output_directory = (
            MODEL_OUTPUTS_PATH
            / p["scenario_dir"]
            / p["change_type"]
            / p["iteration"]
            / "copilot"
        )

        # Make output directory if it doesn't exist
        output_directory.mkdir(parents=True, exist_ok=True)

        # Determine file prefix based on whether first pass or refined prompt (second run)
        file_prefix = "refined_copilot" if p.get("refined") else "copilot"

        # Skip if a copilot output already exists for this prompt combination
        # Needed as rate limit of 50 requests per day on the API
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

        # Construct file name with model, prompt type, scenario, and timestamp for uniqueness
        filename = f"{file_prefix}_{p['prompt_type']}_{p['scenario']}_{timestamp.replace(':', '_')}.json"

        # If dry run, just print what would be outputted, don't call API
        if args.dry_run:
            print(f"-> {output_directory / filename} (dry run)")
            continue

        # Call GitHub Models API
        raw_response, duration, metrics = call_copilot(p["prompt"], model=args.model)

        # Extract code from raw response
        extracted = extract_typescript(raw_response)

        # Build output record matching existing format
        record = [
            {
                "timestamp": timestamp,
                "model_id": f"github/{args.model}",
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
                    "note": "GitHub Models API (Copilot subscription)",
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

        time.sleep(2)

    print("\nDone.")


if __name__ == "__main__":
    main()
