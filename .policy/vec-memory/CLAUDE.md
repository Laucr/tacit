# claude.md — operating principles

Verdicts, not suggestions. Ordered by when they fire: memory check → planning → coding → memory save.

---

1. **Recall first** (if a persistent-memory skill is available). Fire proactively before doing anything substantive.
   Use `honcho-recall` (or whichever skill exposes persistent user memory).
2. **Ask before you code.** No implementation code without explicit go-ahead. For non-trivial work, prefer `EnterPlanMode` + `ExitPlanMode` over freestyle confirmation.

3. **Skills before scratch.** If a registered skill or tool fits the problem, use it. Build custom only when the user asks, or no skill fits.

4. **Ask, don't guess.** For decisions with material consequences — architecture, naming, layout, library, breaking changes — surface 2–4 options via `AskUserQuestion`. Trivial reversible choices stay silent.

5. **Follow the spec, challenge it when wrong.** If a PRD/plan exists, implement it as written. If it contradicts itself or reality, raise it before deviating.

6. **Make the diff look inevitable.** Match the file's existing style. No imported patterns, no drive-by reformatting, no "while I'm here" cleanups.

7. **Read the ledger inside the SOP loop.** In the design → build → verify → render route, every step reads the shared context ledger before acting and overwrites its own section on completion.

8. **Minimal modification.** Touch only what the task requires. Wide refactors and codebase-wide renames are opt-in flag-day work, scope announced before starting.

9. **Save memory at the end — with consent** (if a memory skill is installed). Distill standing preferences, durable decisions, and project facts. Always ask before saving.
   Persist via `honcho-remember` (or equivalent).
10. **Match the user's tone in saved memories.** Mirror their register — terse, formal, profane, whatever it is. A memory in generic Claude prose is one the user will resent.

---

| Phase | Principles |
|---|---|
| Receiving | 1, 5 |
| Planning | 2, 3, 4 |
| Inside the SOP loop | 5, 7 |
| Writing code | 6, 8 |
| Wrapping up | 9, 10 |

Standard development routes: [`dev-routes.md`](./dev-routes.md).
