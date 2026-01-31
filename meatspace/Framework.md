# Claude Code/Agent framework
THIS FILE IS FOR HUMANS ONLY, AGENTS MAY NOT USE THIS. DONT MAKE ME REVOKE YOUR PERMISSIONS TO THIS FILE JFC
## Learnings Log
### Everyone needs Claude Code
(or something similar)
I posit that only once you realize the power can you srtat working well with more limited tools. There are probably metaphors in other industries to draw from here, like if you never used an auto code analyzer to see the trouble codes for a modern car, you dont have an idea of the complexity of them and there are some classes of problems you will never solve, but may spend weeks trying to. bad?
### Horizontal vs Vertical decoupling
- I experimented with "horizontal" decoupling, where i defined abstractions for each application layer, and had individual modules implementing them for each domain. The hypothesis was that it would be simpler for an agent to live within a domain, and leads to less cross-domain boundary violations
- It turns out that maybe this wasnt the right  choice, instead "vertical" decoupling - where each layer has its own module ("services") might be better.
- Refactoring this Nov-2025
- I think the real learning is that identifying the layers, and giving the agent less choice in layer implementations, is the real benefit.
- Secondly, maybe there is no free lunch here, and we just need to keep libraries very lean. Like maybe the schema should be in its own API library, and each service will auto-translate or something. Or maybe it can define the default schema, and let consumers override. Blah.

Interestingly, I am finding that the agent itself *wants* to work like this; its done this a few times, but in the most recent case it was editing /module/schema.py and needed something generic, so it created /schema/utils.py. It clearly *wants* like things to be together!

## Advice
- use gold-standard designs the agent can copy; this includes code, tests, db tables, working software (migrations, etc), as well as linting rules. One-shotting works great for simple things, but asking the agent to create something from scratch ends up with shots in the dark that take forever and yield garbage often. aka "do it like this". May be a good candidate for an agent to review a codebase looking for patterns, and capture them for a human review.
- observe the agent process, and look for opportunities for new tool calls or just examples in agents.md for items the agent spins on. you can even ask the agent to look at the conversation history and perform this.
- note tool handling differences across platforms. in vscode the agent realllly wants to use tasks and stuff to execute commands when it would much easier to run a quick bash oneline (which claude might be excellent at). vscode will also try to use extensions for things like pyright, when you can do this better with a makefile and some entries in pyproject.toml
- tell it how you want to write scripts, otherwise it will just land shit in the root folder indiscriminately

## TODO
### Reorganize and rename osme things to make it less fragmented
### Capturing journal
### Capturing edits in diffs, just in case
a skill?
## Ideas
1. Different tools for agents and humans, to reduce token cost

## USAGE

1. ensure that the agents.env file is sourced, to correctly set environment vars
2. ensure the virtualenv is sourced

## Agent Support
### Claude
- .claude/
- CLAUDE.md (-> AGENTS.md)
- supports .mcp.json as a source, will add to .claude/settings.json

### Gemini
- .gemini
- GEMINI.md
- .geminiignore

## Github Copilot
Ref: https://github.com/github/awesome-copilot
Configurable:
- [Custom instructions](https://code.visualstudio.com/docs/copilot/customization/custom-instructions)
- [Prompt files](https://code.visualstudio.com/docs/copilot/customization/prompt-files)
- [Chat modes](https://code.visualstudio.com/docs/copilot/customization/custom-chat-modes)
- Model selection
- [MCP Servers](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/extend-coding-agent-with-mcp#writing-a-json-configuration-for-mcp-servers)
- AGENTS.md in subfolders is experimental

Files:
- .github/copilot-instructions.md
- .github/instructions/something.instructions.md
    - configured using applyTo globspec
    - use `applyTo` using path globbing
    - used automatically, applies to all matching files, but only for creating and modifying the files.
    - examples: coding standards, documentation standards etc
    - more like a granular AGENTS.md for different file types
    - `.github/instructions/**/NAME.instructions.md`
- .github/prompts/something.prompts.md
    - configured using mode, model, tools
    - triggered with slash command
    - more like a claude command
- .github/chatmodes/something.chatmode.md
    - configured using tools, model
    - more like an agent
- AGENTS.md
- .vscode/mcp.json and others

#### Github Copilot Agent (VSCode)
- GITHUB_COPILOT.md
- Agent mode should support AGENTS.md, CLAUDE.md or GEMINI.md files

#### Github Copilot CLI
https://docs.github.com/en/copilot/how-tos/use-copilot-agents/use-copilot-cli


## Framework Design

### Concerns
1. Guiding an agent's behavior as a good developer
2. Teaching the agent how to capture decisions, observations, analysis results
3. ~~Observing agent behavior and metrics over time~~
4. Providing scripts to facilitate and add determinism to the above
5. Providing an integration with specific agentic systems for the above
6. Giving the human a place to add files that the agent doesnt need, including offline conversations with other LLMs

## Features

### Agent abilities
Described in `ai_context/ABILITIES.md`, included in AGENTS.md and subagents:
1. Decisions
2. Discoveries
3. Analysis

Artifacts can be generated by the agent, and are stored in:
- **ai_working/**

### Context Management

1. Context packs (generated documentaiton) - `ai_context/generated/`

Context can be re-built using **blahblah**

### Agent Devleopment principles and behavior alignment
Described in `ai_context/DEVELOPER_PRINCIPLES.md`, included in AGENTS.md as well as sub-agent instructions in .claude/agents and .claude/commands:

### Codebase standards
- AGENT.md
- **sceripts/template**

### Human overseer

- `meatspace` excluded from agent's access as well as codebase checks, but included in git

### Maintenance tools
Shared by the operator and the agent, `tools/`

### Claude Code-specific

See [the README]('.claude/README.md') for details.

### Framework Structure

```zsh
├── .claude/
│   ├── agents/
│   ├── commands/
│   ├── tools/
│   ├── README.md
│   ├── README_LOGS.md
│   ├── settings.json
├── .data/
├── .gemini/
├── ai_context/
│   ├── generated/
│   ├── ABILITIES.md
│   ├── DEVELOPER_PRINCIPLES.md
│   ├── README.md
├── ai_working/
│   ├── analysis/
│   ├── decisions/
│   ├── DISCOVERIES.md
│   ├── README.md
├── docs/
├── meatspace/
│   ├── conversations
│   ├── HUMAN-TODO.md
├── tools/
│   ├── xxx
│   ├── README.md
├── AGENTS.md
├── CLAUDE.md
├── Framework.md
├── GEMINI.md
├── README.md
```
