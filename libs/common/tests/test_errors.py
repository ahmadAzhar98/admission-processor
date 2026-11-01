import pytest

from common import errors


@pytest.mark.parametrize(
    ("exc", "status"),
    [
        (errors.TenantNotFoundError, 404),
        (errors.AuthenticationError, 401),
        (errors.InvalidRequestError, 400),
        (errors.ObjectNotFoundError, 404),
        (errors.UpstreamServiceError, 502),
    ],
)
def test_errors_carry_http_status(exc, status):
    assert exc.http_status == status


def test_all_errors_share_a_base_class():
    for exc in (errors.TenantConfigError, errors.StorageError, errors.DatabaseError):
        assert issubclass(exc, errors.AdmissionError)


def test_codes_are_unique():
    classes = [
        obj
        for obj in vars(errors).values()
        if isinstance(obj, type) and issubclass(obj, errors.AdmissionError)
    ]
    codes = [cls.code for cls in classes]
    assert len(codes) == len(set(codes))
