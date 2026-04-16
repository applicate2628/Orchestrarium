const { appendWorkerStep } = require("./session/appendWorkerStep");
const { carryForwardWorkerState } = require("./session/carryForwardWorkerState");

function runPersistenceWorkflow({
  ownedTarget,
  workspaceRoot,
  taskSteps = ["locate", "patch", "verify"],
  verificationCommands = ["npm test", "node scripts/verify-persistence.js"],
  patchSummary = "fixed worker continuity",
  handoffNotes = ["preserve worker state"],
}) {
  const [firstStep, ...remainingSteps] = taskSteps;

  const initialSession = {
    ownedTarget,
    workspaceRoot,
    steps: [],
    verificationCommands,
    handoffNotes,
  };

  const afterFirstStep = appendWorkerStep(initialSession, firstStep);
  const beforeCarry = remainingSteps.slice(0, -1).reduce(
    (session, step) => appendWorkerStep(session, step),
    afterFirstStep
  );

  const carried = carryForwardWorkerState(beforeCarry, patchSummary);
  return appendWorkerStep(carried, remainingSteps.at(-1));
}

module.exports = {
  runPersistenceWorkflow,
};
