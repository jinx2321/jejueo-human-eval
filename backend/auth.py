import hmac
import hashlib
import time
import os
import streamlit as st

CLASSROOM_PASSWORDS = {"TUM2026"}

# HMAC secret dynamically resolved from environment or generated per process
ACTIVATION_SECRET = os.environ.get(
    "ACTIVATION_SECRET", 
    hashlib.sha256(b"classroom_activation_secret_seed_2026").hexdigest()
).encode('utf-8')

def create_activation_token(duration_seconds=600):
    """
    Generate a short-lived, HMAC-signed activation token containing only the expiration timestamp.
    Intended as a classroom convenience layer for 10-minute refresh reuse across browser reloads.
    """
    expires_at = int(time.time()) + duration_seconds
    expires_str = str(expires_at)
    sig = hmac.new(ACTIVATION_SECRET, expires_str.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
    return f"{expires_str}.{sig}"

def verify_and_clean_activation_token():
    """
    Verify the HMAC signature and expiration time of the URL activation token.
    Expired or invalid tokens are automatically removed from st.query_params.
    """
    token = st.query_params.get("activation")
    if not token:
        return False
    try:
        parts = token.split(".")
        if len(parts) != 2:
            raise ValueError("Invalid format")
        expires_str, sig = parts
        expires_at = int(expires_str)
        
        # Verify HMAC signature
        expected_sig = hmac.new(ACTIVATION_SECRET, expires_str.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("Signature mismatch")
        
        # Verify timestamp expiration
        if time.time() > expires_at:
            raise ValueError("Token expired")
            
        return True
    except Exception:
        # Expired or invalid tokens are removed from URL query parameters
        if "activation" in st.query_params:
            del st.query_params["activation"]
        return False
