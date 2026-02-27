# Requirements Specification: `eval_harnesses` — Agent Harness Module

**Version:** 1.0
**Package:** `eval_harnesses`
**Python:** ≥ 3.10
**Dependency:** `claude-agent-sdk` (replaces deprecated `claude-code-sdk`)

---

## 1. Purpose & Scope

`eval_harnesses` is a Python module that wraps the Claude Agent SDK to expose two evaluation-ready agent execution strategies:

| Harness | Loop Pattern | Key Characteristic |
|---|---|---|
| `CodeActHarness` | CodeAct | The agent produces and executes Python code as its action mechanism; tools are invoked by executing code |
| `ReActHarness` | ReAct (Reason + Act) | The agent alternates explicit Thought → Action → Observation steps using named tool calls |

Both harnesses must:
- Support **arbitrary tool registration** (built-in Claude Code tools and/or custom Python functions via in-process MCP)
- Emit a **streaming event interface** so callers can observe every reasoning step, tool call, and partial output in real time
- Return a **structured run record** (trace) capturing all turns, tool calls, token usage, cost, and latency
- Be usable as drop-in evaluation backends with a common `run()` interface

---

## 2. SDK Primer (Key Concepts)

The Claude Agent SDK communicates with a bundled Claude Code CLI subprocess over bidirectional JSON on stdin/stdout. The two SDK interfaces relevant here are:

### 2.1 `query()` — Stateless, single-turn
```python
async def query(
    *,
    prompt: str | AsyncIterable[dict],
    options: ClaudeAgentOptions | None = None,
) -> AsyncIterator[Message]
```
- Creates a fresh subprocess per call; no memory across calls
- Streams `Message` objects: `SystemMessage`, `AssistantMessage`, `ToolUseBlock`, `ToolResultBlock`, `ResultMessage`
- Suitable for one-shot/stateless harness patterns (ReAct if manually managing message history)

### 2.2 `ClaudeSDKClient` — Stateful, bidirectional
```python
async with ClaudeSDKClient(options) as client:
    async for msg in client.query(prompt):
        ...
    async for msg in client.query(follow_up):
        ...
```
- Maintains the same subprocess across multiple `.query()` calls (context is preserved)
- Supports `@tool` decorator for in-process custom tools (in-process MCP servers)
- Supports lifecycle hooks (`PreToolUse`, `PostToolUse`, etc.) for deterministic injection
- Supports interrupt/cancellation
- Required for CodeAct (multi-turn code generation + execution within same session)

### 2.3 Key Message Types

| Type | Meaning |
|---|---|
| `SystemMessage` | Session initialized (ready signal) |
| `AssistantMessage` | Claude's response; `.content` is a list of `ContentBlock` |
| `TextBlock` | Reasoning / prose inside an `AssistantMessage` |
| `ToolUseBlock` | Tool invocation; `.name`, `.id`, `.input` (dict) |
| `ToolResultBlock` | Tool execution result; `.tool_use_id`, `.content` |
| `ResultMessage` | Terminal message; `.result` (str), `.usage` (token counts), `.total_cost_usd`, `.duration_ms` |

### 2.4 `ClaudeAgentOptions` Fields of Interest

```python
@dataclass
class ClaudeAgentOptions:
    system_prompt: str | None = None
    allowed_tools: list[str] = field(default_factory=list)
    disallowed_tools: list[str] = field(default_factory=list)
    permission_mode: PermissionMode | None = None   # "acceptEdits" | "default" | ...
    model: str | None = None
    max_turns: int | None = None
    max_budget_usd: float | None = None
    cwd: str | Path | None = None
    mcp_servers: dict[str, McpServerConfig] | str | Path = field(default_factory=dict)
```

### 2.5 Custom Tool Registration

```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool(name="search_web", description="Search the web", input_schema={"query": str})
async def search_web(query: str) -> dict:
    ...
    return {"results": [...]}

server = create_sdk_mcp_server(tools=[search_web])
# Pass server to ClaudeSDKClient(tools=[server])
```

---

## 3. Module Structure

