import base64
import hmac
import hashlib
import time
import os
import streamlit as st

# No real names anywhere in this system. Each evaluator picks their own
# anonymous ID from a short list; that ID is both their login identity and
# the key everything (scores, notes, exports) is stored under. Coordinate
# out-of-band (e.g. text message) so each real evaluator knows which ID is
# theirs, and that no two people use the same one.
ADMIN_ID = "관리자"  # full-access / preview identity, not a real evaluator

EVALUATOR_ID_TO_GROUP = {
    "평가자1": "group_a",
    "평가자2": "group_b",
    "평가자3": "group_c",
}

EVALUATOR_LOGIN_CHOICES = list(EVALUATOR_ID_TO_GROUP.keys()) + [ADMIN_ID]

def group_for_evaluator(evaluator_id):
    return EVALUATOR_ID_TO_GROUP.get(evaluator_id)  # None for ADMIN_ID / unrecognized

# HMAC secret dynamically resolved from environment or generated per process
ACTIVATION_SECRET = os.environ.get(
    "ACTIVATION_SECRET",
    hashlib.sha256(b"participation_activation_secret_seed_2026").hexdigest()
).encode('utf-8')

def _encode_id(evaluator_id):
    return base64.urlsafe_b64encode(evaluator_id.encode('utf-8')).decode('ascii').rstrip('=')

def _decode_id(id_b64):
    padded = id_b64 + "=" * (-len(id_b64) % 4)
    return base64.urlsafe_b64decode(padded.encode('ascii')).decode('utf-8')

def create_activation_token(evaluator_id, duration_seconds=600):
    """
    Generate a short-lived, HMAC-signed activation token containing the evaluator's
    chosen ID and expiration timestamp. Lets a participant refresh/reopen the link
    within the window and be recognized (with the same assignment) again.
    """
    id_b64 = _encode_id(evaluator_id)
    expires_at = int(time.time()) + duration_seconds
    expires_str = str(expires_at)
    payload = f"{id_b64}.{expires_str}"
    sig = hmac.new(ACTIVATION_SECRET, payload.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
    return f"{payload}.{sig}"

def verify_and_clean_activation_token():
    """
    Verify the HMAC signature and expiration time of the URL activation token.
    Expired or invalid tokens are automatically removed from st.query_params.
    Returns the evaluator's chosen ID if valid, or None if the token is
    missing/invalid/expired/no longer a recognized ID.
    """
    token = st.query_params.get("activation")
    if not token:
        return None
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid format")
        id_b64, expires_str, sig = parts
        expires_at = int(expires_str)

        # Verify HMAC signature
        payload = f"{id_b64}.{expires_str}"
        expected_sig = hmac.new(ACTIVATION_SECRET, payload.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("Signature mismatch")

        # Verify timestamp expiration
        if time.time() > expires_at:
            raise ValueError("Token expired")

        evaluator_id = _decode_id(id_b64)
        if evaluator_id not in EVALUATOR_LOGIN_CHOICES:
            raise ValueError("Unrecognized evaluator id")

        return evaluator_id
    except Exception:
        # Expired or invalid tokens are removed from URL query parameters
        if "activation" in st.query_params:
            del st.query_params["activation"]
        return None
