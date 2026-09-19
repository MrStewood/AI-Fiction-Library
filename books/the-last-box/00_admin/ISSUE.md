# Ghost in the Manuscript — Issue Log

Living document. Append dated entries as the controlled-test pilot runs.
Do **not** treat this as a mid-run workflow change list unless an issue is marked HARD BLOCKER.

**Pilot:** The Last Box (restart)  
**Slug:** `the-last-box`  
**Project:** `90e5d01f-e434-4bbc-8026-8a049d2af607`  
**Parent:** GHO-157  
**Kit commit (harness):** `0a528f2`  
**Seed commit:** `2460197` (local, not pushed)

**Canonical copy (survives project wipe):** `/srv/docker/paperclip/ISSUE.md`  
**Project mirror:** `_default/00_admin/ISSUE.md`

**Roster status (2026-09-19 ~00:00Z):** All 12 creative agents **paused** (ME, SA, SP, DA, DR, TRR, CR, RE, LE, FA, RS, Studio Admin). No further board work until fixes land and user resumes.

---

## Freeze snapshot (2026-09-19 ~00:00Z)

| Item | State |
|---|---|
| Parent GHO-157 | `in_review` + **pending `request_confirmation`** (`357b7a52-…`, “Approve to resume pipeline…”) |
| GHO-158 Intake | `done` |
| GHO-159 Creative Brief | `done` (verify-done PASS; DEC-003) |
| GHO-160 Git sync after Intake | `cancelled` (repo mirror read-only uid 1000) |
| GHO-161 Git sync after Brief | `cancelled` (Admin skipped correctly) |
| GHO-162 Premise | `blocked` (bare desc; SA run `d36700e7` lost in BOOK_TEMPLATE; Paperclip auto-blocked after no live path) |
| Creative Brief frontmatter | still `PROPOSED` (Decision Log says approved) |
| `CURRENT_STAGE.md` | `premise` / in_progress |
| `00_admin/book.yaml` | still `current_stage: "intake"` |
| Premise Package | empty template on write_root |
| Runtime `STUDIO_*` | still **not injected** into agent shells |
| Agents | **all paused** |

---

## Root-cause chain (investigation summary)

Almost every restart failure is **ops/runtime + stage-handoff**, not fiction quality.

```
ISS-001 (no STUDIO_* in agent shell)
   ├─► ISS-003 (env_exports circular — pack needs the env it claims to provide)
   ├─► ISS-002 / ISS-020 (relative CLI / raw-curl bare children)
   ├─► ISS-018 (agents abandon one-tool contract after first pack failure)
   ├─► ISS-023 (raw API thrash / empty bearer)
   ├─► ISS-006 / ISS-028 (Intake freestyle; no post-Brief handoff helper used)
   └─► ISS-024 (Premise assignee has no write_root → BOOK_TEMPLATE thrash)

ISS-004 (books/the-last-box root:root 755)
   ├─► ISS-017 (host seed commit ≠ agent push)
   └─► ISS-022 (ME re-issues sync after known permanent failure)

ME process gaps (HEARTBEAT / controlled_test)
   ├─► ISS-019 (brief parent → done)
   ├─► ISS-026 (parent in_review + request_confirmation)  ← ACTIVE PIPELINE STOP
   ├─► ISS-027 (todo↔backlog thrash)
   └─► ISS-021 / ISS-007 / ISS-025 (approval stamps, stage yaml drift, event unlock)

Watchdog blindness
   └─► ISS-005 (exit_healthy while sync fails / empty deliverable thrash)
```

**What worked when the contract was reachable:** GHO-159 Brief on absolute write_root + `verify-done --write-root` PASS; doubled-root guard; Admin cancel-with-comment on RO sync; intake handoff embeds when ME finally ran them with env.

---

## Open issues — investigation + exact address plan

### ISS-001 — Agent runtime has no `STUDIO_*` env (HARD BLOCKER)

- **Severity:** High / systemic  
- **Status:** Open (partial mitigation insufficient)

