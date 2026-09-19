# Ghost in the Manuscript — Issue Log (current run)

Living document for **this** controlled-test run only.  
Prior wipe-run issues are **not** carried forward; fixed items are noted briefly under “Verified fixed,” then we only log what is abnormal **now**.

**Pilot:** The Last Box  
**Slug:** `the-last-box`  
**Project:** `46fa8bdb-1307-4083-85a7-ea26cb13144e` (`SHORT — The Last Box`)  
**Parent:** GHO-163  
**book_id:** `cd35e42f-5e5d-4046-b80b-e8780a33fb20`  
**Workspace:** `/paperclip/instances/default/projects/3120f492-32bb-4dbd-a698-2a062973f460/46fa8bdb-1307-4083-85a7-ea26cb13144e/_default`

**Canonical copy:** `/srv/docker/paperclip/ISSUE.md`  
**Project mirror:** `_default/00_admin/ISSUE.md`

---

## Snapshot (2026-09-19 ~01:21Z)

| Item | State |
|---|---|
| GHO-163 parent | `in_progress`, no pending confirmation, `blockedBy=[]` |
| GHO-164 Intake | `done` |
| GHO-165 Creative Brief | `done` (disk APPROVED; event class locked) |
| GHO-166 Git sync after intake | `done` (commit `86eb477`, push success) |
| GHO-167 Premise | `done` (634 words; verify-done PASS; frontmatter still PROPOSED) |
| GHO-168 Git sync after creative_brief | `in_progress`, **assignee = Managing Editor** (was Studio Admin) |
| GHO-169 Ops README ownership | `in_progress` → Studio Admin (bare description) |
| `CURRENT_STAGE.md` / `book.yaml` | both `premise` (aligned) |
| Creative Brief | APPROVED + DEC-001 event lock + box-as-catalyst |
| Premise Package | content complete; still `PROPOSED` |
| Next expected | approve Premise → `handoff --after premise` → Story Bible |
| Live agents | ME + Studio Admin running; others idle |
| Watchdog now | `intervene` (`bare_issue_description:GHO-169`) — not `exit_healthy` |

---

## Verified fixed (vs prior wiped runs) — do not re-litigate

These previously blocked the pipeline and are **working in this run**:

1. **Runtime `STUDIO_*` injection** — present in `docker-compose.yml` / container (`STUDIO_PROJECTS_ROOT`, `STUDIO_COMPANY_ID`, `STUDIO_CLI`, `STUDIO_BOARD_TOKEN`, …). Pack/handoff/git-sync run without the old circular export dance.
2. **`handoff --after creative_brief`** — implemented via `STAGE_HANDOFF_NEXT`; created GHO-167 (full embeds) + GHO-168.
3. **Absolute write_root embeds** on Brief/Premise children; Premise run wrote the real `_default` path (no empty template / no wipe-run wrong-home success).
4. **Book-root ownership** for `books/the-last-box` — writable (`puck`/`node`); **intake sync GHO-166 succeeded**.
5. **No board `request_confirmation` park** on GHO-163 (prior confirmation on wiped parent was rejected; this parent has none).
6. **Brief approval hygiene** — frontmatter `APPROVED` + DEC-001 locks unspoken event class + box-as-catalyst (prior under-lock / PROPOSED drift).
7. **Stage file drift** — `CURRENT_STAGE.md` and `book.yaml` both say `premise` after Brief handoff.
8. **Watchdog** — currently recommends `intervene`, not false `exit_healthy`, for bare GHO-169.

---

## Decision-by-decision (this run)

### 1. Bootstrap / start-book → GHO-163 + GHO-164 — **good**
New project `46fa8bdb…`, controlled_test, Intake assigned to ME with write_root. Parent left for production (not parked).

**Abnormal:** Intake description still embeds relative `python3 tools/studio.py` (see ISS-001). Project board status is `backlog` while work is active (ISS-010).

### 2. ME Intake (run `90cf2451`) — **mostly good**
- First pack used relative CLI → `can't open file '/app/tools/studio.py'` → recovered with absolute `/paperclip/repos/...`.
- Pack succeeded; `verify-done` on Requirements Ledger; `handoff --after intake` created GHO-165 + GHO-166.
- Parent left `in_progress`. Intake marked `done` with evidence.

**Abnormal:** burned first steps on relative CLI (ISS-001). Mentions of BOOK_TEMPLATE in log noise only — no wrong write observed.

