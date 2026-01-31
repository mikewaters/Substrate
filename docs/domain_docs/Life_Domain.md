# LifeOS: Life Domain

## Domains

### The Self
The **Self** is the representation of your life, and the embodiment of your physical existence in the world. The Self domain models your `Organism` (the meat thing that carries your brain around), the beliefs you hold at any time which align and configure the way you move throughout the world, the behaviors that guide your actions as a result of those beliefs, as well as the changes you plan and implement in order to ensure continual alignment with those beliefs.

### The World
The **World** is the representation of everything that surrounds you that you are forced or choose to interact with. The World domain models your proximate environment, the physical objects that you interact with, and the other people that are in your life.

### Work
**Work** is the representation of how you choose to use your time (or "spend time-currency"). You have defined your beliefs and the changes that you want to make in your life, and the Work domain models the types of activities you engage in to achieve this - your Efforts.

### Facts
State is a domain representing **facts** about some entity within the other Life domains. Some classes have their own specific types or values for their state, others can be shared across classes.

Facts model the current state of existence at a moment in time. These are not within your direct control, but can be influenced by your choices. Every embodied thing has state: your organism has state (its health conditions, for example); the world has state (your house is painted blue, and a tree has fallen across the street); and your work has state (a project is overdue).

---

## [Domain] Self
Models your current state, your beliefs, how you operate your life, and how you define your future state.

### [Class, Singleton] Organism
Description: The meat thing. Your job is to maintain the health and effectiveness of your organism. Can only be one instance of an `Organism` in the LifeOS (for now).
Properties:
- Identity(`Self.Alignment.Identity` instance) optional
- Values[](array of `Self.Alignment.Value`) optional

### [Subdomain] Alignment
The configuration of your organism, the standards you have set - aka your Beliefs. Beliefs fall into two categories: Identity (singleton) and Vision (array).

#### [Class, Singleton] Identity
Your `Identity` is composed of Roles, Archetypes, and Areas of Importance. There can only one identity per `Organism` instance.
Properties:
- Roles optional
- Archtypes optional
- Areas of Importance optional

##### [Property] Roles
Description: The societal roles that are most important to you. You can embody multiple roles, and you can prioritize some roles higher than others (and even deprioritize those that get less important over time).
Examples of roles include: Hacker, Software Expert, Husband.
Data type: array of `Role` objects

###### [Type] Role
Properties:
- Title(str)
- Description(str) optional
- Priority(enum) optional

##### [Property] Archetypes
Description: Examples of individuals that you aspire to be like, either by description or by name.
Examples are "Stoic"
Data type: Array of `Archetype` objects

##### [Type] Archetype
Properties:
- Title(str)
- Description(str) optional
- Importance(str) optional

##### [Property] Areas of Importance
Description: This includes your personal Areas of Interest and Areas of Responsibility. These are references to `Subject`s or `Topic`s in the `Information` Domain (covered elsewhere).
Data type: Array of references to `Information.Subject` (external domain)

#### [Class] Value
Description: Value statements.
Properties:
- Title(str)
- Description(str) optional

### [Subdomain] Operation
Given you have defined your alignment - the standards by which you live your life - you need to implement those standards. To do this, you will define `Principles` that are based on your alignment, and follow `Behaviors` that will help you operate your life.

#### [Class] Principle
Description: List of principle statements.
Properties:
- Title(str)
- Description(str) optional

#### [Class] Behavior
Description: Physical manifestations, actual actions you define that help you live in alignment with your principles.
Properties:
- Title(str)
- Description(str) optional

##### [Subclass of `Behavior`] Method
Description: Specific manner in which you accomplish a type of task or goal
Properties:
- Technique(str) optional

##### [Subclass of `Behavior`] Process
Description: A sequence of steps or techniques
Properties:
- Steps(str) optional

##### [Subclass of `Behavior`] Routine
Description: A sequence of steps that is taken regularly
Properties:
- Steps(str) optional
- Repetition(str) optional

##### [Subclass of `Behavior`] Habit
Description: A habituated sequence of steps that is taken regularly
Properties:
- Steps(str) optional
- Repetition(str) optional
- Reinforcement(str) optional

### [Subdomain] Evolution
Given you are operating your life in alignment with your beliefs, you can look at the current state of your `Self` or the `World` around you and decide that you need to make some change. You need to set the future state of your `Organism`, your `Behaviors`, or even your Beliefs.

#### [Class] Vision
Description: A set of high-level future state assertions.
Examples: Achieve some big thing before the age of 60
Properties:
- Title(str)
- Description(str) optional
- Timeframe(str) optional

#### [Class] Goal
Description: A low-level statement of some change or outcome, in alignment with one or more `Vision`s, that specifies the desired outcomes and is time-bound.
Examples: Lose 20 punds by June
Properties:
- Title(str)
- Description(str) optional
- Timeframe(str) optional

#### [Abstract Class] Delta
Description: Specific individual changes that are desired, that can fall into two types:
1. Outcomes (State changes)
2. Actions (action or Behavior changes)
Examples: Lose weight, Feel better, Wake up earlier
Can be linked to a specific `Problem` (defined in the `State` domain)
Properties:
- Title(str)
- Description(str) optional
- CurrentState(str) optional
- TargetState(str) optional

#### [Concrete Class of `Delta`] Outcome
Description: A type of `Delta` that describes a target state

#### [Concrete Class of `Delta`] Action
Description: a type of `Delta` that describes doing something differently

---

## [Domain] Work
Models how you spend time-currency and engage in Effort.

### [Subdomain] Effort
Efforts are defined using a few types.

#### [Class] Task
Description: An individual item of work.
Properties:
- Title(str)
- Description(str) optional

#### [Class] Project
Description: Some set of tasks and outcomes that you are spending time on
Properties:
- Title(str)
- Description(str) optional

#### [Abstract Class] Activity
Description: Something that can be done.
Properties:
- Title(str)
- Description(str) optional

#### [Concrete Class of `Activity`] Experiment
Description: "Just fooling around", a type of `Activity`.

#### [Concrete Class of `Activity`] Research
Description: In preparation for work, you need to spend time figuring out how to approach a problem. A type of `Activity`.

#### [Concrete Class of `Activity`] Study
Description: You spend specific directed effort learning some new thing. A type of `Activity`.

#### [Concrete Class of `Activity`] Thinking
Description: You spend time creating mental models of life and the world in order to understand it better. A type of `Activity`.

---

## [Domain] World
Models all the embodied things outside of you - phycial or digital.

### [Subdomain] Things
The domain of embodied objects in the world.

### [Abstract Class] Object
Description: A Thing in the world
Properties:
- Title(str)
- Description(str) optional

#### [Concrete Class of `Object`] Physical object
Description: A type of `Object`.

#### [Concrete Class of `Object`] Digital object
Description: A type of `Object`.

### [Class] Asset
Description: Representation of an object (physical or virtual) that you are using for some reason, maybe you have purhcased it or you find yourself with it.
Example: Bicycle, Home, Power Drill, Task management app
Properties:
- Object(reference to `World.Things.Object` instance)
- Usage(str): instructions on how to use an asset. Will be stored using the `Knowledge` domain (found elsewhere). optional
- Age(int) optional

---
