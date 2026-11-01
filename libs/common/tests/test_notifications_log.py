from common.repositories.notifications import InMemoryNotificationLog


def test_claim_is_exclusive_until_released():
    log = InMemoryNotificationLog()
    assert log.claim("uni-a", "app-1", "approved", "log", "en")
    assert not log.claim("uni-a", "app-1", "approved", "log", "en")
    assert log.claim("uni-a", "app-1", "rejected", "log", "en")
    assert log.claim("uni-b", "app-1", "approved", "log", "en")
    log.release("uni-a", "app-1", "approved")
    assert log.claim("uni-a", "app-1", "approved", "log", "en")