### 3. SA Creative Brief (GHO-165, runs `2bd1e5c5` → `c6252c91` → status-reconcile wakes) — **good content, noisy closeout**
- Wrote `development/CREATIVE_BRIEF.md` (~1021 words) on write_root; verify evidence posted.
- DEC-001 locks event class (parental confession/disclosure never fully addressed) and box-as-catalyst.
- Later wakes found board status flapping `done`/`in_progress` and re-reconciled; finally exited on `done`.

**Abnormal:** status echo / zombie wakes after done (ISS-002). DEC-001 still says “Approving authority: pending Managing Editor” while Brief frontmatter is already ME-approved (ISS-007).

### 4. Admin Git sync after intake (GHO-166, run `6de65906`) — **good**
Ran `studio git-sync`; commit `86eb477`; push success; marked done. This is the first clean in-agent sync of the pilot family.

### 5. ME Brief → Premise handoff (~01:08Z) — **good contract**
`studio handoff --after creative_brief` created:
- GHO-167 Premise with absolute pack first-call + write_root + verify-done
- GHO-168 Git sync  
Updated stage files to `premise`. Brief stamped APPROVED.

**Abnormal:** GHO-168 was initially created with **host** CLI path `/srv/docker/paperclip/...` in the description, then patched seconds later to `/paperclip/repos/...` (ISS-003). That means handoff/`studio_cli()` still sometimes emits host paths into board text.

### 6. SA Premise (GHO-167, run `dd6f151e`) — **good delivery**
- Pack + write Premise Package (634 words) on write_root; `verify-done` exit 0; PATCH done.
- Content respects locked event class and box-as-catalyst.

**Abnormal:** first CLI attempt used host path `/srv/docker/paperclip/...` (failed), then agent path (ISS-003). Premise frontmatter left `PROPOSED` with no ME approve / next handoff yet (ISS-008 — may be timing). Log contains BOOK_TEMPLATE / request_confirmation string hits (likely instruction/tool text); no board confirmation created.

### 7. Admin Git sync after Brief (GHO-168, run `121e1324`) — **correct diagnosis, incomplete disposition**
- `git-sync` fails: `PermissionError` on `/paperclip/repos/AI-Fiction-Library/README.md` (root-owned). Book tree itself is fine; **repo README** blocks `update_readme()`.
- Dry-run mirror otherwise OK; pending stage=premise changes.
- Run later **cancelled** when issue was reassigned.

**Abnormal:** repo-level root ownership of `README.md` (ISS-004). Sync not left cleanly `blocked` before ownership theft (see §8).

### 8. ME self-assigns GHO-168 + opens GHO-169 (~01:20Z) — **bad**
Activity: `assigneeAgentId` **from Studio Admin → Managing Editor**, interrupting Admin run `121e1324`. ME comments that sync is blocked on README ownership and creates GHO-169 (ops) for Admin.

**Abnormal:**
- ME must not take Git sync ownership (ISS-005).
- GHO-169 is a bare one-liner (no first-call / write_root) (ISS-006).
- Creating a sibling ops issue is reasonable; **stealing** the sync assignee is not.

### 9. ME `reopen-parent` / watchdog loop on GHO-163 (~01:03–01:21Z) — **bad thrash**
After Brief/Premise progress, parent accrued recovery noise (“assignee not invokable” while agents were paused/restarting). ME then ran `studio reopen-parent` / watchdog **many times** (dozens of near-identical comments). Parent is already `in_progress` with empty `blockedBy`.

**Abnormal:** EXIT-after-success not honored; unbound ME runs (`issueId` empty) keep re-entering the same reopen path (ISS-009). Burns tokens; delays Premise approval → Story Bible handoff.

### 10. Live state after Premise done — **stalled**
Premise is done on disk; no `handoff --after premise` yet. Pipeline is stuck on README ops + ME thrash rather than creative next stage.

---

## Open issues (this run only)

### ISS-001 — Intake (and some seeded text) still embeds relative `python3 tools/studio.py`
- **Found:** GHO-164 description; ME run `90cf2451` first pack failed under `/app/tools/studio.py`.
- **Severity:** Medium
- **Evidence:** Issue text “First tool call” uses relative CLI; absolute path only after recovery. Later handoff-created issues (GHO-165/167) correctly use `/paperclip/repos/...`.
- **Impact:** Guaranteed first-call failure on Intake every restart until description generator is fixed.
- **Needed:** `intake_description` / start-book embeds must use agent absolute `STUDIO_AGENT_CLI` (same as `_assignment_desc`), never bare `tools/studio.py`.

