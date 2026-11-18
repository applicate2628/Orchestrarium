"""Public SDK capture custody hook ordering without provider or process launch."""
from pathlib import Path
from types import SimpleNamespace
import io
import pytest
from test_sdk_launch_entrypoint import owner, private_capture_root


def test_actual_capture_binding_precedes_runner_and_execution(tmp_path,monkeypatch):
    events=[]
    class Runner:
        def __init__(self): events.append("runner")
        def close(self):
            return SimpleNamespace(outcome="closed",failure_id=None,unsettled_run_token_sha256=())
    class Operation:
        request=SimpleNamespace(provider="codex",write_workspace=str(tmp_path/"workspace"))
        recovery_max_bytes=100
        def bind_capture_directory(self,path):
            assert path.parent==tmp_path/"capture" and path.is_dir()
            assert path.name.startswith("sdk-review-")
            self.path=path
            events.append("bind")
        def execute(self,runner):
            assert self.path.is_dir()
            events.append("execute")
        def recovery_bytes(self): return b'{"authorizing":false}\n'
        def receive(self): return SimpleNamespace(terminal_bytes=b"scanned\n",exit_code=0)
    monkeypatch.setattr(owner,"ProcessRunnerV1",Runner)
    monkeypatch.setattr(owner.sys,"stdout",SimpleNamespace(buffer=io.BytesIO()))
    with owner.ReservedExternalRunV1(owner.TerminalReceiptV1.reserve(tmp_path/"terminal")) as reserved:
        assert owner._launch_sdk_review(Operation(),reserved)==0
    assert events==["bind","runner","execute"]


@pytest.mark.parametrize("mode",["missing","denied"])
def test_unbound_worker_never_constructs_runner(tmp_path,monkeypatch,mode):
    class Operation:
        request=SimpleNamespace(provider="codex",write_workspace=str(tmp_path/"workspace"))
        def execute(self,*args): pytest.fail("worker executed before capture custody")
    operation=Operation()
    if mode=="denied":
        def denied(path): raise ValueError("capture is inside writable workspace")
        operation.bind_capture_directory=denied
    monkeypatch.setattr(owner,"ProcessRunnerV1",lambda:pytest.fail("runner before capture custody"))
    with owner.ReservedExternalRunV1(owner.TerminalReceiptV1.reserve(tmp_path/"terminal")) as reserved:
        assert owner._launch_sdk_review(operation,reserved)==1
    assert not list((tmp_path/"capture").iterdir())
