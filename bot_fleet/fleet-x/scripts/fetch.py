#!/usr/bin/env python3
"""Fetch recent posts for watchlist handles via XFlux (not official X API).

Reads XFLUX_API_KEY from env or box secret store. Never prints the key.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

def _secret_from_store(name: str) -> str | None:
    """Read a secret from box-secrets.json (v1 secrets.* or v2 card.*). Never log values."""
    for p in (
        Path("/home/box/agent-data/box-secrets.json"),
        Path("/home/box/sand-data/box-secrets.json"),
    ):
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text() or "{}")
        except Exception:
            continue
        # v1: {"secrets": {"NAME": "..." or {"value": "..."}}}
        secrets = data.get("secrets") or {}
        val = secrets.get(name)
        if isinstance(val, dict):
            val = val.get("value") or val.get("secret")
        if val:
            return str(val).strip()
        # v2: {"card": {"NAME": "..."}}
        card = data.get("card") or {}
        val = card.get(name)
        if isinstance(val, dict):
            val = val.get("value") or val.get("secret")
        if val:
            return str(val).strip()
    return None


BASE = "https://www.xfluxapi.com/api/v1"
DEFAULT_HANDLES = ["karpathy", "trq212", "elonmusk", "dhh", "tobi", "poteto"]



def _via_fleet_secrets(name: str) -> str | None:
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "fleet_secrets_load",
            "/home/box/agent-data/fleet-secrets/load.py",
        )
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.get_secret(name)
    except Exception:
        return None
    return None

def load_key() -> str:
    key = _via_fleet_secrets("XFLUX_API_KEY")
    if key:
        return key
    key = os.environ.get("XFLUX_API_KEY") or os.environ.get("XFLUX_API_TOKEN")
    if key:
        return key.strip()
    key = _secret_from_store("XFLUX_API_KEY") if "_secret_from_store" in globals() else None
    if key:
        return key
    raise SystemExit("XFLUX_API_KEY missing (Infisical / env / box secret store)")


def api_get(path: str, key: str, params: dict | None = None) -> dict:
    q = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{BASE}{path}{q}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {key}",
            "X-API-Key": key,
            "Accept": "application/json",
            "User-Agent": "BotFleet-Cooper/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:800]
        raise SystemExit(f"XFlux HTTP {e.code}: {body}") from e


def normalize_tweets(payload: dict, username: str) -> list[dict]:
    """Best-effort normalize across possible XFlux response shapes."""
    data = payload.get("data", payload)
    tweets = data
    if isinstance(data, dict):
        tweets = (
            data.get("tweets")
            or data.get("posts")
            or data.get("items")
            or data.get("results")
            or []
        )
    out = []
    if not isinstance(tweets, list):
        return out
    for t in tweets:
        if not isinstance(t, dict):
            continue
        tid = t.get("id") or t.get("tweet_id") or t.get("id_str")
        text = t.get("text") or t.get("full_text") or t.get("content") or ""
        created = t.get("created_at") or t.get("createdAt") or t.get("date") or ""
        # XFlux often returns tweet ids that 404 on x.com/twitter.com (not real
        # snowflakes). Only keep an explicit permalink from the API; otherwise
        # fall back to the profile URL so digests never ship dead status links.
        raw_url = (t.get("url") or t.get("permalink") or t.get("tweet_url") or "").strip()
        if raw_url.startswith("http") and "/status/" in raw_url:
            url = raw_url
        else:
            url = f"https://x.com/{username}"
        out.append(
            {
                "id": tid,
                "username": username,
                "text": text,
                "created_at": created,
                "url": url,
                "like_count": t.get("like_count") or t.get("likeCount") or t.get("favorite_count"),
                "retweet_count": t.get("retweet_count") or t.get("retweetCount"),
            }
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Fleet XFlux watchlist fetch")
    ap.add_argument(
        "--handles",
        default=",".join(DEFAULT_HANDLES),
        help="Comma-separated usernames without @ (default: Cooper core five)",
    )
    ap.add_argument("--limit", type=int, default=8, help="Posts per handle (default 8)")
    ap.add_argument(
        "--since-hours",
        type=float,
        default=None,
        help="Optional client-side filter: keep posts newer than N hours (best-effort)",
    )
    ap.add_argument("--json", action="store_true", help="Print full JSON (default)")
    ap.add_argument("--markdown", action="store_true", help="Print a compact markdown digest")
    args = ap.parse_args()

    key = load_key()
    handles = [h.strip().lstrip("@") for h in args.handles.split(",") if h.strip()]
    if not handles:
        raise SystemExit("no handles")

    all_posts: list[dict] = []
    errors: list[dict] = []
    for h in handles:
        try:
            payload = api_get(f"/users/{urllib.parse.quote(h)}/tweets", key, {"limit": args.limit})
            posts = normalize_tweets(payload, h)
            all_posts.extend(posts)
        except SystemExit as e:
            errors.append({"username": h, "error": str(e)})
        except Exception as e:  # noqa: BLE001
            errors.append({"username": h, "error": str(e)})

    if args.since_hours is not None:
        # best-effort; keep all if timestamps unparseable
        import datetime as dt
        from email.utils import parsedate_to_datetime

        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=args.since_hours)
        filtered = []
        for p in all_posts:
            raw = p.get("created_at") or ""
            try:
                ts = parsedate_to_datetime(raw) if raw else None
                if ts is None:
                    filtered.append(p)
                    continue
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=dt.timezone.utc)
                if ts >= cutoff:
                    filtered.append(p)
            except Exception:
                filtered.append(p)
        all_posts = filtered

    result = {
        "ok": True,
        "provider": "xflux",
        "handles": handles,
        "limit_per_handle": args.limit,
        "post_count": len(all_posts),
        "posts": all_posts,
        "errors": errors,
        "note": "Each successful XFlux call uses 1 monthly quota unit (plan-dependent).",
    }

    if args.markdown:
        lines = [f"# XFlux watchlist ({len(all_posts)} posts)", ""]
        by = {}
        for p in all_posts:
            by.setdefault(p["username"], []).append(p)
        for h in handles:
            lines.append(f"## @{h}")
            items = by.get(h) or []
            if not items:
                err = next((e for e in errors if e["username"] == h), None)
                lines.append(f"- (quiet / no posts){(' — ' + err['error']) if err else ''}")
            else:
                for p in items:
                    text = (p.get("text") or "").replace("\n", " ").strip()
                    if len(text) > 220:
                        text = text[:217] + "…"
                    url = p.get("url") or ""
                    # Mark profile-only links so writers don't invent status URLs
                    if url and "/status/" not in url:
                        lines.append(f"- {text} (profile) {url}".rstrip())
                    else:
                        lines.append(f"- {text} {url}".rstrip())
            lines.append("")
        print("\n".join(lines))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