**Investigation**
- Paperclip `docker-compose.yml` injects only `PAPERCLIP_*` / OpenCode keys into the `paperclip` container. No `STUDIO_*`.
- Agent shells see `PAPERCLIP_API_KEY` (and related) but not `STUDIO_COMPANY_ID`, `STUDIO_PROJECTS_ROOT`, `STUDIO_API_URL`, `STUDIO_CLI`, `STUDIO_BOARD_TOKEN`.
- `expand_agent_instructions.py` injects a TOOLS **prose prelude** with `export …` lines into `adapterConfig.instructions.TOOLS`. That is documentation the model may type — **not** process environment inheritance.
- `studio pack` returns `env_exports` JSON, but pack itself requires those vars → circular (ISS-003).
- Confirmed this run: ME `create-issue` / pack failed `missing_env STUDIO_COMPANY_ID` then `projects_root_not_found`; SA Brief only succeeded after manually applying exports in-shell.

**Address plan (exact)**
1. Add to `docker-compose.yml` under `paperclip.environment` (agent-visible values, not host paths):
   - `STUDIO_PROJECTS_ROOT=/paperclip/instances/default/projects`
   - `STUDIO_COMPANY_ID=3120f492-32bb-4dbd-a698-2a062973f460` (or derive from seed)
   - `STUDIO_API_URL=https://mypuck.duckdns.org` (or `http://127.0.0.1:3100` if in-container)
   - `STUDIO_CLI=python3 /paperclip/repos/AI-Fiction-Library/tools/studio.py`
   - `STUDIO_REPO=/paperclip/repos/AI-Fiction-Library`
   - `STUDIO_BOARD_TOKEN` mapped from existing board secret **or** document that studio.py must accept `PAPERCLIP_API_KEY` as token fallback (preferred: code change in `studio.py` `_require_env` / token resolution: `STUDIO_BOARD_TOKEN || PAPERCLIP_API_KEY`).
2. Recreate/restart `paperclip` container; verify with a one-shot agent shell / debug run: `env | grep STUDIO_`.
3. Smoke: `studio pack --slug the-last-box --role story_architect --work premise` with **zero** manual exports.
4. Keep TOOLS prelude as backup docs only; do not treat it as the fix.
5. Acceptance: ME can run `studio handoff` / `create-issue` on first tool call without export dance.

---

### ISS-002 — Issue “first tool call” still uses relative `python3 tools/studio.py`

- **Severity:** Medium  
- **Status:** Open

**Investigation**
- `studio_cli()` falls back to `"python3 tools/studio.py"` when `STUDIO_CLI` unset.
- SA on GHO-159 ran relative path → `can't open file '.../companies/.../tools/studio.py'`. Absolute path only after TOOLS/`STUDIO_CLI`.
- Intake handoff embeds absolute CLI when env is set at handoff time; bare curl children (ISS-020) embed nothing.

**Address plan (exact)**
1. In `studio.py` `studio_cli()`: default to absolute agent path `/paperclip/repos/AI-Fiction-Library/tools/studio.py` when file exists; never emit bare `tools/studio.py` into issue text.
2. Audit `_assignment_desc`, `_sync_desc`, `intake_description`, pack `job.primary_command` — all must use `studio_cli()` / `$STUDIO_CLI`.
3. After ISS-001, regenerate any open child descriptions that lack absolute first-call (GHO-162).
4. Acceptance: grep board issue descriptions for `tools/studio.py` (relative) → zero hits on new issues.

---

### ISS-003 — Pack “apply env_exports first” is circular

- **Severity:** High (design)  
- **Status:** Open (resolved by ISS-001; text cleanup after)

**Investigation**
- Pack JSON instructs “Apply `env_exports` first”; pack cannot run without those exports.
- Agents waste turns discovering this.

**Address plan (exact)**
1. Ship ISS-001 (runtime injection) — primary fix.
2. Change pack guidance string from “apply env_exports first” to “env must already be in the process; env_exports is diagnostic/echo only.”
3. Optionally: pack soft-mode that prints bootstrap exports on `missing_env` without requiring API (local path-only), but prefer (1).
4. Acceptance: first creative heartbeat runs pack successfully with no prior export tool calls.

---

### ISS-004 — Git sync lane fails in-agent (permissions) and retries

- **Severity:** High (repeat)  
- **Status:** Open

