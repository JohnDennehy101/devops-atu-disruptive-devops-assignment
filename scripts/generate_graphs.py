import json
from collections import defaultdict
from pathlib import Path
from pyexpat import model

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import Patch
import numpy as np

# Paths used within the script defined as constants for easy modificiations
REPO_ROOT = Path(__file__).parent.parent
RESULTS_PATH = REPO_ROOT / "eval_outputs" / "results.jsonl"
OUTPUT_DIRECTORY = REPO_ROOT / "figures"
OUTPUT_DIRECTORY.mkdir(exist_ok=True)

# IEEE figure widths: single column (3.5 inches) and double column (7 inches)
SINGLE_COLUMN_WIDTH = 3.5
DOUBLE_COLUMN_WIDTH = 7

# Figure heights used in graphs
SMALL_HEIGHT = 2.5
MEDIUM_HEIGHT = 3
LARGE_HEIGHT = 3.5

# Setting constants for y axis limits for pass rate charts
# Most use full pass rate range (0-100%) but some focused analyses
# use a more limited range to better show differences between models (e.g. 0-75%)
# Adding 5 buffer to each to ensure bars don't touch the top of the graph
Y_LIMIT_FULL_RANGE = 105
Y_LIMIT_FOCUSED_RANGE = 75

# IEEE style used across all graphs: Times New Roman, 8pt base, no plot titles (as will set these via captions in the report)
# DPI also set to 300 for print quality
plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "font.size": 8,
        "axes.titlesize": 9,
        "axes.labelsize": 8,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 7,
        "figure.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.05,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)

# Colour palette used across graphs
COLOURS = {
    "open_source": "#7A9CC6",
    "closed_source": "#8ABF8A",
    "tool_using": "#C4726C",
    "initial": "#BFBFBF",
    "refined": "#7A9CC6",
    "scenario1": "#A8B8CC",
    "scenario2": "#9DC4A0",
    "scenario3": "#CDA5A1",
}

# Split models into categories for grouped analysis
OPEN_SOURCE_MODELS = [
    "DeepSeek-Coder-V2-Lite-Instruct",
    "Mistral-Nemo-Instruct-2407",
    "Mistral-Small-24B-Instruct-2501",
    "Qwen2.5-Coder-14B-Instruct",
    "Qwen2.5-Coder-32B-Instruct",
    "gemma-3-12b-it",
    "gemma-3-27b-it",
]

CLOSED_SOURCE_MODELS = [
    "claude-sonnet-4-20250514",
    "deepseek-chat",
    "gpt-4o",
    "gpt-5.4",
]

TOOL_USING_MODELS = [
    "mcp-claude-sonnet-4-20250514",
    "playwright-agents-claude-sonnet-4-20250514",
]

# Open-source model parameter counts in billions for size scaling analysis
MODEL_PARAMETER_COUNTS = {
    "gemma-3-12b-it": 12,
    "Qwen2.5-Coder-14B-Instruct": 14,
    "Mistral-Nemo-Instruct-2407": 12,
    "DeepSeek-Coder-V2-Lite-Instruct": 16,
    "Mistral-Small-24B-Instruct-2501": 24,
    "gemma-3-27b-it": 27,
    "Qwen2.5-Coder-32B-Instruct": 32,
}

# Scenario definitions and display labels
SCENARIOS = ["diff-only", "diff-and-source-code", "diff-and-source-code-and-tests"]
SCENARIO_LABELS = ["Diff Only", "Diff + Source\nCode", "Diff + Source\n+ Tests"]
SCENARIO_COLOURS = [COLOURS["scenario1"], COLOURS["scenario2"], COLOURS["scenario3"]]

# Prompt type definitions
INITIAL_PROMPT_TYPES = ["zero-shot", "few-shot", "instruction", "chain-of-thought"]
REFINED_PROMPT_TYPES = [
    "refined_zero-shot",
    "refined_few-shot",
    "refined_instruction",
    "refined_chain-of-thought",
]
ALL_PROMPT_TYPES = INITIAL_PROMPT_TYPES + REFINED_PROMPT_TYPES
PROMPT_TYPE_LABELS = [
    "Zero-Shot",
    "Few-Shot",
    "Instruction",
    "Chain-of-\nThought",
    "Refined\nZero-Shot",
    "Refined\nFew-Shot",
    "Refined\nInstruction",
    "Refined\nChain-of-\nThought",
]

# Short display names for chart labels
MODEL_DISPLAY_NAMES = {
    "DeepSeek-Coder-V2-Lite-Instruct": "DeepSeek\nCoder-Lite",
    "Mistral-Nemo-Instruct-2407": "Mistral\nNemo",
    "Mistral-Small-24B-Instruct-2501": "Mistral\nSmall-24B",
    "Qwen2.5-Coder-14B-Instruct": "Qwen2.5\nCoder-14B",
    "Qwen2.5-Coder-32B-Instruct": "Qwen2.5\nCoder-32B",
    "claude-sonnet-4-20250514": "Claude\nSonnet 4",
    "deepseek-chat": "DeepSeek\nChat",
    "gemma-3-12b-it": "Gemma-3\n12B",
    "gemma-3-27b-it": "Gemma-3\n27B",
    "gpt-4o": "GPT-4o",
    "gpt-5.4": "GPT-5.4",
    "mcp-claude-sonnet-4-20250514": "Claude\n+ MCP",
    "playwright-agents-claude-sonnet-4-20250514": "Claude\n+ Agents",
}

