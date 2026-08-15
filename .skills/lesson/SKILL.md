---
name: lesson
description: >
  Project-local learning mode for Ms. Nancy. Use only when the user explicitly
  starts a request with `/lesson` or directly asks to use the lesson skill. Do
  not trigger for ordinary confusion, implementation, debugging, or explanation
  requests. This skill calibrates the user's current understanding, classifies
  the learning gap, proposes a concise practice-first plan, and only then
  creates lesson artifacts if the user approves.
---

# Lesson Skill

Use this skill as an explicit learning mode for the Ms. Nancy project.

This skill runs only when the user explicitly invokes `/lesson` or asks to use
the lesson skill.

## Purpose

Help the user become the technical owner of Ms. Nancy through practice.

The user learns best by doing. Prefer small exercises, toy projects, artifacts,
walkthroughs, debugging labs, and hands-on experiments.

## Workflow

### 1. Scope the lesson request

Identify what the user wants to learn from:

- a concept,
- a file or code path,
- a bug,
- an implementation the agent shipped,
- a hardware/audio topic,
- an architecture or product tradeoff,
- a decision that now feels unclear.

If the request references repo code, inspect the relevant files before asking
the user questions. Do not ask questions whose answers are visible in the repo.

### 2. Calibrate first

Before teaching or creating artifacts, ask direct calibration questions to gauge
the user's current understanding.

The questions can be hard. Prefer questions that reveal the actual gap:

- "Explain what a thread is in your own words."
- "What do you think can go wrong if two threads mutate the same buffer?"
- "Why would blocking speaker playback delay interruption?"
- "What do you think sample rate means?"
- "What is the difference between hardware latency and model latency?"
- "Which part of this design do you distrust?"

Wait for the user's answers before continuing. Do not create files before this
calibration step unless the user explicitly tells you to skip calibration.

### 3. Classify the gap

After calibration, classify the gap. The categories below are a starting point,
not a fixed taxonomy. Adapt when the topic does not fit.

- **Vocabulary:** a term or API name needs a short explanation.
- **Code mechanics:** Python, callbacks, loops, types, buffers, locks, async,
  threads, tests, or debugging mechanics.
- **System concept:** realtime streams, event loops, state machines, barge-in,
  VAD, memory, retrieval, observability, evals.
- **Hardware/audio:** microphones, speakers, Raspberry Pi, Linux services,
  sample rates, PCM formats, drivers, latency, wake activation.
- **Architecture/product tradeoff:** sequencing, local vs cloud, rented vs owned
  infrastructure, milestone scope, UX tradeoffs.
- **Debugging skill:** how to instrument, reproduce, isolate, and prove a fix.

State the classification briefly and name the smallest useful learning artifact.

### 4. Propose a concise plan

Before creating anything, propose a short lesson plan and wait for approval.
When the topic needs it, include a short conceptual bridge before the exercises:
enough reasoning for the user to understand what they are about to practice, but
not a full lecture.

A good plan is concrete and small:

- "One toy producer/consumer buffer exercise, then map it back to `audio.py`."
- "One artifact demo showing sample rate and PCM16, plus two prediction
  questions."
- "A code walkthrough of the event loop, then a TODO exercise that adds one
  event handler."
- "A debugging checklist and a tiny script that measures latency."
- "A short mental model for threads, then a tiny exercise that shows two flows
  touching shared state."

Avoid sprawling lessons. One concept per lesson unless the user asks for a
larger sequence.

### 5. Create practice-first artifacts

After approval, create the smallest artifacts that make the concept ownable.

Good artifact types:

- tiny Python exercises with TODOs,
- toy projects under `lessons/<topic>/`,
- artifact demos when visualization or interaction helps,
- annotated walkthrough markdown,
- debugging labs,
- small scripts that measure or expose behavior,
- decision worksheets for architecture/hardware tradeoffs.

Bias toward exercises and toy projects. Explanations should support practice,
not replace it.

### 6. Store lessons deliberately

Write lesson artifacts under `lessons/` by default:

- `lessons/exercise_<topic>.py` for a tiny one-file exercise,
- `lessons/<topic>/` for multi-file exercises, toy projects, demos, or notes.

Do not update `CLAUDE.md`, `specs/ROADMAP.md`, product code, or dependency files
unless the user explicitly asks.

### 7. Map back to Ms. Nancy

End every lesson by connecting the toy concept back to the product:

- which file or subsystem it explains,
- what bug or decision it helps with,
- what the user should now be able to reason about,
- what to inspect next if they want to go deeper.

### 8. Check ownership

Finish with a small ownership check:

- ask the user to explain the concept back,
- ask them to predict behavior before running code,
- ask them to modify the exercise,
- or ask one sharp tradeoff question.

The lesson is done when the user has practiced the idea and can connect it back
to Ms. Nancy.