**Investigation**
- Host: `/srv/docker/paperclip/AI-Fiction-Library/books/the-last-box` is `root:root` mode `755`.
- Container: `/paperclip/repos/AI-Fiction-Library/books/the-last-box` same. Agent uid 1000 cannot write (PermissionError on copy, e.g. `structure/BEAT_SHEET.md`).
- `start_book.py` has chown helpers gated on `STUDIO_RUNTIME_CONTAINER` — either not run or chowned wrong tree / wrong uid.
- GHO-160: Admin diagnosed RO, failed to PATCH `blocked` cleanly, cancelled. GHO-161: ME recreated sync anyway (ISS-022).

**Address plan (exact)**
1. **Immediate ops:** `chown -R 1000:1000` (or the paperclip agent uid) on host `AI-Fiction-Library/books/the-last-box` (and prefer `books/` parent for future seeds). Verify inside container as uid 1000: `touch …/books/the-last-box/.writetest`.
2. Fix `start-book` seed path: always chown seed book_root to agent uid after mkdir/copy; fail loud if chown skipped.
3. **Pilot policy (preferred until (2) proven):** host-only `studio git-sync` from orchestration shell; do **not** create in-agent Git sync children for controlled_test. Watchdog/ME: if last sync comment contains “read-only” / PermissionError, refuse new sync siblings.
4. When in-agent sync remains: on PermissionError → `blocked` (not cancel) + stop.
5. Acceptance: either agent `git-sync` exits 0, or board has exactly one `blocked` sync with ops note and zero recreates.

---

### ISS-005 — Watchdog reports `exit_healthy` while children fail / thrash

- **Severity:** Medium  
- **Status:** Open

**Investigation**
- Open failing sync / empty Premise still yielded `exit_healthy` / “no clear single mutation.”
- Does not weight: git-sync fail loops, empty deliverable + in_progress, BOOK_TEMPLATE-only reads, missing first-call embeds, env-missing pack loops, parent `in_review`+confirmation.

**Address plan (exact)**
1. Extend watchdog heuristics in `studio.py` watchdog / BOARD_WATCHDOG guidance:
   - Fail-open recommend intervene if any child title matches `Git sync` and last comment has PermissionError/read-only within N hours.
   - Flag deliverable path empty/template while assignee run age > threshold.
   - Flag issue description missing `First tool call` / `write_root`.
   - Flag parent `request_confirmation` when `controlled_test=true`.
   - Flag consecutive reads under `BOOK_TEMPLATE`.
2. Change recommendation enum: never `exit_healthy` if any of the above fire.
3. Acceptance: replay freeze snapshot → watchdog must recommend intervene, not healthy.

---

### ISS-006 — Intake completed without pack success or verify-done

- **Severity:** Medium (process)  
- **Status:** Open (disk content OK; contract not)

**Investigation**
- ME never got pack; hand-wrote intake artifacts; marked done via curl; no verify-done in log.
- Disk ledger/manifest/decision log were still good.

**Address plan (exact)**
1. After ISS-001: Intake description already embeds pack — enforce via soft gate.
2. Add `verify-done` requirement for Intake key artifacts (at least `REQUIREMENTS_LEDGER.md`) before ME may PATCH done — either in HEARTBEAT text or studio `done` helper.
3. Optional API/helper: `studio complete-issue --require-verify …`.
4. Acceptance: next Intake run log contains pack exit 0 + verify-done PASS before `done`.

---

### ISS-007 — `book.yaml` `current_stage` drifts from `CURRENT_STAGE.md`

- **Severity:** Low–Medium  
- **Status:** Open (active drift: stage=premise vs yaml=intake)

**Investigation**
- ME updated `CURRENT_STAGE.md` to premise; `00_admin/book.yaml` left at `intake`.
- Downstream tools that read yaml see wrong stage.

**Address plan (exact)**
1. In every `studio handoff --after <stage>` success path: write both `CURRENT_STAGE.md` **and** `book.yaml.current_stage` to the next stage.
2. Add watchdog drift check: if files disagree → intervene.
3. One-shot repair for this pilot (when unpausing): set yaml `current_stage: premise` to match CURRENT_STAGE (or re-run handoff).
4. Acceptance: after handoff, both files agree; freeze drift would be auto-detected.

