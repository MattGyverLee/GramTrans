# Contract: Human-Agent Provisioning (`Lib/wordforms.py`) — US2 FR-009

Every copied human evaluation needs a valid target owner. Provision (or reuse) exactly one human
agent per run and reuse it across every evaluation, rather than duplicating an agent per evaluation.

## `plan_agent(target, ctx) -> ProvisionedAgent`

Pure/decision pass, invoked once per run before any evaluation is written.

**Behavior**
- Prefer an existing target human agent: `AgentOperations.GetHumanAgents()` (or
  `FindByType(is_human=True)`); reuse the first → `ProvisionedAgent(created=False)` → **Link** in
  Preview.
- If the target has no human agent, plan a create → `ProvisionedAgent(created=True)` → **Add** in
  Preview (FR-009, US2 scenario 3). The provisioning decision is visible in the Preview.

## `apply_agent(decision, target, ctx) -> ICmAgent`

Move-mode only.
- When `created`, `AgentOperations.Create(name)` then `SetHuman(agent, person)` to mark it human;
  the agent lives in `AnalyzingAgentsOC`.
- Cache the resulting agent on the run context; **every** copied evaluation this run is owned by
  this single agent (no per-evaluation duplication, FR-009 / edge case "Human agent identity").

**Postconditions**
- Every copied human-approve / human-deny evaluation has a valid human-agent owner in the target.
- Exactly one agent is provisioned per run when none pre-exists; an existing agent is reused, not
  duplicated.

## Non-goals
- Does not copy the source agent object by GUID (agents are project-scoped identities, not transfer
  content).
- Does not provision parser agents (parser evaluations are out of scope by the human-eval gate).
