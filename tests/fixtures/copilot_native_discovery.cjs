// Installed runtime parser only. Never create a chat/session manager, execute a
// hook, load plugins, discover policies, or access the real user configuration.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const [nativeFile, project, home, expectedFile, invalidProject] = process.argv.slice(2);
const runtime = require(nativeFile);
async function load(directory) {
    const created = await runtime.hookSessionCreate({
        cwd: directory, repoRoot: directory, sessionId: 'isolated-parser-fixture',
        settingsJson: '{}', userHooksDir: path.join(home, '.copilot/hooks'),
        allowLocalhost: false, allowHttpAuthHooks: false, discoverPolicies: false
    });
    try {
        const empty = JSON.parse(await runtime.hookSessionSnapshot(created.handle));
        assert.equal(empty.hookCount, 0);
        const load = await runtime.hookSessionLoadRepo(created.handle, path.join(directory, '.github/hooks'));
        const snapshot = JSON.parse(await runtime.hookSessionSnapshot(created.handle));
        const resources = await runtime.hookSessionListResources(created.handle);
        return {load, snapshot, resources};
    } finally {
        runtime.hookSessionDispose(created.handle);
    }
}
(async () => {
    const expected = expectedFile === '-' ? null : JSON.parse(fs.readFileSync(expectedFile, 'utf8'));
    const positive = await load(project);
    assert.equal(positive.snapshot.hookCount, expected ? 1 : 0);
    assert.equal(positive.resources.length, expected ? 1 : 0);
    if (expected) {
        assert.equal(positive.resources[0].event, 'preToolUse');
        assert.equal(positive.snapshot.hooks[0].isPolicy, false);
        assert.deepEqual(JSON.parse(positive.snapshot.hooks[0].specJson).config,
                         expected.hooks.preToolUse[0]);
    }
    assert.deepEqual(positive.load.errors, []);
    assert.deepEqual(positive.load.warnings, []);
    const negative = await load(invalidProject);
    assert.equal(negative.snapshot.hookCount, 0);
    assert.ok(negative.load.errors.length + negative.load.warnings.length > 0);
    console.log(JSON.stringify({positive, negative, hookExecutionRequested: false}));
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
