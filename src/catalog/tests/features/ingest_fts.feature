@skip
Feature: Ingest a corpus and search
  In order to verify search over ingested content
  As a catalog user
  I want ingested markdown notes to be discoverable via keyword queries

  Scenario: Ingest a corpus and search for a keyword
    Given the "vault-mini" corpus
    When I ingest the corpus
    Then the ingest result reports 4 documents created and 0 failures
    When I search for "python" with limit 10
    Then I should see at least 2 results
    And the result paths should include "note1.md" or "projects/project1.md"
