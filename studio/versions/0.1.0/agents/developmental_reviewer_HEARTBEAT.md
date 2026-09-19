# Heartbeat

## Identity
Check STUDIO_TASK_ID, STUDIO_WAKE_REASON, STUDIO_COMPANY_ID, STUDIO_AGENT_ID.


## Zombie-run guard
If STUDIO_TASK_ID / assigned issue is already `done` or `cancelled`: comment nothing further, do not rewrite artifacts, EXIT immediately.

## Default mode
Heartbeat timers are OFF for this role. You wake on assignment.

## On wake
1. Read the assigned issue + linked parent/book context
2. Read only the required context packet (brief/canon/contract/prior summary) — not the entire project dump unless reviewing the full manuscript
3. Do exactly the assigned unit of work
4. Write artifacts
5. Comment + confirmed disposition
6. EXIT

## Do not
- Start unassigned future stages
- Hire agents or clone yourself
- Linger after disposition
- Ask the board for ordinary creative decisions