---

### ISS-008 — ME zombie run after issue `done`

- **Severity:** Low–Medium  
- **Status:** Open

**Investigation**
- GHO-158 marked done while ME run `1510d834` continued; late file rewrites after done.

**Address plan (exact)**
1. HEARTBEAT / AGENTS: “If assigned issue already `done`/`cancelled` → EXIT immediately; no further disk writes.”
2. Prefer Paperclip behavior: finishing/cancelling run on terminal status (if API supports); else watchdog kill stale runs.
3. Acceptance: marking child done ends ME activity on that child within one heartbeat.

---

### ISS-009 — Wrong API field on comment (`content` vs `body`)

- **Severity:** Low  
- **Status:** Open (mitigate via helpers)

**Investigation**
- ME POST comment with `content` → validation error; `body` works.

**Address plan (exact)**
1. Prefer `studio` comment/status helpers exclusively in TOOLS (ban raw curl for comments when helper exists).
2. One-line TOOLS note: comments use `body`, not `content`.
3. Acceptance: no `content`-field comment errors in next run logs.

---

### ISS-010 — Doubled company-id workspace path (historical; guard shipped)

- **Severity:** High when active  
- **Status:** Mitigated in kit; depends on ISS-001 to be reached

**Investigation**
- Wrong `STUDIO_PROJECTS_ROOT=.../projects/<cid>` doubled path; Brief wrote off-canon.
- `validate_projects_root` hard-fail shipped in studio.py.

**Address plan (exact)**
1. Keep guard; ensure ISS-001 injects **parent** projects root (`/paperclip/instances/default/projects`), never `.../projects/<cid>`.
2. Document in studio.env comments; expander prelude already warns.
3. Acceptance: pack refuses doubled root; smoke pack lands files only under project `_default`.

---

### ISS-011 — False disk verification under `/tmp` or repos checkout (historical)

- **Severity:** High when active  
- **Status:** Mitigated; verified working on GHO-159

**Investigation**
- Wipe run: SA verified under `/tmp` and marked done; canon empty.
- Restart Brief: `verify-done --write-root` on absolute `_default` PASS.

**Address plan (exact)**
1. No further code unless regression; keep forbidden-path + section-emptiness gates.
2. Ensure Premise/Bible packs embed same verify-done command.
3. Acceptance: verify-done fails if file only exists under `/tmp` or `BOOK_TEMPLATE`.

---

### ISS-012 — Board approval parked controlled-test creative choices (historical)

- **Severity:** Medium  
- **Status:** Mitigated in constitution/pack; **regressed in spirit via ISS-026**

**Investigation**
- Wipe: board approval parked creative choice.
- Kit: `board_policy.allow_board_approval: false`; SA hard rules.
- Restart Brief: no board ask. ME later used `request_confirmation` for pipeline resume (ISS-026) — same class of stop.

**Address plan (exact)**
1. Extend ban from “creative board ask” to “any `request_confirmation` / parent park for stage continuation when `controlled_test=true`.”
2. Implement with ISS-026.
3. Acceptance: zero pending confirmations during controlled_test stage advances.

---

### ISS-013 — Duplicate Creative Brief / wrong deliverable path (historical)

- **Severity:** Medium  
- **Status:** Mitigated; verified this run (single GHO-159 via intake handoff)

**Address plan (exact)**
1. Keep `handoff --after intake` as sole Brief creator.
2. Extend same pattern for later stages (ISS-028) so ME never curl-duplicates.
3. Acceptance: one content issue per stage transition.

---

### ISS-014 — Scope jump before Brief approval (historical / watch)

- **Severity:** Medium creative-process  
- **Status:** Watch — Premise run read future templates (ISS-024), which is a precursor

**Address plan (exact)**
1. Pack/forbidden_paths: block reads/writes of later-stage templates until stage gate.
2. Watchdog: alert on `STORY_BIBLE` / `ENDING_DESIGN` / `BEAT_SHEET` access during premise.
3. Acceptance: Premise run never opens bible/ending templates.

---

### ISS-015 — Creative Brief under-locks the unspoken event

- **Severity:** Low–Medium (creative quality)  
- **Status:** Open