# Manual label offsets for scatter plot
# to avoid overlapping text labels
SCATTER_LABEL_OFFSETS = {
    "claude-sonnet-4-20250514": (-15, -14),
    "deepseek-chat": (8, 6),
    "gpt-4o": (-15, 12),
    "gpt-5.4": (-10, 6),
    "Qwen2.5-Coder-32B-Instruct": (8, 0),
    "Mistral-Small-24B-Instruct-2501": (8, -10),
    "Qwen2.5-Coder-14B-Instruct": (8, -10),
    "gemma-3-27b-it": (-10, -12),
    "Mistral-Nemo-Instruct-2407": (-20, 8),
    "DeepSeek-Coder-V2-Lite-Instruct": (8, 6),
    "gemma-3-12b-it": (8, -10),
}


def load_results():
    """
    Load all results from the JSONL file.
    """

    # Start with empty list
    results = []

    # Load in results file and append each line to results list
    with open(RESULTS_PATH) as f:
        for line in f:
            results.append(json.loads(line))

    # Finally return the list of results
    return results


def calculate_pass_rates(results, group_by="model", filter_fn=None):
    """
    Calculate pass rates grouped by a specified field from the results.
    Groups by model if default value used but can group by any field.
    Optionally filter results using the filter_fn parameter
    """

    # Use defaultdict to simplify counting of passed and total runs per group
    stats = defaultdict(lambda: {"passed": 0, "total": 0})

    # Loop over passed results
    for individual_result in results:
        # If filter function provided and returns false for this result, skip it
        if filter_fn and not filter_fn(individual_result):
            continue

        # Get value of field to group by
        key = individual_result[group_by]

        # Update total count for this group
        stats[key]["total"] += 1

        # If this result is a pass, update passed count for this group
        if individual_result.get("passed"):
            stats[key]["passed"] += 1

    # Return the stats dict with counts of passed and total runs per group
    return stats


def calculate_category_pass_rate(model_stats, model_list):
    """
    Calculate total pass rate for a group of models (e.g. all open-source models)
    Uses per-model stats from calculate_model_pass_rates and a list of model names.
    """
    # Calculate total passed across all runs in the provided list
    total_passed = sum(
        model_stats[individual_model]["passed"] for individual_model in model_list
    )

    # Calculate total number of tests across all runs in the provided list
    total_runs = sum(
        model_stats[individual_model]["total"] for individual_model in model_list
    )

    # Calculate and return pass rate as percentage
    return total_passed / total_runs * 100 if total_runs else 0


def get_model_color(model):
    """
    Return colour hex based on passed model name
    """

    # If model name in defined tool using models list,
    # return hex for tool using models
    if model in TOOL_USING_MODELS:
        return COLOURS["tool_using"]

    # If model name in defined closed source models list
    # return hex for closed source models
    elif model in CLOSED_SOURCE_MODELS:
        return COLOURS["closed_source"]

    # Default to open source colour for all other models
    return COLOURS["open_source"]


def get_model_order(results):
    """
    Order models by overall pass rate
    To ensure consistency across graphs
    """

    # Call helper function to get model pass rates
    model_stats = calculate_pass_rates(results)

    # Then sort by pass rate (ascending order)
    return sorted(
        model_stats,
        key=lambda model: model_stats[model]["passed"]
        / max(model_stats[model]["total"], 1),
    )


def add_bar_labels(ax, bars, fmt="{:.0f}", fontsize=6, offset=1, fontweight="normal"):
    """
    Add value labels above each bar in a bar chart.
    Skips bars with zero height.
    """

    # Loop over provided bars
    for bar in bars:
        # Get the bar height
        height = bar.get_height()

        # If greater than zero, add text label above bar with provided format
        if height > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + offset,
                fmt.format(height),
                ha="center",
                va="bottom",
                fontsize=fontsize,
                fontweight=fontweight,
            )


def save_figure(fig, name):
    """
    Save figure as PNG (300 DPI for print quality) and to meet IEEE paper style
    guidelines.
    """

    # Save figure to output directory with specified name
    fig.savefig(OUTPUT_DIRECTORY / f"{name}.png")

    # Close it to release memory
    plt.close(fig)

    # Print for debugging
    print(f"{name}")


def generate_overall_pass_rates_by_model_graph(results, model_order):
    """
    This function generates a graph showing the overall pass rate by model
    """

    # Use helper function to get stats per model
    stats = calculate_pass_rates(results)

    # Use the provided model order to ensure consistent ordering across graphs
    models = model_order

    # Calculate pass rate for each model
    pass_rates = [
        stats[individual_model]["passed"] / stats[individual_model]["total"] * 100
        for individual_model in models
    ]

    # Get the colours for each model based on configuration (using helper function)
    bar_colours = [get_model_color(individual_model) for individual_model in models]

    # Get display labels for each model (using defined mapping to shorten names)
    labels = [
        MODEL_DISPLAY_NAMES.get(individual_model, individual_model)
        for individual_model in models
    ]

    # Remove new lines from labels to ensure single line display
    single_line_labels = [l.replace("\n", " ") for l in labels]

    # Use matplotlib to create bar chart
    figure, axes = plt.subplots(figsize=(DOUBLE_COLUMN_WIDTH, MEDIUM_HEIGHT))

    # Create bars (number of models) with heights based on pass rates and colours based on model category
    bars = axes.bar(
        range(len(models)),
        pass_rates,
        color=bar_colours,
        edgecolor="black",
        linewidth=0.5,
    )

    add_bar_labels(axes, bars, fmt="{:.1f}")

    # Should have one per model so can use this for ticks
    axes.set_xticks(range(len(models)))

    # Set the x axis labels to the single line model names
    axes.set_xticklabels(single_line_labels, rotation=35, ha="right", fontsize=6)

    # Set y axis label and limts
    axes.set_ylabel("Pass Rate (%)")
    axes.set_ylim(0, Y_LIMIT_FULL_RANGE)

    # Format the y axis to include percentage signs
    axes.yaxis.set_major_formatter(mticker.PercentFormatter())

    # Crate the legend with custom values for each model category
    # Open-source, closed-source and tool-using (MCP/Agents)
    legend_elements = [
        Patch(
            facecolor=COLOURS["open_source"],
            edgecolor="black",
            linewidth=0.5,
            label="Open-Source",
        ),
        Patch(
            facecolor=COLOURS["closed_source"],
            edgecolor="black",
            linewidth=0.5,
            label="Closed-Source",
        ),
        Patch(
            facecolor=COLOURS["tool_using"],
            edgecolor="black",
            linewidth=0.5,
            label="Tool-Using (MCP/Agents)",
        ),
    ]

    # Set the legend on the graph
    axes.legend(handles=legend_elements, loc="upper left", framealpha=0.9)

    # Call helper function to actually save the generated figure to disk
    save_figure(figure, "fig1_overall_pass_rates")


