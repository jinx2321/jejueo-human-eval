import json
import os
import time
import py_compile
import hmac
import hashlib
import pytest

# Test 1: Python syntax compilation test for core files
def test_python_syntax_compilation():
    assert py_compile.compile('app.py', doraise=True) is not None
    assert py_compile.compile('sampling.py', doraise=True) is not None

# Test 2: evaluation_batch_100.json schema and entry verification
def test_evaluation_batch_json_validity():
    batch_file = "evaluation_batch_100.json"
    assert os.path.exists(batch_file), f"{batch_file} does not exist"
    
    with open(batch_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert isinstance(data, list), "Dataset must be a JSON array"
    assert len(data) == 100, f"Expected 100 entries, got {len(data)}"
    
    required_keys = {"source", "reference", "10M", "100M", "Llama_Simple", "Llama_Preserve", "Llama_FewShot", "OpenAI", "original_index"}
    for idx, item in enumerate(data):
        missing = required_keys - set(item.keys())
        assert not missing, f"Item index {idx} missing keys: {missing}"
        assert isinstance(item["source"], str) and len(item["source"]) > 0, f"Item {idx} has invalid source"

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

def test_hmac_token_expired():
    expired_token = create_test_token(duration=-10)
    assert verify_test_token(expired_token) is False

def test_hmac_token_tampered():
    valid_token = create_test_token(duration=600)
    tampered_token = valid_token[:-4] + "ffff"
    assert verify_test_token(tampered_token) is False
