import json

import pytest
from pydantic import BaseModel

from common.errors import InvalidRequestError, TenantNotFoundError
from common.http import body_bytes, header, http_handler, json_response, parse_body
from common.testing import FakeHttpEvent


class Payload(BaseModel):
    name: str
    count: int


def test_json_response_shapes():
    response = json_response(201, Payload(name="x", count=1))
    assert response["statusCode"] == 201
    assert json.loads(response["body"]) == {"name": "x", "count": 1}
    assert response["headers"]["Content-Type"] == "application/json"


def test_header_lookup_is_case_insensitive():
    event = FakeHttpEvent(headers={"X-Tenant-Id": "uni-a"})
    assert header(event, "x-tenant-id") == "uni-a"
    assert header(event, "missing") is None


def test_body_bytes_accepts_str():
    assert body_bytes(FakeHttpEvent(body="hé")) == "hé".encode()


def test_parse_body_reports_field_names_only():
    event = FakeHttpEvent(body=json.dumps({"name": "35202-1234567-3", "count": "many"}))
    with pytest.raises(InvalidRequestError) as info:
        parse_body(event, Payload)
    assert "count" in str(info.value)
    assert "35202" not in str(info.value)


def test_handler_maps_domain_errors():
    @http_handler
    def handler(event, context):
        raise TenantNotFoundError("uni-z")

    response = handler(FakeHttpEvent(), None)
    assert response["statusCode"] == 404
    assert json.loads(response["body"]) == {"error": "tenant_not_found"}


def test_handler_hides_unexpected_errors():
    @http_handler
    def handler(event, context):
        raise RuntimeError("secret internals")

    response = handler(FakeHttpEvent(), None)
    assert response["statusCode"] == 500
    assert "secret" not in response["body"]