def generate_approach_comparison_graph(results):
    """
    Generate graph for showing overall pass rates by model category
    As open-source, closed-source and tool-using models used in the study
    """

    # Define categories dict with tuple of model list per catgory and colour
    # per category
    categories = {
        "Open-Source": (OPEN_SOURCE_MODELS, COLOURS["open_source"]),
        "Closed-Source": (CLOSED_SOURCE_MODELS, COLOURS["closed_source"]),
        "Tool-Using\n(MCP/Agents)": (TOOL_USING_MODELS, COLOURS["tool_using"]),
    }

    # Use helper function to get stats per model from results
    stats = calculate_pass_rates(results)

    # Define lists to hold labels, pass rates, colours for display
    category_labels = []
    category_rates = []
    category_colours = []

    # Loop over the categories defined above to generate
    # aggregate pass rate for each category and construct lists for display
    # on the graph
    for category_name, (model_list, colour) in categories.items():
        category_rates.append(calculate_category_pass_rate(stats, model_list))
        category_labels.append(category_name)
        category_colours.append(colour)

    # Use matplotlib to create bar chart with the category labels, pass rates and colours
    figure, axes = plt.subplots(figsize=(SINGLE_COLUMN_WIDTH, SMALL_HEIGHT))

    # Create bars for each category with heights based on pass rates and colours based on category
    bars = axes.bar(
        range(len(category_labels)),
        category_rates,
        color=category_colours,
        edgecolor="black",
        linewidth=0.5,
        width=0.6,
    )

    add_bar_labels(axes, bars, fmt="{:.1f}%", fontsize=7, offset=1.5, fontweight="bold")

    # Set x ticks and labels to length of category labels
    axes.set_xticks(range(len(category_labels)))
    axes.set_xticklabels(category_labels)

    # Set y axis label and limits
    axes.set_ylabel("Pass Rate (%)")
    axes.set_ylim(0, Y_LIMIT_FULL_RANGE)

    # Call helper function to save the generated figure to disk
    save_figure(figure, "fig2_approach_comparison")


def generate_prompt_engineering_impact_graph(results, model_order):
    """
    Initial vs refined prompt pass rates per model.
    This graph shows the impact of prompt engineering by comparing pass rates for initial
    prompt runs vs refined prompt runs for each model.
    """

    # Models that use tools (MCP/Agents) don't have prompt types, so filtering out
    # to ensure clean analysis of prompt engineering impact on models that did
    # use prompts
    not_tool = lambda record: record["model"] not in TOOL_USING_MODELS

    # Calculate stats separately for initial and refined prompts using helper function with filter
    initial_stats = calculate_pass_rates(
        results,
        filter_fn=lambda record: not_tool(record)
        and not record["prompt_type"].startswith("refined_"),
    )
    refined_stats = calculate_pass_rates(
        results,
        filter_fn=lambda record: not_tool(record)
        and record["prompt_type"].startswith("refined_"),
    )

    # Only include models that have both initial and refined runs for a fair comparison
    models = [
        individual_model
        for individual_model in model_order
        if initial_stats[individual_model]["total"] > 0
        and refined_stats[individual_model]["total"] > 0
    ]

    # Get pass rates for initial prompts for each model
    initial_rates = [
        calculate_category_pass_rate(initial_stats, [individual_model])
        for individual_model in models
    ]

    # Get pass rates for refined prompts for each model
    refined_rates = [
        calculate_category_pass_rate(refined_stats, [individual_model])
        for individual_model in models
    ]

    # Build labels and colours for display based on model category and defined display colours
    labels = [
        MODEL_DISPLAY_NAMES.get(individual_model, individual_model)
        for individual_model in models
    ]

    # Use numpy arange method to get x positions for each model and define bar width
    x = np.arange(len(models))
    width = 0.35

    # Use matplotlib to create grouped bar chart comparing initial vs refined prompt pass rates for each model
    figure, axes = plt.subplots(figsize=(DOUBLE_COLUMN_WIDTH, MEDIUM_HEIGHT))

    # First set of bars for initial prompt pass rates, positioned to left of centre
    bars1 = axes.bar(
        x - width / 2,
        initial_rates,
        width,
        label="Initial Prompts",
        color=COLOURS["initial"],
        edgecolor="black",
        linewidth=0.5,
    )

    # Second set of bars for refined prompt pass rates, positioned to right of centre
    bars2 = axes.bar(
        x + width / 2,
        refined_rates,
        width,
        label="Refined Prompts",
        color=COLOURS["refined"],
        edgecolor="black",
        linewidth=0.5,
    )

    # Call helper function to add value labels above each bar for both initial and refined bars
    add_bar_labels(axes, bars1)
    add_bar_labels(axes, bars2)

    # Set x tickets and labels to model names
    # rotation and alignment used for better readability
    axes.set_xticks(x)
    axes.set_xticklabels(labels, rotation=0, ha="center")
    axes.set_ylabel("Pass Rate (%)")
    axes.set_ylim(0, Y_LIMIT_FULL_RANGE)
    axes.legend(loc="upper left", framealpha=0.9)

    # Call helper function to save the generated figure to disk
    save_figure(figure, "fig3_prompt_engineering")


