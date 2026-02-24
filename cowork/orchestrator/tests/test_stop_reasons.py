from __future__ import annotations

from app.runtime.stop_reasons import StopReason, build_error_end, build_error_event, build_stopped_end


def test_build_error_end_normalizes_unknown_stop_reason_to_model_call_failed() -> None:
    payload = build_error_end("unexpected_provider_failure", "upstream error")
    assert payload["stop_reason"] == StopReason.model_call_failed.value


def test_build_stopped_end_normalizes_unknown_stop_reason_to_user_stop() -> None:
    payload = build_stopped_end("manual_interrupt_from_ui", reason="manual interrupt from ui")
    assert payload["stop_reason"] == StopReason.user_stop.value


def test_build_error_event_normalizes_unknown_stop_reason() -> None:
    payload = build_error_event("failed", stop_reason="arbitrary_reason")
    assert payload["stop_reason"] == StopReason.model_call_failed.value
