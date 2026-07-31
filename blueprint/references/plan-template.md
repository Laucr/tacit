---
feature: <slug>
artifact: plan
version: 1.0
prd_version: 1.0
last_aligned: <today>
status: current
---

# Plan: <Feature Title>

**PRD:** .claude/prds/<slug>.md
**Date:** <today>
**Status:** Draft

<!-- Frontmatter rules:
     - `prd_version` MUST equal the current PRD's `version` at the moment
       this plan was last reconciled. Drift-check compares them.
     - When the PRD pivots, this plan is stale. Either re-emit the plan
       (bumping `version`, syncing `prd_version`, refreshing `last_aligned`)
       or run the `pivot` skill which does it for you.
     - `status: superseded` when a newer plan version replaces this one. -->


## The Problem

<What we're solving and why the current state is insufficient. Be direct — name the pain. 2-3 sentences max.>

## The Approach

<How we're going to solve it. Lead with the decision, then explain the reasoning. If you considered alternatives, say what they were and why you rejected them — don't hide the thought process. Write this like you're explaining to a sharp colleague, not filling in a template.>

## The Work

<!-- Carmack-style task list. Use markers to track progress:
     *  = done
     +  = noted earlier, done later
     -  = decided against
     (no marker) = still open

     Group by logical phase. Each item should be one clear action.
     Add file paths and function names where they matter. Skip them where they don't. -->

### Phase 1: <Title>

<Brief rationale for why this phase comes first, if not obvious.>

- `path/to/file.go` — <what changes and why>
- `path/to/other.go` — <what changes and why>

### Phase 2: <Title>

- ...

## Trade-offs

<!-- Be honest. Name the downsides of this approach. If there's a performance cost, say so.
     If we're taking on tech debt, say so. If we're choosing simplicity over correctness
     in some edge case, say so. Then say how we'll deal with it (or that we accept it). -->

- <Trade-off 1: what it costs us, what we get, how we mitigate or accept it>

## Testing

<!-- What gives us confidence this works. Not a bureaucratic test plan —
     just: what do we check, and how. -->

- <What we test and how>

## Not Doing

<!-- Things we explicitly decided against or deferred, and why.
     Prevents future "why didn't you..." questions. -->

- <What we're not doing, and a one-line reason>