def generate_scenario_impact_graph(results):
    """
    Graph to show pass rates by scenario
    Three scenarios used in this project:
    diff-only sent to model as context
    diff and source code sent to model as context
    diff and source code and tests sent to model as context
    """

    # Call helper function to calculate pass rates grouped by scenario, filtering out tool-using models as they don't have scenarios
    # As tool-using models use the full context of the application (determining themselves what is relevant)
    stats = calculate_pass_rates(
        results,
        group_by="scenario",
        filter_fn=lambda r: r["model"] not in TOOL_USING_MODELS,
    )

    # Get pass rates for each scenario using helper function
    rates = [calculate_category_pass_rate(stats, [s]) for s in SCENARIOS]

    # Use matplotlib to create bar chart comparing pass rates across the three scenarios with defined colours
    figure, axes = plt.subplots(figsize=(SINGLE_COLUMN_WIDTH, SMALL_HEIGHT))

    # Define bars with heights based on pass rates and colours based on defined scenario colours
    bars = axes.bar(
        range(len(SCENARIOS)),
        rates,
        color=SCENARIO_COLOURS,
        edgecolor="black",
        linewidth=0.5,
        width=0.6,
    )

    # Call helper function to add value labels above each bar with percentage format and bold font weight
    add_bar_labels(axes, bars, fmt="{:.1f}%", fontsize=7, fontweight="bold")

    # Set ticks and labels for x axis based on defined scenario labelsq
    axes.set_xticks(range(len(SCENARIOS)))
    axes.set_xticklabels(SCENARIO_LABELS)

    # Set y axis label and limits
    axes.set_ylabel("Pass Rate (%)")
    axes.set_ylim(0, Y_LIMIT_FOCUSED_RANGE)

    # Call helper function to save the generated figure to disk
    save_figure(figure, "fig4_scenario_impact")


def generate_prompt_type_comparison_graph(results):
    """
    Generates a graph to show pass rate by prompt type with
    initial vs refined prompt types grouped together for comparison.
    """

    # Use helper function to calculate pass rates grouped by prompt type,
    # filtering out tool-using models as they don't have prompt types
    stats = calculate_pass_rates(
        results,
        group_by="prompt_type",
        filter_fn=lambda r: r["model"] not in TOOL_USING_MODELS,
    )

    # Initialise empty list that will hold pass rates and colours for each prompt types
    rates = []
    bar_colors = []

    # Loop over each prompt
    for individual_prompt in ALL_PROMPT_TYPES:
        # Append the calculate pass rate
        rates.append(calculate_category_pass_rate(stats, [individual_prompt]))

        # Determine if initial or refined prompt type to set bar colour according to type
        is_refined = individual_prompt in REFINED_PROMPT_TYPES
        bar_colors.append(COLOURS["refined"] if is_refined else COLOURS["initial"])

    # Use matplotlib to create bar chart comparing pass rates across prompt types for initial vs refined
    figure, axes = plt.subplots(figsize=(DOUBLE_COLUMN_WIDTH, SMALL_HEIGHT))

    # Define bars with heights based on pass rates and colours based on whether initial or refined prompt type
    bars = axes.bar(
        range(len(ALL_PROMPT_TYPES)),
        rates,
        color=bar_colors,
        edgecolor="black",
        linewidth=0.5,
    )

    # Call helper function to add value labels above each bar with percentage format
    add_bar_labels(axes, bars, fmt="{:.1f}")

    # Set ticks and labels for x axis based on defined prompt type labels
    axes.set_xticks(range(len(ALL_PROMPT_TYPES)))
    axes.set_xticklabels(PROMPT_TYPE_LABELS, rotation=0, ha="center")

    # Set y axis label and limits
    axes.set_ylabel("Pass Rate (%)")
    axes.set_ylim(0, Y_LIMIT_FOCUSED_RANGE)

    # Add vertical line to divide initial vs refined prompt types for clearer comparison
    axes.axvline(
        x=len(INITIAL_PROMPT_TYPES) - 0.5, color="grey", linestyle="--", linewidth=0.8
    )

    # Construct legend manually
    legend_elements = [
        Patch(
            facecolor=COLOURS["initial"],
            edgecolor="black",
            linewidth=0.5,
            label="Initial Prompts",
        ),
        Patch(
            facecolor=COLOURS["refined"],
            edgecolor="black",
            linewidth=0.5,
            label="Refined Prompts",
        ),
    ]

    # Add legend to the graph
    axes.legend(handles=legend_elements, loc="upper left", framealpha=0.9)

    # Call helper function to save the generated figure to disk
    save_figure(figure, "fig5_prompt_types")


