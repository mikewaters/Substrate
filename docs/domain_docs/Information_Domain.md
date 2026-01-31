# LifeOS: Information Domain
Information includes:
- Topics and Subjects
- Concepts
- Facts

useful things:

- dcterms:Location

- foaf:topic


- foaf:Project
- xsd:anyURI
- prov:wasDerivedFrom
- owl:equivalentClass when I want to redefine something internally http://www.w3.org/2002/07/owl#equivalentClass







## [Domain] Subject

---

## [Domain] Concept
skos:Concept
---

## [Domain] Facts
Models all the potential cross-cutting `Facts` that you may need to address or ignore.

### [Subdomain] Challenges
Adversities that impede one's ability to operate or evolve.

#### [Class] Problem
Description: Types of `Problems` are Stuggles, Worries, or Emergencies. Generally applies to the Organism, but can also apply to things in the World.
Properties:
- Title(str)
- Description(str) optional
- Source(reference to `World.Things.Object` instance) optional
- Target(reference to `Self.Organism` instance) optional

#### [Class] Risk
Description: Risks are also problems, but are hazardous to you or to your family. Each Risk may have an associated Hazard.
Properties:
- Title(str)
- Description(str) optional
- Affects(reference to `World.Things.Object` or `Self.Organism` instance) optional

### [Subdomain] Circumstances
Intrinsic states of some entity that can be construed as positive, negative, or neutral, but which can be resolved or mitigated given effort.

#### [Class] Condition
Description: The health of a thing
- Title(str)
- Description(str) optional
- Affects(`World.Things.Object` instance) optional

#### [Class] Hazard
Description: A dangerous thing that poses a risk.
- Title(str)
- Description(str) optional
- Cause(reference to `Facts.Circumstances.Hazard` instance) optional

#### [Class] Capability
Description: Abilities and limitations.
- Title(str)
- Description(str) optional
- Target(reference to `World.Things.Object` or `Self.Organism` instance) optional
