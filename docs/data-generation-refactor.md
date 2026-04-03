# Data Generation Refactor Specification

## Overview

This application generates Salesforce data from NLP prompts, including parent-child and cross-object relationships. The current implementation has gaps that make same-run multi-object generation unreliable. This specification defines the required fixes, expected behavior, and acceptance criteria.

## Goal

Refactor and stabilize the synthetic data generation engine so it can reliably create records from NLP prompts while preserving all requested relationships, counts, and hierarchy. The system must work correctly for both existing-org references and newly created parent records in the same execution run.

---

## Phase 1: Core Relationship Fixes

### 1. Inject newly created parent IDs into the runtime cache immediately

#### Problem

Parent records are created successfully, but their returned Salesforce IDs are not added back into the generator relationship cache before child record generation starts.

#### Required fix

After each successful insert for an object:

* capture all returned Salesforce record IDs
* immediately update `generator.cache['record_ids'][object_name]`
* make these IDs available for downstream child generation in the same execution run

#### Expected behavior

If the prompt says:

* `Generate 10 Accounts and 5 Contacts linked to each Account`

Then:

* Accounts are inserted first
* returned Account IDs are immediately added to cache
* Contacts use these exact Account IDs without querying Salesforce again for the same batch dependency

#### Acceptance criteria

* Child generation in the same run uses newly created parent IDs successfully
* No dependency on SOQL read-after-write timing for same-batch parent-child relationships
* Fresh org execution works without child insert failure due to missing parent IDs

---

### 2. Remove fake Salesforce placeholder IDs completely

#### Problem

The current fallback inserts hardcoded fake IDs like `001000000000001AAA`, which always fail and hide the real root cause.

#### Required fix

Remove all hardcoded placeholder ID generation.

Replace with one of these valid behaviors:

* return `None` for unresolved references
* block generation for that dependent child record
* raise a structured dependency-resolution error

#### Expected behavior

If no valid parent ID exists:

* the system must not fabricate a relationship ID
* the system must surface a clear error such as:

  * `Missing Account reference for Contact.AccountId`
  * `Cannot generate child records because no valid parent IDs were available`

#### Acceptance criteria

* No fake Salesforce IDs are ever used anywhere in the generation flow
* Unresolved references fail explicitly and transparently
* API failures due to fabricated IDs are eliminated

---

## Phase 2: Preserve Relationship Topology From Prompt Intent

### 3. Build explicit parent-child assignment maps

#### Problem

Children are currently linked using random parent selection, which breaks user intent such as `5 Contacts per Account`.

#### Required fix

Before generating child records:

* interpret the requested relationship counts from the prompt
* build a deterministic parent-child assignment plan
* assign children to parents according to the requested structure, not random selection

#### Expected behavior

If the prompt says:

* `Generate 3 Accounts and 5 Contacts for each Account`

Then the system should:

* create exactly 3 Accounts
* create exactly 15 Contacts
* assign exactly 5 Contacts to each Account

Not:

* 15 Contacts randomly distributed across 3 Accounts

#### Acceptance criteria

* Requested child-per-parent distribution is preserved exactly
* Parent-child counts match prompt intent
* Random relationship assignment is not used when the prompt specifies structure

---

### 4. Introduce a relationship planning stage before execution

#### Problem

The current execution flow appears generation-first instead of plan-first.

#### Required fix

Add a pre-execution planning layer that:

* parses object counts
* identifies dependencies
* orders object creation topologically
* builds relationship mappings
* validates whether each dependency can be resolved

#### Expected behavior

For a multi-object request such as:

* `Generate 5 Accounts, 2 Opportunities per Account, and 3 Contacts per Account`

The planner should produce:

* object creation order: `Account -> Opportunity, Contact`
* expected total records
* per-parent assignment map
* dependency validation report

#### Acceptance criteria

* Every generation run produces a clear execution plan before inserts begin
* Parent objects are always generated before dependent child objects
* Relationship mapping exists before child record creation starts

---

## Phase 3: Strengthen Execution Flow

### 5. Refactor `execute_bulk_data_plan` to support cross-object cache updates

#### Problem

The execution engine tracks created IDs in results but does not update the generator relationship cache.

#### Required fix

Refactor `execute_bulk_data_plan` so that after each object insert:

* created IDs are written into the results structure
* created IDs are written into the generator cache
* created IDs are written into the relationship planner state

#### Expected behavior

The execution engine becomes the single source of truth for:

* what was created
* which IDs are available
* which downstream objects can now use those IDs

#### Acceptance criteria

* Newly inserted IDs are accessible to all downstream generation steps
* Cache state and execution results remain synchronized
* Same logic works consistently across prompt-based and GitHub or Snowfakery-based generation flows

---

### 6. Make object-selector generation relationship-aware