def generate_cost_efficiency_graph(results):
    """
    Generates a scatter plot comparing average inference time (cost proxy) vs pass rate for each model to
    show a measure of cost-efficiency of different models used in the work.
    """

    # Use helper function to calculate pass rates grouped by model to get pass rate data for each model
    pass_stats = calculate_pass_rates(results)

    # Collect inference times per model separately
    # if it is available (not all runs have the inference time data point)
    inference_times = defaultdict(list)

    # Loop over results
    for individual_result in results:
        # If inference time data point available for this run, append to list
        if individual_result.get("inference_time_s"):
            inference_times[individual_result["model"]].append(
                individual_result["inference_time_s"]
            )

    # Use matplotlib to create scatter plot comparing average inference time vs pass rate for each model
    figure, axes = plt.subplots(figsize=(DOUBLE_COLUMN_WIDTH, LARGE_HEIGHT))

    # Loop over each model and its pass rate stats to plot on the graph
    for individual_model, stats in pass_stats.items():
        # If inference time data not available for this model or total runs is zero, skip it as it can't plot without these
        if not inference_times[individual_model] or stats["total"] == 0:
            continue

        # Use helper function to calculate pass rate for this model and average inference time across runs for this model
        rate = calculate_category_pass_rate(pass_stats, [individual_model])
        average_inference_time = sum(inference_times[individual_model]) / len(
            inference_times[individual_model]
        )

        # Call helper function to get colour for this model based on category and plot on scatter graph with marker style based on category
        color = get_model_color(individual_model)
        marker = (
            "D"
            if individual_model in TOOL_USING_MODELS
            else ("s" if individual_model in CLOSED_SOURCE_MODELS else "o")
        )

        # Plot the scatter point for this model with average inference time on x axis and pass rate on y axis, using colour and marker style based on model category
        axes.scatter(
            average_inference_time,
            rate,
            c=color,
            s=40,
            edgecolors="black",
            linewidth=0.5,
            zorder=3,
            marker=marker,
        )

        # Get the short display name for this model based on defined mapping and remove new lines for better display on graph
        short = MODEL_DISPLAY_NAMES.get(individual_model, individual_model).replace(
            "\n", " "
        )

        # Calculate label offsets for this model from defined manual offsets to avoid overlapping labels on the graph
        offset = SCATTER_LABEL_OFFSETS.get(individual_model, (8, 4))

        # Use offset to position label for model on graph and show model name next to scatter point
        axes.annotate(
            short,
            (average_inference_time, rate),
            textcoords="offset points",
            xytext=offset,
            fontsize=5.5,
            arrowprops=dict(arrowstyle="-", color="grey", lw=0.4),
        )

    # Set axis labels
    axes.set_xlabel("Average Inference Time (seconds)")
    axes.set_ylabel("Pass Rate (%)")

    # Set y axis limits to full range to show cost-efficiency across all models, including those with lower pass rates
    axes.set_ylim(0, Y_LIMIT_FULL_RANGE)
    axes.grid(True, alpha=0.3, linewidth=0.5)

    # Construct legend manually to show marker styles for open-source, closed-source and tool-using models
    legend_elements = [
        plt.Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor=COLOURS["open_source"],
            markeredgecolor="black",
            markersize=6,
            label="Open-Source",
        ),
        plt.Line2D(
            [0],
            [0],
            marker="s",
            color="w",
            markerfacecolor=COLOURS["closed_source"],
            markeredgecolor="black",
            markersize=6,
            label="Closed-Source",
        ),
        plt.Line2D(
            [0],
            [0],
            marker="D",
            color="w",
            markerfacecolor=COLOURS["tool_using"],
            markeredgecolor="black",
            markersize=6,
            label="Tool-Using",
        ),
    ]

    # Add legend to the graph
    axes.legend(handles=legend_elements, loc="lower right", fontsize=6, framealpha=0.9)

    # Call helper function to save the generated figure to disk
    save_figure(figure, "fig6_cost_efficiency")


def generate_heatmap_graph(results, model_order):
    """
    Generates a Heatmap with pass rates by model on y axis and prompt type on
    x axis to show detailed comparison of performance across
    differet prompt engineering approaches for each model.
    """
    # Calculate per-model prompt type stats using helper
    # Note using not tool filter again to exclude tool-using models as they don't have prompt types
    not_tool = lambda r: r["model"] not in TOOL_USING_MODELS

    # Calculate pass rates grouped by model and prompt type, filtering out tool-using models
    per_model_prompt_stats = {
        m: calculate_pass_rates(
            results,
            group_by="prompt_type",
            filter_fn=lambda r, model=m: not_tool(r) and r["model"] == model,
        )
        for m in model_order
        if m not in TOOL_USING_MODELS
    }

    # Custom labels for prompt types that are shown on x axis
    heatmap_pt_labels = [
        "Zero-Shot",
        "Few-Shot",
        "Instruction",
        "CoT",
        "Ref. Zero-Shot",
        "Ref. Few-Shot",
        "Ref. Instruction",
        "Ref. CoT",
    ]

    # Only include models that have at least one run for at least one prompt type to avoid showing models with no data in the heatmap
    heatmap_models = [
        individual_model
        for individual_model in model_order
        if individual_model in per_model_prompt_stats
        and any(
            per_model_prompt_stats[individual_model][pt]["total"] > 0
            for pt in ALL_PROMPT_TYPES
        )
    ]

    # Get display labels for models, removing new lines for better display on heatmap
    model_labels = [
        MODEL_DISPLAY_NAMES.get(m, m).replace("\n", " ") for m in heatmap_models
    ]

    # Build heatmap matrix of the stats with models on y axis and prompt types on x axis
    matrix = np.full((len(heatmap_models), len(ALL_PROMPT_TYPES)), np.nan)

    # Loop over models
    for i, m in enumerate(heatmap_models):
        # Loop over prompt types
        for j, pt in enumerate(ALL_PROMPT_TYPES):
            # Use helper function to calculate pass rate for this model and prompt type and populate in matrix
            rate = calculate_category_pass_rate(per_model_prompt_stats[m], [pt])
            if per_model_prompt_stats[m][pt]["total"] > 0:
                matrix[i, j] = rate

    # Use matplotlib to create heatmap from the matrix with defined labels and colour map
    figure, axes = plt.subplots(figsize=(DOUBLE_COLUMN_WIDTH, LARGE_HEIGHT))

    # Create heatmap image with pass rate values, using colour map to show low vs high pass rates and setting limits to 0-100%
    image = axes.imshow(matrix, cmap="RdYlGn", aspect="auto", vmin=0, vmax=100)

    # Loop over each matrix cell to add text labels with pass rate values
    for i in range(len(heatmap_models)):
        # Loop over prompt types to add text labels for each cell, showing pass rate value or '-' if no data, and using white text for very low or high pass rates for better visibility
        for j in range(len(ALL_PROMPT_TYPES)):
            cell_value = matrix[i, j]

            # If cell value is not NaN, add text label with pass rate value formatted as percentage
            if not np.isnan(cell_value):
                color = "white" if cell_value < 30 or cell_value > 80 else "black"
                axes.text(
                    j,
                    i,
                    f"{cell_value:.0f}",
                    ha="center",
                    va="center",
                    fontsize=6,
                    color=color,
                )
            # Otherwise, if no data, add a grey '-' to indicate no data
            else:
                axes.text(j, i, "-", ha="center", va="center", fontsize=6, color="grey")

    # Set ticks and labels for x and y axis based on defined prompt type labels and model labels
    # rotation and font size adjustments addded for easiser readabilitt
    axes.set_xticks(range(len(ALL_PROMPT_TYPES)))
    axes.set_xticklabels(heatmap_pt_labels, rotation=45, ha="right", fontsize=6)
    axes.set_yticks(range(len(heatmap_models)))
    axes.set_yticklabels(model_labels, fontsize=7)

    # Divider between initial and refined prompt types for clearer comparison
    axes.axvline(x=len(INITIAL_PROMPT_TYPES) - 0.5, color="black", linewidth=1.5)

    # Add colour bar to side of heatmap to show mapping of colours to pass rate values
    colour_bar = figure.colorbar(image, ax=axes, shrink=0.8, pad=0.02)

    # Add label to colour bar
    colour_bar.set_label("Pass Rate (%)", fontsize=7)

    # Adjust tick parameters for colour bar for better readability
    colour_bar.ax.tick_params(labelsize=6)

    # Call helper function to save the generated figure to disk
    save_figure(figure, "fig7_heatmap")


