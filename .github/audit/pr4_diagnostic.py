"""Read-only native admission diagnostic against the unchanged PR source."""
import dataclasses
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

root=Path(sys.argv[1]).resolve()
out=Path(sys.argv[2]).resolve();out.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(root))
from tests import test_process_runner_windows_runtime as tests
runner=tests._load_runner()
observed={'platform':sys.platform,'python':sys.version,'source_root':str(root),
          'environment_lengths':{k:len(os.environ.get(k,'')) for k in ('PATH','TEMP','TMP','SYSTEMROOT')}}
with tempfile.TemporaryDirectory(prefix='pr4-owner-diagnostic-') as directory:
    for name,cwd in [('checkout',root),('fresh_temp',Path(directory))]:
        try:
            observed[name]=dataclasses.asdict(runner.bind_cwd_identity(str(cwd)))
        except Exception:
            observed[name]={'traceback':traceback.format_exc()}
    request=tests._request(runner,(sys.executable,str(tests.CHILD),'identity'))
    try:
        observed['request_validation']=dataclasses.asdict(runner.validate_process_request(request))
    except Exception:
        observed['request_validation']={'traceback':traceback.format_exc()}
    with_trace=[]
    def trace(frame,event,arg):
        if event=='exception' and Path(frame.f_code.co_filename).name=='process_runner.py':
            error=arg[1]
            if isinstance(error,runner.ProcessSupervisionError) and len(with_trace)<30:
                with_trace.append({'function':frame.f_code.co_name,'line':frame.f_lineno,
                                   'failure_id':getattr(error,'failure_id',None),'message':str(error)})
        return trace
    sys.settrace(trace)
    owner=runner.ProcessRunnerV1()
    try:
        result=owner.run(request)
    finally:
        owner.close();sys.settrace(None)
    observed['result']={'outcome':result.outcome,'failure_id':result.failure_id,'exceptions':with_trace}
(out/'native-diagnostic.json').write_text(json.dumps(observed,indent=2),encoding='utf-8')
print(json.dumps(observed,indent=2))