**Investigation**
- Brief names “the truth / family event” without locking event class; wipe-run over-locked abandonment. Controlled-test asked to self-lock assumptions.

**Address plan (exact)**
1. Add Brief checklist / pack mission bullet: lock unspoken-event **type** (1 sentence) OR Decision Log “deferred with single candidate X.”
2. Optional verify-done section presence check for “Unspoken event (locked)” heading.
3. Before resume: ME DEC amendment locking event class **or** force Premise issue to choose from one listed candidate.
4. Acceptance: Brief or DEC states event class before Premise `done`.

---

### ISS-016 — “Box neither will touch” risks object-as-MacGuffin

- **Severity:** Low (creative)  
- **Status:** Open

**Address plan (exact)**
1. Style note in Brief/Premise pack: box = catalyst/pressure, not puzzle inventory.
2. Craft-auditor flag: object-catalog / inventory drift.
3. Acceptance: Premise/Bible treat box as relationship pressure, not quest item list.

---

### ISS-017 — Seed git registration vs in-agent git-sync mismatch

- **Severity:** Medium  
- **Status:** Open (tied to ISS-004)

**Investigation**
- Host start-book committed seed `2460197`; agent cannot push; origin/main diverges.

**Address plan (exact)**
1. Same as ISS-004: fix ownership **or** host-only sync for pilots.
2. Registry should record “sync_pending_ops” vs fake success.
3. Acceptance: either agent push updates origin, or host sync is the only path and board doesn’t claim agent sync success.

---

### ISS-018 — One-tool contract abandoned after first failure

- **Severity:** High (behavioral)  
- **Status:** Open

**Investigation**
- ME: 3 pack env failures → freehand Intake + raw curl children.
- Pattern will repeat at every stage until ISS-001 + policy.

**Address plan (exact)**
1. ISS-001 first.
2. HEARTBEAT / ME SOUL: “On studio tool failure → comment + `blocked` (or EXIT); never freestyle board creates / status via raw curl.”
3. Watchdog: detect raw `POST /api/companies/.../issues` without preceding successful studio handoff in run → intervene.
4. Acceptance: next env failure produces blocked issue, not bare curl children.

---

### ISS-019 — ME briefly marked parent BOOK `done` during stage advance

- **Severity:** High (process near-miss)  
- **Status:** Open

**Investigation**
- Run `91d6ed6e`: PATCH GHO-157 → `done`, then ~12s later → `in_progress`. Violates Final-Auditor-only parent-done rule.

**Address plan (exact)**
1. ME HEARTBEAT hard rule: never set parent BOOK to `done` / `in_review` except release audit path.
2. If Paperclip allows: server-side or studio wrapper guard rejecting parent `done` unless title/role conditions met.
3. Acceptance: stage handoffs leave parent `in_progress` only.

---

### ISS-020 — Post-Brief handoff used raw curl, not stage handoff / create-issue

- **Severity:** High (contract regression)  
- **Status:** Open (caused GHO-161/162 bare descriptions)

**Investigation**
- ME tried `studio create-issue --work premise` twice (env fail / projects_root fail).
- Fell back to raw POST → GHO-161/162 one-line descriptions, no First tool call / write_root / verify-done.
- Contrast: GHO-159 from `handoff --after intake` had full `_assignment_desc`.

**Address plan (exact)**
1. ISS-001 so create-issue/handoff work.
2. ISS-028: implement `handoff --after creative_brief` (code currently lists the stage in `stage_handoffs` but **only implements `intake`** — other keys fall through to SCENE logic).
3. ME TOOLS: post-Brief path = exactly `studio handoff --slug … --after creative_brief`; forbid raw issue POST.
4. Repair this pilot: cancel/replace GHO-162 with handoff-created Premise (or PATCH description to full `_assignment_desc`).
5. Acceptance: Premise issue contains absolute write_root + pack first-call + verify-done gate.

---

### ISS-021 — Brief approved in Decision Log but frontmatter still `PROPOSED`

- **Severity:** Medium (canon hygiene)  
- **Status:** Open

**Investigation**
- DEC-003 approved; `CREATIVE_BRIEF.md` still `status: PROPOSED`, `approved_by: null`.