def generate_scenario_per_model_graph(results, model_order):
    """
    This graph shows a detailed comparison of how different models perform across the three scenarios used in the work:
    diff-only sent to model as context
    diff and source code sent to model as context
    diff and source code and tests sent to model as context"""

    # Filter to refined prompts only for fair comparison across models
    refined_filter = lambda r: r["model"] not in TOOL_USING_MODELS and r[
        "prompt_type"
    ].startswith("refined_")

    # Calculate pass rates grouped by model and scenario
    per_model_scenario_stats = {
        individual_model: calculate_pass_rates(
            results,
            group_by="scenario",
            filter_fn=lambda r, model=individual_model: refined_filter(r)
            and r["model"] == model,
        )
        for individual_model in model_order
        if individual_model not in TOOL_USING_MODELS
    }

    # Filter to models that at least have one run for at least one scneaerio
    models = [
        individual_model
        for individual_model in model_order
        if individual_model in per_model_scenario_stats
        and any(
            per_model_scenario_stats[individual_model][s]["total"] > 0
            for s in SCENARIOS
        )
    ]

    # Get display labels for models, removing new lines for better display on graph
    labels = [
        MODEL_DISPLAY_NAMES.get(individual_model, individual_model)
        for individual_model in models
    ]

    # Use numpy arange method to get x positions for each model and define bar width
    x = np.arange(len(models))
    width = 0.25

    # Use matplotlib to create grouped bar chart comparing pass rates across the three scenarios for each model
    figure, axes = plt.subplots(figsize=(DOUBLE_COLUMN_WIDTH, MEDIUM_HEIGHT))

    # Loop over each scenario to add bars for each model for this scenario, with heights based on pass rates and colours based on defined scenario colours
    for i, (
        individual_scenario,
        individual_scenario_label,
        individual_scenario_color,
    ) in enumerate(zip(SCENARIOS, SCENARIO_LABELS, SCENARIO_COLOURS)):
        # Use helper function to calculate pass rates for this scenario for each model and plot bars for this scenario, positioned based on scenario index for grouped display
        rates = [
            calculate_category_pass_rate(
                per_model_scenario_stats[m], [individual_scenario]
            )
            for m in models
        ]
        axes.bar(
            x + (i - 1) * width,
            rates,
            width,
            label=individual_scenario_label,
            color=individual_scenario_color,
            edgecolor="black",
            linewidth=0.3,
        )

    # Set x tickets and labels to model names, rotation and alignment used for better readability
    axes.set_xticks(x)
    axes.set_xticklabels(labels, rotation=0, ha="center")
    axes.set_ylabel("Pass Rate (%)")
    axes.set_ylim(0, Y_LIMIT_FULL_RANGE)

    # Add legend to the graph
    axes.legend(fontsize=6, loc="upper left", framealpha=0.9)

    # Call helper function to save the generated figure to disk
    save_figure(figure, "fig8_scenario_per_model")


