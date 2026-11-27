---
name: pstack-blast-radius
description: "Check what an app or infrastructure change could break outside its immediate diff."
---

# Pstack blast radius

Adapted from pstack's blast-radius workflow.

Trace callers and consumers beyond the edited file. Check API payloads and browser state, model/tool contracts, environment variables, Secret keys, image tags, chart values, route names and identity headers. Inspect both routing modes when a shared chart field changes.

Report concrete failure scenarios and the affected flow. Distinguish a demonstrated regression from a plausible risk. Run a focused reproduction or acceptance test when execution is available. Do not add speculative layers or tests that repeat the implementation.

For auth changes, verify the anonymous, allowed-user and denied-user paths. For deployments, check rollout, health, upstream timeouts and rollback implications. Fix relevant failures within the authorized task and report external gaps precisely.
