#!/usr/bin/env python3
"""Beads round bootstrap script for the search improvement loop.

Creates and manages bd (Beads) tasks for iterative search improvement
campaigns. Each campaign consists of multiple rounds, where each round
has plan, implement, and evaluate subtasks with dependency ordering.

Usage:
    python bootstrap_round.py init --title "..." --description "..."
    python bootstrap_round.py advance --state-file experiments/campaign_state.json --experiment-path experiments/2026-02-15/run1
    python bootstrap_round.py status --state-file experiments/campaign_state.json
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


DEFAULT_STATE_FILE = "experiments/campaign_state.json"
DEFAULT_MAX_ROUNDS = 3
STALL_THRESHOLD = 2  # stop after this many consecutive rounds with no improvement


def run_bd(args: list[str]) -> subprocess.CompletedProcess:
    """Run a bd CLI command and return the result.

    Args:
        args: Arguments to pass to the bd command.

    Returns:
        CompletedProcess with stdout/stderr captured as text.

    Raises:
        SystemExit: If bd command fails.
    """
    cmd = ["bd"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"bd command failed: {' '.join(cmd)}", file=sys.stderr)
        print(f"stderr: {result.stderr}", file=sys.stderr)
        raise SystemExit(1)
    return result


def parse_task_id(bd_output: str) -> str:
    """Extract task ID from bd create output.

    Expects output like 'Created issue: substrate-XX' or similar.

    Args:
        bd_output: Raw stdout from bd create command.

    Returns:
        The task ID string (e.g. 'substrate-42').

    Raises:
        SystemExit: If no task ID can be parsed from output.
    """
    # Match patterns like "substrate-123", "substrate-1", etc.
    match = re.search(r"(substrate-\d+)", bd_output)
    if not match:
        print(f"Could not parse task ID from bd output: {bd_output!r}", file=sys.stderr)
        raise SystemExit(1)
    return match.group(1)


def create_task(title: str, task_type: str = "task", priority: int = 2,
                description: str = "") -> str:
    """Create a bd task and return its ID.

    Args:
        title: Task title.
        task_type: Task type (default 'task').
        priority: Task priority (default 2).
        description: Task description body.

    Returns:
        The created task's ID string.
    """
    args = [
        "create",
        f"--title={title}",
        f"--type={task_type}",
        f"--priority={priority}",
    ]
    if description:
        args.append(f"--description={description}")
    result = run_bd(args)
    return parse_task_id(result.stdout)


def add_dependency(task_id: str, depends_on: str) -> None:
    """Add a dependency between two tasks.

    Args:
        task_id: The task that is blocked.
        depends_on: The task that must complete first.
    """
    run_bd(["dep", "add", task_id, depends_on])


def close_task(task_id: str) -> None:
    """Close a bd task.

    Args:
        task_id: The task ID to close.
    """
    run_bd(["close", task_id])


def update_task_status(task_id: str, status: str) -> None:
    """Update a task's status.

    Args:
        task_id: The task ID to update.
        status: New status value (e.g. 'in_progress').
    """
    run_bd(["update", task_id, f"--status={status}"])


def create_round_tasks(campaign_title: str, round_number: int,
                       parent_task_id: str) -> dict:
    """Create plan/implement/evaluate tasks for a single round.

    Creates three subtasks with dependencies:
        implement is blocked by plan,
        evaluate is blocked by implement.

    Args:
        campaign_title: The parent campaign title for labeling.
        round_number: The round number (1-indexed).
        parent_task_id: The parent campaign task ID.

    Returns:
        Dict with round metadata including task IDs.
    """
    prefix = f"[{campaign_title}] Round {round_number}"

    plan_id = create_task(
        title=f"{prefix}: Plan",
        description=(
            f"Plan improvements for round {round_number}. "
            f"Identify failure modes, design experiment, define success criteria. "
            f"Parent: {parent_task_id}"
        ),
    )

    implement_id = create_task(
        title=f"{prefix}: Implement",
        description=(
            f"Implement planned changes for round {round_number}. "
            f"Apply code/config changes and run ingestion. "
            f"Parent: {parent_task_id}"
        ),
    )

    evaluate_id = create_task(
        title=f"{prefix}: Evaluate",
        description=(
            f"Evaluate results for round {round_number}. "
            f"Run harness, compare metrics, write recommendations. "
            f"Parent: {parent_task_id}"
        ),
    )

    # Set dependency chain: implement blocked by plan, evaluate blocked by implement
    add_dependency(implement_id, plan_id)
    add_dependency(evaluate_id, implement_id)

    # Mark plan as in_progress since it's the first actionable task
    update_task_status(plan_id, "in_progress")

    return {
        "round_number": round_number,
        "plan_task_id": plan_id,
        "implement_task_id": implement_id,
        "evaluate_task_id": evaluate_id,
        "experiment_path": None,
        "key_metric_value": None,
        "status": "in_progress",
    }


def load_state(state_file: Path) -> dict:
    """Load campaign state from a JSON file.

    Args:
        state_file: Path to the state JSON file.

    Returns:
        Parsed campaign state dict.

    Raises:
        SystemExit: If state file does not exist or is malformed.
    """
    if not state_file.exists():
        print(f"State file not found: {state_file}", file=sys.stderr)
        raise SystemExit(1)
    try:
        return json.loads(state_file.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Failed to read state file: {exc}", file=sys.stderr)
        raise SystemExit(1)


def save_state(state: dict, state_file: Path) -> None:
    """Save campaign state to a JSON file.

    Args:
        state: Campaign state dict.
        state_file: Path to write the state JSON file.
    """
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2) + "\n")


def load_metrics(metrics_file: Path) -> Optional[float]:
    """Load the key metric value from a metrics JSON file.

    Looks for a 'key_metric' field at the top level. If not found, looks
    for 'mrr_at_k' or 'recall_at_k' as fallbacks.

    Args:
        metrics_file: Path to the metrics JSON file.

    Returns:
        The key metric value as a float, or None if not found.
    """
    if not metrics_file.exists():
        return None
    try:
        data = json.loads(metrics_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    for key in ("key_metric", "mrr_at_k", "recall_at_k", "ndcg_at_k"):
        if key in data:
            try:
                return float(data[key])
            except (TypeError, ValueError):
                continue
    return None


def check_stopping_criteria(state: dict, new_metric: Optional[float]) -> Optional[str]:
    """Check whether the campaign should stop.

    Args:
        state: Current campaign state.
        new_metric: Key metric value from the just-completed round, or None.

    Returns:
        A stopping reason string if the campaign should stop, or None to continue.
    """
    current_round = state["current_round"]
    max_rounds = state["max_rounds"]

    # Hard cap on rounds
    if current_round >= max_rounds:
        return f"reached max rounds ({max_rounds})"

    # Check for stalled improvement
    if new_metric is not None:
        rounds_with_metrics = [
            r for r in state["rounds"]
            if r["key_metric_value"] is not None
        ]
        if len(rounds_with_metrics) >= STALL_THRESHOLD:
            recent = rounds_with_metrics[-STALL_THRESHOLD:]
            all_stalled = all(
                new_metric <= r["key_metric_value"]
                for r in recent
            )
            if all_stalled:
                return (
                    f"no improvement for {STALL_THRESHOLD} consecutive rounds "
                    f"(metric={new_metric})"
                )

    return None


# -- Subcommands ---------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize a new improvement campaign.

    Creates a parent task and the first round of subtasks.

    Args:
        args: Parsed CLI arguments with title, description, max_rounds,
              and state_file.

    Returns:
        Exit code (0 for success).
    """
    state_file = Path(args.state_file)

    # Create parent campaign task
    parent_id = create_task(
        title=args.title,
        description=args.description,
        priority=1,
    )

    # Create round 1 subtasks
    round_info = create_round_tasks(args.title, 1, parent_id)

    state = {
        "campaign_title": args.title,
        "parent_task_id": parent_id,
        "max_rounds": args.max_rounds,
        "current_round": 1,
        "rounds": [round_info],
        "stopping_reason": None,
    }

    save_state(state, state_file)
    print(json.dumps(state, indent=2))
    return 0


