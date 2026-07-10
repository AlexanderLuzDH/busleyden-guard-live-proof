from src.auth.session import SessionRegistry


def test_first_token_use_is_accepted():
    registry = SessionRegistry()
    assert registry.accept("signed-token") is True