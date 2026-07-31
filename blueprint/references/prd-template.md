---
feature: <slug>
artifact: prd
version: 1.0
last_aligned: <today>
status: current
---

# PRD: <Feature Title>

**Version:** 1.0
**Date:** <today>
**Status:** Draft

<!-- Frontmatter rules:
     - `version` is the source of truth. Bump it whenever the requirements change.
       Minor bump (1.0 → 1.1) for clarifications, additions, edits that don't
       invalidate downstream work. Major bump (1.x → 2.0) for pivots —
       anything that makes the existing plan or build report wrong.
     - `status` is one of: current | superseded.
     - When you bump `version`, also update `last_aligned` to today's date.
     - The `pivot` skill bumps version automatically on a pivot. Manual edits
       should also bump (minor) to keep `plumb` honest. -->

## Stable Sections

<!-- IDs in headings (`§N.M`) are stable handles. Plans, reports, and bailiff
     checklists reference them. If you re-order sections, keep the IDs;
     don't recycle a deleted ID for a new section. -->

## 1. Overview

<What is this feature? Why is it needed? 2-3 sentences.>

## 2. Goals

- <Goal 1>
- <Goal 2>

## 3. Non-Goals

- <What this feature explicitly does NOT do>

## 4. Constraints

<!-- Include this section when the user provided specific constraints (API names, timeouts,
     field lists, service dependencies, etc.). Capture them verbatim so nothing gets lost.
     Omit this section if the user gave a high-level request with no hard constraints. -->

- <Constraint from user, e.g. "must call service X">
- <Constraint from user, e.g. "timeout ≤ 3s">
- <Constraint from user, e.g. "return fields: A, B, C">

## 5. User Stories / Use Cases

<!-- Optional. Most useful for user-facing features or complex workflows.
     Skip for simple internal APIs or service-to-service wiring. -->

1. <As a ..., I want ..., so that ...>

## 6. Technical Design

### 6.1 Data Flow

<How data moves through the system. Include a mermaid diagram if helpful.>

### 6.2 API / Interface

<New or modified endpoints, function signatures, proto messages, etc.>

### 6.3 Data Model

<!-- Optional. Include when new structs, tables, or stored data are involved.
     Skip for stateless pass-through APIs. -->

<New or modified data structures, database tables, etc.>

### 6.4 Dependencies

<External services, libraries, configs this feature depends on.>

### 6.5 Reuse & Existing Patterns

<!-- Important: document what you found in the codebase that this feature should reuse.
     This is especially valuable when the user gave a vague request — it shows
     how you arrived at the proposed design. -->

- <Existing service client / helper that can be reused>
- <Naming or structural pattern this feature should follow>
- <Similar feature in the codebase used as reference>

## 7. Error Handling

<How errors are handled. Fail-fast? Partial results? Retries?>

## 8. Open Questions

- <Question 1>
- <Question 2>