def cmd_advance(args: argparse.Namespace) -> int:
    """Advance the campaign to the next round.

    Closes the current round's evaluate task, checks stopping criteria,
    and optionally creates the next round's subtasks.

    Args:
        args: Parsed CLI arguments with state_file, experiment_path,
              optional metrics_file, and force_stop flag.

    Returns:
        Exit code (0 for success).
    """
    state_file = Path(args.state_file)
    state = load_state(state_file)

    if state["stopping_reason"] is not None:
        print(
            f"Campaign already stopped: {state['stopping_reason']}",
            file=sys.stderr,
        )
        print(json.dumps(state, indent=2))
        return 0

    current_round_idx = state["current_round"] - 1
    current_round = state["rounds"][current_round_idx]

    # Close the evaluate task with evidence reference
    experiment_path = str(args.experiment_path)
    close_task(current_round["evaluate_task_id"])
    current_round["experiment_path"] = experiment_path
    current_round["status"] = "completed"

    # Load key metric if provided
    new_metric = None
    if args.metrics_file:
        new_metric = load_metrics(Path(args.metrics_file))
        if new_metric is not None:
            current_round["key_metric_value"] = new_metric

    # Check for forced stop
    if args.force_stop:
        state["stopping_reason"] = "manual stop (--force-stop)"
        save_state(state, state_file)
        print(json.dumps(state, indent=2))
        return 0

    # Check stopping criteria
    reason = check_stopping_criteria(state, new_metric)
    if reason is not None:
        state["stopping_reason"] = reason
        save_state(state, state_file)
        print(json.dumps(state, indent=2))
        return 0

    # Create next round
    next_round_num = state["current_round"] + 1
    round_info = create_round_tasks(
        state["campaign_title"], next_round_num, state["parent_task_id"]
    )
    state["rounds"].append(round_info)
    state["current_round"] = next_round_num

    save_state(state, state_file)
    print(json.dumps(state, indent=2))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show campaign status.

    Reads the state file and outputs a JSON summary including current round,
    completed rounds, and task statuses.

    Args:
        args: Parsed CLI arguments with state_file.

    Returns:
        Exit code (0 for success).
    """
    state_file = Path(args.state_file)
    state = load_state(state_file)

    completed = [r for r in state["rounds"] if r["status"] == "completed"]
    in_progress = [r for r in state["rounds"] if r["status"] == "in_progress"]

    summary = {
        "campaign_title": state["campaign_title"],
        "parent_task_id": state["parent_task_id"],
        "max_rounds": state["max_rounds"],
        "current_round": state["current_round"],
        "completed_rounds": len(completed),
        "in_progress_rounds": len(in_progress),
        "stopping_reason": state["stopping_reason"],
        "rounds": state["rounds"],
    }

    print(json.dumps(summary, indent=2))
    return 0


# -- CLI -----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all subcommands.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        prog="bootstrap_round",
        description=(
            "Beads round bootstrap script for search improvement campaigns. "
            "Creates and manages bd tasks for iterative improvement loops."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- init ------------------------------------------------------------------
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a new improvement campaign.",
    )
    init_parser.add_argument(
        "--title", required=True,
        help="Campaign title (used as parent task title).",
    )
    init_parser.add_argument(
        "--description", required=True,
        help="Campaign description (used as parent task description).",
    )
    init_parser.add_argument(
        "--max-rounds", type=int, default=DEFAULT_MAX_ROUNDS,
        help=f"Maximum number of rounds (default: {DEFAULT_MAX_ROUNDS}).",
    )
    init_parser.add_argument(
        "--state-file", default=DEFAULT_STATE_FILE,
        help=f"Path to save campaign state JSON (default: {DEFAULT_STATE_FILE}).",
    )

    # -- advance ---------------------------------------------------------------
    advance_parser = subparsers.add_parser(
        "advance",
        help="Advance to the next round after completing an evaluation.",
    )
    advance_parser.add_argument(
        "--state-file", required=True,
        help="Path to campaign state JSON file.",
    )
    advance_parser.add_argument(
        "--experiment-path", required=True,
        help="Path to the completed experiment folder (evidence reference).",
    )
    advance_parser.add_argument(
        "--metrics-file", default=None,
        help=(
            "Path to metrics.json for the completed round. "
            "Used to check improvement-based stopping criteria."
        ),
    )
    advance_parser.add_argument(
        "--force-stop", action="store_true", default=False,
        help="Force-stop the campaign after closing the current round.",
    )

    # -- status ----------------------------------------------------------------
    status_parser = subparsers.add_parser(
        "status",
        help="Show campaign status.",
    )
    status_parser.add_argument(
        "--state-file", required=True,
        help="Path to campaign state JSON file.",
    )

    return parser


def main() -> int:
    """Entry point for the bootstrap_round CLI.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "init": cmd_init,
        "advance": cmd_advance,
        "status": cmd_status,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
