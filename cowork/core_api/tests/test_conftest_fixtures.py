from app.security import decode_access_token


def test_test_user_fixture_creates_persisted_user(db_session, test_user):
    found_user = db_session.get(type(test_user), test_user.id)
    assert found_user is not None
    assert found_user.email == test_user.email


def test_auth_token_fixture_targets_test_user(auth_token, test_user):
    assert decode_access_token(auth_token) == test_user.id


def test_auth_headers_fixture_uses_bearer_token(auth_headers, auth_token):
    assert auth_headers["Authorization"] == f"Bearer {auth_token}"
