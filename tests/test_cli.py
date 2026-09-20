import pytest

from lakematch.cli import main


@pytest.mark.parametrize('args', [['run'], ['train'], ['cluster'], ['doctor'], ['bench']])
def test_commands_reject_missing_required_inputs(args):
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2


def test_bench_all_needs_no_engine_config_and_passes_explicit_root(monkeypatch, capsys):
    from lakematch.benchmark import campaign
    calls = []
    def execute(**kwargs):
        calls.append(kwargs)
        return {'status': 'plan_only'}
    monkeypatch.setattr(campaign, 'execute', execute)
    main(['bench', '--all', '--plan', '--project-root', '/prepared/checkout'])
    assert calls == [{'project_root': '/prepared/checkout', 'plan': True}]
    assert 'plan_only' in capsys.readouterr().out


def test_normal_commands_reject_benchmark_switches():
    with pytest.raises(SystemExit) as exc:
        main(['run', '--config', 'examples/synthetic.yaml', '--all'])
    assert exc.value.code == 2
