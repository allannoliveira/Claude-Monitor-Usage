import json
from datetime import datetime, timedelta, timezone

from claude_monitor import local_logs
from claude_monitor.formatting import compact_until, human_tokens, level
from claude_monitor.usage_api import parse_usage_body
from claude_monitor.widget_render import STYLE_ORDER, Row, next_style, render

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def test_compact_until():
    assert compact_until(NOW + timedelta(minutes=35), NOW) == "35m"
    assert compact_until(NOW + timedelta(hours=2, minutes=59), NOW) == "2h"
    assert compact_until(NOW + timedelta(days=4, hours=1), NOW) == "4d"
    assert compact_until(NOW - timedelta(minutes=1), NOW) == "0m"
    assert compact_until(None, NOW) == "—"


def test_human_tokens_and_level():
    assert human_tokens(999) == "999"
    assert human_tokens(52_700) == "52.7k"
    assert human_tokens(3_600_000) == "3.6M"
    assert (level(10), level(75), level(95)) == ("ok", "warn", "crit")


def test_parse_usage_body_classic():
    body = {
        "five_hour": {"utilization": 79.0, "resets_at": "2026-10-09T14:00:00Z"},
        "seven_day": {"utilization": 11.0, "resets_at": "2026-10-13T12:00:00+00:00"},
        "seven_day_opus": None,
    }
    windows, credits = parse_usage_body(body)
    assert [w.key for w in windows] == ["five_hour", "seven_day"]
    assert windows[0].percentage == 79.0
    assert windows[0].resets_at == datetime(2026, 10, 9, 14, 0, tzinfo=timezone.utc)
    assert credits is None


def test_parse_usage_body_limits_array():
    body = {"limits": [
        {"kind": "session", "percent": 40, "resets_at": "2026-10-09T14:00:00Z"},
        {"kind": "weekly_all", "percent": 5},
        {"kind": "weekly", "percent": 12, "scope": {"model": {"display_name": "Opus"}}},
    ]}
    windows, _ = parse_usage_body(body)
    keys = {w.key: w.percentage for w in windows}
    assert keys["five_hour"] == 40 and keys["seven_day"] == 5
    assert any("Opus" in w.label for w in windows)


def test_render_all_styles():
    rows = [Row("5h", 79, NOW + timedelta(hours=2)), Row("7d", None, None)]
    for style in STYLE_ORDER:
        for scale in (1.0, 1.5):
            img = render(rows, style, round(48 * scale), scale)
            assert img.mode == "RGBA" and img.height == round(48 * scale) and img.width > 50
    assert next_style(STYLE_ORDER[-1]) == STYLE_ORDER[0]


def test_local_logs_dedupe(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    project = tmp_path / "projects" / "demo"
    project.mkdir(parents=True)
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    usage = {"input_tokens": 10, "output_tokens": 20,
             "cache_creation_input_tokens": 30, "cache_read_input_tokens": 40}
    line = {"type": "assistant", "timestamp": ts, "requestId": "req_1",
            "message": {"id": "msg_1", "model": "claude-opus-5-5", "usage": usage}}
    # a mesma mensagem aparece 2x (streaming) + uma linha sem usage
    (project / "s.jsonl").write_text(
        "\n".join([json.dumps(line), json.dumps(line), json.dumps({"type": "user"})]),
        encoding="utf-8",
    )
    result = local_logs.collect_local_usage()
    assert result.last_5h.messages == 1
    assert result.last_5h.total == 100
    assert "claude-opus-5-5" in result.by_model_5h