def generate_model_size_scaling_graph(results):
    """
    This graph shows the relationship between model size (in billions of parameters) and pass rate for the open-source models in the study to
    see if scaling up model size correlated with better performancew across the models.
    """

    # Use helper function to calculate pass rates grouped by model, filtering to only include models with defined parameter counts for a fair comparison of scaling trends
    stats = calculate_pass_rates(
        results, filter_fn=lambda r: r["model"] in MODEL_PARAMETER_COUNTS
    )

    # Use matplotlib to create scatter plot comparing model size vs pass rate for open-source models
    figure, axes = plt.subplots(figsize=(SINGLE_COLUMN_WIDTH, MEDIUM_HEIGHT))

    # Loop over each model and its pass rate stats to plot on the graph
    for individual_model, individual_scenario_stats in stats.items():
        # If this model doesn't have any runs, skip it as it can't plot without data
        if individual_scenario_stats["total"] == 0:
            continue

        # Get model size from defined mapping and calculate pass rate for this model using helper function
        size = MODEL_PARAMETER_COUNTS[individual_model]
        rate = calculate_category_pass_rate(stats, [individual_model])

        # Plot the scatter point for this model with model size on x axis and
        # pass rate on y axis, using open-source colour mapping
        # and circular marker style for the mo
        axes.scatter(
            size,
            rate,
            c=COLOURS["open_source"],
            s=50,
            edgecolors="black",
            linewidth=0.5,
            zorder=3,
        )

        # Construct short display naem for model based on defined mapping
        short = MODEL_DISPLAY_NAMES.get(individual_model, individual_model).replace(
            "\n", " "
        )

        # Annote the model name next to the scatter point with defined manual offsets to avoid overlapping labels on the graph
        axes.annotate(
            short, (size, rate), textcoords="offset points", xytext=(5, 4), fontsize=5.5
        )

    # Trend line to show overall relationship between model size and pass rates
    sizes = [
        MODEL_PARAMETER_COUNTS[individual_model]
        for individual_model in stats
        if stats[individual_model]["total"] > 0
    ]
    rates = [
        stats[individual_model]["passed"] / stats[individual_model]["total"] * 100
        for individual_model in stats
        if stats[individual_model]["total"] > 0
    ]

    # Z is linear fit of sizes and rates
    # Calling this returns slope and intercept for best fit line
    linear_fit = np.polyfit(sizes, rates, 1)

    # P is polynomial function based on the linear fit
    # Basically can then plug in any x value (model size) to get the corresponding y value (pass rate) on the trend line
    polynomial = np.poly1d(linear_fit)

    # Values generated from linear fit to plot trend line
    x_line = np.linspace(min(sizes) - 1, max(sizes) + 1, 100)

    # Trend line plotted with dashed style and grey colour to show overall relationship between model size and pass rate across the open-source models
    axes.plot(x_line, polynomial(x_line), "--", color="grey", linewidth=0.8, alpha=0.7)

    # Set axis labels and limits, and add grid for easier readability
    axes.set_xlabel("Model Parameters (Billions)")
    axes.set_ylabel("Pass Rate (%)")
    axes.set_ylim(0, Y_LIMIT_FOCUSED_RANGE)
    axes.grid(True, alpha=0.3, linewidth=0.5)

    # Call helper function to save the generated figure to disk
    save_figure(figure, "fig8_model_size_scaling")


def generate_test_counts_graph(results, model_order):
    """
    This graph shows the total number of tests passed per model,
    including only the refined prompt runs for a fair comparison of performance across models
    with the best prompts."""

    # Calculate stats grouped by model, filtering to include only refined prompt runs
    # for a comparison of performance across models with the best prompts,
    # and includes tool-using models
    stats = defaultdict(lambda: {"tests_passed": 0, "tests_failed": 0, "runs": 0})

    # Loop over results
    for individual_result in results:
        # Get the model for this run
        individual_model = individual_result["model"]
        # Include tool-using models (no prompt types) and refined prompt runs only
        # As performance for initial prompts was much lower
        if individual_model not in TOOL_USING_MODELS and not individual_result.get(
            "prompt_type", ""
        ).startswith("refined_"):
            continue

        # Update stats for this model with the number of tests passed and failed for this run,
        # and count the number of runs for averaging later if needed
        stats[individual_model]["tests_passed"] += individual_result.get(
            "passed_count", 0
        )
        stats[individual_model]["tests_failed"] += individual_result.get(
            "failed_count", 0
        )
        stats[individual_model]["runs"] += 1

    # Just exclude playwright agents as only 8 tests completed with this so
    # it was skewing the graph
    models = [
        individual_model
        for individual_model in model_order
        if individual_model in stats
        and stats[individual_model]["tests_passed"]
        + stats[individual_model]["tests_failed"]
        > 0
        and individual_model != "playwright-agents-claude-sonnet-4-20250514"
    ]

    # Get the number of tests passed and failed for each model to plot on the graph
    passed = [stats[individual_model]["tests_passed"] for individual_model in models]
    failed = [stats[individual_model]["tests_failed"] for individual_model in models]

    # Get labels and colours for each model based on defined mappings and categories for display on the graph
    labels = [
        MODEL_DISPLAY_NAMES.get(individual_model, individual_model)
        for individual_model in models
    ]
    bar_colors = [get_model_color(individual_model) for individual_model in models]

    # Use matplotlib to create grouped bar chart comparing number of test assertions passed across models,
    # with bars coloured based on model category
    figure, axes = plt.subplots(figsize=(DOUBLE_COLUMN_WIDTH, MEDIUM_HEIGHT))

    # Create bars for passed assertions with heights based on number of tests passed
    bars_passed_assertions = axes.bar(
        range(len(models)),
        passed,
        color=bar_colors,
        edgecolor="black",
        linewidth=0.3,
        label="Passed",
    )

    # Add grey bars for failed tests stacked on top of passed
    axes.bar(
        range(len(models)),
        failed,
        bottom=passed,
        color="lightgrey",
        edgecolor="black",
        linewidth=0.3,
        label="Failed",
    )

    # Add passed/total labels above each stacked bar
    for bar, passed_count, failed_count in zip(bars_passed_assertions, passed, failed):
        total = passed_count + failed_count
        if total > 0:
            axes.text(
                bar.get_x() + bar.get_width() / 2,
                total + 5,
                f"{passed_count}/{total}",
                ha="center",
                va="bottom",
                fontsize=5.5,
            )

    # Set x ticks and labels to model names, rotation and alignment used for better readability
    single_labels = [l.replace("\n", " ") for l in labels]
    axes.set_xticks(range(len(models)))
    axes.set_xticklabels(single_labels, rotation=35, ha="right", fontsize=6)
    axes.set_ylabel("Tests")

    # Define custom legend elemnts to show menaing of each bar colour
    legend_elements = [
        Patch(
            facecolor=COLOURS["open_source"],
            edgecolor="black",
            linewidth=0.5,
            label="Passed (Open-Source)",
        ),
        Patch(
            facecolor=COLOURS["closed_source"],
            edgecolor="black",
            linewidth=0.5,
            label="Passed (Closed-Source)",
        ),
        Patch(
            facecolor=COLOURS["tool_using"],
            edgecolor="black",
            linewidth=0.5,
            label="Passed (Tool-Using)",
        ),
        Patch(facecolor="lightgrey", edgecolor="black", linewidth=0.5, label="Failed"),
    ]

    # Set the actual legend on the graph
    axes.legend(handles=legend_elements, fontsize=6, loc="upper left", framealpha=0.9)

    # Call helper function to save the generated figure to disk
    save_figure(figure, "fig9_test_counts")


