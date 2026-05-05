---
engine: codex

network:
  allowed:
    - defaults
    - github

on:
  pull_request:
    types: [opened, synchronize]
    paths:
      - openapi_v5.yaml

permissions:
  contents: read
  pull-requests: read
  actions: read

safe-outputs:
  github-token: ${{ secrets.GH_TOKEN }}
  push-to-pull-request-branch:
    target: triggering
    labels: [sync]
    protected-files: fallback-to-issue
---

# Register newly-introduced services in cx-api-docs

## When this runs

Triggered by every PR that touches `openapi_v5.yaml`. Only does real work when the PR's head branch matches `facade-sync/*` (the branches opened by `.github/workflows/sync-from-facade.yaml`). For any other PR, exit cleanly without changes.

The `safe-outputs.push-to-pull-request-branch` handler additionally enforces the `sync` label on the triggering PR, so other PRs won't get bot commits even on a mis-detect.

## Why this workflow exists

`sync-from-facade.yaml` overwrites `openapi_v5.yaml` from `openapi-facade/may26/openapi.yaml` and runs `make build`, which regenerates `api-reference/v5/<service>/*.mdx` via `mintlify-scrape`. When the upstream spec introduces a **new service** (a new tag → a new directory under `api-reference/v5/`), two hand-authored gates aren't yet aware:

1. `service-overviews/<service>-overview.mdx` — the human-written landing page that `build_navigation_file.py:171-190` copies into each version's service dir as `overview.mdx`.
2. `build_navigation_file.py`'s `V5_SERVICES` dict (`build_navigation_file.py:63-65`) — services not listed there are silently dropped from `docs.json` nav (`build_navigation_file.py:120-121`).

Your job: detect any new services in the regenerated `api-reference/v5/`, fill in those gaps, and push a follow-up commit to the same PR.

## Instructions

### Step 1 — Trigger guard

Read `github.head_ref`. If it does not start with `facade-sync/`, stop. Output one line: `Skipping: PR head branch is <branch>, not a facade-sync/* branch.` and exit.

### Step 2 — Identify candidate services

List subdirectories of `api-reference/v5/`. Each subdirectory name is a service key (kebab-case, e.g. `actions-service`, `alert-definitions-service`).

### Step 3 — Identify what's already registered

Read `build_navigation_file.py`. Resolve `V5_SERVICES` (note: it is `{**V4_SERVICES}` which is `{**V3_SERVICES, ...}`) to the full set of currently-registered keys.

### Step 4 — Diff

For every directory under `api-reference/v5/` whose key is **not** in the resolved `V5_SERVICES` set, that's a candidate new service.

Filter out services that already have `service-overviews/<key>-overview.mdx` AND are missing only from the dict — those are an existing gap not caused by this sync. Still wire them up the same way (they're effectively "new to the nav"), but mention them separately in your final report.

**If the resulting list of new services is empty, stop. Do not push an empty commit, do not modify any files.** Output: `No new services to register.` and exit.

### Step 5 — For each new service, wire it up

#### 5a. Generate the overview MDX (only if missing)

If `service-overviews/<service>-overview.mdx` does **not** already exist, create it.

Source the content from `openapi_v5.yaml`:
- Find the OpenAPI `tag` whose name matches the service. `mintlify-scrape` buckets endpoints into directories using the `tags` field on each operation. The tag name → directory name mapping is the kebab-cased tag.
- Collect every operation under that tag with its `summary`, `description`, method, and path.
- If multiple tags or none match unambiguously, **skip this service** and list it under "ambiguous" in Step 8.

Match the shape of an existing overview — open `service-overviews/actions-service-overview.mdx` as the template:

```mdx
# <Service Display Name> overview

<2-3 paragraph description synthesized from the tag description and operation summaries. Explain what the service is for, what kinds of resources it manages, and any notable capabilities (batch ops, ordering, scoping, etc.).>


## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/...` | <summary> |
| ...    | ...  | ... |
```

Do **not** invent capabilities not evidenced by the spec. Keep the description grounded in operation summaries.

#### 5b. Update `build_navigation_file.py`

Add an entry to the appropriate dict — almost always `V5_SERVICES` directly (it spreads `V4_SERVICES`). Only add to `V5_SERVICES`. **Do not edit `V3_SERVICES` or `V4_SERVICES`** — those are frozen.

```python
'<service-key>': '<Display Name>',
```

- Display name = title-case the kebab-case key with spaces (e.g. `incidents-service` → `Incidents Service`, `quota-allocation-rule-set-service` → `Quota Allocation Rule Set Service`).
- Insert in alphabetical order by key.
- If `V5_SERVICES` is currently `{**V4_SERVICES}` only (no own entries), convert it to `{**V4_SERVICES, '<key>': '<Display Name>'}` and grow it from there.

### Step 6 — Build and verify

From the repo root:

```bash
make clean
make build
```

It must exit 0. The build will:
- Re-run `mintlify-scrape` (idempotent on the same spec).
- Re-run `python3 build_navigation_file.py`, which will now copy your new `service-overviews/<key>-overview.mdx` into `api-reference/v5/<key>/overview.mdx` and include the service in `docs.json` nav.

If `make build` fails:
- Python error in `build_navigation_file.py` you just edited → fix the obvious issue (trailing comma, wrong dict, key collision) and retry, up to 2 attempts.
- After 2 failed attempts, stop. Do not push. Leave a PR comment via `add-comment` (or the available commenting safe-output) describing what you tried and the error.

### Step 7 — Commit

Stage **only**:
- `service-overviews/<new>-overview.mdx` (one or more)
- `build_navigation_file.py`
- The regenerated `docs.json`
- The regenerated `api-reference/v5/<key>/overview.mdx` (whichever the `make build` step produced as a result of the new overview file)

Do **not** stage anything else under `api-reference/`, do **not** stage `openapi_v5.yaml`, and do **not** stage anything under `service-overviews/` you didn't create. The sync PR already owns those files.

Commit message:

```
Register <N> new service(s) from openapi-facade sync

Added: <comma-separated list of new service keys>
```

The `push-to-pull-request-branch` safe-output handles the actual push to the triggering PR's branch.

### Step 8 — Report

In your final response, output a brief summary:

- New services detected (count + list of keys), or "none — exiting".
- Files modified (list of paths).
- Build outcome (success / failure with one-line cause).
- Services skipped due to ambiguous tag mapping or other reason — flag for human reviewer.
- Any orphan-overview cases (overview MDX existed but service was missing from `V5_SERVICES`) — useful for the reviewer to know.

## Constraints

- **Do not touch** `openapi_v5.yaml`, `openapi_v4.yaml`, `openapi_v3.yaml`, or any `*.mdx` file under `api-reference/v{3,4,5}/<service>/` other than the regenerated `overview.mdx` produced by `make build` (and you don't write those by hand — they come from `python3 build_navigation_file.py` copying from `service-overviews/`).
- **Do not edit** `V3_SERVICES` or `V4_SERVICES` — only `V5_SERVICES`.
- **Do not edit** `introduction-v{3,4,5}.mdx`, `quickstart.mdx`, the use-case MDX files at repo root, `essentials/`, or `snippets/`.
- **Do not invent display names** for services with ambiguous spec tags. Skip and report instead.
- **Idempotency**: running this workflow twice on the same PR must produce no new commits the second time. Step 4's empty-diff exit guarantees this.
