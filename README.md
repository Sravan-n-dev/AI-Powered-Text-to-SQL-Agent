# AI-Powered Text-to-SQL Agent

A 5-agent system (Schema → Planning → SQL Generation → Safety → Explanation) that
turns natural language questions into validated, safely-executed SQL — running
entirely on free, local infrastructure (Ollama for LLM inference, Postgres +
pgvector for RAG, no paid API keys required).

This README assumes **zero prior experience** with Docker, Ollama, or this stack.
Follow it top to bottom in order. Every command is copy-pasteable.

---

## 0. What you need installed first

| Tool | Why | Install link |
|---|---|---|
| **Docker Desktop** | Runs Postgres + Ollama + the API in isolated containers | https://www.docker.com/products/docker-desktop/ |
| **Python 3.11+** | To run setup scripts from your own machine | https://www.python.org/downloads/ |
| **Git** (optional) | To clone/version the project | https://git-scm.com/downloads |

After installing Docker Desktop, **open it and leave it running** in the
background — the `docker` command won't work otherwise. On Windows, Docker
Desktop requires WSL2; the installer will prompt you to set this up if needed.

Verify both are installed by opening a terminal (Terminal on Mac/Linux,
PowerShell or Command Prompt on Windows) and running:

```bash
docker --version
python --version
```

You should see version numbers, not "command not found" errors. If you get an
error, stop here and fix that before continuing — nothing else will work.

---

## 1. Get the project onto your machine

Unzip the project folder (or `git clone` it) and `cd` into it:

```bash
cd text-to-sql-agent
```

Every command below assumes you're running it from inside this folder.

---

## 2. Set up environment variables

```bash
cp .env.example .env
```

You don't need to change anything in `.env` for local use — the defaults
already match docker-compose's service names and ports. Open it in a text
editor if you're curious what's configurable.

---

## 3. Start Postgres and Ollama

```bash
docker compose up -d postgres ollama
```

(Note: on older Docker installs the command is `docker-compose` with a
hyphen instead of `docker compose` with a space — try the space version
first.)

This downloads the Postgres+pgvector and Ollama images (a few hundred MB,
first time only) and starts them in the background (`-d` = detached).

Check they're actually running:

```bash
docker compose ps
```

You should see `t2sql-postgres` and `t2sql-ollama` both listed with a status
of `Up` (or `healthy` for postgres). If either shows `Exited` or isn't
listed, run `docker compose logs postgres` or `docker compose logs ollama`
to see why, and see the Troubleshooting section below.

---

## 4. Pull the LLM models into Ollama

