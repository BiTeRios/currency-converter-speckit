# Lab 3 desktop refresh and browser interface

The original desktop converter gains a clearer form, result, and rate provenance.
A separate browser interface lets users convert against the same official BNM source
and gives Selenium an end-to-end test target.

## Requirements

- FR-001. Keep the desktop entry point and its behavior contract. Use a light palette
  with a blue accent and a prominent result, effective date, and source.
- FR-002. Provide an independent local browser entry point at `127.0.0.1:8000`.
  Present a Russian-language form and result side by side on wide screens and stacked
  on narrow screens. Support visible focus and keyboard submission.
- FR-003. Default to today's date and USD to MDL when available. Support amount entry,
  both currency selectors, swap, date entry, Today, Convert, and Refresh. Disable
  Convert while loading or when the amount or a currency selection is missing.
- FR-004. Use the existing core for date and amount validation, decimal arithmetic,
  currency options, output formatting, rate loading, and cache persistence. Show
  both directions of the rate and handle equal currencies.
- FR-005. Keep selections when they still exist after a date change. Clear unavailable
  selections and request a new choice before converting. Identify the requested
  and effective dates when rates come from an earlier day.
- FR-006. On a source failure, show a readable error and a retry action. Offer the
  persisted rate and its date when available. The user must confirm before it becomes
  active. Recognize a damaged cache, and keep the application usable without a cache.
- SC-001. The existing unit suite and local Tkinter checks pass.
- SC-002. Selenium verifies live, fallback, and offline workflows using a deterministic
  XML source and temporary cache. Document separate unit and browser test commands.
