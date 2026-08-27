#!/usr/bin/env python3
"""Regression tests for the committed Stage 0 baseline pin and local-only policy."""
from __future__ import annotations
import json, os, subprocess, sys, tempfile, time, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASELINE_DIR=ROOT/'baseline'/'orchestrarium-v1'; PIN_PATH=BASELINE_DIR/'baseline-pin.json'; README_PATH=BASELINE_DIR/'README.md'; GITIGNORE_PATH=ROOT/'.gitignore'
EXPECTED_COMMIT='ce2052fb773576fd6e3206c2a7e21e01852d556b'; EXPECTED_TREE='04dccf4575f17c9c5533474d2e0fd1503bfeceb7'
TOOL_PATHS={
'inventoryGenerator':'baseline/orchestrarium-v1/tooling/build_inventory.py',
'targetEffectGenerator':'baseline/orchestrarium-v1/tooling/build_target_effect_baseline.py',
'pytestComparator':'baseline/orchestrarium-v1/tooling/compare_pytest_baseline.py',
'commandComparator':'baseline/orchestrarium-v1/tooling/compare_command_baseline.py'}
SOURCE_PATHS={
'inventoryGenerator':'scripts/baseline/build_inventory.py',
'targetEffectGenerator':'scripts/baseline/build_target_effect_baseline.py',
'pytestComparator':'scripts/baseline/compare_pytest_baseline.py',
'commandComparator':'scripts/baseline/compare_command_baseline.py'}
VALIDATOR_MARKERS=('src.codex/skills/lead/scripts/validate-skill-pack.sh','src.claude/agents/scripts/validate-skill-pack.sh','src.gemini/scripts/validate-pack.sh','src.qwen/scripts/validate-pack.sh','scripts/sync-agents-mode-docs.py','scripts/validate-agents-spine.py','scripts/sync-universal-hooks.py','scripts/validate-agents-mode-installers.py')
IGNORED_EXECUTABLE_PATHS=(':(glob)tests/**',':(glob)**/conftest.py',':(glob)scripts/**',':(glob)**/*.py',':(glob)**/*.sh',':(glob)**/*.ps1',':(glob)**/pyproject.toml',':(glob)**/pytest.ini',':(glob)**/tox.ini',':(glob)**/setup.cfg',':(exclude,glob).scratch/**',':(exclude,glob)**/__pycache__/**',':(exclude,glob).pytest_cache/**',':(exclude,glob)node_modules/**',':(exclude,glob).venv/**',':(exclude,glob)venv/**')

