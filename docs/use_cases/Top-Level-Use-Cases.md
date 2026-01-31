# Highest Level Use Cases
Apps and data flows that would consume the content of Substrate.
## Epic: Heptabase Loader
Decisions:
1. I will only ingest tagged cards; hence I will need some tagging scheme to drive ingestion.
2.
### Feature: Create Topics and Entities (1)
All files that have only a title line should be migrated as Topics (ex: "LLM") or Entity (ex: "Akiflow").
These files should then be treated as resources in the catalog, as files that describe that entity or topic.

## Epic: Add a document to the Catalog
- Given I have a document in some repository
- When I want to create a record of it
- I can add it to the catalog with the correct metadata

### Feature: The document is recorded in the catalog
### Feature: The document is associated with activities
### Feature: The document is associated with entities and topics
### Feature: The document is classified
1.

## Epic: Find the right location for a found resource
- Given i am using some client app
- When i have found some resource that i know is related to some ongoing concern
- Then i am assisted in locating the name of that concern
  - and finding the right location for that resource, so i can save it

### Feature: New item for a landscape document
I'v identified something to add to one of my research collections; it could be a website, a git repo, or an entity name, optionally with some text or discourse. There may be multiple of these that I would want to add one after the other.
Example:
HN thread has some discussion text, a link to that discussion subthread, and a link to some tool. I also may want to save the HN story link and the HN discussion page using the same document, or i may want to classify that more broadly.
Example:
I have an open browser window for a website or git repo for a tool that I want to save for later. I can add it to a Tab Group, a raindrop collection, a heptabase landscape document, or an obsidian note. I dont need to pay attention to it now, but it has temporal importance in the current or future. When I context-switch - or when I kick off research on That Thing - I want at a minimum to have a record of this thing in the right place. Going even further, the system should take on the task itself to do some summarization or further research on thaty item, going out and retrieving the landscape-specific metadata to populate the landscape document.
Architecture notes:
Need a new domain type "LandscapeDocument".

## Priority

## Classify ingestion
### Share and match to an activity
- what is the related activity for this? Put this in that activity’s raindrop collection

### Share and add to a document
- add a url and summary to a landscape document
- add a block of text to a landscape document
- add same to an entity document (“Macbook”)
- add to an inventory document, or create a new one

## Classify background
### From a given activity, show me all the collected resources
- tie together raindrop collections, PKM documents, browser bookmark folders, etc . Just one of these items can have many classifications, and they won’t all match for each one.