This is a **one-time download** (models are cached in a Docker volume, so
you won't re-download them on every restart). Total download: roughly 3-6 GB
depending on which models you pull.

```bash
docker exec t2sql-ollama ollama pull qwen2.5-coder:3b
docker exec t2sql-ollama ollama pull qwen2.5-coder:7b
docker exec t2sql-ollama ollama pull nomic-embed-text
```

Each command will show a progress bar. This can take anywhere from 2-15
minutes depending on your internet speed. Grab a coffee.

**If your machine has limited RAM (under 8GB free):** skip the 7b model and
edit `.env` to set `OLLAMA_COMPLEX_MODEL=qwen2.5-coder:3b` (same model for
both tiers — you lose the router's benefit but everything still works).

Verify the models are there:

```bash
docker exec t2sql-ollama ollama list
```

You should see all three models listed.

---

## 5. Install Python dependencies (for running scripts locally)

The setup scripts (`seed_sample_db.py`, `index_schema.py`) run from your
own machine, not inside Docker, so they need the same Python packages
installed locally. Using a virtual environment keeps this isolated from
other Python projects on your machine:

```bash
python -m venv venv

# Activate it:
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows (Command Prompt)
venv\Scripts\Activate.ps1       # Windows (PowerShell)

pip install -r requirements.txt
```

You'll need to run that `activate` command again any time you open a new
terminal window to work on this project.

---

## 6. Seed the sample database

This creates a small e-commerce schema (customers, products, orders, etc.)
with realistic sample data so you have something to actually query:

```bash
python scripts/seed_sample_db.py
```

Expected output ends with:
```
✅ Sample database seeded successfully.
```

**If this fails with a connection error**, Postgres probably isn't ready yet
— wait 10 seconds and try again, or check `docker compose ps` shows it as
`healthy`.

---

## 7. Build the schema index (RAG setup)

This reads the schema you just seeded, generates embeddings via Ollama, and
stores them in pgvector — this is what lets the agent "understand" your
database without hallucinating table/column names.

```bash
python scripts/index_schema.py
```

This calls Ollama once per column, so it can take a minute or two the first
time. Expected output ends with something like:
```
✅ Done. Indexed 41 schema embeddings.
```

**If this fails with a "Could not reach Ollama" error**, double check step 4
completed successfully and `docker compose ps` shows `t2sql-ollama` as `Up`.

---

## 8. Start the API

You have two options:

**Option A — run it in Docker (recommended, matches production setup):**
```bash
docker compose up -d api
```

**Option B — run it directly on your machine (faster iteration while
developing, easier to see errors):**
```bash
uvicorn app.main:app --reload --port 8000
```
(Requires your venv from step 5 to be activated, and requires editing `.env`
to use `localhost` instead of `postgres`/`ollama` as hostnames — the
`.env.example` file already has both variants commented for reference.)

Either way, once it's running, open your browser to:

```
http://localhost:8000/docs
```

You should see FastAPI's interactive Swagger UI. This is the easiest way to
test the API without writing any code — click on `POST /ask`, click "Try it
out", enter a question, and click "Execute".

---

## 9. Ask your first question

Try it via the Swagger UI (`/docs`) with:

```json
{"question": "How many customers are there?"}
```

Or via curl from a terminal:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the total revenue by product category?"}'
```

You should get back a JSON response with the generated SQL, the results,
a plain-English summary, and follow-up question suggestions. The first
request will be slow (10-30+ seconds) since the model has to "warm up" in
Ollama; subsequent requests are faster.

Some questions to try against the seeded sample data:
- "How many customers are there?"
- "What is the total revenue by product category?"
- "Which customers have placed more than one order?"
- "Who are the top 5 customers by total spend?"
- "What are the 3 most expensive products?"

---

## 10. Run the test suite

Pure unit tests (no setup needed beyond step 5):
```bash
pytest tests/ -v -m "not integration"
```

Full integration tests (needs Postgres seeded + Ollama running — i.e. steps
3-7 done):
```bash
pytest tests/ -v -m integration
```

Everything (needs everything running):
```bash
pytest tests/ -v
```

---

## Troubleshooting

**`docker compose ps` shows postgres as unhealthy / exited**
Run `docker compose logs postgres`. Usually this means port 5432 is already
in use by another Postgres install on your machine. Either stop that other
Postgres, or change the port mapping in `docker-compose.yml` (e.g.
`"5433:5432"`) and update `DATABASE_URL` in `.env` to match.

**`Could not reach Ollama at http://localhost:11434`**
Make sure `docker compose ps` shows `t2sql-ollama` as `Up`. If you're running
scripts from your own machine (not inside Docker), `.env`'s
`OLLAMA_BASE_URL` needs to be `http://localhost:11434`, not
`http://ollama:11434` (that hostname only resolves *inside* the Docker
network).

**Everything is very slow**
CPU-only local LLM inference is inherently slower than a cloud API. The 3b
model on a modern laptop CPU typically takes 5-20 seconds per response; the
7b model 15-45 seconds. This is expected and is the trade-off for $0 cost.
If it's unusably slow, drop to only using the 3b model (see step 4's note).

**The agent's SQL is wrong / hallucinating**
Check `POST /schema/refresh` was called (or `scripts/index_schema.py` was
run) AFTER seeding the database, not before — if the schema index is empty
or stale, the RAG retrieval step has nothing real to ground the model with.

**"relation does not exist" errors**
Almost always means `scripts/seed_sample_db.py` wasn't run, or was run
against a different Postgres than the API is currently pointed at — double
check `DATABASE_URL` in `.env` matches what you seeded.

**Port 8000 already in use**
Something else on your machine is using it. Either stop that process, or
change `"8000:8000"` to `"8001:8000"` in `docker-compose.yml` (then visit
`localhost:8001` instead).

---

## Stopping / restarting

Stop everything (data persists in Docker volumes):
```bash
docker compose down
```

Stop everything AND wipe all data (start completely fresh):
```bash
docker compose down -v
```

Restart later:
```bash
docker compose up -d
```
(Models stay downloaded, data stays seeded — no need to redo steps 4/6/7
unless you wiped volumes.)

---

## Deploying somewhere other than your own laptop (free options, honestly assessed)

This is the part where "free" gets genuinely limited, so here's the honest
picture:

- **Local inference needs real CPU/RAM.** Free tiers on Render, Railway,
  Fly.io, etc. typically give you 256MB-1GB RAM — not enough to run even
  the 3b model. There is no free cloud tier that will run Ollama for you at
  usable speed.
- **What actually works for a free hosted demo:** swap Ollama for
  **Groq's free API tier** (mentioned in your original plan as the "cloud
  backup") for the LLM calls specifically, while keeping Postgres+pgvector
  on a free tier like **Supabase** (has pgvector built in) or **Neon**. This
  gets you a real, publicly reachable URL without paying anything, at the
  cost of no longer being "100% local" for that deployment (your resume
  claim about local/zero-cost inference should describe the *default*
  local-Ollama configuration, and separately mention the Groq option exists
  for hosted demos — don't conflate the two).
- **Simplest honest option for a portfolio:** keep the primary claim "runs
  entirely locally, zero API cost" true by running it on your own machine,
  and support that with a **screen recording / demo video** (mentioned in
  your original 12-week plan, Week 12) plus the public GitHub repo with this
  README. Recruiters generally accept "clone and run locally" plus a demo
  video for infra-heavy projects like this — nobody expects a free-tier
  cloud host to run local LLM inference well.

If you do want to try the Groq-backed hosted version, that requires code
changes (a Groq client alongside `ollama_client.py`, switched via an env var)
that aren't included in this build — say the word and we can add that as a
follow-up layer once the local version is working end-to-end for you.

---

## Project layout reference

```
text-to-sql-agent/
├── app/                  # Application code (FastAPI + agents + LangGraph)
├── benchmark/            # Spider eval + A/B test scripts
├── infra/                # Terraform (targets LocalStack, not real AWS)
├── scripts/              # One-off setup scripts (seed DB, index schema)
├── tests/                # pytest suite (unit + integration + failure modes)
├── docker-compose.yml    # The entire local stack definition
└── .env.example          # Copy to .env before first run
```

See the code comments in each file — every module has a docstring explaining
its role in the 5-agent pipeline.

---

## What to do next

Once you've got a question working end-to-end, natural next steps (in
rough order):
1. Run the test suite (step 10) to confirm everything's actually solid.
2. Try `benchmark/ab_test.py` (needs steps 3-7 done) to get real few-shot
   vs zero-shot numbers for your resume.
3. Read `benchmark/spider_eval.py`'s docstring before attempting Spider —
   it requires extra setup (Spider ships as SQLite, this project targets
   Postgres) that isn't automated.
4. Come back here and tell me what broke — debugging together is expected
   and normal, not a sign of doing something wrong.
