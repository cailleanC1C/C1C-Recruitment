"""Secret redaction helpers shared across CoreOps commands."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

import discord

__all__ = [
    "mask_secret",
    "mask_service_account",
    "sanitize_data",
    "sanitize_embed",
    "sanitize_log",
    "sanitize_text",
]


_SECRET_FRAGMENT_RE = re.compile(
    r"(?<![A-Za-z0-9_-])"
    r"(?P<secret>(?=[A-Za-z0-9_-]*[A-Za-z])(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{32,})"
    r"(?![A-Za-z0-9_-])"
)
_DISCORD_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{24}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,}")
_WEBHOOK_RE = re.compile(r"https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/\S+", re.I)
_PRIVATE_KEY_BLOCK_RE = re.compile(r"-----BEGIN [^-]+-----.*?-----END [^-]+-----", re.DOTALL)
_GOOGLE_API_KEY_RE = re.compile(r"AIza[0-9A-Za-z\-_]{35}")
_OAUTH_TOKEN_RE = re.compile(r"ya29\.[0-9A-Za-z\-_]{20,}")
_SECRET_FIELD_RE = re.compile(
    r"(?P<prefix>(token|secret|credential|key)\s*[=:]\s*)(?P<secret>[^\s,;]+)",
    re.IGNORECASE,
)
_JSON_SECRET_FIELD_RE = re.compile(
    r"(?P<prefix>\"(?:token|secret|credential|key)\"\s*:\s*\")(?P<secret>.*?)(?P<suffix>\")",
    re.IGNORECASE | re.DOTALL,
)
_SERVICE_ACCOUNT_INLINE_RE = re.compile(
    r"\{[^{}]*\"type\"\s*:\s*\"service_account\".*?\}",
    re.DOTALL,
)


def _stable_suffix(text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()
    return digest[:4]


def mask_secret(text: str) -> str:
    suffix = _stable_suffix(text)
    return f"***{suffix}"


def mask_service_account(text: str) -> str:
    suffix = _stable_suffix(text)
    length = len(text)
    return f"***sa-json:len={length}-{suffix}"


def _looks_like_service_account(text: str) -> bool:
    if "service_account" not in text or "private_key" not in text:
        return False
    try:
        data = json.loads(text)
    except Exception:
        return False
    if not isinstance(data, Mapping):
        return False
    type_value = data.get("type")
    return str(type_value) == "service_account" and "private_key" in data


def _replace(pattern: re.Pattern[str], text: str, replacer) -> str:
    return pattern.sub(lambda match: replacer(match.group(0), match), text)


def sanitize_text(value: Any) -> Any:
    if value is None:
        return value
    text = str(value)
    if not text:
        return text

    stripped = text.strip()
    if _looks_like_service_account(stripped):
        return mask_service_account(stripped)

    sanitized = text

    def generic(mask_target: str, _match: re.Match[str]) -> str:
        return mask_secret(mask_target)

    sanitized = _replace(_SERVICE_ACCOUNT_INLINE_RE, sanitized, lambda seg, _: mask_service_account(seg))
    sanitized = _replace(_PRIVATE_KEY_BLOCK_RE, sanitized, generic)
    sanitized = _replace(_WEBHOOK_RE, sanitized, generic)
    sanitized = _replace(_DISCORD_TOKEN_RE, sanitized, generic)
    sanitized = _replace(_GOOGLE_API_KEY_RE, sanitized, generic)
    sanitized = _replace(_OAUTH_TOKEN_RE, sanitized, generic)
    sanitized = _replace(_JSON_SECRET_FIELD_RE, sanitized, lambda _seg, match: f"{match.group('prefix')}{mask_secret(match.group('secret'))}{match.group('suffix')}")
    sanitized = _replace(_SECRET_FIELD_RE, sanitized, lambda _seg, match: f"{match.group('prefix')}{mask_secret(match.group('secret'))}")
    sanitized = _replace(_SECRET_FRAGMENT_RE, sanitized, generic)

    return sanitized


def sanitize_data(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, Mapping):
        return {key: sanitize_data(val) for key, val in value.items()}
    if isinstance(value, tuple):
        return tuple(sanitize_data(item) for item in value)
    if isinstance(value, list):
        return [sanitize_data(item) for item in value]
    if isinstance(value, set):
        return {sanitize_data(item) for item in value}
    return value


def sanitize_log(message: str, *, extra: Mapping[str, Any] | None = None) -> tuple[str, Mapping[str, Any] | None]:
    clean_message = str(sanitize_text(message))
    clean_extra = None
    if extra is not None:
        clean_extra = {key: sanitize_data(value) for key, value in extra.items()}
    return clean_message, clean_extra


def sanitize_embed(embed: discord.Embed) -> discord.Embed:
    if embed.title:
        embed.title = str(sanitize_text(embed.title))
    if embed.description:
        embed.description = str(sanitize_text(embed.description))

    for index, field in enumerate(list(embed.fields)):
        name = str(sanitize_text(field.name)) if field.name else field.name
        value = str(sanitize_text(field.value)) if field.value else field.value
        embed.set_field_at(index, name=name or field.name, value=value or field.value, inline=field.inline)

    footer = embed.footer
    if footer and footer.text:
        embed.set_footer(text=str(sanitize_text(footer.text)), icon_url=footer.icon_url)

    author = embed.author
    if author and author.name:
        embed.set_author(name=str(sanitize_text(author.name)), url=author.url, icon_url=author.icon_url)

    return embed
