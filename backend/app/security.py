"""Signing keys, demo passes and role tokens."""
import base64
import hashlib
import hmac
import json
import time
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .config import BACKEND_DIR, settings

KEYS_DIR = BACKEND_DIR / "keys"


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def b64u_dec(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _load_key(env_value: str, name: str) -> Ed25519PrivateKey:
    if env_value:
        return Ed25519PrivateKey.from_private_bytes(base64.b64decode(env_value))
    KEYS_DIR.mkdir(exist_ok=True)
    path = KEYS_DIR / f"{name}.key"
    if not path.exists():
        raw = Ed25519PrivateKey.generate().private_bytes(
            serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
        path.write_text(base64.b64encode(raw).decode())
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(path.read_text().strip()))


class Signer:
    def __init__(self, env_value: str, name: str):
        self._key = _load_key(env_value, name)
        self.public_raw = self._key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.key_id = name + "-" + hashlib.sha256(self.public_raw).hexdigest()[:8]

    @property
    def public_b64(self) -> str:
        return base64.b64encode(self.public_raw).decode()

    def sign(self, data: bytes) -> bytes:
        return self._key.sign(data)

    def verify(self, data: bytes, sig: bytes) -> bool:
        try:
            Ed25519PublicKey.from_public_bytes(self.public_raw).verify(sig, data)
            return True
        except Exception:
            return False


_pass_signer: Signer | None = None
_log_signer: Signer | None = None


def pass_signer() -> Signer:
    global _pass_signer
    if _pass_signer is None:
        _pass_signer = Signer(settings.pass_signing_key, "pass")
    return _pass_signer


def log_signer() -> Signer:
    global _log_signer
    if _log_signer is None:
        _log_signer = Signer(settings.log_signing_key, "log")
    return _log_signer


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


# --- Demo trip pass -------------------------------------------------------------------------

def issue_pass(trip_label: str, route_id: str, valid_from: float, valid_to: float, kyc_level: str = "demo"):
    payload = {"pass_id": "P-" + uuid.uuid4().hex[:10], "trip_label": trip_label, "route_id": route_id,
               "valid_from": int(valid_from), "valid_to": int(valid_to), "kyc_level": kyc_level}
    body = canonical(payload)
    qr = b64u(body) + "." + b64u(pass_signer().sign(body))
    return payload, qr


def verify_pass(qr: str, now: float | None = None) -> dict:
    now = now or time.time()
    try:
        body_s, sig_s = qr.strip().split(".", 1)
        body, sig = b64u_dec(body_s), b64u_dec(sig_s)
        payload = json.loads(body)
    except Exception:
        return {"valid": False, "reason": "unreadable"}
    if not pass_signer().verify(body, sig):
        return {"valid": False, "reason": "forged", "payload": payload}
    if now > payload.get("valid_to", 0):
        return {"valid": False, "reason": "expired", "payload": payload}
    if now < payload.get("valid_from", 0) - 3600:
        return {"valid": False, "reason": "not_yet_valid", "payload": payload}
    return {"valid": True, "reason": "ok", "payload": payload}


# --- Role tokens (responder / presenter) -----------------------------------------------------

def make_role_token(role: str, ttl_s: int = 24 * 3600) -> str:
    exp = int(time.time()) + ttl_s
    msg = f"{role}.{exp}"
    mac = hmac.new(settings.token_secret.encode(), msg.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{msg}.{mac}"


def check_role_token(token: str | None) -> str | None:
    if not token or token.count(".") != 2:
        return None
    role, exp, mac = token.split(".")
    good = hmac.new(settings.token_secret.encode(), f"{role}.{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(mac, good) or int(exp) < time.time():
        return None
    return role
