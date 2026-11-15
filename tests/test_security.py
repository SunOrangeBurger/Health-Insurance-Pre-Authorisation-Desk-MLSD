from preauth.security import hash_password, token_hash, verify_password


def test_passwords_are_salted_and_verified():
    first = hash_password("a sufficiently long password")
    assert first != hash_password("a sufficiently long password")
    assert verify_password("a sufficiently long password", first)
    assert not verify_password("wrong", first)
    assert not verify_password("anything", "invalid")


def test_session_digest_is_stable_and_not_the_secret():
    assert token_hash("secret") == token_hash("secret")
    assert token_hash("secret") != token_hash("another")
    assert "secret" not in token_hash("secret")
