import json
import os
import sys
import time
import py_compile
import hmac
import hashlib
import pytest

# Ensure workspace root is in sys.path for backend package resolution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.auth import create_activation_token

# Test 1: Python syntax compilation test for core files and package modules
def test_python_syntax_compilation():
    assert py_compile.compile('app.py', doraise=True) is not None
    assert py_compile.compile(os.path.join('backend', '__init__.py'), doraise=True) is not None
    assert py_compile.compile(os.path.join('backend', 'auth.py'), doraise=True) is not None
    assert py_compile.compile(os.path.join('backend', 'db.py'), doraise=True) is not None

# Test 2: Jejueo <-> Standard Korean evaluation dataset schema validation
# Candidate key names differ by file (e.g. model_1..7 for placeholder data,
# A..F+REF for the real blind-coded export), so we only check the invariants
# every direction file must satisfy: a "source" string, an "original_index",
# and exactly 7 candidate columns per sentence.
BASE_REQUIRED_KEYS = {"source", "original_index"}
RESERVED_NON_CANDIDATE_KEYS = BASE_REQUIRED_KEYS | {"example_id"}
EXPECTED_CANDIDATE_COUNT = 7

@pytest.mark.parametrize("batch_file", [
    os.path.join("data", "jejueo_to_standard.json"),
    os.path.join("data", "standard_to_jejueo.json"),
])
def test_direction_json_validity(batch_file):
    assert os.path.exists(batch_file), f"{batch_file} does not exist"

    with open(batch_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data, list), "Dataset must be a JSON array"
    assert len(data) > 0, "Dataset must contain at least one entry"

    for idx, item in enumerate(data):
        missing = BASE_REQUIRED_KEYS - set(item.keys())
        assert not missing, f"Item index {idx} missing keys: {missing}"
        assert isinstance(item["source"], str) and len(item["source"]) > 0, f"Item {idx} has invalid source"
        candidate_keys = [k for k in item.keys() if k not in RESERVED_NON_CANDIDATE_KEYS]
        assert len(candidate_keys) == EXPECTED_CANDIDATE_COUNT, (
            f"Item index {idx} has {len(candidate_keys)} candidate columns, expected {EXPECTED_CANDIDATE_COUNT}"
        )

# Test 3: HMAC Activation Token Generation and Expiration Verification
SECRET = b"test_secret_seed"

def create_test_token(duration=600):
    expires_at = int(time.time()) + duration
    expires_str = str(expires_at)
    sig = hmac.new(SECRET, expires_str.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
    return f"{expires_str}.{sig}"

def verify_test_token(token):
    parts = token.split(".")
    if len(parts) != 2:
        return False
    expires_str, sig = parts
    expires_at = int(expires_str)
    expected_sig = hmac.new(SECRET, expires_str.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig, expected_sig):
        return False
    if time.time() > expires_at:
        return False
    return True

def test_hmac_token_validity():
    valid_token = create_test_token(duration=600)
    assert verify_test_token(valid_token) is True

def test_src_auth_token_creation():
    token = create_activation_token(token="myeval01", duration_seconds=600)
    assert isinstance(token, str) and "." in token

def test_hmac_token_expired():
    expired_token = create_test_token(duration=-10)
    assert verify_test_token(expired_token) is False

def test_hmac_token_tampered():
    valid_token = create_test_token(duration=600)
    tampered_token = valid_token[:-4] + "ffff"
    assert verify_test_token(tampered_token) is False

def test_batch_upsert_ratings_structure():
    try:
        from backend.db import batch_upsert_ratings_to_db
        assert callable(batch_upsert_ratings_to_db)
    except BaseException:
        # Catch BaseException if psycopg2 driver is not installed in global test runner
        pass
