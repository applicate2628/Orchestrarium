"""Full-state Grok profile drift; offline protocol evidence, no native launch."""
import pytest
from test_sdk_grok import GrokAcpExchange, Peer, config, request, response, successful_frames


def update(options):
    return {'jsonrpc':'2.0','method':'session/update','params':{'sessionId':'session-fixture',
        'update':{'sessionUpdate':'config_option_update','configOptions':options}}}


@pytest.mark.parametrize('options', [config(model='other'), config(effort='low'), config()[:1]])
def test_close_drift_is_sticky_and_drains_actual_close(options):
    frames = successful_frames()
    frames[-1:-1] = [update(options), update(config())]
    peer = Peer(frames)
    exchange = GrokAcpExchange(auth_method='fixture-auth')
    result = exchange.run(request(), peer)
    assert result.execution_error == 'grok_config_mismatch'
    assert result.protocol_closed
    assert result.native_result_text == 'Native review'
    assert result.status == 'incomplete'
    assert not peer.responses
    assert sum(f.get('method') == 'session/prompt' for f in peer.sent) == 1
    with pytest.raises(ValueError, match='consumed'):
        exchange.run(request(), peer)


def test_already_selected_model_drift_during_effort_setter_cannot_be_restored():
    frames = successful_frames()
    frames[4:4] = [update(config(model='other')), update(config())]
    frames[7:] = [response(6, {})]  # only cleanup is allowed after setter completion
    peer = Peer(frames)
    result = GrokAcpExchange(auth_method='fixture-auth').run(request(), peer)
    assert result.execution_error == 'grok_config_mismatch'
    assert result.protocol_closed
    assert not any(f.get('method') == 'session/prompt' for f in peer.sent)
    assert sum(f.get('method') == 'session/set_config_option' for f in peer.sent) == 2


def test_prompt_drift_drains_text_and_ignores_unrelated_options():
    frames = successful_frames()
    restored = config() + [{'id':'display','type':'future','currentValue':{'opaque':True}}]
    frames[5:5] = [update(config(model='other')), update(restored)]
    peer = Peer(frames)
    result = GrokAcpExchange(auth_method='fixture-auth').run(request(), peer)
    assert result.execution_error == 'grok_config_mismatch'
    assert result.native_result_text == 'Native review'
    assert result.protocol_closed and not peer.responses
