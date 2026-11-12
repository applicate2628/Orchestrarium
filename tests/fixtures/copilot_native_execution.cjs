// Installed hook processor only; no SDK client/chat/model or tool execution.
const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const [nativeFile, project, home] = process.argv.slice(2);
const runtime = require(nativeFile);
(async () => {
    const created = await runtime.hookSessionCreate({cwd:project, repoRoot:project,
        sessionId:'isolated-execution', settingsJson:'{}',
        userHooksDir:path.join(home,'.copilot/hooks'), allowLocalhost:false,
        allowHttpAuthHooks:false, discoverPolicies:false});
    const lifecycle = [];
    let signalLifecycle = ()=>{};
    try {
        const env = {hostCwd:project, isWindows:true,
            hostEnv:Object.entries(process.env).map(([key,value])=>({key,value})),
            envVarNamesToFilterFromShellsAndMcp:[], envVarNamesToFilterFromShellsOnly:[],
            allowLocalhost:false, allowHttpAuthHooks:false, userAgent:'isolated-hook-test'};
        runtime.hookProcessorConfigure(created.handle,{env,hooks:{}},
            event=>{lifecycle.push(event);signalLifecycle();},()=>{});
        const loaded = await runtime.hookSessionLoadRepo(created.handle,path.join(project,'.github/hooks'));
        assert.equal(loaded.hookCount,1);
        assert.deepEqual(loaded.errors,[]);
        assert.deepEqual(loaded.warnings,[]);
        const cases = [
            ['bash',{command:'git worktree add must-not-exist'},'[stray-artifact AUDIT]'],
            ['create_file',{filePath:'src/not-created',content:['C:','Users','alice','fixture'].join('/')},'[machine-local-path AUDIT]'],
            ['create',{path:'src/not-created',content:'ordinary'},null],
            ['unqualified-tool',{command:'git worktree add must-not-exist'},null],
        ];
        for (const [index,[toolName,args,expected]] of cases.entries()) {
            const id='fixture-'+index;
            // SDK Ww serializes the tool argument string into toolArgsJson.
            const result = await runtime.hookProcessorPreToolUse(created.handle,
                [{id,toolName,toolArgsJson:JSON.stringify(JSON.stringify(args))}],
                'isolated-execution',()=>{},undefined);
            try {
                assert.equal(typeof result.lifecycleInvocationId,'string');
                assert.ok(result.lifecycleInvocationId.length > 0);
                assert.ok(!result.lifecycleErrorMessage);
                assert.ok(!result.lifecycleErrorStack);
                assert.ok(!result.lifecycleErrorSource);
                assert.deepEqual(result.denials,[]);
                assert.deepEqual(result.askRequests,[]);
                assert.deepEqual(result.allowedToolCallIds,[]);
                assert.deepEqual(result.argMutations,[]);
                assert.equal(result.additionalContexts.length,expected ? 1 : 0);
                if(expected) {
                    assert.equal(result.additionalContexts[0].toolCallId,id);
                    assert.ok(result.additionalContexts[0].context.includes(expected));
                }
            } finally {
                if(result.lifecycleInvocationId) runtime.hookProcessorCompletePreToolUseLifecycle(
                    created.handle,result.lifecycleInvocationId,result.denials,result.logs,
                    result.lifecycleErrorMessage,result.lifecycleErrorStack,result.lifecycleErrorSource);
            }
        }
        await new Promise((resolve,reject)=>{
            const timer=setTimeout(()=>reject(new Error('Lifecycle callbacks did not settle')),5000);
            signalLifecycle=()=>{
                if(lifecycle.filter(x=>x.phase==='end').length===cases.length){clearTimeout(timer);resolve();}
            };
            signalLifecycle();
        });
        assert.equal(lifecycle.filter(x=>x.phase==='start').length,cases.length);
        assert.equal(lifecycle.filter(x=>x.phase==='end').length,cases.length);
        assert.equal(fs.existsSync(path.join(project,'must-not-exist')),false);
        assert.equal(fs.existsSync(path.join(project,'src/not-created')),false);
        console.log(JSON.stringify({cases:cases.length,nativeHookExecution:true,
            modelSessionCreated:false,toolExecutionRequested:false,lifecycleCompleted:true}));
    } finally {runtime.hookSessionDispose(created.handle);}
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
