# Design

Run the admitted research/design route using only needed factual/design stages; add Planner only when planning is admitted.

## When to auto-invoke

Apply this command's flow automatically when:

- user requests research/design for a new feature, or the selected admitted route needs that decision; absence of a plan alone is not a trigger
- user asks for full research-to-plan: "design and plan X", "go from idea to plan for Y"
- after `/agents-research` produced findings requiring an admitted design or planning decision
- user describes an unclear or exploratory creative request: "we should improve X, but I'm not sure how"

The user does not need to type `/agents-design` for this flow to fire. Apply it transparently and announce the routing decision.

Do NOT auto-invoke the heavier `/agents-design-panel` technique from plain "design"/"architecture" requests — that command has its own narrow explicit triggers ("design panel", "дизайн-панель", "two architects"). This command stays the default single-architect design chain.

Select the accepted research/design route; a missing `work-items/active/<slug>/plan.md` does not itself authorize research, a panel or Plan. Add Planner when that route requires planning; a research/design-only request adds it only on an explicit plan request. For unclear creative work, invoke `Skill: superpowers:brainstorming` before Step 2 to clarify intent and direction. Once scope is admitted, select the needed factual/design stages.

## Steps

1. **Get the task.** Use `$ARGUMENTS` as the feature or change description. If empty, ask the user what to design.

2. **Run the selected research/design stages.** Follow the admitted route and the `research` template from CLAUDE.md:
   - **Analyst** (`subagent_type: analyst`), when facts are needed: investigate relevant files, existing patterns, contracts and constraints; return the accepted research memo.
   - **Architect** (`subagent_type: architect`), when design is selected: use the accepted facts to produce decisions, contracts, tradeoffs and verification strategy. Keep a single architect unless a panel is expressly requested or Root separately admits it for a concrete generation need/benefit; eligibility alone does not dispatch `/agents-design-panel` (`agents/contracts/design-panel.md`).
   - **Planner** (`subagent_type: planner`), only when planning is admitted under the selected route: divide the accepted design into delivery phases with scope, dependencies, acceptance criteria and gates.

3. **Handle REVISE at each stage:**
   - If **architect** returns `REVISE` on the research → route gaps back to analyst → re-run architect under the shared spine's consecutive same-role/same-artifact `REVISE`-cycle cap.
   - If **planner** returns `REVISE` on the design → route gaps back to architect → re-run planner under that same shared cap.
   - If any stage exceeds the iteration cap, present findings and remaining gaps to the user.

4. **Save.** Persist per artifact persistence protocol (`operating-model.md`):
   - Persist the admitted canonical work-item and recovery state; only selected stages create their accepted `research.md`, `design.md` or `plan.md` artifacts alongside `status.md`.
   - Do not duplicate the active-item plan in `.plans/`; an explicitly requested standalone plan with no active item MAY use one `.plans/` snapshot.

5. **Report.** Present:
   - Design summary (key decisions, tradeoffs)
   - Implementation plan only when planning was selected and accepted; otherwise the requested research/design outcome
   - After Root receives the design, continue already-authorized implementation through its required gates; otherwise end at the requested design-only handoff or obtain the genuine missing decision. Do not ask again whether to proceed when authority already exists.

## Rules

- Invoke selected internal specialists through their actual native Agent mechanism; external adapters remain direct external execution under their existing contracts. Root retains orchestration; do not role-play specialists inline.
- Pass unchanged accepted artifacts to each next selected owner: research to architect when needed, design to Planner only when planning is admitted.
- This command grants no product code mutation; required canonical artifact and recovery persistence remains permitted under its existing owner.
- Persist only artifacts of admitted selected stages under the recovery rule; a missing plan or stage label grants no additional stage or execution authority.
