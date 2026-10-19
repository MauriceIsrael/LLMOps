"""Signed actor assertion verification with EdDSA (Ed25519), JWKS, anti-replay and revocation.

Implements the cryptographic identity layer for KB governance (issue #7, ADR D3 evolution):
- EdDSA (Ed25519) algorithm for compact, fast and secure asymmetric signatures.
- Published JWKS (RFC 8037 OKP Ed25519 format).
- Anti-replay protection enforcing unique `jti` per assertion with expiration tracking.
- Immediate revocation for `jti`, expert handles and email addresses.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

DEFAULT_ISSUER = "archinex"
DEFAULT_AUDIENCE = "knowledge-hub"
DEFAULT_EXP_SECONDS = 300  # 5 minutes
DEFAULT_MAX_TTL_SECONDS = 900  # longest lifetime (exp - iat) the Hub accepts, ARCHINEX_ASSERTION_MAX_TTL
DEFAULT_CLOCK_SKEW_SECONDS = 30  # tolerance on iat / nbf / exp, ARCHINEX_CLOCK_SKEW
JWKS_URL_TTL_SECONDS = 300  # a fetched key set is trusted this long before it is read again
JWKS_URL_RETRY_SECONDS = 30  # shortest delay between two fetches (unknown kid, failed fetch)

logger = logging.getLogger(__name__)


def _seconds_from_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, "").strip())
    except ValueError:
        return default
    return value if value >= 0 else default


def max_ttl_seconds() -> int:
    return _seconds_from_env("ARCHINEX_ASSERTION_MAX_TTL", DEFAULT_MAX_TTL_SECONDS)


def clock_skew_seconds() -> int:
    return _seconds_from_env("ARCHINEX_CLOCK_SKEW", DEFAULT_CLOCK_SKEW_SECONDS)


class ActorAssertionError(ValueError):
    """Raised when an actor assertion cannot be verified."""

    def __init__(self, reason: str, code: str = "invalid_assertion") -> None:
        self.reason = reason
        self.code = code
        super().__init__(f"{code}: {reason}")


def generate_ed25519_keypair(kid: str | None = None) -> tuple[ed25519.Ed25519PrivateKey, dict[str, Any]]:
    """Generate an Ed25519 private key and its public JWK representation (RFC 8037)."""
    private_key = ed25519.Ed25519PrivateKey.generate()
    key_id = kid or str(uuid.uuid4())[:8]
    jwk = public_key_to_jwk(private_key.public_key(), kid=key_id)
    return private_key, jwk


def public_key_to_jwk(public_key: ed25519.Ed25519PublicKey, kid: str | None = None) -> dict[str, Any]:
    """Convert an Ed25519 public key into an RFC 8037 compliant JWK dict."""
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    x = base64.urlsafe_b64encode(pub_bytes).decode("ascii").rstrip("=")
    jwk: dict[str, Any] = {
        "kty": "OKP",
        "crv": "Ed25519",
        "x": x,
        "use": "sig",
    }
    if kid:
        jwk["kid"] = kid
    return jwk


def jwk_to_public_key(jwk: dict[str, Any]) -> ed25519.Ed25519PublicKey:
    """Parse an RFC 8037 OKP Ed25519 JWK dict into an Ed25519PublicKey."""
    if jwk.get("kty") != "OKP" or jwk.get("crv") != "Ed25519":
        raise ValueError(f"Unsupported JWK key type / curve: kty={jwk.get('kty')} crv={jwk.get('crv')}")
    x_b64 = str(jwk.get("x") or "")
    if not x_b64:
        raise ValueError("Missing 'x' coordinate in Ed25519 JWK")
    raw = base64.urlsafe_b64decode(x_b64 + "=" * (-len(x_b64) % 4))
    return ed25519.Ed25519PublicKey.from_public_bytes(raw)


class JWKSRegistry:
    """Registry of trusted public keys for validating Archinex actor assertions."""

    def __init__(self) -> None:
        self._keys_by_kid: dict[str, ed25519.Ed25519PublicKey] = {}
        self._default_key: ed25519.Ed25519PublicKey | None = None
        self._jwks_cache: dict[str, Any] = {"keys": []}
        self._lock = threading.Lock()
        self._env_signatures: dict[str, str] = {}  # source name -> what it held when it was last read
        self._url_kids: set[str] = set()  # the keys that came from ARCHINEX_JWKS_URL (and expire with it)
        self._url_fetched_at = 0.0
        self._url_attempted_at = 0.0

    def clear(self) -> None:
        with self._lock:
            self._keys_by_kid.clear()
            self._default_key = None
            self._jwks_cache = {"keys": []}
            self._env_signatures.clear()
            self._url_kids.clear()
            self._url_fetched_at = 0.0
            self._url_attempted_at = 0.0

    def remove_key(self, kid: str) -> None:
        with self._lock:
            self._keys_by_kid.pop(kid, None)
            self._jwks_cache = {"keys": [k for k in self._jwks_cache.get("keys", []) if k.get("kid") != kid]}
            if self._default_key is not None and not self._keys_by_kid:
                self._default_key = None

    def add_public_key(self, key: ed25519.Ed25519PublicKey, kid: str | None = None) -> str:
        with self._lock:
            key_id = kid or str(uuid.uuid4())[:8]
            self._keys_by_kid[key_id] = key
            if self._default_key is None:
                self._default_key = key
            jwk = public_key_to_jwk(key, kid=key_id)
            # Update cache
            keys = [k for k in self._jwks_cache.get("keys", []) if k.get("kid") != key_id]
            keys.append(jwk)
            self._jwks_cache = {"keys": keys}
            return key_id

    def add_jwk(self, jwk: dict[str, Any]) -> str:
        key = jwk_to_public_key(jwk)
        kid = jwk.get("kid")
        return self.add_public_key(key, kid=kid)

    def add_jwks(self, jwks: dict[str, Any]) -> None:
        for k in jwks.get("keys", []):
            self.add_jwk(k)

    def refresh_from_environment(self, kid: str | None = None) -> None:
        """Register the public keys a deployment trusts, from the environment (never raises).

        * ``ARCHINEX_JWKS``: a JWKS document (``{"keys": [...]}``) in the variable itself;
        * ``ARCHINEX_JWKS_FILE``: the path of a file holding one (a file replaced on disk is read again);
        * ``ARCHINEX_JWKS_URL``: fetched (``https``, or ``http`` on loopback) and kept for ``JWKS_URL_TTL_SECONDS``; read
          again at most every ``JWKS_URL_RETRY_SECONDS``, and at once when a ``kid`` is unknown (a key rotation).

        Fail closed: a source that cannot be read or parsed contributes no key, and keys that came from the URL are dropped
        when the URL has been unreachable for longer than the cache lifetime, never trusted past it.
        """
        raw = os.getenv("ARCHINEX_JWKS", "").strip()
        if raw:
            if raw.startswith(("{", "[")):
                self._load_text("ARCHINEX_JWKS", raw, raw)
            else:
                logger.warning("ARCHINEX_JWKS must hold the JWKS document itself; a file path goes in ARCHINEX_JWKS_FILE")
        file_path = os.getenv("ARCHINEX_JWKS_FILE", "").strip()
        if file_path:
            self._load_file(file_path)
        url = os.getenv("ARCHINEX_JWKS_URL", "").strip()
        if url:
            self._refresh_url(url, kid)

    def _load_file(self, file_path: str) -> None:
        path = Path(file_path)
        try:
            signature = f"{path}:{path.stat().st_mtime_ns}"
            if self._env_signatures.get("ARCHINEX_JWKS_FILE") == signature:
                return
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("ARCHINEX_JWKS_FILE: cannot read %s (%s); no key is trusted from it", file_path, exc)
            return
        self._load_text(f"ARCHINEX_JWKS_FILE ({path})", text, signature, name="ARCHINEX_JWKS_FILE")

    def _load_text(self, source: str, text: str, signature: str, name: str | None = None) -> None:
        key = name or source
        with self._lock:
            if self._env_signatures.get(key) == signature:
                return
            self._env_signatures[key] = signature
        self._add_document(text, source)

    def _refresh_url(self, url: str, kid: str | None) -> None:
        now = time.time()
        stale = now - self._url_fetched_at >= JWKS_URL_TTL_SECONDS
        unknown = bool(kid) and kid not in self._keys_by_kid
        if (stale or unknown) and now - self._url_attempted_at >= JWKS_URL_RETRY_SECONDS:
            self._url_attempted_at = now
            if self._load_url(url):
                self._url_fetched_at = now
        if now - self._url_fetched_at >= JWKS_URL_TTL_SECONDS and self._url_kids:
            # The URL could not be read again in time: its keys are not trusted any longer (fail closed).
            logger.error("ARCHINEX_JWKS_URL unreachable for over %s s: its keys are no longer trusted", JWKS_URL_TTL_SECONDS)
            for old in list(self._url_kids):
                self.remove_key(old)
            self._url_kids.clear()

    def _load_url(self, url: str) -> bool:
        parsed = urlparse(url)
        loopback = parsed.hostname in ("localhost", "127.0.0.1", "::1")
        if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
            logger.warning("ARCHINEX_JWKS_URL must be https (or http on loopback); no key is trusted from %s", url)
            return False
        try:
            with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310 - scheme checked above
                text = response.read(1_000_000).decode("utf-8")
        except Exception as exc:  # network, TLS, decoding: trust nothing new
            logger.warning("ARCHINEX_JWKS_URL: cannot fetch %s (%s); no key is trusted from it", url, exc)
            return False
        kids = self._add_document(text, f"ARCHINEX_JWKS_URL ({url})")
        if kids is None:
            return False
        for gone in self._url_kids - kids:  # a key withdrawn from the published set is withdrawn here too
            self.remove_key(gone)
        self._url_kids = kids
        return True

    def _add_document(self, text: str, source: str) -> set[str] | None:
        try:
            document = json.loads(text)
            keys = document.get("keys") if isinstance(document, dict) else document
            if not isinstance(keys, list) or not keys:
                raise ValueError("no 'keys' array")
            parsed = [(jwk_to_public_key(jwk), jwk.get("kid")) for jwk in keys]
        except Exception as exc:
            logger.warning("%s: not a usable JWKS (%s); no key is trusted from it", source, exc)
            return None
        kids: set[str] = set()
        for public, key_id in parsed:
            kids.add(self.add_public_key(public, kid=key_id))
        return kids

    def key_count(self) -> int:
        with self._lock:
            return len(self._keys_by_kid)

    def get_key(self, kid: str | None = None) -> ed25519.Ed25519PublicKey | None:
        with self._lock:
            if kid:
                return self._keys_by_kid.get(kid)  # a named key that is not declared is not trusted
            if len(self._keys_by_kid) == 1:
                return next(iter(self._keys_by_kid.values()))
            return self._default_key

    def to_jwks(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._jwks_cache)


class JTIReplayStore:
    """Anti-replay store keeping track of seen `jti` tokens until expiration."""

    def __init__(self) -> None:
        self._seen_jtis: dict[str, float] = {}  # jti -> exp
        self._lock = threading.Lock()

    def clear(self) -> None:
        with self._lock:
            self._seen_jtis.clear()

    def record_jti(self, jti: str, exp: float | int) -> bool:
        """Record a JTI. Returns True if recorded (new), False if replay detected."""
        now = time.time()
        with self._lock:
            # Purge expired entries
            expired = [k for k, v in self._seen_jtis.items() if v <= now]
            for k in expired:
                del self._seen_jtis[k]

            if jti in self._seen_jtis:
                return False
            self._seen_jtis[jti] = float(exp)
            return True

    def is_seen(self, jti: str) -> bool:
        now = time.time()
        with self._lock:
            exp = self._seen_jtis.get(jti)
            if exp is None:
                return False
            if exp <= now:
                del self._seen_jtis[jti]
                return False
            return True


class RevocationStore:
    """Immediate revocation store for JTIs, handles, or emails."""

    def __init__(self) -> None:
        self._revoked_jtis: dict[str, dict[str, Any]] = {}
        self._revoked_actors: dict[str, dict[str, Any]] = {}  # handle/email -> details
        self._lock = threading.Lock()

    def clear(self) -> None:
        with self._lock:
            self._revoked_jtis.clear()
            self._revoked_actors.clear()

    def revoke_jti(self, jti: str, reason: str = "revoked by admin", expires_at: float | None = None) -> None:
        with self._lock:
            self._revoked_jtis[jti] = {
                "reason": reason,
                "revoked_at": time.time(),
                "expires_at": expires_at,
            }

    def revoke_actor(self, identifier: str, reason: str = "revoked by admin") -> None:
        key = identifier.strip().lower()
        with self._lock:
            self._revoked_actors[key] = {
                "reason": reason,
                "revoked_at": time.time(),
            }

    def is_revoked(
        self,
        jti: str | None = None,
        handle: str | None = None,
        email: str | None = None,
    ) -> tuple[bool, str]:
        with self._lock:
            if jti and jti in self._revoked_jtis:
                return True, f"Token jti '{jti}' is revoked: {self._revoked_jtis[jti]['reason']}"
            if handle and handle.strip().lower() in self._revoked_actors:
                h_key = handle.strip().lower()
                return True, f"Actor '{handle}' is revoked: {self._revoked_actors[h_key]['reason']}"
            if email and email.strip().lower() in self._revoked_actors:
                e_key = email.strip().lower()
                return True, f"Email '{email}' is revoked: {self._revoked_actors[e_key]['reason']}"
            return False, ""


# Singletons
_jwks_registry = JWKSRegistry()
_replay_store = JTIReplayStore()
_revocation_store = RevocationStore()


def get_jwks_registry() -> JWKSRegistry:
    return _jwks_registry


def get_replay_store() -> JTIReplayStore:
    return _replay_store


def get_revocation_store() -> RevocationStore:
    return _revocation_store


def sign_actor_assertion(
    private_key: ed25519.Ed25519PrivateKey,
    sub: str,
    kid: str | None = None,
    email: str | None = None,
    handle: str | None = None,
    roles: list[str] | tuple[str, ...] | None = None,
    domain_roles: dict[str, list[str]] | None = None,
    delegation: dict[str, Any] | None = None,
    jti: str | None = None,
    exp_seconds: int = DEFAULT_EXP_SECONDS,
    iss: str = DEFAULT_ISSUER,
    aud: str = DEFAULT_AUDIENCE,
) -> str:
    """Sign an actor assertion JWT with EdDSA (Ed25519)."""
    now = int(time.time())
    token_jti = jti or str(uuid.uuid4())
    payload: dict[str, Any] = {
        "iss": iss,
        "sub": sub,
        "aud": aud,
        "iat": now,
        "nbf": now,
        "exp": now + exp_seconds,
        "jti": token_jti,
    }
    if email:
        payload["email"] = email
    if handle:
        payload["handle"] = handle
    if roles:
        payload["roles"] = list(roles)
    if domain_roles:
        payload["domain_roles"] = domain_roles
    if delegation:
        payload["delegation"] = delegation

    headers = {"kid": kid} if kid else {}
    return jwt.encode(payload, private_key, algorithm="EdDSA", headers=headers)


class ActorAssertionVerifier:
    """Verifies signed actor assertions against trusted JWKS with anti-replay and revocation checks."""

    def __init__(
        self,
        registry: JWKSRegistry | None = None,
        replay_store: JTIReplayStore | None = None,
        revocation_store: RevocationStore | None = None,
    ) -> None:
        self.registry = registry or get_jwks_registry()
        self.replay_store = replay_store or get_replay_store()
        self.revocation_store = revocation_store or get_revocation_store()

    def verify(
        self,
        token: str,
        expected_issuer: str | None = None,
        expected_audience: str | None = None,
        check_replay: bool = True,
    ) -> dict[str, Any]:
        """Cryptographically verify an EdDSA actor assertion.

        Checks:
        1. Token structure, header and algorithm (strictly EdDSA).
        2. Known key ID in registry (or single default key).
        3. Signature verification with public key.
        4. Expiration (`exp`) and not-before (`nbf`).
        5. Issuer and audience matches if specified.
        6. Presence of mandatory `jti` anti-replay claim.
        7. Revocation checks for JTI and actor.
        8. Anti-replay verification preventing JTI reuse.
        """
        if not token or not isinstance(token, str):
            raise ActorAssertionError("Assertion token is missing or empty", code="missing_token")

        token = token.strip()
        try:
            unverified_header = jwt.get_unverified_header(token)
        except Exception as e:
            raise ActorAssertionError(f"Malformed token header: {e}", code="malformed_token") from e

        alg = unverified_header.get("alg")
        if alg != "EdDSA":
            raise ActorAssertionError(f"Invalid algorithm '{alg}': only EdDSA is permitted", code="invalid_algorithm")

        kid = unverified_header.get("kid")
        self.registry.refresh_from_environment(kid)
        pub_key = self.registry.get_key(kid)
        if pub_key is None:
            raise ActorAssertionError(
                f"Unknown or untrusted signing key kid '{kid}': declare its public key in ARCHINEX_JWKS, ARCHINEX_JWKS_FILE or "
                "ARCHINEX_JWKS_URL",
                code="unknown_key",
            )

        decode_options: dict[str, Any] = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_nbf": True,
            "verify_iat": True,
            "require": ["exp", "jti", "sub"],
        }
        issuer = expected_issuer or os.getenv("ARCHINEX_ISSUER", DEFAULT_ISSUER)
        audience = expected_audience or os.getenv("ARCHINEX_AUDIENCE", DEFAULT_AUDIENCE)

        skew = clock_skew_seconds()
        try:
            payload = jwt.decode(
                token,
                pub_key,
                algorithms=["EdDSA"],
                issuer=issuer,
                audience=audience,
                leeway=skew,
                options=cast(Any, decode_options),
            )
        except jwt.ExpiredSignatureError as e:
            raise ActorAssertionError("Actor assertion has expired", code="token_expired") from e
        except jwt.InvalidIssuerError as e:
            raise ActorAssertionError(f"Invalid assertion issuer: {e}", code="invalid_issuer") from e
        except jwt.InvalidAudienceError as e:
            raise ActorAssertionError(f"Invalid assertion audience: {e}", code="invalid_audience") from e
        except jwt.PyJWTError as e:
            raise ActorAssertionError(f"Assertion verification failed: {e}", code="invalid_signature") from e

        jti = payload.get("jti")
        if not jti:
            raise ActorAssertionError("Assertion lacks mandatory 'jti' anti-replay claim", code="missing_jti")

        # A long-lived assertion is a bearer secret: the lifetime is bounded, not left to the signer.
        exp_claim = float(payload["exp"])
        issued = float(payload.get("iat") or payload.get("nbf") or time.time())
        max_ttl = max_ttl_seconds()
        if exp_claim - issued > max_ttl:
            raise ActorAssertionError(
                f"Assertion lifetime {int(exp_claim - issued)} s exceeds the {max_ttl} s the Hub accepts", code="lifetime_too_long"
            )

        handle = payload.get("handle") or (payload.get("sub") if str(payload.get("sub", "")).startswith("@") else None)
        email = payload.get("email") or (payload.get("sub") if "@" in str(payload.get("sub", "")) else None)

        # Check immediate revocation
        is_revoked, reason = self.revocation_store.is_revoked(jti=jti, handle=handle, email=email)
        if is_revoked:
            raise ActorAssertionError(reason, code="token_revoked")

        # Anti-replay check
        if check_replay:
            # Kept until the clock tolerance is over too, or a token accepted late could be replayed once forgotten.
            exp = float(payload.get("exp", time.time() + DEFAULT_EXP_SECONDS)) + skew
            if not self.replay_store.record_jti(jti, exp=exp):
                raise ActorAssertionError(f"Replay detected: token jti '{jti}' has already been used", code="replay_detected")

        return payload

