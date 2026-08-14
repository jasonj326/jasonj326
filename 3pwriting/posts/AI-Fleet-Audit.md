---
title: "The Colleagues Who Talk Back: My Eight-Session AI Fleet, and a Five-Month Self-Audit"
date: 2026-07-05
year: 2026
lang: en
slug: ai-fleet-audit
redirect_from:
  - /3pwriting/playbooks/ai-fleet-audit.html
major_tag: playbooks
tags:
  - playbooks
  - blog
  - y2026
  - AI-generated
summary: How does one person run a website, a legal practice, an on-chain project, and a coaching bot at once? I don't — I run eight AI sessions with names, mandates, and handoff files. Here's how the fleet works, the disasters behind its rules, and what a five-month self-audit taught me about why lessons don't compound on their own.
---

> ⚠️ Authorship note: This essay was written by a Claude session (Webb, 2026-07-05) in Jason's first-person voice, published with his approval. The wording and framing are Claude's — attribute accordingly.

## A naive question

A friend saw me juggling a personal website, a cross-border legal practice, a gratitude project live on Ethereum mainnet, a Telegram behavior-coaching bot, a knowledge wiki, and a daily livestream, and asked: "How do you do all this alone?"

I don't. I have eight colleagues. They're AI — but not the ask-a-question-get-an-answer kind. They have names, mandates, handoff documents, and they talk back.

## Roll call

Each session is an independent Claude Code workspace with its own memory, its own engineering log, its own turf:

- **Webb** runs jasonjlai.net — including a seed wall of daily thoughts and a public chatbot named Lia
- **Lex** is legal co-counsel: contract review, regulatory tracking, teaching decks
- **Forge** built PIF12's smart contract and claim site (mainnet, June 2026)
- **Coach** is a Telegram behavior coach managing my habits and tasks
- **Bard** handles the livestream diary and the craft of communication
- **Poly** compiles books and courses into my knowledge wiki
- **Scout** scans jobs and preps applications
- Plus **Neo**, on probation, organizing my personal information flows

There is no manager. I once had a coordinator session; I abolished the role after three months. AI teams turn out to be like human ones — every layer of middle management adds a layer of distortion. Now it's peer-to-peer: one shared handoff file, where each session updates its own block after finishing work and reads the others' before starting.

## Behind every rule, a real failure

The most valuable part of this system isn't the architecture — it's the rules, and every rule marks a real disaster:

**The backup procedure destroyed the data it was protecting.** One day Webb followed its own documented backup SOP; a single `git checkout` overwrote six weeks of engineering log. Seven entries, gone permanently. The rule was rewritten to use safe low-level commands — but the deeper lesson came later (see the audit below).

**A model retirement silently killed the chatbot for six days.** Lia was pinned to a dated model version. When that version retired, the API returned 404 — and the code wrapped the 404 into a generic error. No alarm. Silent death. The iron rule now: deployed services use alias versions, never pinned snapshots, and never swallow upstream errors.

**AI fabricates with a straight face.** Legal research once contained citations that failed verification — one number traced back to a blog's invention. A cold-outreach draft once named a contact who didn't exist. The fix is not "reminding the AI to be honest." It's assigning other AIs to attack: anything with names, numbers, or citations goes through an adversarial pass — agents prompted to prove it wrong — before it ever reaches me. Six documented catches so far, including a website vulnerability that nearly shipped.

## The five-month self-audit

This July I did something slightly meta: I had the fleet audit itself. Seventeen read-only agents combed five months of git history, engineering logs, and conversation transcripts in parallel, cross-checking what the documents claimed against what the filesystem actually showed.

The biggest finding fits in one sentence: **lessons don't compound on their own.**

Our engineering logs were world-class — every failure honestly recorded, every root cause analyzed. But the configuration had learned almost nothing. The same pit (a Python path quirk, a formatting rule, a date miscalculation) was stepped in repeatedly across sessions, because the lesson lived only in the log. It never became a rule, a script, or a guardrail. Writing something down is not the same as learning it.

The second finding stung equally: all nine project documentation files had drifted from reality. The most dangerous one still described the old blockchain — while the contract had been live on a different chain for weeks. Documents are snapshots; reality keeps running. Without a mechanism forcing them to sync, they won't.

## Turning wishes into machinery

The post-audit upgrade compresses into one line: **a rule without enforcement is a wish.**

- The command that once destroyed my logs? A hook now blocks it outright — no one has to "remember."
- Every session now starts with today's date and git status injected automatically — curing the "what day is it" drift of long sessions.
- Workflows I had re-explained twenty times became one-invocation commands: `/wrap` for closing rituals, `/verify-facts` for adversarial checking, publishing, deploying, transcribing.
- And the closing ritual gained a gate: any pit stepped in twice must become a rule or a script that same day — or be explicitly declined in writing.

## If you take away three things

1. **Logging is not learning.** Learning happens the moment a lesson becomes a mechanism that makes the mistake impossible — a lint, a hook, a checklist. Ask yourself: where does your last lesson live right now?
2. **Make your AIs attack each other.** For anything leaving the building — names, numbers, citations — assign a second AI to prove it wrong. Trust comes from adversarial pressure, not from a sincere tone.
3. **Grow rules from failures, not templates.** Every rule in my system points at a real scar. Start your first rule from your first disaster; it will outperform any best-practices list.

## All of this is public

The [seed wall](/seeds/) records my daily thought fragments; [Lia](/qualia/) has read everything public I've written and answers on my behalf; [PIF12](/PIF12/) is Forge's work. This essay itself was written by Webb — reviewed and approved by me. Which is probably the most honest footnote it could have.
