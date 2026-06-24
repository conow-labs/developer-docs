#!/usr/bin/env python3
"""Conow Smart Energy CLI.

Thin wrapper around the Conow / Tuya end-user energy Open API.
Auth: Bearer token in Authorization header (sk-xxx).

Covers home-level energy reads — indicator dictionary, aggregate / trend /
top, hour-level forecast, tariff query/label, real-time flow, power curve,
optimization impact, station metadata — plus a `list-homes` helper for
home_id discovery.

All subcommands print JSON to stdout by default. Use --output text for a
flattened human-readable dump.

Environment variables:
  CONOW_API_KEY    sk-xxx bearer token (required unless --api-key is set).
                   Get a key from your Conow App or the Tuya Open Platform.
  CONOW_BASE_URL   optional gateway override; if unset the CLI auto-derives
                   the data-center URL from the sk- key prefix (sk-AY ->
                   openapi.tuyacn.com, sk-AZ -> openapi.tuyaus.com, etc).
                   Set this only when targeting a custom or staging
                   deployment.
  CONOW_HOME_ID    default home_id for energy subcommands (optional).
  CONOW_HOMES_PATH list-homes path on the gateway; default is the Tuya
                   end-user path /v1.0/end-user/homes/all. Override when the
                   gateway exposes a different one.
  CONOW_TIMEZONE   explicit timezone override for energy subcommands
                   (optional); indicators auto-fill from /home/station when
                   omitted.
  CONOW_VERBOSE    set to 1 to print a redacted request summary to stderr
                   (the api key is masked as sk-XXXX***YYYY).

Base-URL resolution priority:
  1. --base-url flag (highest)
  2. $CONOW_BASE_URL
  3. Auto-derive from sk- key prefix (data-center map)
  4. Hard error with the supported prefixes listed
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_TIMEOUT = 20
HOME_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".home_cache.json")


def _redact(value: Optional[str]) -> str:
    """Return a redacted, stable fingerprint for an api key (sk-XXXX***YYYY).

    Used both for cache namespacing and for verbose-mode logs so we never
    echo the raw key. Stable across runs for the same input.
    """
    if not value:
        return "sk-****"
    s = str(value)
    if len(s) <= 8:
        return "sk-****"
    return f"{s[:6]}***{s[-4:]}"

# Tuya sk- key 前两个字符（去掉 "sk-" 之后的 2 位）映射到对应数据中心 base URL。
# 来源：Tuya Open API 数据中心规则；不同区域的 sk- key 物理上隔离，不能跨域用。
# 自定义 / 灰度 / 调试网关请用 CONOW_BASE_URL 显式覆盖。
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

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


class ConowError(RuntimeError):
    """Raised when the remote API returns a business error or http failure."""


class GatewayBusinessError(ConowError):
    """Raised after a `success:false` gateway envelope has already been printed.

    The full payload (code + msg) is emitted to stdout first so the caller
    still sees it; this exception only drives the non-zero exit code and the
    friendly stderr hint. `code`/`msg` carry the gateway envelope fields.
    """

    def __init__(self, code: Any, msg: str) -> None:
        self.code = code
        self.msg = msg
        super().__init__(f"gateway error {code}: {msg}")


class HomeResolutionError(ConowError):
    """Raised when a home_id cannot be resolved unambiguously.

    Carries the candidate homes (matched subset on ambiguity, full list on a
    genuine not-found / multi-home account) so the caller can ask the user to
    pick by name. This is a *normal* "need user input" condition — NOT a
    gateway failure — so `resolve-home` reports it without the gateway-error
    treatment.
    """

    def __init__(self, message: str, candidates: List[Dict[str, Any]]) -> None:
        super().__init__(message)
        self.candidates = candidates


# Gateway envelope code -> friendly, actionable one-liner. The raw code/msg is
# never hidden — this is printed alongside it.
GATEWAY_CODE_HINTS: Dict[Any, str] = {
    1010: "Token invalid — the path exists but this key has no access. Check CONOW_API_KEY.",
    1106: (
        "You don't have access to that home — run list-homes to see homes on "
        "this key. Also confirm your key's sk-XX region matches your account's "
        "data center, or set CONOW_BASE_URL."
    ),
    1108: "This capability isn't available on the current gateway.",
    1109: (
        "Param illegal — check field names / enum casing (time_aggr_type is "
        "UPPERCASE, date_type is lowercase) against references/api_reference.md."
    ),
    1110: (
        "Illegal param — a required field is missing or out of range. For "
        "tariff-query / tariff-label, pass --direction import|export."
    ),
    501: "Server rejected the request — check date_type / parameters.",
}


def _gateway_error_fields(payload: Any) -> Optional[Tuple[Any, str]]:
    """Return (code, msg) when `payload` is a gateway `success:false` envelope."""
    if not isinstance(payload, dict):
        return None
    if payload.get("success") is False:
        return payload.get("code"), str(payload.get("msg", ""))
    return None


def _verbose() -> bool:
    return os.environ.get("CONOW_VERBOSE") == "1"


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
        "Override the gateway with CONOW_BASE_URL only when targeting a\n"
        "custom or staging deployment.\n"
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

    if _verbose():
        safe_headers = dict(headers)
        if "Authorization" in safe_headers:
            safe_headers["Authorization"] = "Bearer " + _redact(
                safe_headers["Authorization"].replace("Bearer ", "", 1)
            )
        sys.stderr.write(f"[conow] {method} {url}\n")
        sys.stderr.write(f"[conow] headers={safe_headers}\n")
        if data is not None:
            sys.stderr.write(f"[conow] body={data.decode('utf-8')}\n")

    req = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        status = e.code
    except urllib.error.URLError as e:
        raise ConowError(f"network error calling {url}: {e}") from e

    if _verbose():
        sys.stderr.write(f"[conow] status={status} body={raw[:800]}\n")

    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError as e:
        raise ConowError(f"non-json response (http {status}): {raw[:400]}") from e

    if status >= 400:
        raise ConowError(f"http {status}: {payload}")
    return payload


def _api_call(
    args: argparse.Namespace,
    method: str,
    path: str,
    query: Optional[Dict[str, Any]] = None,
    body: Optional[Any] = None,
) -> Dict[str, Any]:
    base_url = args.base_url.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    url = base_url + path
    q = {k: v for k, v in (query or {}).items() if v is not None and v != ""}
    if q:
        url = url + "?" + urllib.parse.urlencode(q, doseq=True)

    if not args.api_key:
        _die_missing_api_key()

    headers = {
        "Authorization": f"Bearer {args.api_key}",
        "Accept": "application/json",
    }
    return _http_request(method, url, headers, body=body, timeout=args.timeout)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _emit_payload(args: argparse.Namespace, payload: Any) -> None:
    """Render a payload to stdout in the selected output style. Never raises.

    Use this for locally-synthesized envelopes (e.g. a resolve-home
    disambiguation result) that carry `success:false` but are NOT gateway
    business errors.
    """
    if args.output == "json":
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    elif isinstance(payload, (dict, list)):
        _print_flat("", payload)
    else:
        sys.stdout.write(str(payload) + "\n")


def _print_payload(args: argparse.Namespace, payload: Any) -> None:
    """Print a *gateway* payload, then raise GatewayBusinessError on `success:false`.

    The raw payload (including `code`/`msg`) is always emitted first so the
    caller sees it; the raised exception only drives the non-zero exit code
    and the friendly stderr hint in `main`. Only use this for payloads that
    came back from the gateway — locally-built envelopes go through
    `_emit_payload` so a synthesized `success:false` is not mistaken for a
    backend failure.
    """
    _emit_payload(args, payload)

    fields = _gateway_error_fields(payload)
    if fields is not None:
        code, msg = fields
        raise GatewayBusinessError(code, msg)


def _print_flat(prefix: str, obj: Any) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            _print_flat(f"{prefix}.{k}" if prefix else str(k), v)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _print_flat(f"{prefix}[{i}]", v)
    else:
        sys.stdout.write(f"{prefix} = {obj}\n")


def _merge_body(base: Dict[str, Any], override_json: Optional[str]) -> Dict[str, Any]:
    if not override_json:
        return base
    try:
        extra = json.loads(override_json)
    except json.JSONDecodeError as e:
        raise ConowError(f"invalid --body-json: {e}") from e
    if not isinstance(extra, dict):
        raise ConowError("--body-json must be a JSON object")
    merged = dict(base)
    merged.update(extra)
    return merged


def _parse_kv_list(kvs: Optional[List[str]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not kvs:
        return out
    for kv in kvs:
        if "=" not in kv:
            raise ConowError(f"--param must be key=value, got {kv!r}")
        k, v = kv.split("=", 1)
        out[k.strip()] = v
    return out


def _csv(values: Optional[List[str]]) -> Optional[List[str]]:
    if not values:
        return None
    out: List[str] = []
    for v in values:
        out.extend(s.strip() for s in v.split(",") if s.strip())
    return out or None


# ---------------------------------------------------------------------------
# Home discovery
# ---------------------------------------------------------------------------


def _load_home_cache() -> Dict[str, Any]:
    if not os.path.exists(HOME_CACHE_PATH):
        return {}
    try:
        with open(HOME_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_home_cache(data: Dict[str, Any]) -> None:
    try:
        with open(HOME_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _extract_homes(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Best-effort extraction of a home list from the public homes API.

    The exact response shape can vary by gateway. We accept common shapes:
      {"result": [{"home_id": ..., "name": ...}, ...]}
      {"result": {"homes": [...]}, ...}
      {"homes": [...]}
    """
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