### ISS-002 — Post-done status flap / echo wakes on Creative Brief
- **Found:** GHO-165 comments 00:54–00:56Z
- **Severity:** Low–Medium
- **Evidence:** SA reports board showed `in_progress` again after `done`; multiple reconcile wakes; eventually exits on done.
- **Impact:** Extra SA runs after content finished; risk of scope reopen.
- **Needed:** Paperclip/studio: don’t re-wake assignee on own completion echo; HEARTBEAT already says exit-if-done (worked eventually).

### ISS-003 — Host path `/srv/docker/paperclip/...` leaks into agent issue text / first commands
- **Found:** GHO-168 description created with host CLI, patched to agent path at 01:09:15Z; SA Premise run also tried host path first.
- **Severity:** Medium
- **Evidence:** Activity diff on GHO-168 `description`; SA run `dd6f151e` command log.
- **Impact:** First commands fail inside container; confuses agents; suggests `studio_cli()` sometimes resolves host `STUDIO_CLI` during handoff.
- **Needed:** Inside agent runtime, `studio_cli()` must prefer `/paperclip/repos/...` (or `STUDIO_AGENT_CLI`); never emit host paths into board descriptions. Guard/rewrite on handoff emit.

### ISS-004 — `AI-Fiction-Library/README.md` root-owned blocks git-sync after book_root fix
- **Found:** GHO-168 Admin run `121e1324`; host `stat` = `root:root 644`
- **Severity:** High (active sync blocker)
- **Evidence:** `PermissionError: .../README.md`; book_root itself is writable and intake sync already succeeded.
- **Impact:** Every sync that updates README/registry metadata fails even when book tree is fine.
- **Needed:** Ops `chown` README (and audit other root-owned files under repo mount); git-sync should fail with `blocked` + precise path; prefer not requiring README write for book-only sync if possible.

### ISS-005 — ME self-assigned Git sync (GHO-168), interrupting Studio Admin
- **Found:** 2026-09-19T01:20:57Z activity on GHO-168
- **Severity:** High (role breach / process)
- **Evidence:** `assigneeAgentId` from Admin → ME; `interruptedRunId=121e1324`; ME then filed GHO-169.
- **Impact:** Wrong role owns sync; Admin diagnosis run cancelled; ME is not the sync operator.
- **Needed:** Reassign GHO-168 back to Studio Admin (or leave blocked for Admin). Policy/HEARTBEAT: ME must not claim `Git sync` issues; watchdog should flag wrong-role sync assignee (like draft wrong-role).

### ISS-006 — Ops child GHO-169 has bare description
- **Found:** GHO-169 create ~01:20:53Z
- **Severity:** Medium
- **Evidence:** One-line PermissionError note; no first-call, no acceptance criteria. Watchdog `intervene_reasons: bare_issue_description:GHO-169`.
- **Impact:** Admin gets an under-specified ticket; watchdog correctly refuses healthy exit.
- **Needed:** Even ops tickets should include exact path, required chown target, and “re-run git-sync on GHO-168 after fix” acceptance. Prefer studio helper to open ops/blocker issues.

### ISS-007 — DEC-001 still says “pending Managing Editor” after Brief APPROVED
- **Found:** `00_admin/DECISION_LOG.md` vs Brief frontmatter
- **Severity:** Low (canon hygiene)
- **Evidence:** DEC-001 approving authority line still pending; Brief `approved_by: managing_editor` / `approved_at: 2026-09-19`.
- **Impact:** Downstream readers may think event lock is unapproved.
- **Needed:** On Brief stamp/handoff, also flip DEC approval line (or ME patches DEC when approving).

### ISS-008 — Premise done but still `PROPOSED`; no Story Bible handoff yet
- **Found:** `development/PREMISE_PACKAGE.md` frontmatter; board has no Story Bible issue
- **Severity:** Medium (pipeline stall — partly caused by ISS-004/005/009)
- **Evidence:** GHO-167 `done`; stage files still `premise`; no GHO for Story Bible.
- **Impact:** Creative progress stopped after a successful Premise.
- **Needed:** ME approve/stamp Premise → `studio handoff --after premise` (creates Story Bible + sync). Do this only after stopping reopen thrash; sync can stay blocked in parallel without parking parent.

