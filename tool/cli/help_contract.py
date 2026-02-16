"""Help contract utilities for the `substrate` CLI."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json


@dataclass(frozen=True)
class HelpOption:
    """Represents one CLI option in the help contract."""

    flag: str
    value_type: str
    accepted_values: str
    default: str
    effect: str


@dataclass(frozen=True)
class HelpExample:
    """Represents one runnable help example."""

    title: str
    command: str
    expected: str


@dataclass(frozen=True)
class HelpLink:
    """Represents one related command reference."""

    command: str
    reason: str


@dataclass(frozen=True)
class SafetyContract:
    """Safety metadata for a CLI command."""

    side_effect_class: str
    idempotency: str
    confirmation_required: str


@dataclass(frozen=True)
class HelpOutput:
    """Output contract details for a CLI command."""

    stdout: str
    stderr: str
    help_json_schema: list[str]


@dataclass(frozen=True)
class HelpPayload:
    """Structured help payload for the `substrate` root command."""

    name: str
    summary: str
    when_to_use: list[str]
    when_not_to_use: list[str]
    safety: SafetyContract
    preconditions: list[str]
    usage: str
    arguments: list[str]
    options: list[HelpOption]
    output: HelpOutput
    exit_codes: dict[str, str]
    examples: list[HelpExample]
    see_also: list[HelpLink]

    def to_json_dict(self) -> dict[str, object]:
        """Return a stable JSON-serializable representation."""
        return {
            "name": self.name,
            "summary": self.summary,
            "when_to_use": self.when_to_use,
            "when_not_to_use": self.when_not_to_use,
            "safety": asdict(self.safety),
            "preconditions": self.preconditions,
            "usage": self.usage,
            "arguments": self.arguments,
            "options": [asdict(option) for option in self.options],
            "output": asdict(self.output),
            "exit_codes": self.exit_codes,
            "examples": [asdict(example) for example in self.examples],
            "see_also": [asdict(link) for link in self.see_also],
        }


HELP_JSON_FIELDS = [
    "name",
    "summary",
    "when_to_use",
    "when_not_to_use",
    "safety",
    "preconditions",
    "usage",
    "arguments",
    "options",
    "output",
    "exit_codes",
    "examples",
    "see_also",
]


def build_substrate_root_payload() -> HelpPayload:
    """Build the contract payload for `substrate` v0."""
    return HelpPayload(
        name="substrate",
        summary="Agent-first command surface for Substrate v0 help and planning.",
        when_to_use=[
            "You need machine-reliable command instructions for substrate workflows.",
            "You are deciding whether to use substrate or substrate-admin.",
        ],
        when_not_to_use=[
            "You need to run eval or search metrics now; use substrate-admin.",
            "You need destructive/indexing operations; use substrate-admin.",
        ],
        safety=SafetyContract(
            side_effect_class="read-only",
            idempotency="idempotent",
            confirmation_required="no",
        ),
        preconditions=[
            "No database, network, or service preconditions are required for v0 help surfaces.",
        ],
        usage="substrate [--log-level LEVEL] [--help] [--help-json]",
        arguments=[],
        options=[
            HelpOption(
                flag="--log-level, --debug-level",
                value_type="string",
                accepted_values="DEBUG|INFO|WARNING|ERROR|CRITICAL",
                default="CRITICAL",
                effect="Configure CLI logging verbosity.",
            ),
            HelpOption(
                flag="--help, -h",
                value_type="flag",
                accepted_values="true",
                default="false",
                effect="Print contract help in fixed section order.",
            ),
            HelpOption(
                flag="--help-json",
                value_type="flag",
                accepted_values="true",
                default="false",
                effect="Print machine-readable help contract JSON.",
            ),
        ],
        output=HelpOutput(
            stdout="Help contract text (`--help`) or JSON (`--help-json`).",
            stderr="Usage errors for unsupported arguments.",
            help_json_schema=HELP_JSON_FIELDS,
        ),
        exit_codes={
            "0": "success",
            "2": "usage or argument error",
            "130": "interrupted",
        },
        examples=[
            HelpExample(
                title="minimal success",
                command="substrate --help",
                expected="Print sectioned agentic help text.",
            ),
            HelpExample(
                title="machine-readable help",
                command="substrate --help-json",
                expected="Print JSON contract for automation and tooling.",
            ),
            HelpExample(
                title="failure mode",
                command="substrate search methods",
                expected="Exit 2 with guidance to use substrate-admin in v0.",
            ),
        ],
        see_also=[
            HelpLink(
                command="substrate-admin eval golden",
                reason="Run golden-query evaluation workflows.",
            ),
            HelpLink(
                command="substrate-admin search methods",
                reason="Run search method comparison metrics.",
            ),
        ],
    )


def payload_to_json(payload: HelpPayload) -> str:
    """Serialize a help payload to formatted JSON."""
    return json.dumps(payload.to_json_dict(), indent=2)


def render_text(payload: HelpPayload) -> str:
    """Render the help payload in the required section order."""
    lines = [
        "NAME",
        f"  {payload.name}",
        "",
        "SUMMARY",
        f"  {payload.summary}",
        "",
        "WHEN TO USE",
    ]
    lines.extend(f"  - {item}" for item in payload.when_to_use)
    lines.extend(["", "WHEN NOT TO USE"])
    lines.extend(f"  - {item}" for item in payload.when_not_to_use)
    lines.extend(
        [
            "",
            "SAFETY",
            f"  side_effect_class: {payload.safety.side_effect_class}",
            f"  idempotency: {payload.safety.idempotency}",
            f"  confirmation_required: {payload.safety.confirmation_required}",
            "",
            "PRECONDITIONS",
        ]
    )
    lines.extend(f"  - {item}" for item in payload.preconditions)
    lines.extend(
        [
            "",
            "USAGE",
            f"  {payload.usage}",
            "",
            "ARGUMENTS",
        ]
    )
    if payload.arguments:
        lines.extend(f"  {argument}" for argument in payload.arguments)
    else:
        lines.append("  (none)")
    lines.extend(["", "OPTIONS"])
    for option in payload.options:
        lines.append(
            "  "
            f"{option.flag}  {option.value_type}  {option.accepted_values}  "
            f"{option.default}  {option.effect}"
        )
    lines.extend(
        [
            "",
            "OUTPUT",
            f"  stdout: {payload.output.stdout}",
            f"  stderr: {payload.output.stderr}",
            "  --help-json schema:",
        ]
    )
    lines.extend(f"    - {field}" for field in payload.output.help_json_schema)
    lines.extend(["", "EXIT CODES"])
    for code, meaning in payload.exit_codes.items():
        lines.append(f"  {code}: {meaning}")
    lines.extend(["", "EXAMPLES"])
    for example in payload.examples:
        lines.append(f"  # {example.title}")
        lines.append(f"  {example.command}")
        lines.append(f"  # expected: {example.expected}")
        lines.append("")
    if lines[-1] == "":
        lines.pop()
    lines.extend(["", "SEE ALSO"])
    for link in payload.see_also:
        lines.append(f"  {link.command}  - {link.reason}")
    return "\n".join(lines)