```
eval_harnesses/
├── __init__.py                  # Public exports
├── base.py                      # BaseHarness ABC + shared types
├── codeact.py                   # CodeActHarness
├── react.py                     # ReActHarness
├── tools.py                     # Tool registry + helpers
├── events.py                    # Streaming event types
├── trace.py                     # Trace / run record types
└── exceptions.py                # Domain exceptions
```

---

## 4. Data Model

### 4.1 Streaming Events (`events.py`)

All events inherit from `HarnessEvent`. The harness emits these via an `AsyncIterator[HarnessEvent]` during a run. Callers iterate this to see real-time progress.

```python
@dataclass
class HarnessEvent:
    harness_id: str        # Unique run ID (UUID4)
    turn: int              # Current agent turn number (0-indexed)
    timestamp: float       # Unix timestamp (time.time())

@dataclass
class ThinkingEvent(HarnessEvent):
    """Partial or complete reasoning text from the model."""
    text: str
    is_partial: bool       # True if more text follows in the same turn

@dataclass
class ToolCallEvent(HarnessEvent):
    """The model has decided to call a tool."""
    tool_use_id: str
    tool_name: str
    tool_input: dict[str, Any]

@dataclass
class ToolResultEvent(HarnessEvent):
    """A tool execution has completed."""
    tool_use_id: str
    tool_name: str
    result: str | list     # Raw tool result content
    error: str | None      # Non-None if the tool raised

@dataclass
class CodeGeneratedEvent(HarnessEvent):
    """CodeAct only: the model emitted a code block for execution."""
    language: str          # e.g. "python"
    code: str

@dataclass
class CodeExecutedEvent(HarnessEvent):
    """CodeAct only: code was executed, result captured."""
    code: str
    stdout: str
    stderr: str
    exit_code: int

@dataclass
class TurnCompleteEvent(HarnessEvent):
    """A complete agent turn has finished."""
    assistant_text: str    # All text from this turn concatenated

@dataclass
class RunCompleteEvent(HarnessEvent):
    """The entire run has finished."""
    result: str            # Final ResultMessage.result
    usage: dict | None     # Token usage stats
    total_cost_usd: float | None
    duration_ms: int | None

@dataclass
class ErrorEvent(HarnessEvent):
    """An error occurred during the run."""
    error_type: str
    message: str
    recoverable: bool
```

### 4.2 Turn Record (`trace.py`)

```python
@dataclass
class ToolCall:
    tool_use_id: str
    tool_name: str
    tool_input: dict[str, Any]
    result: str | list | None
    error: str | None
    duration_ms: float

@dataclass
class TurnRecord:
    turn_number: int
    thinking: str          # All TextBlock content concatenated
    tool_calls: list[ToolCall]
    # CodeAct-specific
    code_generated: str | None    # The code block the model wrote
    code_stdout: str | None
    code_stderr: str | None
    code_exit_code: int | None
    # Timing
    started_at: float
    ended_at: float

@dataclass
class RunTrace:
    harness_type: Literal["codeact", "react"]
    harness_id: str
    prompt: str
    model: str | None
    system_prompt: str | None
    turns: list[TurnRecord]
    result: str | None               # Final answer from ResultMessage
    usage: dict | None               # Token usage from ResultMessage
    total_cost_usd: float | None
    total_duration_ms: int | None    # Wall clock from first SystemMessage to ResultMessage
    error: str | None                # Set if run terminated with an exception
```

---

## 5. Tool Registry (`tools.py`)

The module provides a lightweight registry that unifies built-in SDK tools and custom Python function tools.

### 5.1 `ToolSpec`

```python
@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any] | type    # Passed to @tool decorator
    fn: Callable[..., Awaitable[dict]] | None = None  # None = built-in SDK tool
    is_builtin: bool = False  # True = name passed to allowed_tools directly
```

### 5.2 `ToolRegistry`

