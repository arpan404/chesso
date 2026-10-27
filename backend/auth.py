"""Verify Clerk session JWTs against the configured instance, never client IDs."""

from urllib.parse import urlparse

import jwt
from fastapi import HTTPException


class ClerkVerifier:
    def __init__(
        self, issuer: str, authorized_parties: list[str], public_key: str = ""
    ):
        self.issuer = issuer.rstrip("/")
        self.authorized_parties = authorized_parties
        self.public_key = public_key.replace("\\n", "\n")
        self.jwks = None
        if issuer:
            parsed = urlparse(issuer)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.path not in ("", "/")
            ):
                raise ValueError(
                    "CHESSO_CLERK_ISSUER must be the HTTPS Clerk frontend API origin."
                )
            self.jwks = jwt.PyJWKClient(
                self.issuer + "/.well-known/jwks.json", lifespan=300, timeout=5
            )

    def __call__(self, token: str) -> str:
        if not self.issuer:
            raise HTTPException(
                503, "Configure CHESSO_CLERK_ISSUER to enable account access."
            )
        try:
            key = self.public_key or self.jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.issuer,
                options={
                    "require": ["exp", "iat", "nbf", "iss", "sub", "sid"],
                    "verify_aud": False,
                },
                leeway=5,
            )
            if (
                claims.get("azp") not in self.authorized_parties
                or claims.get("sts") == "pending"
            ):
                raise jwt.InvalidTokenError(
                    "Invalid authorized party or incomplete session."
                )
            if not isinstance(claims["sub"], str) or not claims["sub"].startswith(
                "user_"
            ):
                raise jwt.InvalidTokenError("Invalid user ID.")
            return claims["sub"]
        except jwt.PyJWKClientConnectionError as exc:
            raise HTTPException(
                503, "Login verification is temporarily unavailable. Try again."
            ) from exc
        except jwt.PyJWTError as exc:
            raise HTTPException(
                401, "Your login could not be verified. Sign in again."
            ) from exc
