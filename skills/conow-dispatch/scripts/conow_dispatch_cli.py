#!/usr/bin/env python3
"""Conow Home AI Dispatch CLI (end-user gateway).

Shares CONOW_BASE_URL / CONOW_API_KEY with conow-energy and conow-device.
The base URL is auto-derived from the sk- key prefix and maps to the
corresponding data center; override via CONOW_BASE_URL only when using a
dedicated gateway URL.

Endpoint contracts:
  - Unified read entrypoint:
      GET /v1.0/end-user/energy/homes/dispatch?home_id=<HID>
      * result={"savePercent":"0"} with no deviceDispatchList => disabled
      * result with deviceDispatchList / scheduleList / groupId etc. => enabled
  - /dispatch/disable: write endpoint, POST JSON body `{"home_id":"..."}`.
    The backend DOES declare a separate save/enable endpoint, but this skill
    *intentionally* does not surface enabling/save — direct users to the Conow
    App's AI Dispatch / Savings Mode toggle. The no-enable behavior is a
    deliberate policy choice, not an API gap.
  - Field name is **home_id** (snake_case) on the request side; the live
    gateway returns camelCase response fields (savePercent, deviceDispatchList,
    groupId, reasonList) — see references/dispatch_reference.md.

The CLI now uses `home_id` as the request field. `--group-id` is still
accepted for backward compatibility but is mapped to `--home-id` with a
one-time deprecation warning on stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_TIMEOUT = 20
DEFAULT_HOMES_PATH = "/v1.0/end-user/homes/all"
DISPATCH_PATH = "/v1.0/end-user/energy/homes/dispatch"
DISABLE_PATH = "/v1.0/end-user/energy/homes/dispatch/disable"

# Tuya sk- key 前两个字符（去掉 "sk-" 之后的 2 位）映射到对应数据中心 base URL。
# 与 conow-energy / conow-device 保持一致。
TUYA_DC_BY_KEY_PREFIX: Dict[str, str] = {
    "AY": "https://openapi.tuyacn.com",        # China
    "AZ": "https://openapi.tuyaus.com",        # US West
    "EU": "https://openapi.tuyaeu.com",        # Central Europe
    "IN": "https://openapi.tuyain.com",        # India
    "UE": "https://openapi-ueaz.tuyaus.com",   # US East
    "WE": "https://openapi-weaz.tuyaeu.com",   # Western Europe
    "SG": "https://openapi-sg.iotbing.com",    # Singapore
}


def _key_prefix(api_key: Optional[str]) -> Optional[str]:
    """Return the 2-letter data-center prefix from a sk-XX... key, or None."""
    if not api_key or not api_key.startswith("sk-") or len(api_key) < 5:
        return None
    return api_key[3:5].upper()


def _resolve_base_url(args: argparse.Namespace) -> None:
    """Mutate args.base_url to a usable URL or exit with a helpful message.

    Priority: explicit --base-url / $CONOW_BASE_URL > sk- key prefix map.
    """
    if getattr(args, "base_url", None):
        return
    api_key = getattr(args, "api_key", None)
    if not api_key:
        _die_missing_api_key()
    prefix = _key_prefix(api_key)
    if prefix and prefix in TUYA_DC_BY_KEY_PREFIX:
        args.base_url = TUYA_DC_BY_KEY_PREFIX[prefix]
        return
    if prefix:
        sys.stderr.write(
            f"error: cannot resolve gateway URL — sk-{prefix}... is not a known\n"
            "Tuya data-center prefix.\n"
            f"  supported prefixes: {', '.join(sorted(TUYA_DC_BY_KEY_PREFIX))}\n"
            "  set CONOW_BASE_URL or pass --base-url to point at a custom\n"
            "  gateway, or check that your API key matches your account region.\n"
        )
    else:
        sys.stderr.write(
            "error: cannot resolve gateway URL.\n"
            "  No --base-url / CONOW_BASE_URL is set, and the API key has no\n"
            "  recognizable sk-XX... region prefix. Set CONOW_API_KEY to a\n"
            "  valid sk- key, or pass --base-url to point at a custom gateway.\n"
        )
    raise SystemExit(2)


class ConowDispatchError(RuntimeError):
    pass


# Gateway business errors arrive as HTTP 200 with success:false + a numeric
# `code`. These are *platform envelope* codes (observed empirically), not part
# of the dispatch contract. Map the common ones to a friendly hint; always keep
# the raw code/msg in the printed payload.
GATEWAY_CODE_HINTS: Dict[Any, str] = {
    1106: "permission denied — this key has no access to that home/capability "
    "(check that the home is bound to this account, and that the sk- key "
    "region matches the home's data center)",
    1108: "URI path invalid — capability unavailable on this gateway "
    "(check the sk- key region / base URL matches your account's data center)",
    1109: "required parameter missing",
    1110: "illegal parameter — the end-user gateway expects home_id",
}


def _gateway_hint(code: Any) -> Optional[str]:
    if code is None:
        return None
    hint = GATEWAY_CODE_HINTS.get(code)
    if hint is None:
        try:
            hint = GATEWAY_CODE_HINTS.get(int(code))
        except (TypeError, ValueError):
            hint = None
    return hint


def _redacted_key(api_key: Optional[str]) -> str:
    """Return a log-safe rendering of the api key (never the raw secret)."""
    if not api_key:
        return "(unset)"
    if len(api_key) <= 8:
        return "sk-***"
    return f"{api_key[:5]}...{api_key[-2:]}"


def _die_missing_api_key() -> None:
    """Print a friendly missing-API-key message and exit with code 2."""
    sys.stderr.write(
        "error: CONOW_API_KEY is not set.\n"
        "\n"
        "This skill needs a Conow / Tuya end-user API key (starts with `sk-`).\n"
        "  1. Get a key from your Conow App or the Tuya Open Platform.\n"
        "  2. Configure it as an environment variable, e.g.\n"
        "         export CONOW_API_KEY=\"sk-...\"\n"
        "     or pass it on the command line with `--api-key sk-...`.\n"
        "\n"
        "Once set, the CLI will auto-detect the gateway URL from the key\n"
        "prefix (sk-AY -> China, sk-AZ -> US West, sk-EU -> Europe, ...).\n"
        "Override the gateway with CONOW_BASE_URL only if your deployment\n"
        "provides a dedicated gateway URL.\n"
    )
    raise SystemExit(2)


def _http_request(
    method: str,
    url: str,
    headers: Dict[str, str],
    body: Optional[Any] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    data: Optional[bytes] = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        status = e.code
    except urllib.error.URLError as e:
        raise ConowDispatchError(f"network error: {e}") from e
    try:
        payload: Dict[str, Any] = json.loads(raw) if raw else {}
    except json.JSONDecodeError as e:
        raise ConowDispatchError(f"non-json (http {status}): {raw[:400]}") from e
    if status >= 400:
        raise ConowDispatchError(f"http {status}: {payload}")
    return payload


def _api_call(
    args: argparse.Namespace,
    method: str,
    path: str,
    query: Optional[Dict[str, Any]] = None,
    body: Optional[Any] = None,
) -> Dict[str, Any]:
    base = args.base_url.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    url = base + path
    q = {k: v for k, v in (query or {}).items() if v is not None and v != ""}
    if q:
        url = url + "?" + urllib.parse.urlencode(q, doseq=True)
    if not args.api_key:
        _die_missing_api_key()
    headers = {
        "Authorization": f"Bearer {args.api_key}",
        "Accept": "application/json",
    }
    if os.environ.get("CONOW_VERBOSE"):
        # Redacted request summary; never leak the raw key.
        sys.stderr.write(
            f"[conow-dispatch] {method} {url}\n"
            f"  auth: Bearer {_redacted_key(args.api_key)}\n"
            + (f"  body: {json.dumps(body, ensure_ascii=False)}\n" if body is not None else "")
        )
    return _http_request(method, url, headers, body=body, timeout=args.timeout)


def _print_json(obj: Any) -> None:
    json.dump(obj, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def _display_width(s: str) -> int:
    """Terminal column width of a string, counting CJK wide chars as 2."""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in s)


def _pad_display(s: str, width: int) -> str:
    """Left-justify `s` to `width` *display* columns (CJK-aware), so table columns line up."""
    pad = width - _display_width(s)
    return s + (" " * pad if pad > 0 else "")


# ---------------------------------------------------------------------------
# home-id resolution & backwards compat with --group-id
# ---------------------------------------------------------------------------

_DEPRECATION_WARNED = False


def _warn_group_id_deprecated() -> None:
    global _DEPRECATION_WARNED
    if _DEPRECATION_WARNED:
        return
    _DEPRECATION_WARNED = True
    sys.stderr.write(
        "[conow-dispatch] note: --group-id / CONOW_GROUP_ID is kept as a "
        "backwards-compatible alias for --home-id / CONOW_HOME_ID. The "
        "end-user gateway uses home_id for dispatch; the CLI translates "
        "automatically.\n"
    )


def _home_id(args: argparse.Namespace) -> str:
    """Prefer --home-id / CONOW_HOME_ID. Fall back to --group-id / CONOW_GROUP_ID with a deprecation note."""
    hid = getattr(args, "home_id", None) or os.environ.get("CONOW_HOME_ID", "")
    if not hid:
        legacy = getattr(args, "group_id", None) or os.environ.get(
            "CONOW_GROUP_ID", ""
        )
        if legacy:
            _warn_group_id_deprecated()
            hid = legacy
    if not hid:
        raise ConowDispatchError(
            "missing --home-id (CONOW_HOME_ID). Tip: run `list` first to see "
            "homes under the current key and pick one by name."
        )
    return str(hid).strip()


def _merge_body(
    base: Dict[str, Any], override: Optional[str]
) -> Dict[str, Any]:
    if not override:
        return base
    try:
        extra = json.loads(override)
    except json.JSONDecodeError as e:
        raise ConowDispatchError(f"invalid --body-json: {e}") from e
    if not isinstance(extra, dict):
        raise ConowDispatchError("--body-json must be an object")
    m = dict(base)
    m.update(extra)
    return m


# ---------------------------------------------------------------------------
# list-homes (inline; mirrors conow-energy /homes/all)
# ---------------------------------------------------------------------------


def _extract_homes(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    result = payload.get("result", payload)
    if isinstance(result, list):
        return [h for h in result if isinstance(h, dict)]
    if isinstance(result, dict):
        for key in ("homes", "home_list", "list", "items"):
            lst = result.get(key)
            if isinstance(lst, list):
                return [h for h in lst if isinstance(h, dict)]
    return []


def _home_field(home: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[str]:
    for k in keys:
        if k in home and home[k] not in (None, ""):
            return str(home[k])
    return None


def _list_homes(args: argparse.Namespace) -> List[Dict[str, Any]]:
    path = (
        getattr(args, "homes_path", None)
        or os.environ.get("CONOW_HOMES_PATH")
        or DEFAULT_HOMES_PATH
    )
    p = _api_call(args, "GET", path)
    homes = _extract_homes(p)
    if not homes:
        raise ConowDispatchError(
            f"list-homes path {path} returned no homes; response={p}. "
            "Check --homes-path or CONOW_HOMES_PATH if the home list cannot be loaded."
        )
    out: List[Dict[str, Any]] = []
    for h in homes:
        hid = _home_field(h, ("home_id", "homeId", "id"))
        if not hid:
            continue
        name = _home_field(h, ("name", "home_name", "homeName")) or "(no name)"
        out.append({"home_id": hid, "name": name, "raw": h})
    return out


# ---------------------------------------------------------------------------
# dispatch helpers
# ---------------------------------------------------------------------------


def _dispatch_read(
    args: argparse.Namespace, hid: str, body_override: Optional[str] = None
) -> Dict[str, Any]:
    """Unified /dispatch read. GET with ?home_id= is the live contract."""
    body = _merge_body({"home_id": hid}, body_override)
    # The public read contract is GET + query string, so keep reads on GET.
    return _api_call(args, "GET", DISPATCH_PATH, query=body)


def _summarize_dispatch(result: Dict[str, Any]) -> Dict[str, Any]:
    """Turn a /dispatch result payload into a compact status dict.

    Three states, derived from the explicit live flags (NOT the savePercent
    heuristic, which is unreliable — both a genuinely-disabled and a
    freshly-enabled home can report "0"):

    - ``enabled``  — dispatch is on AND at least one device is actually being
      dispatched right now (``hasDispatch`` truthy) and the home is not
      ``allDeviceUnable``. This is a home actively optimizing.
    - ``idle``     — dispatch is configured (deviceDispatchList present) but
      nothing is dispatching right now: ``allDeviceUnable=true``, or 0 devices
      dispatched (e.g. every device dropped out on a ``cmdConflict``). The home
      is NOT actively saving — do not report it as running.
    - ``disabled`` — no dispatch devices and no positive savePercent signal.
    """
    if not isinstance(result, dict):
        return {"state": "unknown", "save_percent": None, "devices": 0, "devices_dispatched": 0}
    devs = result.get("deviceDispatchList") or []
    dispatched = sum(1 for d in devs if isinstance(d, dict) and d.get("hasDispatch"))
    conflicts = sum(1 for d in devs if isinstance(d, dict) and d.get("cmdConflict") == 1)
    save = result.get("savePercent")
    all_unable = result.get("allDeviceUnable")
    if devs and dispatched > 0 and all_unable is not True:
        state = "enabled"
    elif devs:
        # Configured but not currently acting (allDeviceUnable / 0 dispatched).
        state = "idle"
    elif all_unable is True:
        state = "disabled"
    elif save in (None, "", "0", 0):
        state = "disabled"
    else:
        state = "enabled"
    return {
        "state": state,
        "save_percent": save,
        "devices": len(devs),
        "devices_dispatched": dispatched,
        "cmd_conflicts": conflicts,
        "all_device_unable": all_unable,
        "predictable": result.get("predictable"),
        "group_id": result.get("groupId"),
    }


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------


def cmd_list(args: argparse.Namespace) -> None:
    """Scan all homes bound to current key and summarise their dispatch state in parallel."""
    homes = _list_homes(args)
    name_filter = (args.name or "").strip().lower()
    if name_filter:
        homes = [h for h in homes if name_filter in h["name"].lower()]
    if args.limit and args.limit > 0:
        homes = homes[: args.limit]

    results: List[Dict[str, Any]] = []

    def probe(h: Dict[str, Any]) -> Dict[str, Any]:
        hid = h["home_id"]
        row: Dict[str, Any] = {"home_id": hid, "name": h["name"]}
        try:
            p = _dispatch_read(args, hid, args.body_json or None)
            if p.get("success"):
                row.update(_summarize_dispatch(p.get("result") or {}))
            else:
                row["state"] = "error"
                row["error_code"] = p.get("code")
                row["error_msg"] = p.get("msg")
        except ConowDispatchError as e:
            row["state"] = "error"
            row["error_code"] = "network"  # distinguish transport failure from a gateway code
            row["error_msg"] = str(e)
        return row

    workers = max(1, int(args.workers or 8))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(probe, h) for h in homes]
        for f in as_completed(futs):
            results.append(f.result())

    order = {"enabled": 0, "idle": 1, "disabled": 2, "error": 3, "unknown": 4}
    results.sort(key=lambda r: (order.get(r.get("state"), 9), r.get("name", "")))

    enabled = [r for r in results if r.get("state") == "enabled"]
    idle = [r for r in results if r.get("state") == "idle"]
    disabled = [r for r in results if r.get("state") == "disabled"]
    errors = [r for r in results if r.get("state") == "error"]

    summary = {
        "total": len(results),
        "enabled": len(enabled),
        "idle": len(idle),
        "disabled": len(disabled),
        "errors": len(errors),
        "homes": results,
    }
    if args.output == "json":
        _print_json(summary)
        return

    # text output. Names can contain CJK (double-width) characters, so pad to a
    # target display width rather than code-point count, or columns drift.
    def _flags(r: Dict[str, Any]) -> str:
        bits = []
        if r.get("all_device_unable") is True:
            bits.append("ALL DEVICES UNABLE")
        if r.get("cmd_conflicts"):
            bits.append(f"{r['cmd_conflicts']} cmd conflict(s)")
        return f"  [{', '.join(bits)}]" if bits else ""

    sys.stdout.write(
        f"Scanned {summary['total']} homes: "
        f"{summary['enabled']} enabled, "
        f"{summary['idle']} idle, "
        f"{summary['disabled']} disabled, "
        f"{summary['errors']} errors.\n"
    )
    if enabled:
        sys.stdout.write("\nEnabled (actively dispatching):\n")
        for r in enabled:
            sys.stdout.write(
                f"  {r['home_id']:>10s}  {_pad_display(r['name'], 36)}  "
                f"savePercent={r.get('save_percent')}  "
                f"devices={r.get('devices')} ({r.get('devices_dispatched')} dispatched)\n"
            )
    if idle:
        sys.stdout.write(f"\nIdle ({len(idle)}) — dispatch on but not currently acting:\n")
        for r in idle:
            sys.stdout.write(
                f"  {r['home_id']:>10s}  {_pad_display(r['name'], 36)}  "
                f"savePercent={r.get('save_percent')}  "
                f"devices={r.get('devices')} ({r.get('devices_dispatched')} dispatched)"
                f"{_flags(r)}\n"
            )
    if disabled:
        sys.stdout.write(f"\nDisabled ({len(disabled)}):\n")
        for r in disabled:
            sys.stdout.write(f"  {r['home_id']:>10s}  {r['name']}\n")
    if errors:
        sys.stdout.write(f"\nErrors ({len(errors)}):\n")
        for r in errors:
            code = r.get("error_code")
            code_part = f"code={code}  " if code is not None else ""
            sys.stdout.write(
                f"  {r['home_id']:>10s}  {r['name']}  "
                f"{code_part}msg={r.get('error_msg')}\n"
            )


def cmd_query(args: argparse.Namespace) -> Optional[Dict[str, Any]]:
    """Full /dispatch payload for one home. This is the live read/status endpoint.

    Important: an unknown/unauthorized home_id returns the SAME shape as a
    genuinely-disabled home (success:true, result={"savePercent":"0",
    "predictable":true, "allDeviceUnable":false}). So before treating a "0"
    result as a real disabled home, validate the home_id is actually bound to
    this account via /homes/all — otherwise report a not-found error.
    """
    hid = _home_id(args)
    homes = _list_homes(args)
    known = {h["home_id"] for h in homes}
    if hid not in known:
        raise ConowDispatchError(
            f"Home {hid} not found under this account — run `list` to see the "
            "homes bound to the current key and pick one."
        )
    p = _dispatch_read(args, hid, args.body_json or None)
    _print_json(p)
    return p


def cmd_disable(args: argparse.Namespace) -> Optional[Dict[str, Any]]:
    """Disable dispatch on a home. Write op — effect is immediate on the target home."""
    body = _merge_body({"home_id": _home_id(args)}, args.body_json)
    p = _api_call(args, "POST", DISABLE_PATH, body=body)
    _print_json(p)
    return p


# ---------------------------------------------------------------------------
# arg parsing
# ---------------------------------------------------------------------------


def _add_home_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--home-id",
        default=os.environ.get("CONOW_HOME_ID", ""),
        help="Home id (from /homes/all). Env: CONOW_HOME_ID.",
    )
    p.add_argument(
        "--group-id",
        default=os.environ.get("CONOW_GROUP_ID", ""),
        help=argparse.SUPPRESS,
    )


def _add_body_override(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--body-json",
        default="",
        help=argparse.SUPPRESS,
    )


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Conow Home AI Dispatch CLI (end-user gateway)"
    )
    ap.add_argument("--api-key", default=os.environ.get("CONOW_API_KEY", ""))
    ap.add_argument(
        "--base-url",
        default=os.environ.get("CONOW_BASE_URL"),
        help=(
            "Gateway base URL. If unset, the CLI auto-derives the data-center "
            "URL from the sk- key prefix (sk-AY -> openapi.tuyacn.com, etc). "
            "Set this only if your deployment provides a dedicated gateway URL."
        ),
    )
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)

    sp = ap.add_subparsers(dest="cmd", required=True)

    # list (aliases: batch, summary) -- the default entrypoint for "what's going on?"
    p = sp.add_parser(
        "list",
        aliases=["batch", "summary"],
        help=(
            "Scan all homes under current key and summarise dispatch state. "
            "Use this as the default answer to broad 'what's the scheduling "
            "situation' questions instead of asking the user to pick a home."
        ),
    )
    p.add_argument("--name", default="", help="case-insensitive substring filter on home name")
    p.add_argument("--limit", type=int, default=0, help="cap scanned homes (0=unlimited)")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument(
        "--output", choices=["text", "json"], default="text",
        help="text gives a compact summary; json is machine-readable",
    )
    p.add_argument("--homes-path", default=os.environ.get("CONOW_HOMES_PATH"))
    _add_body_override(p)
    p.set_defaults(func=cmd_list)

    # query (alias: status) -- single-home full payload, derive state from it
    p = sp.add_parser(
        "query",
        aliases=["status"],
        help="GET /dispatch for one home (the live read endpoint; contains both status and plan)",
    )
    _add_home_flags(p)
    # query always emits the full JSON payload; accept --output for symmetry with
    # `list` (json is the only meaningful mode here) so a caller habituated to it
    # does not hit an argparse error.
    p.add_argument("--output", choices=["json"], default="json", help=argparse.SUPPRESS)
    _add_body_override(p)
    p.set_defaults(func=cmd_query)

    # disable
    p = sp.add_parser("disable", help="Disable dispatch for a home (write op)")
    _add_home_flags(p)
    _add_body_override(p)
    p.set_defaults(func=cmd_disable)

    ns = ap.parse_args(argv)
    _resolve_base_url(ns)
    try:
        payload = ns.func(ns)
    except ConowDispatchError as e:
        _print_json({"success": False, "error": str(e)})
        return 1
    # A gateway business error arrives as HTTP 200 + success:false. The payload
    # has already been printed by the command; surface a friendly hint on stderr
    # and exit non-zero so callers/scripts notice the failure.
    if isinstance(payload, dict) and payload.get("success") is False:
        code = payload.get("code")
        msg = payload.get("msg")
        hint = _gateway_hint(code)
        line = f"[conow-dispatch] gateway error: code={code} msg={msg}"
        if hint:
            line += f"\n  hint: {hint}"
        sys.stderr.write(line + "\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
