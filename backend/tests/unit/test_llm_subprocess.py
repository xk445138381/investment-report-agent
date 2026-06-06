from agents.analysis import llm_subprocess


def test_call_llm_sends_prompt_via_stdin(monkeypatch):
    captured = {}

    class Result:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["input"] = kwargs.get("input")
        return Result()

    long_prompt = "x" * 10000
    monkeypatch.setattr(llm_subprocess.subprocess, "run", fake_run)

    assert llm_subprocess.call_llm("key", "https://example.test", "model", long_prompt) == "ok"
    assert long_prompt not in captured["args"][2]
    assert long_prompt in captured["input"]