def generate_token_usage_graph(results):
    """
    This graph shows the average number of output tokens generated per model,
    with an overlay of model pass rates to view the relationship between token
    usage and performance across the models.
    """

    # Use helper function to calculate pass rates grouped by model to get pass rate data for each model
    pass_stats = calculate_pass_rates(results)

    # Collect output token counts per model separately
    token_counts = defaultdict(list)
    for individual_result in results:
        tok = individual_result.get("output_token_count", 0)
        if tok and tok > 0:
            token_counts[individual_result["model"]].append(tok)

    # Sort by average token count ascending from left to right so bar heights progress naturally
    models = [
        individual_model
        for individual_model in pass_stats
        if token_counts[individual_model] and pass_stats[individual_model]["total"] > 0
    ]

    # Sort models by average token count for better visual progression of bar heights, while keeping the same order for pass rates and labels
    models.sort(key=lambda m: sum(token_counts[m]) / len(token_counts[m]))

    # Get average token count for each model
    average_tokens = [
        sum(token_counts[individual_model]) / len(token_counts[individual_model])
        for individual_model in models
    ]

    # Get pass rates for each model using helper function
    pass_rates = [
        calculate_category_pass_rate(pass_stats, [individual_model])
        for individual_model in models
    ]

    # Use helper function to get bar colours and labels for each model
    bar_colors = [get_model_color(m) for m in models]
    labels = [MODEL_DISPLAY_NAMES.get(m, m) for m in models]

    # Use matplotlib to create bar chart comparing average output token counts across models
    # with an overlay line plot for pass rates,
    # also have bars coloured based on model category (open-source, closed-source, tool-using)
    figure, axis1 = plt.subplots(figsize=(DOUBLE_COLUMN_WIDTH, MEDIUM_HEIGHT))

    # Make bar chart for average token counts
    bars = axis1.bar(
        range(len(models)),
        average_tokens,
        color=bar_colors,
        edgecolor="black",
        linewidth=0.3,
    )

    # Add labels and ticks for x axis based on model names, rotation and alignment used for better readability
    axis1.set_xticks(range(len(models)))
    axis1.set_xticklabels(labels, rotation=0, ha="center")
    axis1.set_ylabel("Average Output Tokens")

    # Token count added above each bar with formatting to show as numbers
    add_bar_labels(axis1, bars, fmt="{:.0f}", fontsize=5.5, offset=5)

    # Separate axis for pass rates
    axis2 = axis1.twinx()

    # Plots the pass rates as a line plot with markers
    axis2.plot(
        range(len(models)),
        pass_rates,
        "k-o",
        markersize=4,
        linewidth=1.2,
        label="Pass Rate",
        zorder=5,
    )

    # Sets label and limits for hte pass rate y axis
    axis2.set_ylabel("Pass Rate (%)")
    axis2.set_ylim(0, Y_LIMIT_FULL_RANGE)

    # Add pass rate points below the line to avoid clashing with token labels
    for i, rate in enumerate(pass_rates):
        axis2.annotate(
            f"{rate:.0f}%",
            (i, rate),
            textcoords="offset points",
            xytext=(0, -12),
            ha="center",
            fontsize=5.5,
            fontweight="bold",
        )

    # Manually make legend to show meaning of bar colours and
    # line added
    legend_elements = [
        Patch(
            facecolor=COLOURS["open_source"],
            edgecolor="black",
            linewidth=0.5,
            label="Tokens (Open-Source)",
        ),
        Patch(
            facecolor=COLOURS["closed_source"],
            edgecolor="black",
            linewidth=0.5,
            label="Tokens (Closed-Source)",
        ),
        plt.Line2D(
            [0],
            [0],
            color="black",
            marker="o",
            markersize=4,
            linewidth=1.2,
            label="Pass Rate",
        ),
    ]

    # Set the actual legend on the graph
    axis1.legend(handles=legend_elements, fontsize=6, loc="lower right", framealpha=0.9)

    # Call helper function to save the generated figure to disk
    save_figure(figure, "fig10_token_usage")


def main():
    # Debugging print statements to show progress and key information about the data being loaded and processed
    print(f"Loading results from {RESULTS_PATH}")

    # Call helper function to load results from disk
    results = load_results()
    print(f"Loaded {len(results)} results")
    print(f"Output directory: {OUTPUT_DIRECTORY}\n")

    # Call helper function to determine model order for consistent display across graphs based on the results data
    model_order = get_model_order(results)

    # Debugging print statement to let user know that figure generation now taking place
    print("Generating figures:")

    # Calls all the graph generation function features in order to create them
    generate_overall_pass_rates_by_model_graph(results, model_order)
    generate_approach_comparison_graph(results)
    generate_prompt_engineering_impact_graph(results, model_order)
    generate_scenario_impact_graph(results)
    generate_prompt_type_comparison_graph(results)
    generate_cost_efficiency_graph(results)
    generate_heatmap_graph(results, model_order)
    generate_model_size_scaling_graph(results)
    generate_test_counts_graph(results, model_order)
    generate_token_usage_graph(results)

    # Once complete let user know that all figures have been generated
    # to the output directory with a print statement
    print(f"\nAll figures saved to {OUTPUT_DIRECTORY}/")


if __name__ == "__main__":
    main()
