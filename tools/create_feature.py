#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pydantic-ai",
#   "openai",
#   "pydantic",
#   "python-dotenv",
# ]
# ///
"""
Create stub feature specifications from textual description, using an LLM.

Usage: $0 "Text description of a feature" --provider openai|ollama --model [model-specifier]
- Creates a new feature directory in `$PROJECT_ROOT/docs/features` with the next available number
- Stubs a PRD.md file using a prompt, the text feature description, and structured outputs

Default provider: openai
Default model: gpt-4o-mini
Requires OPENAI_API_KEY for non-ollama inference

"""
import argparse
import asyncio
import os
import re
import shutil
import sys
import tempfile
from typing import List, Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

DEFAULT_PROVIDER = "openai"
DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "ollama": "llama3"
}
FEATURES_ROOT = os.path.join('docs', 'features')
PROMPT = (
    "You are an expert product manager. Based on the user's feature description, "
    "generate a detailed Product Requirements Document (PRD). "
    "Flesh out the problem statement, create clear user stories, define specific acceptance criteria, "
    "and list items that are explicitly out of scope. The user will provide the feature description as their input."
)

class PRD(BaseModel):
    """A model for a Product Requirements Document."""
    title: str = Field(..., description="The main title of the feature.")
    problem_statement: str = Field(..., description="A clear and concise description of the problem this feature will solve.")
    #user_stories: List[str] = Field(..., description="A list of user stories describing the feature from an end-user's perspective.")
    acceptance_criteria: List[str] = Field(..., description="A list of criteria that must be met for the feature to be considered complete.")
    out_of_scope: List[str] = Field(..., description="A list of items that are explicitly not part of this feature.")

    def to_markdown(self) -> str:
        """Converts the PRD model to a Markdown string."""
        markdown = f"# {self.title}\n\n"
        markdown += f"## Problem Statement\n{self.problem_statement}\n\n"
        # markdown += "## User Stories\n"
        # for story in self.user_stories:
        #     markdown += f"- {story}\n"
        # markdown += "\n"
        markdown += "## Acceptance Criteria\n"
        for criteria in self.acceptance_criteria:
            markdown += f"- {criteria}\n"
        markdown += "\n"
        markdown += "## Out of Scope\n"
        for item in self.out_of_scope:
            markdown += f"- {item}\n"
        markdown += "\n## Requirements Detail\n"
        return markdown

# --- Core Functions ---

def find_next_feature_dir(features_dir):
    """
    Finds the next available feature number in a features directory
    having the following naming scheme:
        ./FEAT-NNN

    Checks both the main features directory and the completed features
    directory to avoid duplicate feature numbers.
    """
    if not os.path.isdir(features_dir):
        return "FEAT-001"

    max_num = 0

    # Check main features directory
    feature_dirs = [d for d in os.listdir(features_dir) if os.path.isdir(os.path.join(features_dir, d))]
    for dirname in feature_dirs:
        match = re.match(r'FEAT-(\d+)', dirname)
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num

    # Check completed features directory
    completed_dir = os.path.join(features_dir, 'completed')
    if os.path.isdir(completed_dir):
        completed_feature_dirs = [d for d in os.listdir(completed_dir) if os.path.isdir(os.path.join(completed_dir, d))]
        for dirname in completed_feature_dirs:
            match = re.match(r'FEAT-(\d+)', dirname)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num

    next_feature_num = max_num + 1
    return f"FEAT-{next_feature_num:03d}"


async def generate_prd_details(description: str, provider: Literal['openai', 'ollama'], model: str) -> PRD:
    """
    Generates a detailed PRD using the specified LLM provider with pydantic_ai.Agent.
    """
    print("Generating detailed PRD with AI Agent. This may take a moment...")

    # The PydanticAI Agent is initialized with a model string like "provider:model_name"
    model_string = f"{provider}:{model}"
    print(f"Using PydanticAI Agent with model: {model_string}")

    # Define the Agent with a dynamic system prompt
    agent = Agent(
        model_string,
        output_type=PRD,
    )

    @agent.system_prompt
    def prd_generation_prompt(ctx: RunContext) -> str:
        """Generates the system prompt for creating the PRD."""
        return PROMPT

    try:
        result = await agent.run(description)
        prd = result.output
        if not isinstance(prd, PRD):
             raise Exception(f"AI agent returned an unexpected type: {type(prd)}")

        prd.title = description # Ensure the original title is used
        return prd
    except Exception as e:
        print(f"Error during AI generation with {provider}: {e}", file=sys.stderr)
        if provider == 'ollama':
            print("\nPlease ensure the Ollama server is running and the specified model is available.", file=sys.stderr)
        elif provider == 'openai':
            if not os.getenv("OPENAI_API_KEY"):
                print("\nError: OPENAI_API_KEY environment variable not set for OpenAI provider.", file=sys.stderr)
        sys.exit(1)

async def main():
    """
    Main function to create a new feature.
    """
    load_dotenv()

    parser = argparse.ArgumentParser(description="Create a new feature structure with an AI-generated PRD.")
    parser.add_argument("description", type=str, help="A short, descriptive sentence for the new feature.")
    parser.add_argument("--provider", type=str, default=DEFAULT_PROVIDER, choices=['openai', 'ollama'], help="The LLM provider to use.")
    parser.add_argument("--model", type=str, help="The specific model to use for generation (e.g., 'gpt-4o-mini', 'llama3').")
    args = parser.parse_args()

    model = args.model
    if not model:
        model = DEFAULT_MODELS[args.provider]

    script_dir = os.path.dirname(os.path.realpath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, '..'))
    features_dir = os.path.join(project_root, FEATURES_ROOT)

    feature_name = find_next_feature_dir(features_dir)
    final_feature_dir = os.path.join(features_dir, feature_name)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_feature_dir = os.path.join(temp_dir, feature_name)
        os.makedirs(temp_feature_dir, exist_ok=True)

        prd_content = await generate_prd_details(args.description, args.provider, model)

        prd_path = os.path.join(temp_feature_dir, 'PRD.md')
        plan_path = os.path.join(temp_feature_dir, 'IMPLEMENTATION_PLAN.md')
        try:
            with open(prd_path, 'w') as f:
                f.write(prd_content.to_markdown())
            with open(plan_path, 'w') as f:
                f.write("# Implementation Plan\n\n")
            print(f"Successfully created AI-generated PRD in temporary location: {prd_path}")
        except IOError as e:
            print(f"Error writing to file {prd_path}: {e}", file=sys.stderr)
            sys.exit(1)

        try:
            shutil.move(temp_feature_dir, final_feature_dir)
            print(f"Successfully moved feature to: {final_feature_dir}")
        except Exception as e:
            print(f"Error moving feature directory to final destination: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
