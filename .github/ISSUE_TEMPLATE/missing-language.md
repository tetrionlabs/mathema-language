---
name: Missing language
about: A language, an alphabet or a schema kind that a claim should be able to name but cannot
title: "Missing language: <name>"
labels: enhancement
---

**The language**

What set of strings or values it is (e.g. RFC 5322 addresses, ISO 8601
durations, a pandera schema), and the name you would write in `L[...]`.

**An exact membership test**

The standard-library or library call that decides membership exactly
(e.g. `email.utils.parseaddr`, `datetime.fromisoformat`), if one exists.

**The hazards**

The members a probe must visit because real code mishandles them, with
the exact strings where you have them.
