# Inputs

- `task.md` - the planner task, required behavior, and witness JSON contract.
- `workitems.json` - the eight work items and their explicit `depends_on` edges.
- `constraints.md` - binding constraints; constraint C1 ADDS a derived edge (c-cache depends on d-auth)
  that is not written in any `depends_on` list.
