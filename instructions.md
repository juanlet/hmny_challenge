# Founding Engineer — Take-Home
*Build something real. Use AI. Show us how you think.*

---

## The gig

Build a **Document Extraction API** — a backend service that accepts an uploaded income
document, uses an LLM to extract structured data from it, and returns clean, validated
output. This is the core intelligence behind Harmony's applicant document processing
pipeline.

You've got **24 hours**. We expect **2–3 hours of actual work**. Use whatever AI tools
you want — Claude Code, Cursor, Copilot, whatever. We're not testing whether you can
type code. We're testing whether you can make good decisions fast, handle failure
thoughtfully, and understand what you shipped.

---

## What you're building

A property manager is tired of manually reviewing tenant income documents. You're
building the backend service that does the heavy lifting:

1. A tenant uploads a proof of income document (pay stub, offer letter, or bank
statement — any one doc is fine)
2. Your service uses an LLM to extract structured fields from the document
3. The API returns clean, validated output — or a clear, structured error if extraction
fails or the document is ambiguous

No frontend required. This is backend and AI integration only.

---

## Tech stack

| Layer | Use this |
|---|---|
| **Backend** | Python / FastAPI |
| **AI** | LLM-powered document extraction. We like [LangGraph](https://langchain-ai.github.io/langgraph/) for orchestration and [BAML](https://docs.boundaryml.com/) for structured LLM calls — not required, but if you know them, use them |
| **LLM** | Any provider (OpenAI, Anthropic, Groq, etc.) — configurable via environment variable |

Beyond that, use whatever libraries make sense. No database or frontend required.

---

## What we need to see

### The basics (must have)

**Document upload endpoint** — A `POST /submissions` endpoint that accepts a file upload
(PDF or image) and returns extraction results synchronously.

**LLM extraction** — This is the interesting part. Use an LLM to extract structured
fields from the uploaded document:
- `employer_name`
- `gross_income` (numeric)
- `pay_frequency` (weekly / bi-weekly / monthly / other)
- `income_period` (the date range or pay period the document covers)
- Any other fields you think are worth pulling

We're evaluating three things in this section: how you structure the prompt, how you
define the output schema, and how you handle low-confidence or malformed LLM responses.
There's no single right answer — but your DECISIONS.md should explain your choices.

**Failure handling — required, not optional** — This is as important as the happy path.
Your API must handle all three of the following cases with a structured, actionable
response (not a 500):

1. A required field cannot be extracted — the document doesn't contain it or it's
illegible
2. The LLM returns a value that fails schema validation (e.g. `gross_income` comes back
as a string like "three thousand dollars" instead of a number)
3. The uploaded file is not a supported format (non-PDF, non-image)

For each case, your API should return a consistent error shape that tells the caller
*what* failed and *why*, not just that something went wrong.

**Pydantic validation** — Clean input and output schemas. The API should reject bad
inputs gracefully and return well-typed extraction results.

**Tests** — Unit tests for your core extraction logic. Should run with `pytest` using
mocked LLM responses — no API keys needed to run the test suite. We want to see your
testing philosophy, not just coverage for coverage's sake. At minimum, write tests for
each of the three failure cases above.

**Commit history** — This is a must-have, not a nice-to-have. **Do not squash your
commits.** We want to see how you break down the problem, how you iterate, and how your
thinking evolves. A single "initial commit" tells us nothing. Frequent, focused commits
with clear messages tell us a lot.

### Bonus points

None of these are required. All of them would impress us.

- LLM fallback chain (if OpenAI fails, try Groq, etc.)
- Async extraction (return a job ID, process in background, expose a status endpoint)
- Structured logging
- Docker Compose setup that just works
- Strict type checking (Pyright / mypy)

---

## How we'll evaluate

**Extraction logic** — Are the prompts thoughtful? Does extraction actually work on the
sample document? How is the output schema defined, and does it constrain the LLM
appropriately?

**Failure handling** — Does the API behave predictably when things go wrong? Are error
responses structured and actionable, or vague?

**API design** — Clean endpoints, Pydantic schemas, proper error handling. Does the API
behave predictably?

**Code quality** — Readable, typed, handles errors, no obvious security issues (e.g.
unrestricted file types, no input validation).

**Does it run?** — Can we clone it and run it with a few simple commands? A working
README matters.

**Testing** — Do your tests actually test meaningful behavior? We'll run them ourselves.

**Velocity and process** — Your commit history is a first-class deliverable. We read it
like a narrative of how you think and work.

---

## Deliverables

1. **GitHub repo** (public or private — we'll send you the emails to invite if private)
2. **README.md** — how to run it, architecture overview, what AI tools you used, key
design decisions
3. **Working API** we can run locally against the sample document
4. **Commit history** — don't squash. Seriously. We read every commit.
5. **DECISIONS.md** — see below

### About DECISIONS.md

Short doc (1 page, bullets are fine) covering:

- **Why you built it this way.** What did you consider and reject? If we needed to add
a second document type (say, a government ID with different fields), what would you
change?
- **Where it's fragile.** What's the biggest shortcut you took? What breaks first in
production? What happens if someone uploads a 50-page PDF or a document in a language
other than English?
- **One thing you'd refactor.** Point to specific code, explain what's wrong, how
you'd fix it.
- **A judgment call you made under uncertainty.** Describe one decision where you
weren't sure what the right answer was. What did you consider, and what would have
caused you to go a different direction?

This is how we tell the difference between someone who understands their code and
someone who generated it and moved on.

---

## What happens next

If your submission advances, we'll do a **45-minute technical walkthrough:**

1. **Demo** (5 min) — show us the API working against the sample document
2. **Code walkthrough** (15 min) — screen-share your IDE, walk us through the
architecture and your extraction approach
3. **Live modification** (15 min) — we'll give you a constraint that creates mild
tension with your existing design. Something like: "The LLM provider you've been using
just went down — walk us through how you'd add a fallback to a second provider without
breaking the API contract." Use whatever tools you normally use, AI included.
4. **Discussion** (10 min) — your DECISIONS.md, how you'd scale this, how you work

Not a gotcha. Just a conversation about code you wrote.

---

## Logistics

- **Window:** 24 hours from when you receive this
- **Effort:** 2–3 hours
- **Questions:** Email zach@harmonyworks.com — asking good questions is a positive signal
- **Submit:** Reply with your GitHub repo link

---

## What we're really after

We're hiring a founding engineer. The core of Harmony's product is intelligent document
processing — collecting sensitive financial documents from applicants, extracting
structured data from them, and doing something useful with that data. This is not a toy
problem; it's the actual thing we're building.

We know 2–3 hours isn't enough to build a production system. We're not looking for
perfection. We're looking for someone who makes smart tradeoffs, handles failure cases
thoughtfully, and ships something we can reason about.

Good luck — we're excited to see what you build.