**Address plan (exact)**
1. Add `studio approve-artifact --path … --by managing_editor` (or fold into handoff): flip frontmatter `status/approved_by/approved_at`.
2. ME approval checklist: Decision Log entry **and** stamp file.
3. One-shot repair before resume: stamp Brief APPROVED to match DEC-003.
4. Acceptance: approved artifacts never remain PROPOSED after DEC.

---

### ISS-022 — Re-issuing git-sync after known permanent permission failure

- **Severity:** Medium  
- **Status:** Open

**Investigation**
- GHO-160 comments diagnose RO; ME immediately created GHO-161 “Repo may be read-only.”

**Address plan (exact)**
1. ME policy: if prior sync for slug is cancelled/blocked with PermissionError → do not create sibling; comment on parent “sync parked for ops.”
2. Watchdog refuse recommend-another-sync while blocker stands (ISS-005).
3. Host-only sync option (ISS-004).
4. Acceptance: at most one open sync issue per stage; no recreate without ownership fix note.

---

### ISS-023 — Wrong board API paths / auth thrash when marking done

- **Severity:** Medium  
- **Status:** Open

**Investigation**
- SA: `/api/companies/{cid}/issues/{id}` → 404; `/api/issues/{id}` works. Empty bearer from malformed Authorization.
- Admin: block PATCH validation failures before cancel.

**Address plan (exact)**
1. Prefer studio helpers for comment/status/done; TOOLS should not show company-scoped issue PATCH.
2. Token: auto-map `PAPERCLIP_API_KEY` → board token in studio.py (ISS-001).
3. Document canonical routes once in TOOLS.
4. Acceptance: closeout uses one studio helper call; no 404/empty-bearer loops.

---

### ISS-024 — Premise assignee exploring company `BOOK_TEMPLATE` instead of write_root

- **Severity:** High (wrong-home thrash)  
- **Status:** Open — GHO-162 now `blocked`; Premise still empty

**Investigation**
- SA run `d36700e7`: 16 consecutive reads under company workspace including `BOOK_TEMPLATE/{development,bible/…}` and company PROCESS docs. **Zero** project `_default` reads. Issue had no write_root. Paperclip later auto-blocked GHO-162 (no live execution path).

**Address plan (exact)**
1. Fix description via ISS-020/028 handoff embeds (absolute write_root + pack).
2. Pack `forbidden_paths` + watchdog alert on `BOOK_TEMPLATE` (ISS-005/014).
3. Before resume: replace GHO-162 description or recreate via handoff; clear blocked → todo only after embeds present.
4. Acceptance: first SA Premise tool call is `studio pack … --work premise` against project write_root.

---

### ISS-025 — ME approved Brief without locking unspoken event

- **Severity:** Low–Medium (creative process)  
- **Status:** Open (pairs with ISS-015)

**Investigation**
- DEC-003 cites word count + prompt consistency; no event-class lock.

**Address plan (exact)**
1. Brief approval checklist in ME HEARTBEAT: require ISS-015 lock or explicit deferred candidate in DEC.
2. Refuse handoff to Premise until checklist satisfied (soft: comment; hard: handoff preflight).
3. Acceptance: DEC before Premise contains event lock line.

---

### ISS-026 — ME parked parent with board `request_confirmation` (HARD BLOCKER / ACTIVE STOP)

- **Severity:** High / process stop  
- **Status:** Open — **pending confirmation still on GHO-157**

**Investigation**
- After spawning GHO-161/162, ME set parent `in_review` + `request_confirmation` (“Approve to resume pipeline after Creative Brief approval”). Controlled-test forbids board asks for continuation (ISS-012 class). Pipeline waits on human; Premise orphaned vs parent state machine.

**Address plan (exact)**
1. **Ops now (before any resume):** dismiss/cancel pending confirmation `357b7a52-…`; PATCH GHO-157 → `in_progress` (do not approve-as-workflow — we are fixing the habit).
2. ME constitution/HEARTBEAT: when `controlled_test=true`, never `request_confirmation`, never parent `in_review` for stage gates.
3. `studio handoff` already keeps parent `in_progress` on intake — replicate for all stage handoffs; add explicit “do not request_confirmation” in guidance JSON.
4. Watchdog: pending confirmation on controlled_test parent → intervene (ISS-005).
5. Acceptance: stage advances leave parent `in_progress` with children `todo`; zero confirmations.

