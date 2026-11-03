import json

import pytest
import sentry_sdk
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport

from app.core import sentry

MARKER = "ZQXMARKER9917"


class CollectingTransport(Transport):
    def __init__(self) -> None:
        super().__init__({})
        self.sent: list[str] = []

    def capture_envelope(self, envelope: Envelope) -> None:
        for item in envelope.items:
            self.sent.append(json.dumps(item.payload.json, default=str))


def explode(request_value: str) -> None:
    request_body = f"{MARKER} lives in a local variable"  # noqa: F841
    raise RuntimeError("failed")


def test_a_captured_error_carries_no_local_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = CollectingTransport()
    real_init = sentry_sdk.init
    monkeypatch.setattr(
        sentry_sdk,
        "init",
        lambda **options: real_init(**{**options, "dsn": "http://key@localhost/1", "transport": transport}),
    )
    sentry.init_sentry()
    try:
        try:
            explode(MARKER)
        except RuntimeError as error:
            sentry_sdk.capture_exception(error)
        sentry_sdk.flush()
    finally:
        sentry_sdk.init()  # Back to no client.

    assert transport.sent, "the error should have been captured, or this proves nothing"
    assert not any(MARKER in event for event in transport.sent)