def git(*args,cwd=ROOT):
    r=subprocess.run(['git',*args],cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    if r.returncode: raise AssertionError(f"git {' '.join(args)} failed ({r.returncode})\n{r.stdout}\n{r.stderr}")
    return r.stdout.strip()

def read_section(start_marker,end_marker):
    text=README_PATH.read_text(); start=text.index(start_marker)+len(start_marker); end=text.index(end_marker,start)
    return text[start:end]

def read_guard():
    return read_section('# BEGIN ORCHE_CLEAN_WORKTREE_GUARD','# END ORCHE_CLEAN_WORKTREE_GUARD')

def read_reviewed_candidate_guard():
    return read_section('# BEGIN ORCHE_REVIEWED_CANDIDATE_GUARD','# END ORCHE_REVIEWED_CANDIDATE_GUARD')

def read_timeout_runner():
    return read_section('# BEGIN ORCHE_TIMEOUT_RUNNER','# END ORCHE_TIMEOUT_RUNNER')

class BaselinePinTests(unittest.TestCase):
    def test_pin_matches_main_and_frozen_tool_blobs_in_reviewed_tree(self):
        p=json.loads(PIN_PATH.read_text()); b=p['baseline']; self.assertEqual(p['schemaVersion'],5)
        self.assertEqual(b['sourceBranch'],'main'); self.assertEqual(b['commitSha'],EXPECTED_COMMIT); self.assertEqual(b['treeSha'],EXPECTED_TREE)
        self.assertEqual(git('rev-parse','--verify',f'{EXPECTED_COMMIT}^{{commit}}'),EXPECTED_COMMIT)
        self.assertEqual(git('rev-parse','--verify',f'{EXPECTED_COMMIT}^{{tree}}'),EXPECTED_TREE)
        self.assertEqual(p['toolingAnchor']['kind'],'reviewed-tree-frozen-paths'); self.assertFalse(p['toolingAnchor']['requiresOwningCommitLookup'])
        self.assertEqual(set(p['tooling']),set(TOOL_PATHS))
        for name,path in TOOL_PATHS.items():
            record=p['tooling'][name]; self.assertEqual(record['path'],path); self.assertEqual(record['sourcePath'],SOURCE_PATHS[name]); self.assertNotIn('owningCommit',record)
            self.assertEqual(record['materialization'],'git-cat-file-reviewed-tree-blob')
            line=git('ls-tree','HEAD','--',path); mode,typ,sha,recorded_path=line.split(None,3)
            self.assertTrue(mode); self.assertEqual(typ,'blob'); self.assertEqual(sha,record['gitBlobSha']); self.assertEqual(recorded_path,path); self.assertEqual(git('cat-file','-t',sha),'blob')

    def test_verification_is_local_only_and_outputs_are_not_tracked(self):
        p=json.loads(PIN_PATH.read_text()); evidence=p['evidence']; tracked=set(git('ls-files').splitlines()); ignored=GITIGNORE_PATH.read_text()
        self.assertEqual(evidence['verificationMode'],'local-only'); self.assertFalse(evidence['commitGeneratedOutputs'])
        for wf in ('.github/workflows/orche-stage0-baseline.yml','.github/workflows/_orche_pr2_review2.yml','.github/workflows/_orche_pr2_verify2.yml','.github/workflows/_orche_pr2_verify3.yml'): self.assertNotIn(wf,tracked)
        self.assertIn('/.github/workflows/_orche_pr2_verify*.yml',ignored); self.assertIn('/.github/workflows/_orche_pr2_review*.yml',ignored)
        for name in evidence['requiredGeneratedOutputs']: self.assertNotIn(f'baseline/orchestrarium-v1/{name}',tracked)

    def test_ignored_executable_inputs_detected_without_blocking_scratch(self):
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d)/'repo'; repo.mkdir(); subprocess.run(['git','init','-q'],cwd=repo,check=True)
            (repo/'.gitignore').write_text('.scratch/\ntests/conftest.py\nscripts/local.py\n'); (repo/'tests').mkdir(); (repo/'tests/conftest.py').write_text('x\n'); (repo/'scripts').mkdir(); (repo/'scripts/local.py').write_text('x\n'); (repo/'.scratch').mkdir(); (repo/'.scratch/cache.py').write_text('x\n')
            env={**os.environ,'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':os.devnull}
            r=subprocess.run(['git','ls-files','--others','--ignored','--exclude-standard','--',*IGNORED_EXECUTABLE_PATHS],cwd=repo,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.assertEqual(r.returncode,0,r.stderr); self.assertEqual(r.stdout.splitlines(),['scripts/local.py','tests/conftest.py'])

    def test_clean_worktree_guard_fails_closed_on_tracked_change(self):
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d)/'repo'; repo.mkdir(); subprocess.run(['git','init','-q'],cwd=repo,check=True); subprocess.run(['git','config','user.name','Test'],cwd=repo,check=True); subprocess.run(['git','config','user.email','t@example.invalid'],cwd=repo,check=True)
            (repo/'tracked.txt').write_text('clean\n'); subprocess.run(['git','add','.'],cwd=repo,check=True); subprocess.run(['git','commit','-qm','base'],cwd=repo,check=True); (repo/'tracked.txt').write_text('dirty\n')
            script='VERIFIER_GIT=git\n'+read_guard()+"\nassert_clean_worktree \"$1\"\n"; r=subprocess.run(['bash','-c',script,'bash',str(repo)],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.assertNotEqual(r.returncode,0); self.assertIn('BLOCKED: dirty worktree',r.stderr)

    def test_reviewed_candidate_guard_rejects_baseline_and_mismatched_heads(self):
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d)/'repo'; repo.mkdir(); subprocess.run(['git','init','-q'],cwd=repo,check=True); subprocess.run(['git','config','user.name','Test'],cwd=repo,check=True); subprocess.run(['git','config','user.email','t@example.invalid'],cwd=repo,check=True)
            (repo/'tracked.txt').write_text('baseline\n'); subprocess.run(['git','add','.'],cwd=repo,check=True); subprocess.run(['git','commit','-qm','baseline'],cwd=repo,check=True); baseline=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
            (repo/'tracked.txt').write_text('candidate\n'); subprocess.run(['git','commit','-qam','candidate'],cwd=repo,check=True); candidate=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
            guard=read_reviewed_candidate_guard()
            common=f'VERIFIER_GIT=git\nCANDIDATE_ROOT={repo!s}\nPIN_COMMIT={baseline}\n'
            ok=subprocess.run(['bash','-c',common+f'REVIEWED_REF={candidate}\n'+guard],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.assertEqual(ok.returncode,0,ok.stderr)
            mismatch=subprocess.run(['bash','-c',common+f'REVIEWED_REF={baseline}\n'+guard],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.assertNotEqual(mismatch.returncode,0); self.assertIn('candidate worktree HEAD does not match REVIEWED_REF',mismatch.stderr)
            subprocess.run(['git','checkout','-q',baseline],cwd=repo,check=True)
            self_compare=subprocess.run(['bash','-c',common+f'REVIEWED_REF={baseline}\n'+guard],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.assertNotEqual(self_compare.returncode,0); self.assertIn('candidate ref resolves to the pinned baseline',self_compare.stderr)

    @unittest.skipIf(os.name=='nt', 'POSIX process-group timeout runner')
    def test_timeout_runner_terminates_hanging_command(self):
        runner=read_timeout_runner()
        start=time.monotonic()
        r=subprocess.run([sys.executable,'-c',runner,'0.2',sys.executable,'-c','import time; time.sleep(30)'],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,timeout=10)
        elapsed=time.monotonic()-start
        self.assertEqual(r.returncode,124,r.stderr); self.assertIn('BLOCKED: command timed out',r.stderr); self.assertLess(elapsed,8)

    def test_readme_hardens_toolchain_and_all_gates(self):
        p=json.loads(PIN_PATH.read_text()); readme=README_PATH.read_text()
        self.assertIn(EXPECTED_COMMIT,readme); self.assertIn(EXPECTED_TREE,readme); self.assertNotIn('pull request #3',readme.lower()); self.assertIn('does **not** use GitHub Actions',readme)
        self.assertIn('git-cat-file-reviewed-tree-blob',PIN_PATH.read_text()); self.assertIn('ls-tree "$REVIEWED_REF"',readme); self.assertNotIn('tooling.$key.owningCommit',readme)
        self.assertIn('PATH="$VERIFIER_PATH"',readme); self.assertIn('export PATH="$VERIFIER_PATH"',readme); self.assertNotIn('PATH="$PATH"',readme); self.assertIn('"$BASELINE_ROOT"/*|"$CANDIDATE_ROOT"/*',readme)
        self.assertLess(readme.index('assert_external_tool "$VERIFIER_PYTHON" || exit 1'),readme.index('pin_value()'))
        self.assertLess(readme.index('assert_external_tool "$VERIFIER_GIT" || exit 1'),readme.index('# BEGIN ORCHE_REVIEWED_CANDIDATE_GUARD'))
        self.assertIn('assert_clean_worktree "$BASELINE_ROOT" || exit 1',readme); self.assertIn('assert_clean_worktree "$CANDIDATE_ROOT" || exit 1',readme)
        self.assertIn('status --porcelain=v1 --untracked-files=all',readme); self.assertIn('ls-files --others --ignored --exclude-standard',readme); self.assertIn('BLOCKED: dirty worktree',readme)
        for spec in IGNORED_EXECUTABLE_PATHS: self.assertIn(spec,readme)
        self.assertIn('EVIDENCE_ROOT="$CANDIDATE_ROOT/$(pin_value evidence.generatedOutputDirectory)"',readme); self.assertNotIn('$OUTPUT_ROOT/evidence',readme)
        self.assertEqual(p['evidence']['generatedOutputDirectory'],'.scratch/orche-stage0/orchestrarium-v1')
        self.assertIn('successful diagnostics',readme.lower()); self.assertIn('operational exits',readme.lower())
        self.assertIn('start_new_session=True',readme); self.assertIn('os.killpg',readme); self.assertIn('raise SystemExit(124)',readme); self.assertIn('ORCHE_COMMAND_TIMEOUT_SECONDS',readme)
        self.assertIn('--success-pattern "$success_pattern"',readme); self.assertIn('empty or unconditional `exit 0`',readme)
        self.assertNotIn('REVIEWED_REF="$CANDIDATE_REF"',readme)
        self.assertIn('candidate worktree HEAD does not match REVIEWED_REF',readme)
        self.assertIn('candidate ref resolves to the pinned baseline',readme)
        self.assertIn('--baseline-root "$BASELINE_ROOT"',readme); self.assertIn('--candidate-root "$CANDIDATE_ROOT"',readme)
        self.assertIn("--volatile-pattern 'agents-mode-installer-regression[/\\\\][0-9a-f]{32}'",readme)
        for marker in VALIDATOR_MARKERS: self.assertIn(marker,readme)
        self.assertIn('scripts/check-publication-gate.py',readme); self.assertLess(readme.index('$knowledge-archivist'),readme.index('git push origin refs/tags/'))

if __name__=='__main__': unittest.main()
