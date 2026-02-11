# Ontology Software Design

## Principles

### Design for LLMs

Problems addressed:
- Agent needs to make inferences that should not be necessary; synonyms, terms of art that are unclear, not giving context up-front (requiring the agent to dig for it, and potentially be wrong)
- Context overwhelm, by sheer byte size
- Needing to keep many files in memory to accomplish a task

Problem-solving strategies:
- Locality of reference; code that needs to be changed together should be "close" to each other (this conflictsa with other patterns, and so is a tradeoff in some cases)
- Ubiquitous Language - Each interface should use, and the system should reuse, a single set of distinct terms that provide a shared understanding between the developer and the agent. This extends beyond terminology, to grammar; use the same sentence form
  - ref: https://docs.claude.com/en/docs/agents-and-tools/agent-skills/best-practices#use-consistent-terminology
  - ref: https://martinfowler.com/bliki/UbiquitousLanguage.html
  - ref: https://docs.claude.com/en/docs/agents-and-tools/agent-skills/best-practices#naming-conventions
  - [ ] README: https://www.scribbr.com/nouns-and-pronouns/gerund/
- Shallow, Layered abstractions: Reduce context usage and complexity by forcing the agent to use a well-defined interface, at whichever layer they are working at - and stay at that layer. Too many layers however are counter-productive, and agent may have context bloat or may avoid reading some important context
  - enable progressive context exposure anywhere possible for the agent using the codebase
- Reveal intent using Semantics - making it very clear with minimal context requirements what the outcome or use of a given abstraction is.
- clear responsibilities
- encode usage patterns into explicit functions rather than creating generic utilities


Problem-solving design choices:
- functions and classes embed meaning in the names (semantic packing),  This needs to remain consistent for each type of abstraction across the codebase. choose a format, like "service classes use gerund form (ubiquitous language)
- Keep finders small and intention-revealing (e.g., find_active_by_owner(ownerId)), but don’t let them become an ad-hoc query layer
4. Avoid deep layering

Other ideas:
- - Domain-specific languages

### Aligning Agents
defined in [[Framework.md]]
- use

## DDD Patterns
- Repository pattern for abstracting data implementation away from consumer
  -orm entities are not exposed, instead models are used in other layers
  - methods resemble a colleciton of a single aggregate root
  - repos are a persistenc eboundary, domain
- Aggregate roots - define subgraphs that typically need to be commited atomically
  - Across aggregates, you reference by ID (not object refs)
- Unit of work for ensuring aggregate roots/graph-related entities are updated within transactions, regardless of underlying data store
- cqrs-ish; system data model is complex and evolving, repositories must enforce domain-specific invariants across a graph and so commands must be strict. readers may use unique access patterns (direct access, graph traversal), and so we can deploy query services that can access orm objects
- service layer can aggregate commands across multiple aggregate roots (writes), or expose diverse query patterns for the same (reads)


Pydantic = validation & serialization.
Domain (attrs) = behavior & invariants.
ORM = persistence & identity.
dependency-injector
