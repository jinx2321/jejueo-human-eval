import base64
import hmac
import hashlib
import time
import os
import streamlit as st

# No fixed roster and no real names: an evaluator can type any token they
# like. Which 1/NUM_GROUPS slice of each direction they see is derived from a
# stable hash of that token (see group_index_for_token), so the same token
# always maps to the same slice/assignment, and different tokens spread out
# evenly across the NUM_GROUPS slices. Each evaluator should pick their own
# distinct token - if two people reuse the same one, they'll share a single
# assignment and overwrite each other's scores.
NUM_GROUPS = 6

def group_index_for_token(token, num_groups=NUM_GROUPS):
    # hashlib (not the builtin hash()) so this is stable across processes/runs.
    digest = hashlib.sha256(token.encode('utf-8')).hexdigest()
    return int(digest, 16) % num_groups

# HMAC secret dynamically resolved from environment or generated per process
ACTIVATION_SECRET = os.environ.get(
    "ACTIVATION_SECRET",
    hashlib.sha256(b"participation_activation_secret_seed_2026").hexdigest()
).encode('utf-8')

def _encode_token(token):
    return base64.urlsafe_b64encode(token.encode('utf-8')).decode('ascii').rstrip('=')

def _decode_token(token_b64):
    padded = token_b64 + "=" * (-len(token_b64) % 4)
    return base64.urlsafe_b64decode(padded.encode('ascii')).decode('utf-8')

def create_activation_token(token, duration_seconds=600):
    """
    Generate a short-lived, HMAC-signed activation token containing the evaluator's
    chosen token and expiration timestamp. Lets a participant refresh/reopen the
    link within the window and be recognized (with the same assignment) again.
    """
    token_b64 = _encode_token(token)
    expires_at = int(time.time()) + duration_seconds
    expires_str = str(expires_at)
    payload = f"{token_b64}.{expires_str}"
    sig = hmac.new(ACTIVATION_SECRET, payload.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
    return f"{payload}.{sig}"

def verify_and_clean_activation_token():
    """
    Verify the HMAC signature and expiration time of the URL activation token.
    Expired or invalid tokens are automatically removed from st.query_params.
    Returns the evaluator's chosen token if valid, or None if the token is
    missing/invalid/expired.
    """
    raw = st.query_params.get("activation")
    if not raw:
        return None
    try:
        parts = raw.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid format")
        token_b64, expires_str, sig = parts
        expires_at = int(expires_str)

        # Verify HMAC signature
        payload = f"{token_b64}.{expires_str}"
        expected_sig = hmac.new(ACTIVATION_SECRET, payload.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("Signature mismatch")

        # Verify timestamp expiration
        if time.time() > expires_at:
            raise ValueError("Token expired")

        token = _decode_token(token_b64)
        if not token:
            raise ValueError("Empty token")

        return token
    except Exception:
        # Expired or invalid tokens are removed from URL query parameters
        if "activation" in st.query_params:
            del st.query_params["activation"]
        return None