---

### ISS-027 — ME thrash on Premise status (todo↔backlog) and sync disposition

- **Severity:** Medium  
- **Status:** Open

**Investigation**
- Run `91d6ed6e`: repeated PATCH GHO-162 todo/backlog; GHO-161 done→cancelled; inbox-lite polls; confirmation payload retries.

**Address plan (exact)**
1. HEARTBEAT: after successful child create / handoff → EXIT. No status flipping without new evidence.
2. Sync disposition only via Admin or `blocked`.
3. Acceptance: ME run ends within one heartbeat after handoff emit.

---

### ISS-028 — No implemented stage handoff after Creative Brief

- **Severity:** High (design gap)  
- **Status:** Open — **root of post-Brief regression**

**Investigation**
- `cmd_handoff` sets `stage_handoffs = {intake, creative_brief, premise, …}` but **only `if after_key == "intake"` is implemented**. Other stage keys fall through into SCENE handoff logic (wrong).
- ME invented “atomic handoff” via curl + confirmation → ISS-020/026/024.

**Address plan (exact)**
1. Implement stage map in `cmd_handoff`:

   | `--after` | Creates | Assignee |
   |---|---|---|
   | `creative_brief` | Premise Package + optional Git sync | SA (+ Admin) |
   | `premise` | Story Bible + optional sync | SA |
   | `story_bible` | Ending Design or Beat Sheet (per profile) | SA / SP |
   | … | mirror intake pattern | … |

2. Each content child: `_assignment_desc` with absolute CLI, write_root, pack, verify-done.
3. Always PATCH parent `in_progress`; never confirmation.
4. Update both CURRENT_STAGE.md and book.yaml (ISS-007); stamp prior artifact APPROVED (ISS-021).
5. ME TOOLS primary_command after Brief approve: `studio handoff --slug the-last-box --after creative_brief`.
6. Unit test: dry-run each stage key creates expected titles/roles.
7. Acceptance: Brief→Premise uses one handoff call; child descriptions match GHO-159 quality.

---

### ISS-029 — Premise auto-blocked after failed continuation (NEW)

- **Severity:** Medium (symptom of ISS-020/024)  
- **Status:** Open

**Investigation**
- At ~23:48Z Paperclip moved GHO-162 `blocked`: “retried continuation… no live execution path.”
- Follows SA thrash + ME status flipping + parent park.

**Address plan (exact)**
1. Do not wake into blocked bare issue.
2. After ISS-001/028: recreate Premise via handoff **or** unblock only after description repair + agent pause lifted intentionally.
3. Acceptance: Premise leaves blocked only with full assignment embeds and SA ready.

---

## Working well (do not regress)

1. `start-book --wake` auto-resume of paused ME (no HTTP 409 on restart).
2. Intake issue embeds pack + `handoff --after intake` + absolute write_root (when env present).
3. Handoff creates one Brief + one Git sync with first-call text.
4. Story Architect on **Brief** (GHO-159): correct write_root, verify-done PASS, no board ask, no scope jump.
5. Studio Admin on GHO-161: diagnosed RO, cancelled with clear comment — did not freestyle git.
6. Doubled-root guard + required-section emptiness checks (kit tests 14/14).
7. Roster pause/resume API path works (all 12 paused cleanly this freeze).

---

## Implementation order (before next unpause / wipe)

| Step | Issues | Work |
|---|---|---|
| 0 | — | Keep agents **paused**; clear pending confirmation on GHO-157; set parent `in_progress` (ops only). |
| 1 | **ISS-001**, ISS-003 | Inject `STUDIO_*` (+ token fallback) into paperclip runtime; smoke pack. |
| 2 | **ISS-028**, ISS-020, ISS-002 | Implement `handoff --after creative_brief` (+ later stages); absolute CLI defaults. |
| 3 | **ISS-026**, ISS-019, ISS-027, ISS-012 | ME HEARTBEAT/constitution: no parent done/in_review/confirmation; EXIT after handoff. |
| 4 | **ISS-004**, ISS-017, ISS-022 | chown book_root **or** host-only sync; stop sync recreates. |
| 5 | ISS-021, ISS-007 | Approval stamp + yaml stage sync inside handoff; repair Brief stamp + yaml for this pilot. |
| 6 | ISS-005, ISS-024, ISS-014, ISS-029 | Watchdog heuristics; repair/recreate GHO-162. |
| 7 | ISS-006, ISS-008, ISS-009, ISS-018, ISS-023 | Soft gates + helper-only board mutations. |
| 8 | ISS-015, ISS-025, ISS-016 | Creative event lock + box-as-catalyst notes (before Premise rewrite). |
| 9 | — | Unpause ME (+ SA as needed); run `handoff --after creative_brief`; monitor. |