### ISS-009 — ME reopen-parent / watchdog comment storm on already-clear parent
- **Found:** GHO-163 comments ~01:03–01:21Z; many ME runs with empty `issueId`
- **Severity:** High (active thrash)
- **Evidence:** ≥15 near-identical “reopen-parent / cleared blockedBy” comments while parent already `in_progress` and `blockedBy=[]`. Watchdog earlier pushed `reopen_parent` during recovery; ME does not EXIT.
- **Impact:** Token burn; blocks attention to Premise approval / Story Bible; creates noise.
- **Needed:** `reopen-parent` / watchdog: if parent already `in_progress` and empty blockers → recommend EXIT / next-stage handoff, not reopen again. ME HEARTBEAT: after one successful reopen, EXIT. Cancel unbound ME wakes.

### ISS-010 — Project status left `backlog` while BOOK parent is active
- **Found:** Board project `46fa8bdb…` status `backlog`
- **Severity:** Low
- **Evidence:** `/api/companies/.../projects` list.
- **Impact:** Board filtering/UX may hide active pilot.
- **Needed:** start-book (or first Intake handoff) should set project active/in_progress.

### ISS-011 — Pipeline priority inversion: ops sync blocking creative stage advance
- **Found:** After GHO-167 done, open work is only GHO-168/169; no bible issue
- **Severity:** Medium (process design)
- **Evidence:** Snapshot; CURRENT_STAGE notes still cite Brief handoff children.
- **Impact:** Controlled-test creative path waits on README chown even though Premise artifact is ready.
- **Needed:** Policy: git-sync failure must not prevent `handoff --after premise` when content verify-done PASS; keep one blocked sync issue, advance content lane.

---

## Working well (this run)

1. Runtime `STUDIO_*` env in paperclip container.
2. Intake → Brief handoff with embeds; Brief quality + event lock + box rule.
3. Intake git-sync push success (`86eb477`).
4. Brief → Premise handoff helper; Premise on-canon with verify-done PASS.
5. Stage yaml ↔ CURRENT_STAGE alignment at premise.
6. No parent confirmation park on GHO-163.
7. Watchdog flags bare GHO-169 instead of claiming healthy.

---

## Priority to clear before trusting the next stage

1. **ISS-009** stop ME reopen thrash (pause unbound ME wakes / fix watchdog loop).  
2. **ISS-005** reassign GHO-168 to Studio Admin (or blocked).  
3. **ISS-004** chown `README.md` (and audit repo root files).  
4. **ISS-008 / ISS-011** approve Premise + `handoff --after premise` without waiting on sync.  
5. **ISS-001 / ISS-003** stop relative + host CLI embeds.  
6. **ISS-006 / ISS-007 / ISS-002 / ISS-010** hygiene.

---

## Chronology (this run)

### 2026-09-19 ~00:49Z — Bootstrap
- Prior project `90e5d01f…` wiped/cancelled; new project `46fa8bdb…`; GHO-163 parent + GHO-164 Intake.
- ME wake interrupted once by server SIGTERM; resumed.

### ~00:50–00:58Z — Intake
- Relative CLI fail → absolute pack OK → verify-done → handoff intake → GHO-165/166.
- Intake `done`; parent stays `in_progress`.

### ~00:51–00:56Z — Brief + intake sync
- SA writes Brief + DEC-001 locks; status-reconcile wakes.
- Admin git-sync after intake succeeds (`86eb477`).

### ~01:08–01:12Z — Premise handoff + Premise done
- ME `handoff --after creative_brief` → GHO-167/168 (host path briefly in sync desc).
- SA Premise verify-done PASS → `done`.
- Admin sync hits README root ownership; thrash begins.

### ~01:03–01:21Z — Recovery / reopen storm + sync ownership theft
- Parent recovery comments while agents not invokable; then ME reopen-parent loop.
- ME takes GHO-168 from Admin; opens bare GHO-169 ops ticket.
- Watchdog: intervene on bare GHO-169.
- Premise still unapproved / Story Bible not issued.

---

## How to update

Append under **Chronology** and/or add `ISS-xxx` with: found time, evidence (issue/run/path), severity, impact, needed fix.  
Keep host canonical; mirror to project `00_admin/ISSUE.md` after substantive updates.