def _home_id_field(home: Dict[str, Any]) -> Optional[str]:
    for key in ("home_id", "homeId", "id"):
        if key in home and home[key] not in (None, ""):
            return str(home[key])
    return None


def _home_name_field(home: Dict[str, Any]) -> str:
    for key in ("name", "home_name", "homeName"):
        if key in home and home[key]:
            return str(home[key])
    return "(no name)"


DEFAULT_HOMES_PATH = "/v1.0/end-user/homes/all"


def _homes_path(args: argparse.Namespace) -> str:
    return (
        getattr(args, "homes_path", None)
        or os.environ.get("CONOW_HOMES_PATH")
        or DEFAULT_HOMES_PATH
    )


def _list_homes_remote(args: argparse.Namespace) -> List[Dict[str, Any]]:
    """Call the configured list-homes endpoint.

    The exact path varies by gateway. If the default Tuya public path returns
    `1108 uri path invalid`, pass --homes-path or set CONOW_HOMES_PATH to the
    correct path for the deployment you are hitting.
    """
    path = _homes_path(args)
    payload = _api_call(args, "GET", path)
    homes = _extract_homes(payload)
    if not homes:
        raise ConowError(
            f"list_homes path {path} returned no homes. Gateway response: {payload}. "
            "If you see 'uri path invalid', pass --homes-path or set CONOW_HOMES_PATH."
        )
    _save_home_cache(
        {
            "base_url": args.base_url,
            "homes_path": path,
            "api_key_fingerprint": _redact(args.api_key),
            "fetched_at": int(time.time()),
            "homes": homes,
        }
    )
    return homes


MIN_REVERSE_SUBSTRING_LEN = 3


def _match_home_by_name(
    homes: List[Dict[str, Any]], query: str
) -> List[Tuple[Dict[str, Any], str]]:
    """Fuzzy match homes by name.

    Strategy, in priority order:

    1. Case-insensitive **exact** match on the full name wins outright.
    2. The query happens to equal a home_id — accept as exact.
    3. Forward substring (``q in name``) — "小明" matches "小明家".
    4. Reverse substring (``name in q``) — "小明家别墅" matches a home literally
       named "小明". To prevent short, generic names (e.g. "预发", "测试") from
       silently swallowing much longer queries that only coincidentally share
       a short prefix, reverse substring requires the home name to be at least
       :data:`MIN_REVERSE_SUBSTRING_LEN` characters. Callers that want to
       search by a 2-character short name should pass that 2-character name as
       the query itself (which hits the exact / forward branches).

    Returns ``[(home, home_id), ...]``.
    """
    q = (query or "").strip().lower()
    if not q:
        return []
    exact: List[Tuple[Dict[str, Any], str]] = []
    forward: List[Tuple[Dict[str, Any], str]] = []
    reverse: List[Tuple[Dict[str, Any], str]] = []
    for h in homes:
        hid = _home_id_field(h)
        if not hid:
            continue
        name = _home_name_field(h).lower()
        if name == q:
            exact.append((h, hid))
            continue
        if q == hid.lower():
            exact.append((h, hid))
            continue
        if q in name:
            forward.append((h, hid))
            continue
        if name in q and len(name) >= MIN_REVERSE_SUBSTRING_LEN:
            reverse.append((h, hid))
    if exact:
        return exact
    if forward:
        return forward
    return reverse