```python
class ToolRegistry:
    def register_builtin(self, name: str) -> None:
        """Add a built-in Claude Code tool (e.g. 'Bash', 'Read', 'WebSearch')."""

    def register_custom(
        self,
        name: str,
        description: str,
        input_schema: dict | type,
        fn: Callable[..., Awaitable[dict]],
    ) -> None:
        """Register a Python async function as a custom in-process MCP tool."""

    def register_from_decorator(self, sdk_tool: SdkMcpTool) -> None:
        """Accept a tool already decorated with @tool from claude_agent_sdk."""

    def get_allowed_tools(self) -> list[str]:
        """Returns list of built-in tool names for ClaudeAgentOptions.allowed_tools."""

    def build_mcp_server(self) -> Any | None:
        """Builds and returns an in-process MCP server from registered custom tools.
        Returns None if no custom tools are registered."""
```

---

## 6. Base Harness (`base.py`)

```python
class BaseHarness(ABC):
    """Abstract base class for both harness implementations."""

    def __init__(
        self,
        tools: ToolRegistry | None = None,
        system_prompt: str | None = None,
        model: str | None = None,
        max_turns: int | None = None,
        max_budget_usd: float | None = None,
        permission_mode: str = "acceptEdits",
        cwd: str | Path | None = None,
        extra_options: dict | None = None,
    ) -> None: ...

    @abstractmethod
    async def run(
        self,
        prompt: str,
        *,
        stream_handler: Callable[[HarnessEvent], Awaitable[None]] | None = None,
    ) -> RunTrace:
        """Execute the agent loop for the given prompt.

        Args:
            prompt: The task/question to give the agent.
            stream_handler: Optional async callback invoked for every HarnessEvent
                            as it is emitted. Useful for real-time logging/display.

        Returns:
            A complete RunTrace capturing all turns, tool calls, and final result.
        """

    async def run_streaming(
        self,
        prompt: str,
    ) -> AsyncIterator[HarnessEvent]:
        """Alternative streaming interface: yields HarnessEvents as an async iterator.

        Completes when RunCompleteEvent or ErrorEvent is emitted.
        The RunTrace can be reconstructed from the event stream or retrieved via
        the last RunCompleteEvent.
        """
```

**Implementation note:** `run()` MUST be implementable in terms of `run_streaming()` (or vice versa). Specifically:

```python
async def run(self, prompt, *, stream_handler=None) -> RunTrace:
    trace_builder = TraceBuilder(...)
    async for event in self.run_streaming(prompt):
        trace_builder.consume(event)
        if stream_handler:
            await stream_handler(event)
    return trace_builder.build()
```

---

## 7. CodeAct Harness (`codeact.py`)

### 7.1 Concept

In CodeAct, the model is instructed to express its actions as Python code blocks. The harness detects code blocks in the model's text output, executes them, and feeds the output back to the model as an observation. This differs from standard tool-calling: **code execution is the primary action mechanism**, though named tools can also be registered and invoked by the generated code.

This maps naturally to the `ClaudeSDKClient` interface because the model's state (code variables, prior execution context) must persist across multiple exchanges.

### 7.2 Execution Model

```
Turn N:
  1. Claude emits TextBlock (reasoning) + optional ToolUseBlock or code fences
  2. Harness detects ```python ... ``` fenced blocks in the TextBlock
  3. Harness executes the code block in a sandboxed subprocess (or restricted exec)
  4. Harness feeds stdout/stderr/exit_code back via the session
  5. If no code block and no tool use → run ends with final answer
```

The harness maintains an **execution context** (e.g., a persistent namespace or subprocess) across turns within a single `run()` call.

### 7.3 System Prompt Requirements

The system prompt MUST include instructions that teach the model the CodeAct protocol:

- Always wrap executable actions in ` ```python ``` ` fences
- Use `print()` to emit results that the harness will observe
- Indicate completion with a final answer in prose (no code fence)
- Tools can be called from within code using their registered names (they appear as importable functions in the execution namespace)

The harness provides a sensible **default system prompt** that can be overridden.

### 7.4 Class Interface

```python
class CodeActHarness(BaseHarness):
    def __init__(
        self,
        tools: ToolRegistry | None = None,
        system_prompt: str | None = None,    # Overrides default CodeAct prompt
        model: str | None = None,
        max_turns: int | None = 20,
        max_budget_usd: float | None = None,
        permission_mode: str = "acceptEdits",
        cwd: str | Path | None = None,
        # CodeAct-specific
        code_executor: CodeExecutor | None = None,  # Pluggable executor (see §7.5)
        code_timeout_seconds: float = 30.0,
        extra_options: dict | None = None,
    ) -> None: ...

    async def run(self, prompt, *, stream_handler=None) -> RunTrace: ...
    async def run_streaming(self, prompt) -> AsyncIterator[HarnessEvent]: ...
```