#### Problem

Manual object selection currently fills lookup fields from arbitrary org IDs without honoring user intent.

#### Required fix

For manual generation mode:

* detect lookup and master-detail dependencies
* allow explicit relationship-aware generation when related objects are part of the request
* only use existing org IDs when the mode explicitly allows external linking

#### Expected behavior

Manual generation should support two controlled modes:

* `Use existing references` from org
* `Create related records in this run` and use returned IDs

#### Acceptance criteria

* Manual generation no longer uses arbitrary relationship assignment without visibility
* Relationship behavior is predictable and configurable
* Manual and prompt-driven flows follow the same relationship rules

---

## Phase 4: Improve Validation and Error Reporting

### 7. Add structured dependency validation before insert

#### Required fix

Before creating child records:

* verify parent object count exists
* verify parent IDs are available
* verify required lookup or master-detail fields can be resolved
* verify relationship constraints are satisfied

#### Expected behavior

The system should fail early with actionable messages instead of failing late at the Salesforce API layer.

#### Acceptance criteria

* Missing dependencies are caught before insert calls
* Validation errors clearly name object, field, and reason
* Users receive actionable messages instead of generic `No data generated`

---

### 8. Propagate detailed per-object and per-record error messages to the UI

#### Required fix

Return structured result payloads that include:

* object name
* attempted count
* success count
* failure count
* created IDs
* failed record details
* field-level API error messages
* dependency and relationship warnings

#### Expected behavior

Users should be able to understand:

* what succeeded
* what failed
* why it failed
* whether the issue was data, dependency, permissions, or Salesforce validation

#### Acceptance criteria

The UI shows meaningful results such as:

* `Account: 10 created, 0 failed`
* `Contact: 0 created, 50 failed`
* `Reason: AccountId unresolved because no parent IDs were available in runtime cache`

---

## Phase 5: Testing and Verification

### 9. Add end-to-end test coverage for relationship generation

#### Scenario A: Same-batch parent-child generation

Prompt:

* `Generate 2 Accounts and 3 Contacts for each Account`

Expected:

* 2 Accounts created
* 6 Contacts created
* each Account has exactly 3 Contacts

#### Scenario B: Multi-level hierarchy

Prompt:

* `Generate 2 Accounts, 2 Opportunities per Account, and 2 Contacts per Account`

Expected:

* 2 Accounts
* 4 Opportunities
* 4 Contacts
* all children correctly linked to created Accounts

#### Scenario C: Missing parent dependency

Prompt:

* `Generate 5 Contacts linked to Accounts`

In a fresh org with no Accounts and no parent creation requested.

Expected:

* no fake IDs used
* clear dependency error returned
* no invalid inserts attempted with fabricated IDs

#### Scenario D: Existing-org reference usage

Prompt:

* `Generate 10 Contacts linked to existing Accounts`

Expected:

* valid existing Account IDs are used
* no fake IDs
* failure occurs only if no Accounts exist and should be clearly reported

#### Scenario E: Explicit distribution integrity

Prompt:

* `Generate 3 Accounts and 5 Contacts for each Account`

Expected:

* exactly 15 Contacts
* each Account has exactly 5 Contacts
* no random uneven distribution

#### Scenario F: GitHub or Snowfakery path

Expected:

* same runtime relationship behavior as prompt path
* same cache update logic
* same validation and error reporting

#### Acceptance criteria for testing

* All critical scenarios pass consistently
* No child generation depends on delayed Salesforce visibility of newly created parents
* No fabricated IDs are used
* Relationship counts and mappings match prompt intent exactly
* Failures are explicit, traceable, and actionable

---

## Required Code Changes Summary

### Must implement

1. Inject inserted parent IDs into `generator.cache['record_ids']` immediately
2. Remove all hardcoded fake ID fallbacks
3. Add relationship planning before execution
4. Replace random child-parent linking with deterministic assignment mapping
5. Refactor `execute_bulk_data_plan` to keep cache and results synchronized
6. Add pre-insert dependency validation
7. Return structured error details to the UI
8. Apply the same fixes to prompt flow, object-selector flow, and GitHub or Snowfakery flow

---

## Definition of Done

The implementation is complete only when:

* the application can create parent and child records in the same run
* newly created parent IDs are reused immediately without relying on SOQL fallback
* prompt-requested relationship topology is preserved exactly
* no fake IDs are generated anywhere
* all flows behave consistently
* errors are explicit and actionable
* end-to-end tests prove relationship integrity across simple, complex, and edge-case scenarios

---

## Instructions for Implementation

Read this specification and implement **Phase 1 only** first. Do not refactor everything at once. Show:

1. where the current issue exists
2. exact code changes
3. updated execution flow
4. how the change will be tested

After Phase 1 is complete and verified, proceed phase by phase.