def _resolve_home_id(args: argparse.Namespace) -> str:
    """Return home_id from --home-id / --home-name / env / auto-discovery.

    Raises ConowError with a useful message when the caller must disambiguate.
    When ambiguity is detected, the error body lists candidate names + ids so
    the calling agent can quote them back to the user verbatim.
    """
    if args.home_id:
        return args.home_id
    env_home = os.environ.get("CONOW_HOME_ID")
    if env_home and not getattr(args, "home_name", None):
        return env_home

    cache = _load_home_cache()
    cached_homes: List[Dict[str, Any]] = cache.get("homes") or []
    cache_match = (
        cached_homes
        and cache.get("api_key_fingerprint") == _redact(args.api_key)
        and cache.get("base_url") == args.base_url
    )
    if cache_match:
        homes = cached_homes
    else:
        try:
            homes = _list_homes_remote(args)
        except ConowError as e:
            hint = (
                "could not auto-discover home_id. The default end-user path is "
                "/v1.0/end-user/homes/all; if that errors, the gateway may use a "
                "different list-homes path -- set CONOW_HOMES_PATH or ask the "
                "user for a home_id (a numeric string). Underlying error: "
                + str(e)
            )
            raise ConowError(hint) from e

    valid = [(h, _home_id_field(h)) for h in homes]
    valid = [(h, hid) for h, hid in valid if hid]
    if not valid:
        raise ConowError("no usable home_id found in list_homes response")

    def _as_candidates(pairs: List[Tuple[Dict[str, Any], str]]) -> List[Dict[str, Any]]:
        return [{"home_id": hid, "name": _home_name_field(h)} for h, hid in pairs]

    home_name = getattr(args, "home_name", None)
    if home_name:
        matches = _match_home_by_name([h for h, _ in valid], home_name)
        if len(matches) == 1:
            picked = matches[0][1]
            sys.stderr.write(
                f"[conow] resolved home_name={home_name!r} -> home_id={picked}\n"
            )
            return picked
        if not matches:
            lines = [f"- {_home_name_field(h)} (home_id={hid})" for h, hid in valid]
            raise HomeResolutionError(
                f"no home matched name {home_name!r}. ask the user to pick one of:\n"
                + "\n".join(lines),
                _as_candidates(valid),
            )
        lines = [f"- {_home_name_field(h)} (home_id={hid})" for h, hid in matches]
        raise HomeResolutionError(
            f"name {home_name!r} is ambiguous. ask the user to pick one of:\n"
            + "\n".join(lines),
            _as_candidates(matches),
        )

    if len(valid) == 1:
        picked = valid[0][1]
        sys.stderr.write(f"[conow] auto-selected home_id={picked}\n")
        return picked

    lines = [f"- {_home_name_field(h)} (home_id={hid})" for h, hid in valid]
    raise HomeResolutionError(
        "multiple homes returned by list_homes; ask the user which one (by name) "
        "and pass --home-name or --home-id. available homes:\n" + "\n".join(lines),
        _as_candidates(valid),
    )


# ---------------------------------------------------------------------------
# Subcommand: list-homes
# ---------------------------------------------------------------------------


def cmd_list_homes(args: argparse.Namespace) -> None:
    homes = _list_homes_remote(args)
    compact = [
        {
            "home_id": _home_id_field(h),
            "name": _home_name_field(h),
            "raw": h,
        }
        for h in homes
    ]
    _print_payload(args, {"homes": compact})


def cmd_resolve_home(args: argparse.Namespace) -> None:
    """Resolve a home_id from --home-name / --home-id / cache without running a query.

    Useful when the agent needs to confirm "which home?" before issuing any
    energy request. Prints a JSON envelope that always includes ``home_id`` on
    success, or ``candidates`` on ambiguity.
    """
    try:
        hid = _resolve_home_id(args)
    except HomeResolutionError as e:
        # Normal "which home?" outcome — NOT a gateway failure. Emit the
        # disambiguation envelope (with the matched candidates) and exit 0 so
        # the calling agent presents candidates[].name instead of reporting a
        # backend error.
        payload: Dict[str, Any] = {"success": False, "error": str(e)}
        if e.candidates:
            payload["candidates"] = e.candidates
        _emit_payload(args, payload)
        return
    except ConowError as e:
        # A real failure (e.g. list_homes could not be reached). Surface it as
        # an error envelope and a non-zero exit via GatewayBusinessError-less
        # path: print and re-raise so main() exits non-zero.
        _emit_payload(args, {"success": False, "error": str(e)})
        raise
    _emit_payload(args, {"success": True, "home_id": hid})


# ---------------------------------------------------------------------------
# Home station helpers
# ---------------------------------------------------------------------------


