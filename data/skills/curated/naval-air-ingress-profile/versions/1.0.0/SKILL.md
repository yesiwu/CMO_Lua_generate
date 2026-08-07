---
name: naval-air-ingress-profile
description: Use when choosing aircraft ingress altitude and approach profile for a naval-air anti-surface strike in contested air defense conditions.
---

# Naval-Air Ingress Profile

## Quick Reference
- Use ingress altitude as a controlled survivability and detection experiment.
- Keep the fixed aircraft state machine intact; modify only registered air-tactics parameters.

## When To Use
- Use when aircraft are detected or lost during approach.
- Use when comparing low-level and higher ingress profiles while preserving the same mission objective.

## Strategy Patterns
### Controlled Ingress Variation
- Alter ingress altitude while preserving target assignment and attack intent.
- Compare the resulting aircraft outcome, strike result, and official score against the same baseline.

## Counterexamples
- Do not alter unsupported route coordinates or Lua behavior to force an ingress result.
- Do not conclude that altitude caused an outcome when several air parameters changed together.
