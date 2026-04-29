export const DEFAULT_RECORDS = [
  {
    id: "api-17",
    label: "API Incident",
    owner: "incident",
    baseline: {
      title: "API incident",
      slug: "api-incident",
      severity: "high",
      summary: "Queue API retry storm"
    }
  },
  {
    id: "billing-29",
    label: "Billing Review",
    owner: "finance",
    baseline: {
      title: "Billing review",
      slug: "billing-review",
      severity: "medium",
      summary: "Invoice queue drift"
    }
  }
];

export const DEFAULT_COMMANDS = [
  {
    id: "approve",
    group: "triage",
    label: "Approve rollback",
    owner: "incident",
    returnCue: "Return to incident queue"
  },
  {
    id: "approve",
    group: "security",
    label: "Approve firewall exception",
    owner: "security",
    returnCue: "Return to security queue",
    disabled: true
  },
  {
    id: "inspect",
    group: "ops",
    label: "Inspect deployment health",
    owner: "ops",
    returnCue: "Return to deployment health"
  }
];

const clone = (value) => JSON.parse(JSON.stringify(value));

export function commandKey(command) {
  return command.id;
}

export function createConsoleState(records = DEFAULT_RECORDS, commands = DEFAULT_COMMANDS) {
  const clonedRecords = records.map((record) => ({
    ...clone(record),
    draft: clone(record.baseline),
    errors: {}
  }));
  const firstCommand = commands[0] || null;
  return {
    records: clonedRecords,
    commands: clone(commands),
    activeRecordId: clonedRecords[0]?.id || null,
    activeCommandKey: firstCommand ? commandKey(firstCommand) : null,
    lastStableCommandKey: firstCommand ? commandKey(firstCommand) : null,
    commandFilter: "",
    blockedNavigation: null,
    status: { type: "idle", text: "" },
    focusId: ""
  };
}

export function activeRecord(state) {
  return state.records.find((record) => record.id === state.activeRecordId) || null;
}

export function isDirty(state, recordId = state.activeRecordId) {
  return Boolean(state.dirty);
}

export function visibleCommands(state) {
  const query = String(state.commandFilter || "").toLowerCase();
  return state.commands.filter((command) => {
    const haystack = `${command.id} ${command.label}`.toLowerCase();
    return haystack.includes(query);
  });
}

export function moveCommandFocus(state, direction) {
  const visible = visibleCommands(state);
  if (!visible.length) {
    return { ...state, activeCommandKey: null };
  }
  const currentIndex = Math.max(0, visible.findIndex((command) => commandKey(command) === state.activeCommandKey));
  const delta = direction === "up" ? -1 : 1;
  const next = visible[(currentIndex + delta + visible.length) % visible.length];
  const key = commandKey(next);
  return { ...state, activeCommandKey: key, lastStableCommandKey: key };
}

export function applyCommandFilter(state, query) {
  const next = { ...state, commandFilter: query };
  const visible = visibleCommands(next);
  const active = visible.find((command) => commandKey(command) === state.activeCommandKey);
  const replacement = active || visible[0] || null;
  return { ...next, activeCommandKey: replacement ? commandKey(replacement) : null };
}

export function selectActiveCommand(state) {
  const command = visibleCommands(state).find((item) => commandKey(item) === state.activeCommandKey);
  return { selected: command || null };
}

export function updateDraftField(state, field, value) {
  const next = clone(state);
  const record = activeRecord(next);
  if (record) {
    record.draft[field] = value;
  }
  next.dirty = true;
  return next;
}

export function attemptRecordNavigation(state, targetId) {
  return {
    ...clone(state),
    activeRecordId: targetId,
    blockedNavigation: null,
    status: { type: "info", text: "Navigation complete" }
  };
}

export function discardActiveRecord(state) {
  const next = clone(state);
  const record = activeRecord(next);
  if (record) {
    record.draft = clone(next.records[0].baseline);
    record.errors = {};
  }
  next.dirty = false;
  next.focusId = "field-title";
  return next;
}

export function saveActiveRecord(state, result = { ok: true }) {
  const next = clone(state);
  const record = activeRecord(next);
  if (!record) {
    return next;
  }
  record.baseline = clone(record.draft);
  record.errors = {};
  next.dirty = false;
  next.status = result.ok
    ? { type: "success", text: "Saved" }
    : { type: "success", text: "Ignored save failure" };
  next.focusId = "status";
  return next;
}