def _extract_station_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return the station result object from a gateway response."""
    if not isinstance(payload, dict):
        return {}
    result = payload.get("result")
    return result if isinstance(result, dict) else {}


def _station_timezone(args: argparse.Namespace, home_id: str) -> Optional[str]:
    """Best-effort lookup of the home's IANA timezone from /home/station.

    Indicators endpoints accept an optional `timezone` field. Supplying the
    station timezone makes day/month/week windows align with the user's home
    locale, especially for homes outside the agent's local timezone.
    """
    try:
        payload = _api_call(
            args,
            "POST",
            "/v1.0/end-user/energy/home/station",
            body={"home_id": home_id},
        )
    except ConowError as e:
        if _verbose():
            sys.stderr.write(f"[conow] could not resolve station timezone: {e}\n")
        return None
    result = _extract_station_result(payload)
    timezone = result.get("time_zone_id") or result.get("timeZoneId")
    if isinstance(timezone, str) and timezone.strip():
        return timezone.strip()
    return None


def _timezone_for_home(args: argparse.Namespace, home_id: str) -> Optional[str]:
    """Return explicit timezone or station timezone when available."""
    explicit = getattr(args, "timezone", None)
    if explicit:
        return explicit
    if getattr(args, "no_auto_timezone", False):
        return None
    tz = _station_timezone(args, home_id)
    if tz:
        # Day/month windows are bucketed in this timezone. It is the home's
        # registered station timezone, which may differ from where the home
        # physically sits — note it so the caller can caveat "today"/"this
        # month" answers (or override with --timezone / CONOW_TIMEZONE).
        sys.stderr.write(
            f"[conow] using home station timezone {tz} for date windows "
            f"(override with --timezone / CONOW_TIMEZONE)\n"
        )
    return tz


def cmd_conow_station(args: argparse.Namespace) -> None:
    """POST /home/station — home name, location, timezone, capacity, owner info."""
    body: Dict[str, Any] = {"home_id": _resolve_home_id(args)}
    if args.biz_data:
        body["biz_data"] = args.biz_data
    body.update(_parse_kv_list(args.param))
    body = _merge_body(body, args.body_json)
    payload = _api_call(args, "POST", "/v1.0/end-user/energy/home/station", body=body)
    _print_payload(args, payload)


# ---------------------------------------------------------------------------
# Subcommand: indicators (aggregate / trend / top / list)
# ---------------------------------------------------------------------------


def _build_multi_query_body(args: argparse.Namespace) -> Dict[str, Any]:
    """Shared builder for aggregate/trend bodies.

    Body fields accepted by the aggregate/trend endpoints:
      indicator_codes -> String (comma-separated, max 20)
      ext_condition   -> String (JSON, for dimension/device filtering)
      date_type       -> String (required)
      begin_date/end_date -> String (required)
      time_aggr_type / device_aggr_type -> String (optional)
      include_children -> Boolean (optional)
      timezone / options -> String (optional)
    """
    home_id = _resolve_home_id(args)
    body: Dict[str, Any] = {
        "home_id": home_id,
        "date_type": args.date_type,
    }
    if args.begin_date:
        body["begin_date"] = args.begin_date
    if args.end_date:
        body["end_date"] = args.end_date
    codes = _csv(args.indicator_code)
    if codes:
        # Server contract: comma-separated String, not a JSON array.
        body["indicator_codes"] = ",".join(codes)
    if args.time_aggr_type:
        body["time_aggr_type"] = args.time_aggr_type.upper()
    if args.device_aggr_type:
        body["device_aggr_type"] = args.device_aggr_type.upper()
    if args.include_children is not None:
        body["include_children"] = args.include_children
    if args.ext_condition:
        body["ext_condition"] = args.ext_condition
    if args.options:
        body["options"] = args.options
    timezone = _timezone_for_home(args, home_id)
    if timezone:
        body["timezone"] = timezone
    body.update(_parse_kv_list(args.param))
    return _merge_body(body, args.body_json)


def cmd_indicators_aggregate(args: argparse.Namespace) -> None:
    body = _build_multi_query_body(args)
    payload = _api_call(args, "POST", "/v1.0/end-user/energy/indicators/aggregate", body=body)
    _print_payload(args, payload)


def cmd_indicators_trend(args: argparse.Namespace) -> None:
    body = _build_multi_query_body(args)
    payload = _api_call(args, "POST", "/v1.0/end-user/energy/indicators/trend", body=body)
    _print_payload(args, payload)


def cmd_indicators_top(args: argparse.Namespace) -> None:
    """POST /indicators/top — fields differ from aggregate/trend.

    Required: home_id, indicator_code (singular), group_by, number (1..50),
              date_type, begin_date, end_date.
    Optional: sort_type (asc/desc), ext_condition, time_aggr_type,
              device_aggr_type, include_children, timezone, options.
    """
    home_id = _resolve_home_id(args)
    body: Dict[str, Any] = {
        "home_id": home_id,
        "date_type": args.date_type,
        "indicator_code": args.indicator_code_single,
        "group_by": args.group_by,
        "number": args.number,
    }
    if args.begin_date:
        body["begin_date"] = args.begin_date
    if args.end_date:
        body["end_date"] = args.end_date
    if args.sort_type:
        body["sort_type"] = args.sort_type.lower()
    if args.time_aggr_type:
        body["time_aggr_type"] = args.time_aggr_type.upper()
    if args.device_aggr_type:
        body["device_aggr_type"] = args.device_aggr_type.upper()
    if args.include_children is not None:
        body["include_children"] = args.include_children
    if args.ext_condition:
        body["ext_condition"] = args.ext_condition
    if args.options:
        body["options"] = args.options
    timezone = _timezone_for_home(args, home_id)
    if timezone:
        body["timezone"] = timezone
    body.update(_parse_kv_list(args.param))
    body = _merge_body(body, args.body_json)
    payload = _api_call(args, "POST", "/v1.0/end-user/energy/indicators/top", body=body)
    _print_payload(args, payload)


def cmd_indicators_list(args: argparse.Namespace) -> None:
    """GET /indicators — system-level indicator metadata.

    No home_id required; only optional query params `energy_type` and `keyword`.
    """
    query: Dict[str, Any] = {}
    if args.energy_type:
        query["energy_type"] = args.energy_type
    if args.keyword:
        query["keyword"] = args.keyword
    query.update(_parse_kv_list(args.param))
    payload = _api_call(args, "GET", "/v1.0/end-user/energy/indicators", query=query)
    _print_payload(args, payload)


# ---------------------------------------------------------------------------
# Subcommand: forecast (POST /v1.0/end-user/energy/forecast)
# ---------------------------------------------------------------------------

# Server contract for POST /v1.0/end-user/energy/forecast:
#   - indicator_codes is a comma-separated string (NOT a JSON array).
#   - The whitelist comes from a server-side enum; values outside it return
#     `1109 暂不支持的预测指标:<code>`.
#   - At most 2 codes per request; exceeding triggers
#     `1109 indicator_codes ... 数量不超过 2`.
#   - Window is hour-granularity only; format is yyyyMMddHH (10 digits).
#   - Windows >48h pass server validation but silently come back with an
#     empty `list[]` and `totalValue=0`. We refuse locally so the caller
#     sees the constraint instead of an empty success.
FORECAST_VALID_CODES = ("ele_forecast_produce", "ele_forecast_consumption")
FORECAST_DEFAULT_CODES = list(FORECAST_VALID_CODES)
FORECAST_MAX_CODES = 2
FORECAST_MAX_HOURS = 48


def _parse_forecast_hour(label: str, value: Optional[str]) -> _dt.datetime:
    if not value:
        raise ConowError(
            f"{label} is required for forecast (yyyyMMddHH, e.g. 2026042700)"
        )
    if len(value) != 10 or not value.isdigit():
        raise ConowError(
            f"{label}={value!r} must be 10 digits in yyyyMMddHH format. "
            "The forecast endpoint is hour-granularity only; date / month / year "
            "windows aren't accepted."
        )
    try:
        return _dt.datetime.strptime(value, "%Y%m%d%H")
    except ValueError as e:
        raise ConowError(
            f"{label}={value!r} is not a valid yyyyMMddHH datetime: {e}"
        ) from e


def _validate_forecast_window(
    begin_date: str, end_date: str, allow_long_window: bool
) -> None:
    begin_dt = _parse_forecast_hour("--begin-date", begin_date)
    end_dt = _parse_forecast_hour("--end-date", end_date)
    if end_dt < begin_dt:
        raise ConowError(
            f"--end-date {end_date} is before --begin-date {begin_date}"
        )
    # End-inclusive hours: a 0-hour delta still represents 1 sample.
    hours = int((end_dt - begin_dt).total_seconds() // 3600) + 1
    if hours > FORECAST_MAX_HOURS and not allow_long_window:
        raise ConowError(
            f"forecast window is {hours}h but the gateway caps at "
            f"{FORECAST_MAX_HOURS}h. Beyond that the gateway silently returns "
            "an empty list with success=true, which is worse UX than failing "
            "fast. Pass --allow-long-window to override and probe anyway."
        )


def _do_forecast_request(
    args: argparse.Namespace,
    *,
    indicator_codes: List[str],
    begin_date: str,
    end_date: str,
    use_cache: Optional[bool],
    scale: Optional[int],
    options: Optional[str],
    allow_any_code: bool,
    allow_long_window: bool,
) -> None:
    """Shared backbone for `forecast` and the deprecated `forecast-indicator` shim."""
    _validate_forecast_window(begin_date, end_date, allow_long_window)

    if not indicator_codes:
        indicator_codes = list(FORECAST_DEFAULT_CODES)
    bad = [c for c in indicator_codes if c not in FORECAST_VALID_CODES]
    if bad and not allow_any_code:
        raise ConowError(
            f"unsupported forecast code(s): {bad}. "
            f"valid: {list(FORECAST_VALID_CODES)}. "
            "Use --allow-any-code if the server contract has changed and you "
            "want to forward arbitrary codes anyway."
        )
    if len(indicator_codes) > FORECAST_MAX_CODES:
        raise ConowError(
            f"forecast supports at most {FORECAST_MAX_CODES} codes per request, "
            f"got {len(indicator_codes)}: {indicator_codes}"
        )

    body: Dict[str, Any] = {
        "home_id": _resolve_home_id(args),
        "indicator_codes": ",".join(indicator_codes),
        "begin_date": begin_date,
        "end_date": end_date,
    }
    if use_cache is not None:
        body["use_cache"] = use_cache
    # `--options` (raw JSON) wins if both are supplied — same precedence as
    # the indicators-aggregate family.
    if options:
        body["options"] = options
    elif scale is not None:
        body["options"] = json.dumps({"scale": scale})
    if args.timezone:
        body["timezone"] = args.timezone
    body.update(_parse_kv_list(args.param))
    body = _merge_body(body, args.body_json)
    payload = _api_call(args, "POST", "/v1.0/end-user/energy/forecast", body=body)
    _print_payload(args, payload)


def cmd_forecast(args: argparse.Namespace) -> None:
    codes = _csv(args.indicator_code) if args.indicator_code else None
    _do_forecast_request(
        args,
        indicator_codes=codes or [],
        begin_date=args.begin_date,
        end_date=args.end_date,
        use_cache=args.use_cache,
        scale=args.scale,
        options=args.options,
        allow_any_code=args.allow_any_code,
        allow_long_window=args.allow_long_window,
    )


def cmd_forecast_indicator(args: argparse.Namespace) -> None:
    """DEPRECATED. Forwards to POST /v1.0/end-user/energy/forecast.

    The legacy GET endpoint /v1.0/end-user/energy/forecast/indicator was
    superseded by the POST endpoint, which accepts up to 2 indicator
    codes per request. This subcommand is kept as a thin shim so existing
    scripts keep working; new callers should prefer `forecast`.
    """
    sys.stderr.write(
        "[DEPRECATION] `forecast-indicator` -> use `forecast` instead. "
        "The new endpoint is POST /v1.0/end-user/energy/forecast and accepts "
        "up to 2 indicator codes per request. Forwarding now.\n"
    )
    _do_forecast_request(
        args,
        indicator_codes=[args.indicator_code_single],
        begin_date=args.begin_date,
        end_date=args.end_date,
        use_cache=args.use_cache,
        scale=args.scale,
        options=args.options,
        allow_any_code=args.allow_any_code,
        allow_long_window=args.allow_long_window,
    )


# ---------------------------------------------------------------------------
# Subcommand: tariff
# ---------------------------------------------------------------------------


def cmd_tariff_query(args: argparse.Namespace) -> None:
    body: Dict[str, Any] = {
        "home_id": _resolve_home_id(args),
        "date_type": args.date_type,
        "begin_date": args.begin_date,
        "end_date": args.end_date,
    }
    if args.direction:
        body["direction"] = args.direction.upper()
    if args.timezone:
        body["timezone"] = args.timezone
    body.update(_parse_kv_list(args.param))
    body = _merge_body(body, args.body_json)
    payload = _api_call(args, "POST", "/v1.0/end-user/energy/tariff/query", body=body)
    _print_payload(args, payload)


def cmd_tariff_label(args: argparse.Namespace) -> None:
    body: Dict[str, Any] = {"home_id": _resolve_home_id(args)}
    if args.direction:
        body["direction"] = args.direction.upper()
    if args.timezone:
        body["timezone"] = args.timezone
    body.update(_parse_kv_list(args.param))
    body = _merge_body(body, args.body_json)
    payload = _api_call(args, "POST", "/v1.0/end-user/energy/tariff/label", body=body)
    _print_payload(args, payload)


# ---------------------------------------------------------------------------
# Subcommand: Conow home/* (/v1.0/end-user/energy/home/{flow,power-curve,impact,indicators,station})
# ---------------------------------------------------------------------------


# Power readings that equal a 32-bit "uninitialized" bit pattern are device
# garbage, not real watts. The most common is 0xAAAAAAAA (2863311530); 0xFFFFFFFF
# and the signed -1 form show up too. We flag, never silently drop, so the
# value stays visible but an AI assistant knows not to quote it as live power.
_POWER_SENTINELS = {2863311530, 4294967295, -1431655766, -1}
_SANE_POWER_CAP_W = 100_000_000  # 100 MW — far above any home; beyond this is garbage.


def _flow_value_is_suspect(value: Any) -> Optional[str]:
    """Return a reason string if a power value looks like a sentinel / garbage, else None."""
    try:
        v = int(float(value))
    except (TypeError, ValueError):
        return None
    if v in _POWER_SENTINELS:
        return f"value {v} == 0x{v & 0xFFFFFFFF:08X} sentinel (uninitialized/NaN), not real power"
    if abs(v) > _SANE_POWER_CAP_W:
        return f"value {v} exceeds a sane home-power cap ({_SANE_POWER_CAP_W} W); likely garbage"
    return None


def _annotate_flow_suspects(payload: Any) -> None:
    """Tag implausible power values in a /home/flow payload in-place with `_suspect`.

    Adds a top-level `_warnings` list when anything is flagged so a caller can
    see at a glance that at least one reading is untrustworthy.
    """
    if not isinstance(payload, dict):
        return
    result = payload.get("result")
    if not isinstance(result, dict):
        return
    indicators = result.get("indicators")
    if not isinstance(indicators, list):
        return
    warnings: List[str] = []
    for ind in indicators:
        if not isinstance(ind, dict):
            continue
        name = ind.get("indicator")
        reason = _flow_value_is_suspect(ind.get("total_value"))
        if reason:
            ind["_suspect"] = reason
            warnings.append(f"{name}.total_value: {reason}")
        for item in ind.get("value_item_list") or []:
            if not isinstance(item, dict):
                continue
            r = _flow_value_is_suspect(item.get("value"))
            if r:
                item["_suspect"] = r
                warnings.append(f"{name} <- {item.get('dev_name') or item.get('dev_id')}: {r}")
    if warnings:
        payload.setdefault("_warnings", []).extend(warnings)


def cmd_conow_flow(args: argparse.Namespace) -> None:
    body: Dict[str, Any] = {"home_id": _resolve_home_id(args)}
    if args.scale is not None:
        body["scale"] = args.scale
    if args.last_mins is not None:
        body["last_mins"] = args.last_mins
    if args.timezone:
        body["timezone"] = args.timezone
    body.update(_parse_kv_list(args.param))
    body = _merge_body(body, args.body_json)
    payload = _api_call(args, "POST", "/v1.0/end-user/energy/home/flow", body=body)
    _annotate_flow_suspects(payload)
    _print_payload(args, payload)


def cmd_conow_power_curve(args: argparse.Namespace) -> None:
    codes = _csv(args.indicator_code)
    body: Dict[str, Any] = {
        "home_id": _resolve_home_id(args),
        "begin_date": args.begin_date,
        "end_date": args.end_date,
    }
    if codes:
        body["indicator_codes"] = ",".join(codes)
    if args.date_type:
        body["date_type"] = args.date_type
    if args.query_type:
        body["query_type"] = args.query_type
    if args.query_step:
        body["query_step"] = args.query_step
    if args.time_aggr_type:
        body["time_aggr_type"] = args.time_aggr_type.upper()
    if args.device_aggr_type:
        body["device_aggr_type"] = args.device_aggr_type.upper()
    if args.auto:
        body["auto"] = args.auto
    if args.options:
        body["options"] = args.options
    if args.ext_condition:
        body["ext_condition"] = args.ext_condition
    if args.timezone:
        body["timezone"] = args.timezone
    body.update(_parse_kv_list(args.param))
    body = _merge_body(body, args.body_json)
    payload = _api_call(args, "POST", "/v1.0/end-user/energy/home/power-curve", body=body)
    _print_payload(args, payload)


def cmd_conow_impact(args: argparse.Namespace) -> None:
    body: Dict[str, Any] = {
        "home_id": _resolve_home_id(args),
        "phone_code": args.phone_code,
        "date_type": args.date_type,
        "begin_date": args.begin_date,
        "end_date": args.end_date,
    }
    if args.options:
        body["options"] = args.options
    if args.timezone:
        body["timezone"] = args.timezone
    body.update(_parse_kv_list(args.param))
    body = _merge_body(body, args.body_json)
    payload = _api_call(args, "POST", "/v1.0/end-user/energy/home/impact", body=body)
    _print_payload(args, payload)


def cmd_conow_indicators(args: argparse.Namespace) -> None:
    # Per backend spec, this endpoint takes an empty body and returns a
    # static home-level indicator dictionary. home_id is intentionally NOT
    # required here.
    body: Dict[str, Any] = {}
    body.update(_parse_kv_list(args.param))
    body = _merge_body(body, args.body_json)
    payload = _api_call(args, "POST", "/v1.0/end-user/energy/home/indicators", body=body)
    _print_payload(args, payload)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _add_global(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--base-url",
        default=os.environ.get("CONOW_BASE_URL"),
        help=(
            "Gateway base URL. If unset, the CLI auto-derives the data-center "
            "URL from the sk- key prefix (sk-AY -> openapi.tuyacn.com, etc). "
            "Set this only when targeting a custom or staging deployment."
        ),
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("CONOW_API_KEY"),
        help="Bearer token, default env CONOW_API_KEY",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="HTTP timeout seconds, default %(default)s",
    )
    parser.add_argument(
        "--output",
        choices=("json", "text"),
        default="json",
        help="Output style, default json",
    )


def _add_home(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--home-id",
        default=None,
        help="Home id. If omitted, falls back to CONOW_HOME_ID (only when no "
             "--home-name is given), otherwise list_homes is called. An "
             "explicit --home-name always overrides a CONOW_HOME_ID default.",
    )
    parser.add_argument(
        "--home-name",
        default=None,
        help="Home name or substring; resolved to home_id via list_homes fuzzy match. "
             "Ignored if --home-id is explicitly set; takes priority over CONOW_HOME_ID.",
    )
    parser.add_argument(
        "--homes-path",
        default=os.environ.get("CONOW_HOMES_PATH"),
        help="Override the list-homes path on the gateway (for auto-discovery fallback).",
    )


def _add_common(parser: argparse.ArgumentParser) -> None:
    _add_global(parser)
    _add_home(parser)
    parser.add_argument(
        "--param",
        action="append",
        metavar="KEY=VALUE",
        help="Extra query/body param, repeatable. Used as escape hatch for fields we did not model.",
    )
    parser.add_argument(
        "--body-json",
        help="Raw JSON object, merged into the request body (wins over convenience flags).",
    )
    parser.add_argument(
        "--timezone",
        default=os.environ.get("CONOW_TIMEZONE"),
        help=(
            "Timezone, default env CONOW_TIMEZONE. Only indicators "
            "aggregate/trend/top auto-fill this from /home/station when omitted "
            "(disable with --no-auto-timezone); forecast / tariff / flow / "
            "power-curve use it verbatim and do not auto-fill."
        ),
    )
    parser.add_argument(
        "--no-auto-timezone",
        action="store_true",
        help="Do not auto-fetch home timezone from /home/station for indicators requests.",
    )


def _add_date_window(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--date-type",
        required=True,
        choices=("quarter", "hour", "day", "month", "year"),
        help="Time granularity. Backend enum is quarter/hour/day/month/year "
             "(there is no `week` — for a weekly total use `day` over the "
             "7-day range with --time-aggr-type sum).",
    )
    parser.add_argument(
        "--begin-date",
        help="Begin date; format keyed off --date-type: year=yyyy, month=yyyyMM, "
             "day=yyyyMMdd, hour=yyyyMMddHH, quarter=yyyyMMddHHmm (12 digits, "
             "15-minute buckets). E.g. 20260415 (day) or 202604151500 (quarter).",
    )
    parser.add_argument("--end-date", help="End date (inclusive), same format as --begin-date.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="conow_cli",
        description="Conow smart energy end-user openapi CLI",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # list-homes
    p = sub.add_parser("list-homes", help="List homes bound to the current api key")
    _add_global(p)
    p.add_argument(
        "--homes-path",
        default=os.environ.get("CONOW_HOMES_PATH"),
        help="Override the list-homes path on the gateway. Default: /v1.0/end-user/homes/all",
    )
    p.set_defaults(func=cmd_list_homes)

    # resolve-home — preflight "which home?" helper, no query side-effects
    p = sub.add_parser(
        "resolve-home",
        help="Resolve home_id from --home-name / --home-id / cache without querying energy",
    )
    _add_global(p)
    _add_home(p)
    p.set_defaults(func=cmd_resolve_home)

    # indicators aggregate / trend (shared multi-query body)
    for name, func, help_text in (
        ("indicators-aggregate", cmd_indicators_aggregate, "POST /indicators/aggregate"),
        ("indicators-trend", cmd_indicators_trend, "POST /indicators/trend"),
    ):
        p = sub.add_parser(name, help=help_text)
        _add_common(p)
        _add_date_window(p)
        p.add_argument(
            "--indicator-code",
            action="append",
            required=True,
            help="Repeatable or comma-separated indicator codes (max 20). "
                 "Gateway expects a single comma-separated string; the CLI joins automatically.",
        )
        p.add_argument(
            "--time-aggr-type",
            type=str.upper,
            choices=("SUM", "AVG", "MAX", "MIN"),
            help="Time aggregation. Wire format is uppercase; the CLI uppercases automatically.",
        )
        p.add_argument(
            "--device-aggr-type",
            type=str.upper,
            choices=("SUM", "AVG", "MAX", "MIN"),
            help="Device aggregation. Wire format is uppercase; the CLI uppercases automatically.",
        )
        p.add_argument(
            "--include-children",
            type=lambda s: s.lower() in ("1", "true", "yes"),
            help="Include child dimensions (true/false)",
        )
        p.add_argument(
            "--ext-condition",
            help='Dimension/device filter as JSON string, e.g. \'{"deviceIds":["dev1","dev2"]}\'',
        )
        p.add_argument("--options", help='Extra options JSON string, e.g. \'{"scale":2}\'')
        p.set_defaults(func=func)

    # indicators top (different body shape)
    p = sub.add_parser("indicators-top", help="POST /indicators/top (TopN by group)")
    _add_common(p)
    _add_date_window(p)
    p.add_argument(
        "--indicator-code",
        dest="indicator_code_single",
        required=True,
        help="Single indicator code (top does not accept multiple).",
    )
    p.add_argument(
        "--group-by",
        required=True,
        help="Group dimension, e.g. device / space / usage",
    )
    p.add_argument(
        "--number",
        type=int,
        required=True,
        help="Top N, must be in [1, 50]",
    )
    p.add_argument("--sort-type", choices=("asc", "desc"), help="Sort order, default desc")
    p.add_argument("--time-aggr-type", type=str.upper, choices=("SUM", "AVG", "MAX", "MIN"))
    p.add_argument("--device-aggr-type", type=str.upper, choices=("SUM", "AVG", "MAX", "MIN"))
    p.add_argument(
        "--include-children",
        type=lambda s: s.lower() in ("1", "true", "yes"),
        help="Include child dimensions (true/false)",
    )
    p.add_argument("--ext-condition", help="Extension filter JSON string")
    p.add_argument("--options", help='Extra options JSON string, e.g. \'{"scale":2}\'')
    p.set_defaults(func=cmd_indicators_top)

    # indicators list (GET /indicators) — system-level, no home_id
    p = sub.add_parser("indicators-list", help="GET /indicators (indicator metadata)")
    _add_global(p)
    p.add_argument(
        "--param",
        action="append",
        metavar="KEY=VALUE",
        help="Extra query param, repeatable.",
    )
    p.add_argument("--energy-type", help="Filter by energy type: electricity / water / gas")
    p.add_argument("--keyword", help="Fuzzy match on code or name")
    # Accept (and ignore) --home-id/--home-name for habitual callers:
    # indicators-list is system-level and the server contract does not take it.
    p.add_argument("--home-id", dest="_ignored_home_id", help=argparse.SUPPRESS)
    p.add_argument("--home-name", dest="_ignored_home_name", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_indicators_list)

    # home station — timezone / country / location / capacity helper
    p = sub.add_parser(
        "conow-station",
        help="POST /home/station (home location, timezone, capacity, owner info)",
    )
    _add_global(p)
    _add_home(p)
    p.add_argument(
        "--param",
        action="append",
        metavar="KEY=VALUE",
        help="Extra body param, repeatable. Used as escape hatch for fields we did not model.",
    )
    p.add_argument(
        "--body-json",
        help="Raw JSON object, merged into the request body (wins over convenience flags).",
    )
    p.add_argument("--biz-data", help="Optional biz_data JSON string for image CDN context")
    p.set_defaults(func=cmd_conow_station)

    # forecast — POST /v1.0/end-user/energy/forecast (hourly, max 48h, up to 2 codes)
    p = sub.add_parser(
        "forecast",
        help="POST /forecast (next-N-hour produce + consumption forecast, hourly, "
             "<=48h window, up to 2 indicator codes per request)",
    )
    _add_common(p)
    p.add_argument(
        "--indicator-code",
        action="append",
        help="Repeatable or comma-separated. Valid codes: "
             "ele_forecast_produce, ele_forecast_consumption (max 2). "
             "Default when omitted: both.",
    )
    p.add_argument(
        "--begin-date",
        required=True,
        help="Forecast window start in yyyyMMddHH (10 digits, hour granularity).",
    )
    p.add_argument(
        "--end-date",
        required=True,
        help="Forecast window end (inclusive) in yyyyMMddHH. Window <=48h.",
    )
    p.add_argument(
        "--use-cache",
        type=lambda s: s.lower() in ("1", "true", "yes"),
        default=None,
        help="true/false. Server default is true; pass false to bypass forecast cache.",
    )
    p.add_argument(
        "--scale",
        type=int,
        help="Decimal places for forecast values. Server default is 4.",
    )
    p.add_argument(
        "--options",
        help='Raw options JSON (overrides --scale), e.g. \'{"scale":3}\'.',
    )
    p.add_argument(
        "--allow-long-window",
        action="store_true",
        help="Skip the local 48h window check. The server will accept the call "
             "but is known to silently return an empty list for windows >48h.",
    )
    p.add_argument(
        "--allow-any-code",
        action="store_true",
        help="Skip the local indicator-code whitelist (forwards arbitrary codes).",
    )
    p.set_defaults(func=cmd_forecast)

    # forecast-indicator — DEPRECATED shim. Routes to the new POST /forecast.
    # The legacy GET /forecast/indicator was never deployed on this gateway.
    p = sub.add_parser(
        "forecast-indicator",
        help="DEPRECATED: forwards to POST /forecast. Prefer the `forecast` subcommand.",
    )
    _add_common(p)
    p.add_argument(
        "--indicator-code",
        dest="indicator_code_single",
        required=True,
        help="Forecast indicator code, e.g. ele_forecast_produce / ele_forecast_consumption.",
    )
    _add_date_window(p)
    # Hidden flags so the shim can hand off to _do_forecast_request unchanged.
    p.add_argument(
        "--use-cache",
        type=lambda s: s.lower() in ("1", "true", "yes"),
        default=None,
        help=argparse.SUPPRESS,
    )
    p.add_argument("--scale", type=int, help=argparse.SUPPRESS)
    p.add_argument("--options", help=argparse.SUPPRESS)
    p.add_argument("--allow-any-code", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--allow-long-window", action="store_true", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_forecast_indicator)

    # tariff
    p = sub.add_parser("tariff-query", help="POST /tariff/query")
    _add_common(p)
    _add_date_window(p)
    p.add_argument(
        "--direction",
        choices=("import", "export"),
        help="Tariff direction. The gateway expects uppercase on the wire; the CLI normalizes it.",
    )
    p.set_defaults(func=cmd_tariff_query)

    p = sub.add_parser("tariff-label", help="POST /tariff/label (price thresholds)")
    _add_common(p)
    p.add_argument(
        "--direction",
        choices=("import", "export"),
        help="Tariff direction. The gateway expects uppercase on the wire; the CLI normalizes it.",
    )
    p.set_defaults(func=cmd_tariff_label)

    # Conow home/* (/v1.0/end-user/energy/home/{flow,power-curve,impact,indicators,station})
    p = sub.add_parser(
        "conow-flow",
        help="POST /home/flow (real-time home power flow + SOC + device-level breakdown)",
    )
    _add_common(p)
    p.add_argument(
        "--scale",
        type=int,
        help="Decimal places for power values (server default is 4).",
    )
    p.add_argument(
        "--last-mins",
        type=int,
        help="Only consider data points from the last N minutes.",
    )
    p.set_defaults(func=cmd_conow_flow)

    p = sub.add_parser(
        "conow-power-curve",
        help="POST /home/power-curve (home-level indicator time series)",
    )
    _add_common(p)
    _add_date_window(p)
    p.add_argument(
        "--indicator-code",
        action="append",
        required=True,
        help="Repeatable or comma-separated indicator codes (max 20). "
             "Example: --indicator-code soc,home_total_photovoltaic_power",
    )
    p.add_argument(
        "--query-step",
        help="Data point step, e.g. 15m / 1h / 1d",
    )
    p.add_argument(
        "--query-type",
        help="Query granularity helper field (rarely needed).",
    )
    p.add_argument(
        "--time-aggr-type",
        type=str.upper,
        choices=("SUM", "AVG", "MAX", "MIN"),
        help="Time aggregation (uppercase on the wire).",
    )
    p.add_argument(
        "--device-aggr-type",
        type=str.upper,
        choices=("SUM", "AVG", "MAX", "MIN"),
        help="Device aggregation (uppercase on the wire).",
    )
    p.add_argument(
        "--auto",
        help="Fill-in mode, default '3' on the server; business callers usually pass '2'.",
    )
    p.add_argument(
        "--options",
        help='Extra options JSON string, e.g. \'{"scale":2,"queryPredict":1}\'',
    )
    p.add_argument(
        "--ext-condition",
        help="Extension filter as JSON string.",
    )
    p.set_defaults(func=cmd_conow_power_curve)

    p = sub.add_parser(
        "conow-impact",
        help="POST /home/impact (revenue / carbon / self-sufficiency; phone_code required)",
    )
    _add_common(p)
    _add_date_window(p)
    p.add_argument(
        "--phone-code",
        required=True,
        help="ISO 3166 alpha-2 country code (e.g. DE, US, CN, SE, JP). "
             "Required by the backend; drives the carbon factor. "
             "Lowercase works but uppercase is conventional.",
    )
    p.add_argument(
        "--options",
        help='Extra options JSON string, e.g. \'{"scale":2}\'',
    )
    p.set_defaults(func=cmd_conow_impact)

    p = sub.add_parser(
        "conow-indicators",
        help="POST /home/indicators (home-level indicator dictionary; no home_id needed)",
    )
    _add_global(p)
    p.add_argument(
        "--param",
        action="append",
        metavar="KEY=VALUE",
        help="Extra body param, repeatable (escape hatch for future fields).",
    )
    p.add_argument(
        "--body-json",
        help="Raw JSON object, merged into the request body.",
    )
    p.add_argument(
        "--timezone",
        default=os.environ.get("CONOW_TIMEZONE"),
        help=argparse.SUPPRESS,
    )
    # Accept (and ignore) --home-id / --home-name so habitual callers don't trip.
    p.add_argument("--home-id", dest="_ignored_home_id", help=argparse.SUPPRESS)
    p.add_argument("--home-name", dest="_ignored_home_name", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_conow_indicators)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _resolve_base_url(args)
    try:
        args.func(args)
    except GatewayBusinessError as e:
        # The full payload was already printed to stdout by _print_payload.
        # Add a friendly, actionable hint to stderr without hiding the raw
        # code/msg, then exit non-zero so callers can detect the failure.
        hint = GATEWAY_CODE_HINTS.get(e.code)
        if hint:
            sys.stderr.write(f"error: gateway {e.code} {e.msg} — {hint}\n")
        else:
            sys.stderr.write(f"error: gateway returned success=false ({e.code} {e.msg})\n")
        return 2
    except ConowError as e:
        sys.stderr.write(f"error: {e}\n")
        return 2
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
