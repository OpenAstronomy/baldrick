import hashlib
import hmac

from flask import current_app

__all__ = ["verify_github_signature", "verify_github_webhook"]


def verify_github_signature(data, signature, secret):
    """
    Verify the HMAC-SHA256 signature of a GitHub webhook delivery.

    Parameters
    ----------
    data : `bytes`
        The raw body of the webhook request.
    signature : `str`
        The value of the ``X-Hub-Signature-256`` header of the request.
    secret : `str`
        The webhook secret shared between GitHub and the bot.

    Returns
    -------
    valid : `bool`
        `True` if the signature matches the payload, `False` otherwise.
    """
    if not secret or not isinstance(signature, str):
        return False

    if not signature.startswith("sha256=") or not signature.isascii():
        return False

    digest = hmac.new(secret.encode("utf-8"), data, hashlib.sha256).hexdigest()

    return hmac.compare_digest("sha256=" + digest, signature)


def verify_github_webhook(data, signature):
    """
    Check whether an incoming GitHub webhook delivery should be processed.

    Deliveries are verified against the secret configured when the app was
    created. If verification was explicitly disabled by setting
    ``BALDRICK_ALLOW_UNVERIFIED_WEBHOOKS`` when the app was created (for
    local development and testing only) all deliveries are accepted.

    Parameters
    ----------
    data : `bytes`
        The raw body of the webhook request.
    signature : `str` or `None`
        The value of the ``X-Hub-Signature-256`` header of the request.

    Returns
    -------
    valid : `bool`
        `True` if the delivery should be processed, `False` if it should be
        rejected.
    """
    secret = getattr(current_app, "webhook_secret", None)

    if secret:
        return verify_github_signature(data, signature, secret)

    return bool(getattr(current_app, "allow_unverified_webhooks", False))
