import json

import httpx
import pytest
from common.errors import UpstreamServiceError

from functions.notify.channels import LogChannel, Message, WebhookChannel, channel_for

MESSAGE = Message(
    tenant_id="uni-a",
    application_id="app-1",
    event="approved",
    medium="email",
    language="en",
    text="University A: application app-1 verified.",
)


def test_log_channel_records():
    channel = LogChannel()
    channel.send(MESSAGE)
    assert channel.sent == [MESSAGE]


def test_webhook_posts_message():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(202)

    WebhookChannel(
        "http://portal/api/notifications", httpx.Client(transport=httpx.MockTransport(handler))
    ).send(MESSAGE)
    assert seen[0]["medium"] == "email" and seen[0]["application_id"] == "app-1"


def test_webhook_failure_raises():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    with pytest.raises(UpstreamServiceError):
        WebhookChannel("http://portal/x", client).send(MESSAGE)


@pytest.mark.parametrize(
    ("medium", "portal", "kind"),
    [
        ("log", "https://p", LogChannel),
        ("sms", "https://p", WebhookChannel),
        ("email", "", LogChannel),
    ],
)
def test_channel_selection(medium, portal, kind):
    assert isinstance(channel_for(medium, portal), kind)