### 7.5 `CodeExecutor` Interface

```python
class CodeExecutor(Protocol):
    async def execute(
        self,
        code: str,
        *,
        timeout: float = 30.0,
    ) -> CodeExecutionResult: ...

@dataclass
class CodeExecutionResult:
    stdout: str
    stderr: str
    exit_code: int
```

The module ships two built-in executors:

| Class | Mechanism | Notes |
|---|---|---|
| `SubprocessExecutor` | `asyncio.create_subprocess_exec` with `python -c` | Default; isolated per code block |
| `PersistentNamespaceExecutor` | `exec()` in a maintained dict namespace across turns | Allows variable persistence; less isolated |

The default is `SubprocessExecutor`. `PersistentNamespaceExecutor` is available for tasks requiring cross-turn state in variables.

### 7.6 Code Block Detection

The harness detects code using a regex pattern against `TextBlock.text`:

```
```python\n(?P<code>[\s\S]+?)\n```
```

Multiple code blocks in a single assistant turn are supported and executed sequentially; their combined output is returned as a single observation.

### 7.7 Tool Integration in CodeAct

When custom tools are registered:
1. The harness wraps each tool as a Python-callable injected into the executor's namespace (for `PersistentNamespaceExecutor`) OR exposes them via allowed MCP tools (for `SubprocessExecutor`).
2. The system prompt instructs Claude that tools are available as `tool_name(...)` function calls within code.

---

## 8. ReAct Harness (`react.py`)

### 8.1 Concept

ReAct (Reason + Act) alternates between the model emitting reasoning (Thought) and taking an action (Action) via a named tool call, after which the harness feeds back an observation (tool result), and the loop continues. The agent signals completion by emitting a final answer without tool calls.

This maps to the SDK's natural tool-use loop. The `ClaudeSDKClient` is used to maintain session context across turns.

### 8.2 Execution Model

```
Turn N:
  1. Claude emits TextBlock (Thought) + zero or more ToolUseBlocks (Actions)
  2. Harness executes each tool call, collecting results
  3. Results are fed back as ToolResultBlocks in the next user turn
  4. If Claude emits TextBlock only (no tool calls) → final answer, run ends
```

The SDK manages this loop internally when using `ClaudeSDKClient`; the harness observes the message stream and collects events without manually injecting tool results (the CLI subprocess handles tool dispatch for built-in tools; custom tools via in-process MCP are handled automatically).

### 8.3 System Prompt Requirements

The system prompt SHOULD structure the model's output into ReAct format. Default prompt instructs:

- Begin each response with **Thought:** — reasoning about what to do next
- If action needed, issue tool calls (Claude's native tool_use mechanism)
- When done, emit **Final Answer:** followed by the answer in prose

### 8.4 Class Interface

```python
class ReActHarness(BaseHarness):
    def __init__(
        self,
        tools: ToolRegistry | None = None,
        system_prompt: str | None = None,
        model: str | None = None,
        max_turns: int | None = 20,
        max_budget_usd: float | None = None,
        permission_mode: str = "acceptEdits",
        cwd: str | Path | None = None,
        # ReAct-specific
        final_answer_marker: str = "Final Answer:",   # Detect run completion from text
        extra_options: dict | None = None,
    ) -> None: ...

    async def run(self, prompt, *, stream_handler=None) -> RunTrace: ...
    async def run_streaming(self, prompt) -> AsyncIterator[HarnessEvent]: ...
```

### 8.5 Termination Conditions

A ReAct run terminates when any of the following occurs:

1. `ResultMessage` is received from the SDK (SDK-managed termination)
2. An `AssistantMessage` contains no `ToolUseBlock` and the text contains `final_answer_marker`
3. `max_turns` has been reached
4. `max_budget_usd` exceeded (SDK raises `BudgetExceededError`)
5. An unrecoverable error is raised

---

## 9. Streaming Requirements

Both harnesses MUST implement full streaming: events must be emitted **as soon as possible**, not batched at the end of a turn.

### 9.1 Event Emission Order Per Turn

```
ThinkingEvent (is_partial=True, may be multiple)
ThinkingEvent (is_partial=False, final text chunk)
ToolCallEvent  (one per tool use)
  ... tool executes ...
ToolResultEvent (one per tool use)
[CodeAct only]:
  CodeGeneratedEvent
  CodeExecutedEvent
TurnCompleteEvent
```

### 9.2 `run_streaming()` Contract

- Returns an `AsyncIterator[HarnessEvent]` immediately (no blocking before first event)
- Emits `RunCompleteEvent` as the final event on success
- Emits `ErrorEvent` as the final event on failure (does not raise)
- The iterator is exhausted after `RunCompleteEvent` or `ErrorEvent`
- Is **cancellation-safe**: if the caller cancels the iterator (e.g. `aclose()`), the underlying SDK session must be cleaned up

### 9.3 Partial Text Streaming

The SDK's `AssistantMessage` may arrive with full content per turn (the CLI buffers internally). However, the harness SHOULD attempt to split large text blocks into partial `ThinkingEvent` chunks (configurable `chunk_size` parameter, default 256 chars) to maintain the appearance of streaming to callers.

If the SDK supports streaming partial text in future versions, the harness should adopt that directly.

---

## 10. Error Handling

### 10.1 SDK Exceptions to Handle

| SDK Exception | Harness Action |
|---|---|
| `CLINotFoundError` | Raise `HarnessConfigError` immediately (not recoverable) |
| `ProcessError` | Emit `ErrorEvent(recoverable=False)`, end run |
| `CLIJSONDecodeError` | Emit `ErrorEvent(recoverable=False)`, end run |
| `asyncio.TimeoutError` (code execution) | Emit `ToolResultEvent(error="timeout")`, continue run |
| Generic `Exception` in custom tool | Emit `ToolResultEvent(error=str(e))`, continue run |

### 10.2 Domain Exceptions (`exceptions.py`)

```python
class HarnessError(Exception): ...
class HarnessConfigError(HarnessError): ...   # Misconfigured harness
class MaxTurnsExceeded(HarnessError): ...     # max_turns reached
class BudgetExceeded(HarnessError): ...       # max_budget_usd reached
class CodeExecutionTimeout(HarnessError): ... # Code block timed out
```

---

## 11. Configuration & Options Summary

All configuration is passed at construction time. Neither harness mutates shared state, so instances are reusable across multiple `run()` calls.

| Parameter | Type | Both | CodeAct | ReAct |
|---|---|---|---|---|
| `tools` | `ToolRegistry` | ✅ | ✅ | ✅ |
| `system_prompt` | `str` | ✅ | ✅ | ✅ |
| `model` | `str` | ✅ | ✅ | ✅ |
| `max_turns` | `int` | ✅ | ✅ | ✅ |
| `max_budget_usd` | `float` | ✅ | ✅ | ✅ |
| `permission_mode` | `str` | ✅ | ✅ | ✅ |
| `cwd` | `Path` | ✅ | ✅ | ✅ |
| `code_executor` | `CodeExecutor` | — | ✅ | — |
| `code_timeout_seconds` | `float` | — | ✅ | — |
| `final_answer_marker` | `str` | — | — | ✅ |

---

## 12. Public API Summary (`__init__.py`)

```python
from eval_harnesses import (
    # Harnesses
    CodeActHarness,
    ReActHarness,
    # Tools
    ToolRegistry,
    ToolSpec,
    # Executors (CodeAct)
    SubprocessExecutor,
    PersistentNamespaceExecutor,
    CodeExecutionResult,
    # Events
    HarnessEvent,
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
    CodeGeneratedEvent,
    CodeExecutedEvent,
    TurnCompleteEvent,
    RunCompleteEvent,
    ErrorEvent,
    # Trace
    RunTrace,
    TurnRecord,
    ToolCall,
    # Exceptions
    HarnessError,
    HarnessConfigError,
    MaxTurnsExceeded,
    BudgetExceeded,
    CodeExecutionTimeout,
)
```

---

## 13. Usage Examples

### 13.1 ReAct with built-in tools

```python
import asyncio
from eval_harnesses import ReActHarness, ToolRegistry

registry = ToolRegistry()
registry.register_builtin("WebSearch")
registry.register_builtin("WebFetch")

harness = ReActHarness(tools=registry, max_turns=10)

async def main():
    trace = await harness.run("What was the closing price of AAPL last Friday?")
    print(trace.result)
    print(f"Turns: {len(trace.turns)}, Cost: ${trace.total_cost_usd:.4f}")

asyncio.run(main())
```

### 13.2 ReAct with custom tool + streaming

```python
from eval_harnesses import ReActHarness, ToolRegistry

registry = ToolRegistry()
registry.register_custom(
    name="lookup_order",
    description="Look up order details by ID",
    input_schema={"order_id": str},
    fn=my_order_lookup_fn,   # async def my_order_lookup_fn(order_id: str) -> dict
)

harness = ReActHarness(tools=registry)

async def on_event(event):
    print(f"[{type(event).__name__}] {event}")

trace = await harness.run("What's the status of order #12345?", stream_handler=on_event)
```

### 13.3 CodeAct with persistent namespace

```python
from eval_harnesses import CodeActHarness, ToolRegistry, PersistentNamespaceExecutor

harness = CodeActHarness(
    tools=ToolRegistry(),  # no tools needed for pure code
    code_executor=PersistentNamespaceExecutor(),
    max_turns=15,
)

async for event in harness.run_streaming("Compute the first 20 Fibonacci numbers and plot them"):
    if hasattr(event, "code"):
        print(f"[CODE]\n{event.code}")
    elif hasattr(event, "stdout"):
        print(f"[OUT] {event.stdout}")
    elif hasattr(event, "result"):
        print(f"[DONE] {event.result}")
```

---

## 14. Testing Requirements

The module must include a `tests/` directory with:

- **Unit tests** for `ToolRegistry`, `TraceBuilder`, all event types, and code block detection regex
- **Integration tests** (skipped if `ANTHROPIC_API_KEY` not set) for both harnesses running against live API with a simple prompt and at least one tool call
- **Mock transport tests**: A `MockTransport` that replays a canned message sequence to test harness logic without API calls
- **Streaming tests**: Verify event ordering invariants (e.g. `ThinkingEvent` before `ToolCallEvent` before `ToolResultEvent` before `TurnCompleteEvent`)

---

## 15. Dependencies

```toml
[project]
requires-python = ">=3.10"

[project.dependencies]
claude-agent-sdk = ">=0.1.0"     # Bundled CLI; replaces deprecated claude-code-sdk
anyio = ">=4.0"                   # Async primitives

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-asyncio",
    "pytest-timeout",
]
```

> **Note:** `claude-agent-sdk` bundles the Claude Code CLI automatically. Node.js is **not** required at runtime. The SDK requires the `ANTHROPIC_API_KEY` environment variable.

---

## 16. Open Questions / Design Decisions

1. **Partial streaming fidelity**: The current SDK buffers full `AssistantMessage` per turn. If Anthropic adds streaming partial text in the CLI protocol, the harness should adopt it. Until then, the chunked `ThinkingEvent` split is a workaround.

2. **CodeAct sandbox security**: `SubprocessExecutor` gives the model access to a real Python interpreter. For evaluation in sensitive environments, consider using a containerized executor (e.g. Docker, Firecracker). The `CodeExecutor` protocol is deliberately pluggable to support this.

3. **Parallel tool calls**: Claude may issue multiple `ToolUseBlock`s in a single turn. Both harnesses should execute them **concurrently** (via `asyncio.gather`) where possible, subject to tool-level concurrency flags.

4. **Trace serialization**: `RunTrace` and all sub-types should be `dataclass`-based and serializable to JSON via `dataclasses.asdict()`. Consider adding a `.to_jsonl()` method for evaluation pipeline compatibility.

5. **Hooks for evaluation**: The `ClaudeSDKClient` supports hooks (`PreToolUse`, `PostToolUse`). The harnesses should expose an optional `hooks` parameter forwarded to the SDK, enabling evaluators to inject deterministic behavior or record low-level events.
