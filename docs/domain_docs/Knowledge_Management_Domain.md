# LifeOS: Knowledge Management Domain
- At ingestion, a note should capture its Use/Purpose, which like "quick relevance"; a minimal capture of some "related to" relationship. This should reference some URI in the system
## What is Information
Information has Content and Structure; "Knowledge" is information with Context.
### Content
The text strings, bytes of data etc.

### Structure
What is the structure of the data, and what is the structure of its container?  This will inform the metadata collected and context expected; should it have a timestamp, is it my own words or someone else's, etc.

### Context
Information is contextualized in these ways: Relevance and Meaning. Relevance indicates what the content is related to, either within the Information domain (for example its Topic, like "Marriage") or within the Life, World, or Work domains (for example the Project "Get married" or some Person like my wife), while Meaning indicates the purpose a given piece of information serves within the wider environment (like my Marriage Certificate).

## What is Structure
A datum of information in this ontology is called a Resource. A Resource has only metadata. Resources with data include Notes and Documents, which are further divided into subtypes.
### Information Type
Information typically begins its life in a Note, and ends its life in a Document. A Document could be as simple as an array of Notes, or as complex as a novel (however unlikely).
For this reason, the structure of a Note is biased towards ease of ingestion, whereas a Document is structured to be used.
#### Resource
Has only metadata
#### Note
- Small amount of data to be incorporated into some Document directly or via synthesis; denotes information that is being ingested at a point in time, whether from my mind or from some other resource.
- What does the datum represent?
  - Log
  - Thought
  - Idea
  - Reference
  - Highlight

#### Document
Bigger container of data, or a Note "promoted"; denotes information that has graduated from intake.
- What type of Notes are in the container?
  - Journal
  - List of X
    - Inventory of objects/assets
    - Task list
  - Notebook, Logbook etc
  - ...
- Has a URI
### Media Type
- URL, Video, Transcript, Text
### Location
- Information System
- URL
### Sources
- URL[]
### Examples of metadata
- What content format is the data in?
- Where is the data located?
- Where did it come from?
- When was it created? Where? By whom? etc
## What is Relevance
What is this information **related to**, within the Life or Information domains (and any others).
### Life domain
- Use or Purpose
  - Memory (Continuity, Brain, Library)
  - Research
  - Experiment
  - Study/Thinking
  - Learning
  - Work - Project, Task
  - Change - Vision, Goal
- Links
  - Can be related to any entity, like a Project, Problem, Principle, Behavior, Goal, or a Subject or Topic thats assigned as an Area of Importance
### Information domain
- Links
  - Subject
  - Topic
  - Object/Asset
  - Concept

## What is Meaning
What does this informaiton **represent**?  While any Document can be related to a Project, a Problem, a Topic, or anything else, some documents have an "official" place within the system.

Examples are:
- the official project plan for project X
- the file where I keep a log of my medicine
- the list of all my Values
- the official document for Value X
- where I keep all information about App A
- where I keep track of apps I've installed on my iPhone
- a representation of State, or some Facts about the self or about something else
- explanation or reference of a Concept or Topic
- documentation for the Knowledge Management Domain (aka this file)


## Domains

---

## [Domain] Information

### [ Class] Resource

---

## [Domain] Y

---
