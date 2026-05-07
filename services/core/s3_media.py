"""Optional S3 storage for user uploads (analyze-media) and generated images (imagine)."""

from __future__ import annotations

import asyncio
import re
from uuid import uuid4

import httpx
from loguru import logger

from services.core.config import settings

_S3_TOKEN_RE = re.compile(r"\bs3://[^\s]+\b")


def media_bucket_configured() -> bool:
    return bool((settings.S3_MEDIA_BUCKET or "").strip())


def parse_s3_uri(uri: str) -> tuple[str | None, str | None]:
    if not uri.startswith("s3://"):
        return None, None
    rest = uri[len("s3://") :]
    parts = rest.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None, None
    return parts[0], parts[1]


def _s3_client():
    import boto3

    kwargs: dict = {}
    region = (settings.AWS_REGION or "").strip()
    if region:
        kwargs["region_name"] = region
    return boto3.client("s3", **kwargs)


def _put_and_presign_sync(
    bucket: str,
    key: str,
    body: bytes,
    content_type: str,
    expires: int,
) -> tuple[str, str]:
    s3 = _s3_client()
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)
    uri = f"s3://{bucket}/{key}"
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )
    return uri, url


async def upload_bytes_to_media_bucket(
    *,
    user_id: str,
    kind: str,
    body: bytes,
    content_type: str,
    filename_suffix: str,
) -> tuple[str, str] | None:
    """
    Upload object to S3. Returns (s3_uri, presigned_https_url) or None if disabled / error.
    kind: "upload" | "generated"
    """
    if not media_bucket_configured():
        return None
    bucket = settings.S3_MEDIA_BUCKET.strip()
    prefix = (settings.S3_MEDIA_PREFIX or "virfriendo").strip().strip("/")
    uid = str(uuid4())
    key = f"{prefix}/{kind}/{user_id}/{uid}{filename_suffix}"
    expires = int(settings.S3_GET_PRESIGNED_SECONDS or 604800)

    def _run():
        return _put_and_presign_sync(bucket, key, body, content_type, expires)

    try:
        return await asyncio.to_thread(_run)
    except Exception as e:
        logger.warning(f"S3 upload failed: {e}")
        return None


async def fetch_and_store_generated_image(*, user_id: str, source_url: str) -> tuple[str, str] | None:
    if not media_bucket_configured():
        return None
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        r = await client.get(source_url, follow_redirects=True)
        r.raise_for_status()
        body = r.content
    ct = (r.headers.get("content-type") or "image/jpeg").split(";")[0].strip().lower()
    suffix = ".jpg"
    content_type = "image/jpeg"
    if "png" in ct:
        suffix, content_type = ".png", "image/png"
    elif "webp" in ct:
        suffix, content_type = ".webp", "image/webp"
    elif "gif" in ct:
        suffix, content_type = ".gif", "image/gif"
    return await upload_bytes_to_media_bucket(
        user_id=user_id,
        kind="generated",
        body=body,
        content_type=content_type,
        filename_suffix=suffix,
    )


def expand_s3_uris_to_presigned(text: str) -> str:
    """Swap s3://bucket/key tokens for time-limited HTTPS URLs for API clients."""
    if not text or not media_bucket_configured():
        return text
    cfg_bucket = settings.S3_MEDIA_BUCKET.strip()
    expires = int(settings.S3_GET_PRESIGNED_SECONDS or 604800)

    def replacement(match: re.Match[str]) -> str:
        uri = match.group(0)
        bucket, key = parse_s3_uri(uri)
        if not bucket or not key or bucket != cfg_bucket:
            return uri
        try:
            s3 = _s3_client()
            return s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires,
            )
        except Exception as e:
            logger.debug("Presign failed for {}: {}", uri, e)
            return uri

    return _S3_TOKEN_RE.sub(replacement, text)