**Not requested yet:** implementing the above. This log is the complete plan. Resume only after Steps 0–2 minimum (env + handoff + clear confirmation).

---

## Chronology (append-only)

### 2026-09-18 — Wipe run (project `51909d1d-…`, GHO-150–155)
- Paused roster blocked first `--wake` (409).
- Intake OK on disk; Brief wrong paths; false done; board approval parked; git-sync thrash.
- Ops notes lived under wiped project admin.

### 2026-09-18 — Redesign slice + wipe
- Shipped pack enrichment, verify-done hardening, intake handoff, start-book resume, TOOLS prelude, controlled-test board-ask ban (`0a528f2`).
- Restarted **without** true runtime env injection (accepted risk — became ISS-001).

### 2026-09-18 — Restart (project `90e5d01f-…`, GHO-157–160)
- Bootstrap OK; Intake disk good; handoff eventually succeeded with manual env.
- Pack fails until exports; relative CLI fails; git-sync fails; Brief correct + verify-done PASS.
- This log opened.

### 2026-09-18 ~23:40–23:46Z — Brief done; sync cancelled; Premise opened
- SA finished GHO-159 correctly; thrash on API routes before done.
- Admin cancelled GHO-160 (RO root-owned book_root).
- ME DEC-003; briefly parent `done`; raw-curl GHO-161/162 bare; CURRENT_STAGE→premise; yaml still intake; Brief still PROPOSED.
- Logged ISS-019…025.

### 2026-09-18 ~23:46–23:48Z — ME parks parent; Premise thrash
- Admin cancelled GHO-161 cleanly.
- ME: env create-issue fail → curl; parent `in_review` + pending confirmation; todo/backlog thrash.
- SA `d36700e7`: BOOK_TEMPLATE-only reads; Premise empty.
- Logged ISS-026…028.

### 2026-09-18 ~23:48Z — Premise auto-blocked
- Paperclip blocked GHO-162 (no live execution path). Logged ISS-029.

### 2026-09-19 ~00:00Z — Full freeze + plan complete
- User: pause all agents; complete ISSUE.md with investigation + exact address plans.
- All 12 creative agents paused.
- This revision: freeze snapshot, root-cause chain, ISS-001…029 each with Investigation + Address plan, implementation order Steps 0–9.

---



### 2026-09-19 ~00:50Z — Harness fixes + wipe + restart
- Implemented: STUDIO_* in paperclip compose (+ STUDIO_BOARD_TOKEN), board_token() fallback, absolute studio_cli via __file__, stage handoffs (intake→…→scene_outline), CURRENT_STAGE/book.yaml sync + artifact stamp, watchdog intervene heuristics, book_root chown wiring, ME controlled-test bans + Brief event-lock checklist.
- Unit tests: 16/16 OK (scrub clean).
- Wiped project `90e5d01f-…` (cancelled); cleared registry + books/the-last-box.
- Fresh start-book: project `46fa8bdb-…`, book_id `cd35e42f-…`, parent **GHO-163**, Intake **GHO-164**; ME run executing Intake; book ownership writable (chown_ok); in-container pack works with inherited STUDIO_*.

## How to update this file

When checking the pilot, append under **Chronology** and/or add/update **ISS-xxx** with:
- Found date / issue id / severity / status
- Investigation (evidence: run id, command, path)
- Address plan (exact steps + acceptance)
- Mitigation status (none / partial / shipped / verified in-run)

Keep host canonical and mirror into project `_default/00_admin/ISSUE.md` after substantive updates.
