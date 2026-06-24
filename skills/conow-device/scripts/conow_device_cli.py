#!/usr/bin/env python3
"""Conow Device CLI — Tuya generic device query/control + Conow energy device
enhanced endpoints, with automatic device-type routing.

Gateway: the base URL is auto-derived from the sk- key prefix and maps to
the corresponding data center. Override via CONOW_BASE_URL when targeting a
dedicated gateway URL.
Auth: Authorization: Bearer sk-xxx

Design goal: agents only invoke the high-level subcommands (e.g.
device-overview, device-control). This CLI first probes the energy device
endpoints (topo / protocol) and then routes to either the energy branch or
the Tuya generic /v1.0/end-user/devices/... branch.

Environment variables:
  CONOW_API_KEY   sk-xxx bearer token (required unless --api-key is set).
                  Get a key from your Conow App or the Tuya Open Platform.
  CONOW_BASE_URL  optional gateway override; if unset the CLI auto-derives
                  the data-center URL from the sk- key prefix (sk-AY ->
                  openapi.tuyacn.com, etc). Set this only if your deployment
                  provides a dedicated gateway URL.
  CONOW_DEVICE_ID default dev_id (optional).

Energy device HTTP paths (end-user prefix):
  GET  /v1.0/end-user/energy/devices/topo
  GET  /v1.0/end-user/energy/devices/protocol
  GET  /v1.0/end-user/energy/devices/model
  GET  /v1.0/end-user/energy/devices/properties
  GET  /v1.0/end-user/energy/devices/alarms
  GET  /v1.0/end-user/energy/devices/indicators
  GET  /v1.0/end-user/energy/devices/indicators/sdata
  POST /v1.0/end-user/energy/devices/issue                # 能源设备参数下发（唯一已发布写口，无校验裸通道）

能源设备 AI 控制（control-plan / control-confirm / energy-controllable）全部在本 CLI 内
客户端实现：能力发现 = energy-model(type=setting) ∩ 内置最小白名单（ENERGY_CONTROL_ALLOWLIST），
取值/枚举/范围校验在本地完成，下发走上面已发布的 /energy/devices/issue。不依赖网关上未发布的
/controllable 与 /control/issue（二者在当前网关返回 1108）。

Generic devices (aligned with tuya-openclaw / tuya-smart-control):
  GET  /v1.0/end-user/devices/all
  GET  /v1.0/end-user/homes/{home_id}/devices
  GET  /v1.0/end-user/devices/{device_id}/detail
  GET  /v1.0/end-user/devices/{device_id}/model
  POST /v1.0/end-user/devices/{device_id}/shadow/properties/issue
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_TIMEOUT = 20

# Tuya sk- key 前两个字符（去掉 "sk-" 之后的 2 位）映射到对应数据中心 base URL。
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
# HTTP
# ---------------------------------------------------------------------------


class ConowDeviceError(RuntimeError):
    """Remote API or validation error."""


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


# Gateway business-code -> friendly hint. The raw code/msg is always kept in the
# payload; these only add an end-user-facing explanation, never hide the original.
GATEWAY_CODE_HINTS: Dict[int, str] = {
    1106: (
        "no access to that home/device — the key may not own it, or it lives in "
        "a different data center than this gateway (check the sk- key region prefix)"
    ),
    1108: "capability/route not available on this gateway (uri path invalid)",
}


def _friendly_gateway_hint(payload: Dict[str, Any]) -> Optional[str]:
    """Map a gateway business code in the payload to a friendly hint, or None."""
    code = payload.get("code")
    try:
        code_int = int(code)
    except (TypeError, ValueError):
        return None
    return GATEWAY_CODE_HINTS.get(code_int)


def _redact_key(api_key: Optional[str]) -> str:
    """Redact an sk- key for verbose logs: keep `sk-A` head + last 4, mask middle."""
    if not api_key:
        return "<none>"
    if len(api_key) <= 8:
        return api_key[:3] + "***"
    return f"{api_key[:4]}***{api_key[-4:]}"


def _verbose_request_summary(
    method: str, url: str, headers: Dict[str, str], body: Optional[Any]
) -> None:
    """If CONOW_VERBOSE=1, print a redacted request summary to stderr (never the raw key)."""
    if os.environ.get("CONOW_VERBOSE", "") not in ("1", "true", "TRUE", "yes"):
        return
    auth = headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        auth_summary = "Bearer " + _redact_key(auth[len("Bearer "):])
    else:
        auth_summary = "<none>"
    sys.stderr.write(f"[conow-device] {method} {url}\n")
    sys.stderr.write(f"[conow-device]   Authorization: {auth_summary}\n")
    if body is not None:
        sys.stderr.write(
            f"[conow-device]   body: {json.dumps(body, ensure_ascii=False)[:500]}\n"
        )


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

    _verbose_request_summary(method, url, headers, body)
    req = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        status = e.code
    except urllib.error.URLError as e:
        raise ConowDeviceError(f"network error: {e}") from e

    try:
        payload: Dict[str, Any] = json.loads(raw) if raw else {}
    except json.JSONDecodeError as e:
        raise ConowDeviceError(f"non-json (http {status}): {raw[:400]}") from e
    if status >= 400:
        raise ConowDeviceError(f"http {status}: {payload}")
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
    return _http_request(method, url, headers, body=body, timeout=args.timeout)


def _print_json(args: argparse.Namespace, obj: Any) -> None:
    # Remember the last top-level object so main() can derive the exit code from
    # a gateway business failure (success:false) without each command re-checking.
    setattr(args, "_last_output", obj)
    json.dump(obj, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


# ---------------------------------------------------------------------------
# 能源设备判断
# ---------------------------------------------------------------------------


def _is_truthy_api_success(payload: Dict[str, Any]) -> bool:
    return payload.get("success") is True


def _result_non_empty(payload: Dict[str, Any]) -> bool:
    r = payload.get("result", payload)
    if r is None:
        return False
    if isinstance(r, dict) and not r:
        return False
    if isinstance(r, list) and not r:
        return False
    return r != ""


def _infer_energy_from_topo_payload(payload: Dict[str, Any]) -> bool:
    if not _is_truthy_api_success(payload):
        return False
    r = payload.get("result")
    if r is None:
        return False
    if isinstance(r, dict) and r:
        for v in r.values():
            if isinstance(v, list) and v:
                return True
            if v:
                return True
    if isinstance(r, list) and r:
        return True
    return _result_non_empty(payload)


def _infer_energy_from_protocol_payload(payload: Dict[str, Any]) -> bool:
    if not _is_truthy_api_success(payload) or not _result_non_empty(payload):
        return False
    r = payload.get("result")
    if isinstance(r, dict):
        for k in ("protocolCode", "protocol_code", "manufacturer", "energyDevType", "energy_dev_type"):
            if r.get(k) not in (None, "", []):
                return True
    return bool(r)


def _safe_energy_get(
    args: argparse.Namespace, path: str, dev_id: str
) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Return (payload or None, error string). 1108 等业务错误不抛，交给上层综合判断。"""
    try:
        p = _api_call(args, "GET", path, query={"device_id": dev_id})
        return p, None
    except ConowDeviceError as e:
        s = str(e)
        if "1108" in s or "uri path invalid" in s.lower():
            return None, "not_deployed_or_path_invalid"
        return None, s


def _flatten_topo_candidates(payload: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not payload or payload.get("success") is not True:
        return []
    result = payload.get("result")
    if not isinstance(result, dict):
        return []

    candidates: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for energy_type, items in result.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            energy_dev_id = item.get("energyDevId") or item.get("energy_dev_id")
            if not energy_dev_id or energy_dev_id in seen:
                continue
            candidate = dict(item)
            candidate.setdefault("energyDevType", energy_type)
            candidates.append(candidate)
            seen.add(energy_dev_id)
    return candidates


def _candidate_energy_type(candidate: Dict[str, Any]) -> str:
    return str(candidate.get("energyDevType") or candidate.get("energy_dev_type") or "").strip()


def _candidate_energy_dev_id(candidate: Dict[str, Any]) -> str:
    return str(candidate.get("energyDevId") or candidate.get("energy_dev_id") or "").strip()


def _select_preferred_energy_candidate(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if len(candidates) <= 1:
        return candidates[0] if candidates else None

    inverter_candidates = [
        candidate for candidate in candidates if _candidate_energy_type(candidate) == "inverter"
    ]
    non_inverter_types = {
        energy_type
        for energy_type in (_candidate_energy_type(candidate) for candidate in candidates)
        if energy_type != "inverter"
    }
    if len(inverter_candidates) == 1 and non_inverter_types == {"collection_stick"}:
        return inverter_candidates[0]
    return None


def _resolve_energy_dev_id(
    args: argparse.Namespace,
    dev_id: str,
    energy_dev_id: str = "",
    topo_payload: Optional[Dict[str, Any]] = None,
) -> Tuple[str, List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if energy_dev_id and energy_dev_id.strip():
        return energy_dev_id.strip(), [], topo_payload

    topo = topo_payload
    if topo is None:
        topo, err = _safe_energy_get(args, "/v1.0/end-user/energy/devices/topo", dev_id)
        if topo is None:
            raise ConowDeviceError(f"failed to resolve energy_dev_id from topo: {err}")

    candidates = _flatten_topo_candidates(topo)
    if not candidates:
        raise ConowDeviceError(f"no energy device found for device_id={dev_id}")
    preferred = _select_preferred_energy_candidate(candidates)
    if preferred:
        resolved = _candidate_energy_dev_id(preferred)
        if resolved:
            return resolved, candidates, topo
    raise ConowDeviceError(
        "multiple energy devices found for "
        f"device_id={dev_id}; please pass --energy-dev-id explicitly. "
        f"candidates={json.dumps(candidates, ensure_ascii=False)}"
    )


def cmd_detect(args: argparse.Namespace) -> None:
    dev_id = _dev_id(args)
    topo, err_t = _safe_energy_get(
        args, "/v1.0/end-user/energy/devices/topo", dev_id
    )
    proto, err_p = _safe_energy_get(
        args, "/v1.0/end-user/energy/devices/protocol", dev_id
    )

    energy_topo = bool(topo and _infer_energy_from_topo_payload(topo))
    energy_proto = bool(proto and _infer_energy_from_protocol_payload(proto))
    is_energy = energy_topo or energy_proto

    out: Dict[str, Any] = {
        "dev_id": dev_id,
        "is_energy_device": is_energy,
        "signals": {
            "topo": {
                "ok": topo is not None,
                "heuristic": energy_topo,
                "error": err_t,
                "payload": topo,
            },
            "protocol": {
                "ok": proto is not None,
                "heuristic": energy_proto,
                "error": err_p,
                "payload": proto,
            },
        },
    }
    if is_energy:
        out["routed_as"] = "energy"
    else:
        out["routed_as"] = "public_tuya_device"
    _print_json(args, out)


def _dev_id(args: argparse.Namespace) -> str:
    did = args.dev_id or os.environ.get("CONOW_DEVICE_ID", "")
    if not did:
        raise ConowDeviceError("missing --dev-id (or CONOW_DEVICE_ID env)")
    return did.strip()


# ---------------------------------------------------------------------------
# 公版
# ---------------------------------------------------------------------------


def cmd_public_detail(args: argparse.Namespace) -> None:
    d = _dev_id(args)
    p = _api_call(args, "GET", f"/v1.0/end-user/devices/{d}/detail")
    _print_json(args, p)


def cmd_public_model(args: argparse.Namespace) -> None:
    d = _dev_id(args)
    p = _api_call(args, "GET", f"/v1.0/end-user/devices/{d}/model")
    _print_json(args, p)


def cmd_public_control(args: argparse.Namespace) -> None:
    d = _dev_id(args)
    if not args.properties:
        raise ConowDeviceError("missing --properties json object for public control")
    try:
        props = json.loads(args.properties)
    except json.JSONDecodeError as e:
        raise ConowDeviceError(f"invalid --properties: {e}") from e
    if not isinstance(props, dict):
        raise ConowDeviceError("--properties must be a JSON object")
    body: Dict[str, Any] = {"properties": []}
    for k, v in props.items():
        body["properties"].append({"code": k, "value": v})
    p = _api_call(
        args,
        "POST",
        f"/v1.0/end-user/devices/{d}/shadow/properties/issue",
        body=body,
    )
    _print_json(args, p)


def _extract_device_list(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    result = payload.get("result")
    if isinstance(result, dict):
        devices = result.get("devices") or result.get("list") or []
    elif isinstance(result, list):
        devices = result
    else:
        devices = []
    return [d for d in devices if isinstance(d, dict)]


def _device_identity(device: Dict[str, Any]) -> Optional[str]:
    did = device.get("device_id") or device.get("dev_id") or device.get("id")
    return str(did) if did else None


def _extract_home_list(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    result = payload.get("result")
    if isinstance(result, dict):
        homes = result.get("homes") or result.get("list") or []
    elif isinstance(result, list):
        homes = result
    else:
        homes = []
    return [h for h in homes if isinstance(h, dict)]


def _home_identity(home: Dict[str, Any]) -> Optional[str]:
    hid = home.get("home_id") or home.get("homeId") or home.get("id")
    return str(hid) if hid else None


def cmd_list_homes(args: argparse.Namespace) -> None:
    payload = _api_call(args, "GET", "/v1.0/end-user/homes/all")
    homes = _extract_home_list(payload)
    out: Dict[str, Any] = {
        "success": payload.get("success"),
        "count": len(homes),
        "homes": [
            {
                "home_id": _home_identity(home),
                "name": home.get("name") or "",
                "role": home.get("role"),
                "raw": home,
            }
            for home in homes
        ],
    }
    if payload.get("success") is not True:
        out["raw"] = payload
    _print_json(args, out)


def cmd_resolve_home(args: argparse.Namespace) -> None:
    query = (args.home_id or args.home_name or "").strip()
    if not query:
        raise ConowDeviceError("missing --home-name or --home-id")

    payload = _api_call(args, "GET", "/v1.0/end-user/homes/all")
    homes = _extract_home_list(payload)
    candidates = [
        {
            "home_id": _home_identity(home),
            "name": home.get("name") or "",
            "role": home.get("role"),
        }
        for home in homes
    ]
    q = query.lower()
    exact = [
        h for h in candidates
        if h["home_id"] == query or h["name"].lower() == q
    ]
    if len(exact) == 1:
        _print_json(args, {"success": True, **exact[0]})
        return

    matches = [
        h for h in candidates
        if h["name"].lower().startswith(q)
        or q in h["name"].lower()
        or (len(h["name"]) >= 3 and h["name"].lower() in q)
    ]
    if len(matches) == 1:
        _print_json(args, {"success": True, **matches[0]})
        return

    _print_json(
        args,
        {
            "success": False,
            "error": "home not found or ambiguous",
            "query": query,
            "candidates": matches or candidates,
        },
    )


def cmd_list_devices(args: argparse.Namespace) -> None:
    if args.home_id:
        path = f"/v1.0/end-user/homes/{args.home_id}/devices"
        query: Dict[str, Any] = {
            "page_no": args.page_no,
            "page_size": args.page_size,
        }
        payload = _api_call(args, "GET", path, query=query)
        scope = "home"
    else:
        payload = _api_call(args, "GET", "/v1.0/end-user/devices/all")
        scope = "account"

    devices = _extract_device_list(payload)
    unique_ids = sorted({did for did in (_device_identity(d) for d in devices) if did})
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    out: Dict[str, Any] = {
        "success": payload.get("success"),
        "scope": scope,
        "home_id": args.home_id or None,
        "count": len(unique_ids),
        "total": result.get("total"),
        "unique_device_ids": unique_ids,
    }
    if not args.summary_only:
        out["devices"] = devices
    if payload.get("success") is not True:
        out["raw"] = payload
    _print_json(args, out)


# ---------------------------------------------------------------------------
# 能源设备直连
# ---------------------------------------------------------------------------


def cmd_energy_topo(args: argparse.Namespace) -> None:
    p = _api_call(args, "GET", "/v1.0/end-user/energy/devices/topo", query={"device_id": _dev_id(args)})
    _print_json(args, p)


def cmd_energy_protocol(args: argparse.Namespace) -> None:
    p = _api_call(args, "GET", "/v1.0/end-user/energy/devices/protocol", query={"device_id": _dev_id(args)})
    _print_json(args, p)


def cmd_energy_model(args: argparse.Namespace) -> None:
    q: Dict[str, Any] = {"device_id": _dev_id(args)}
    if args.type_:
        q["type"] = args.type_
    if args.codes:
        q["codes"] = args.codes
    p = _api_call(args, "GET", "/v1.0/end-user/energy/devices/model", query=q)
    _print_json(args, p)


def cmd_energy_properties(args: argparse.Namespace) -> None:
    dev_id = _dev_id(args)
    resolved_energy_dev_id, _, _ = _resolve_energy_dev_id(
        args, dev_id, args.energy_dev_id or ""
    )
    q: Dict[str, Any] = {
        "device_id": dev_id,
        "energy_dev_id": resolved_energy_dev_id,
    }
    if args.codes:
        q["codes"] = args.codes
    p = _api_call(args, "GET", "/v1.0/end-user/energy/devices/properties", query=q)
    _print_json(args, p)


def cmd_energy_alarms(args: argparse.Namespace) -> None:
    q: Dict[str, Any] = {
        "device_id": _dev_id(args),
        "start_time": args.start_time,
        "end_time": args.end_time,
        "page_num": args.page_num,
        "page_size": args.page_size,
        "weight": args.weight,
    }
    if args.event_type:
        q["event_type"] = args.event_type
    if args.event_status is not None:
        q["event_status"] = args.event_status
    p = _api_call(args, "GET", "/v1.0/end-user/energy/devices/alarms", query=q)
    _print_json(args, p)


def cmd_energy_indicators(args: argparse.Namespace) -> None:
    p = _api_call(
        args, "GET", "/v1.0/end-user/energy/devices/indicators", query={"device_id": _dev_id(args)}
    )
    _print_json(args, p)


def cmd_energy_sdata(args: argparse.Namespace) -> None:
    q: Dict[str, Any] = {
        "device_id": _dev_id(args),
        "indicator_code": args.indicator_code,
        "query_type": args.query_type,
        "query_step": args.query_step,
        "start_time": args.start_time,
        "end_time": args.end_time,
    }
    if args.auto:
        q["auto"] = args.auto
    p = _api_call(args, "GET", "/v1.0/end-user/energy/devices/indicators/sdata", query=q)
    _print_json(args, p)


def cmd_energy_issue(args: argparse.Namespace) -> None:
    if not args.setting:
        raise ConowDeviceError("energy issue requires --setting (JSON object or array)")
    dev_id = _dev_id(args)
    resolved_energy_dev_id, _, _ = _resolve_energy_dev_id(
        args, dev_id, args.energy_dev_id or ""
    )
    try:
        stripped = args.setting.strip()
        st = json.loads(stripped) if stripped[:1] in ("{", "[") else None
    except json.JSONDecodeError as e:
        raise ConowDeviceError(f"invalid --setting: {e}") from e
    if isinstance(st, dict):
        setting = [{"code": k, "value": v} for k, v in st.items()]
    elif isinstance(st, list):
        setting = st
    else:
        raise ConowDeviceError("--setting must be a JSON object or array")
    body: Dict[str, Any] = {
        "device_id": dev_id,
        "energy_dev_id": resolved_energy_dev_id,
        "setting": setting,
    }
    p = _api_call(args, "POST", "/v1.0/end-user/energy/devices/issue", body=body)
    _print_json(args, p)


# ---------------------------------------------------------------------------
# 能源设备控制：两步确认门禁（control-plan 只读预览 / control-confirm 执行）
#
# 设计：能源逆变器（string inverter）的控制通过已发布的 energy-model(type=setting) ∩ 技能内置最小白名单
# 做能力发现 + 本地校验，再经已发布的 POST /energy/devices/issue 下发。普通设备仍走
# public-control（见 device-control）。
# 门禁：control-plan 只发 GET、产出 plan_hash；control-confirm 必须带与本次参数
# 完全一致的 --plan-hash 才会 POST 下发，杜绝「用户同意的不是即将执行的那一笔」。
# ---------------------------------------------------------------------------


def _coerce_value(v: Any) -> str:
    """后端 settings.value 为 String；bool 归一为 true/false，其余 str()。"""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _normalize_settings(args: argparse.Namespace) -> List[Dict[str, str]]:
    """把 --properties(JSON 对象) 或 --settings(JSON 对象/数组) 归一为按 code 排序的 [{code,value}]。"""
    raw = getattr(args, "settings", None) or getattr(args, "properties", None)
    if not raw:
        raise ConowDeviceError("需要 --properties (JSON 对象) 或 --settings (JSON 对象/数组)")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ConowDeviceError(f"settings JSON 非法: {e}") from e
    items: List[Dict[str, str]] = []
    if isinstance(parsed, dict):
        for k, v in parsed.items():
            items.append({"code": str(k), "value": _coerce_value(v)})
    elif isinstance(parsed, list):
        for it in parsed:
            if not isinstance(it, dict) or "code" not in it:
                raise ConowDeviceError("--settings 数组项必须是 {code,value}")
            items.append({"code": str(it["code"]), "value": _coerce_value(it.get("value"))})
    else:
        raise ConowDeviceError("settings 必须是 JSON 对象或数组")
    if not items:
        raise ConowDeviceError("settings 为空")
    items.sort(key=lambda x: x["code"])
    return items


def _plan_hash(dev_id: str, energy_dev_id: str, items: List[Dict[str, str]]) -> str:
    """plan_hash = sha256(dev_id + 已解析的 energy_dev_id + 规范化排序后的 settings)。

    energy_dev_id 必须参与哈希：否则在「1 逆变器 + 电池 + 采集棒」这类多候选拓扑下，
    control-plan 预览的是 A 子设备、control-confirm 却传 B 子设备时哈希仍然相同，
    写入会落到用户没复核过的另一台物理子设备上，门禁形同虚设。把已解析的 energy_dev_id
    纳入哈希后，confirm 端只要解析出的子设备与 plan 不一致就会触发 PLAN_HASH_MISMATCH。
    """
    canonical = json.dumps(
        {"dev_id": dev_id, "energy_dev_id": energy_dev_id, "settings": items},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# AI 可控「最小白名单」——把无校验的 energy-issue 裸通道收口成一小撮安全、用户语义清晰的
# 能源设备控制项（限逆变器 string inverter）。energy-model(type=setting) 物模型会暴露大量设置项
# （含 reset 工厂复位、grid_*_threshold 电网安全阈值、afci、insulation_detection 等危险/装机参数），
# 绝不可整面放给 AI。运行时与 live energy-model 取交集：范围/枚举/单位以设备实测为准，机型不支持的 code 自动不出现。
# 这份白名单就是本技能内置的安全闸门（在客户端收口无校验的 energy-issue 裸通道），新增可控项只需在此登记。
ENERGY_CONTROL_ALLOWLIST: Dict[str, Dict[str, str]] = {
    # —— 逆变器 (string inverter) ——
    "inverter_work_mode_setting": {"cn": "工作模式", "en": "Work mode", "category": "mode"},
    "backup_enable": {"cn": "备电使能", "en": "Backup enable", "category": "backup"},
    "forced_off_grid": {"cn": "强制离网", "en": "Force off-grid", "category": "offgrid"},
    "anti_reflux": {"cn": "防逆流", "en": "Backflow prevention", "category": "feedin"},
    "inverter_switch": {"cn": "逆变器开关", "en": "Inverter on/off", "category": "power"},
}


def _energy_model_settings(args: argparse.Namespace, dev_id: str,
                           codes: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
    """GET energy-model(type=setting) → {code: 物模型属性}。codes 给定时按 code 过滤以缩小载荷。"""
    query: Dict[str, Any] = {"device_id": dev_id, "type": "setting"}
    if codes:
        query["codes"] = ",".join(codes)
    payload = _api_call(args, "GET", "/v1.0/end-user/energy/devices/model", query=query)
    out: Dict[str, Dict[str, Any]] = {}
    for p in (payload.get("result") or []):
        if isinstance(p, dict) and p.get("code"):
            out[p["code"]] = p
    return out


def _spec_of(prop: Dict[str, Any]) -> Dict[str, Any]:
    return prop.get("dataSpec") or {}


def _validate_setting_value(prop: Dict[str, Any], value: str) -> Optional[str]:
    """对照 live 物模型校验取值；合法返回 None，否则返回中文错误。energy-issue 无校验，本函数即闸门。"""
    spec = _spec_of(prop)
    dtype = (prop.get("dataType") or spec.get("type") or "").lower()
    if dtype == "enum":
        rng = [str(x) for x in (spec.get("range") or [])]
        if rng and value not in rng:
            return f"取值非法，枚举应为 {rng}"
        return None
    if dtype in ("bool", "boolean"):
        if value.lower() not in ("true", "false"):
            return "取值非法，布尔应为 true / false"
        return None
    if dtype == "value":
        try:
            v = float(value)
        except ValueError:
            return "取值非法，应为数值"
        lo = spec.get("min"); hi = spec.get("max")
        try:
            if lo is not None and v < float(lo):
                return f"低于下限 {lo}{(' ' + spec['unit']) if spec.get('unit') else ''}"
            if hi is not None and v > float(hi):
                return f"超过上限 {hi}{(' ' + spec['unit']) if spec.get('unit') else ''}"
        except (TypeError, ValueError):
            pass
        return None
    # hourmin / date / string 等暂不在最小白名单语义内，放行但提示人工核对
    return None


def _discover_controllable(
    args: argparse.Namespace, dev_id: str, energy_dev_id: str = ""
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """客户端侧能力发现（替代未发布的 GET /controllable）：
    energy-model(type=setting) ∩ 内置白名单，范围/枚举取实测，并补当前值。
    返回 (energy_dev_id, controllable[], by_code)。"""
    resolved, _, _ = _resolve_energy_dev_id(args, dev_id, energy_dev_id)
    energy_dev_id = resolved
    codes = list(ENERGY_CONTROL_ALLOWLIST.keys())
    model = _energy_model_settings(args, dev_id, codes)

    # 当前值（仅白名单里且物模型存在的 code）
    present = [c for c in codes if c in model]
    current: Dict[str, Any] = {}
    if present:
        try:
            props = _api_call(
                args, "GET", "/v1.0/end-user/energy/devices/properties",
                query={"device_id": dev_id, "energy_dev_id": energy_dev_id,
                       "codes": ",".join(present)},
            )
            for p in (props.get("result") or []):
                if isinstance(p, dict) and p.get("code"):
                    current[p["code"]] = p.get("value")
        except ConowDeviceError:
            pass  # 当前值非必需

    controllable: List[Dict[str, Any]] = []
    by_code: Dict[str, Dict[str, Any]] = {}
    for code in present:
        prop = model[code]
        spec = _spec_of(prop)
        meta = {
            "code": code,
            "name": ENERGY_CONTROL_ALLOWLIST[code]["cn"],
            "name_en": ENERGY_CONTROL_ALLOWLIST[code]["en"],
            "category": ENERGY_CONTROL_ALLOWLIST[code]["category"],
            "channel": "energy",
            "dataType": prop.get("dataType") or spec.get("type"),
            "enumValues": spec.get("range") if (prop.get("dataType") == "enum") else None,
            "min": spec.get("min"), "max": spec.get("max"),
            "step": spec.get("step"), "scale": spec.get("scale"),
            "unit": spec.get("unit"),
            "current": current.get(code),
            "model_name": prop.get("name"),
        }
        controllable.append(meta)
        by_code[code] = meta
    return energy_dev_id, controllable, by_code


def cmd_control_plan(args: argparse.Namespace) -> None:
    """只读预览：客户端能力发现(energy-model∩白名单) + 读当前值 + 本地校验 → 意图 + plan_hash。绝不写。"""
    dev_id = _dev_id(args)
    items = _normalize_settings(args)

    energy_dev_id, controllable, by_code = _discover_controllable(
        args, dev_id, (args.energy_dev_id or "").strip()
    )
    if not by_code:
        raise ConowDeviceError(
            "该设备无可控属性：最小白名单内的控制项在该机型物模型(type=setting)中均不存在。"
            "普通设备请用 public-control；确属能源设备但需要更多控制项时，请在 skill 白名单中登记。"
        )

    plan_items: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for it in items:
        code, val = it["code"], it["value"]
        meta = by_code.get(code)
        if meta is None:
            errors.append({"code": code, "error": "NOT_CONTROLLABLE",
                           "detail": "不在本技能能源控制白名单内（或该机型不支持）"})
            continue
        validation = _validate_setting_value(
            {"dataType": meta["dataType"],
             "dataSpec": {"type": meta["dataType"], "range": meta.get("enumValues"),
                          "min": meta.get("min"), "max": meta.get("max"), "unit": meta.get("unit")}},
            val,
        )
        plan_items.append({
            "code": code, "name": meta["name"], "channel": "energy",
            "from": meta.get("current"), "to": val, "unit": meta.get("unit"),
            "enum": meta.get("enumValues"), "min": meta.get("min"), "max": meta.get("max"),
            "validation": validation,
        })

    ready = (not errors) and all(p.get("validation") is None for p in plan_items)
    # plan_hash 绑定 dev_id + 已解析 energy_dev_id + settings。仅在 ready 时产出哈希：
    # 校验未通过的 plan 不该被 confirm，置空可避免 AI 照搬 next 文案去 confirm 一笔非法计划。
    ph = _plan_hash(dev_id, energy_dev_id or "", items) if ready else None
    if ready:
        nxt = ("向用户复述每一项 名称/from→to/单位 并取得明确同意后，调 "
               "control-confirm --plan-hash <plan_hash>（参数须与本次完全一致，且带同一 --energy-dev-id）。"
               "注意：底层 energy-issue 无校验，技能已在 confirm 时再校验一次；设备离线时下发可能静默失败。")
    else:
        nxt = ("校验未通过：先修正下列 items 中 validation 非空 / errors 中的取值，再重新 control-plan。"
               "ready=false 时不会产出 plan_hash，请勿调用 control-confirm。")
    out = {
        "phase": "plan",
        "dev_id": dev_id,
        "energy_dev_id": energy_dev_id or None,
        "items": plan_items,
        "errors": errors,
        "plan_hash": ph,
        "idempotency_key": ph,
        "ready": ready,
        "next": nxt,
    }
    if not ready:
        # 让退出码与 ready 一致：confirm 才是写口，plan 未就绪应以非零退出提醒调用方。
        setattr(args, "_plan_not_ready", True)
    _print_json(args, out)


def cmd_control_confirm(args: argparse.Namespace) -> None:
    """唯一写口：校验 plan_hash 一致 + 防御性重校验后，经已发布的 POST /energy/devices/issue 下发。"""
    dev_id = _dev_id(args)
    items = _normalize_settings(args)
    if not args.plan_hash:
        raise ConowDeviceError("control-confirm 需要 --plan-hash（来自 control-plan）")

    # 先解析 energy_dev_id（并做防御性重校验：energy-issue 是无校验裸通道，技能是唯一安全闸门）。
    # 必须在算哈希之前解析，因为 plan_hash 绑定了 energy_dev_id——这样换了 --energy-dev-id 就会
    # 触发 PLAN_HASH_MISMATCH，杜绝「确认的是 A 子设备、下发却落到 B 子设备」。
    energy_dev_id, _, by_code = _discover_controllable(
        args, dev_id, (args.energy_dev_id or "").strip()
    )
    expected = _plan_hash(dev_id, energy_dev_id or "", items)
    if expected != args.plan_hash.strip():
        raise ConowDeviceError(
            "PLAN_HASH_MISMATCH：参数（含 energy_dev_id）与 control-plan 不一致，已拒绝执行。"
            "请重新 control-plan 并向用户复述确认。"
        )
    for it in items:
        meta = by_code.get(it["code"])
        if meta is None:
            raise ConowDeviceError(
                f"DP_NOT_SUPPORTED：{it['code']} 不在本技能能源控制白名单内或该机型不支持，已拒绝下发。"
            )
        err = _validate_setting_value(
            {"dataType": meta["dataType"],
             "dataSpec": {"type": meta["dataType"], "range": meta.get("enumValues"),
                          "min": meta.get("min"), "max": meta.get("max"), "unit": meta.get("unit")}},
            it["value"],
        )
        if err:
            raise ConowDeviceError(f"PARAM_ILLEGAL：{it['code']} {err}，已拒绝下发。")
    if not energy_dev_id:
        raise ConowDeviceError("缺少 energy_dev_id，无法下发；请显式传 --energy-dev-id。")

    body: Dict[str, Any] = {
        "device_id": dev_id,
        "energy_dev_id": energy_dev_id,
        "setting": items,  # energy-issue 的字段名就是 setting
    }
    p = _api_call(args, "POST", "/v1.0/end-user/energy/devices/issue", body=body)
    out = {
        "phase": "confirm",
        "issued": bool(p.get("success") is True),
        "dev_id": dev_id,
        "energy_dev_id": energy_dev_id,
        "settings": items,
        "channel": "energy (POST /energy/devices/issue)",
        "response": p,
        "note": "issue 为 fire-and-forget：success=true 表示已受理下发，未必代表设备已生效；"
                "可隔几秒用 energy-properties 复读确认。",
    }
    _print_json(args, out)


def cmd_energy_controllable(args: argparse.Namespace) -> None:
    """能力发现：客户端侧 energy-model(type=setting) ∩ 技能白名单（替代未发布的 GET /controllable）。"""
    dev_id = _dev_id(args)
    energy_dev_id, controllable, _ = _discover_controllable(
        args, dev_id, (args.energy_dev_id or "").strip()
    )
    _print_json(args, {
        "device_id": dev_id,
        "energy_dev_id": energy_dev_id,
        "controllable": controllable,
        "source": "client-side: energy-model(type=setting) ∩ skill allowlist",
    })


# ---------------------------------------------------------------------------
# 统一高层
# ---------------------------------------------------------------------------


def _detect_is_energy(args: argparse.Namespace) -> bool:
    dev_id = _dev_id(args)
    topo, _ = _safe_energy_get(args, "/v1.0/end-user/energy/devices/topo", dev_id)
    proto, _ = _safe_energy_get(args, "/v1.0/end-user/energy/devices/protocol", dev_id)
    e1 = bool(topo and _infer_energy_from_topo_payload(topo))
    e2 = bool(proto and _infer_energy_from_protocol_payload(proto))
    return e1 or e2


def cmd_device_overview(args: argparse.Namespace) -> None:
    dev_id = _dev_id(args)
    # Fetch topo + protocol at most once and classify in-process, instead of
    # calling _detect_is_energy() (which re-fetches both) and then fetching
    # them again in the energy branch.
    topo = proto = None
    topo_err = proto_err = None
    if args.force_route != "public":
        topo, topo_err = _safe_energy_get(
            args, "/v1.0/end-user/energy/devices/topo", dev_id
        )
        proto, proto_err = _safe_energy_get(
            args, "/v1.0/end-user/energy/devices/protocol", dev_id
        )
    if args.force_route == "energy":
        is_energy = True
    elif args.force_route == "public":
        is_energy = False
    else:  # auto
        is_energy = bool(topo and _infer_energy_from_topo_payload(topo)) or bool(
            proto and _infer_energy_from_protocol_payload(proto)
        )

    if is_energy:
        ind, ind_err = _safe_energy_get(
            args, "/v1.0/end-user/energy/devices/indicators", dev_id
        )
        candidates = _flatten_topo_candidates(topo)
        out = {
            "route": "energy",
            "dev_id": dev_id,
            "topo": topo,
            "protocol": proto,
            "indicators": ind,
            "energy_candidates": candidates,
            "errors": {
                "topo": topo_err,
                "protocol": proto_err,
                "indicators": ind_err,
            },
        }
        try:
            resolved_energy_dev_id, _, _ = _resolve_energy_dev_id(
                args, dev_id, args.energy_dev_id or "", topo
            )
            query: Dict[str, Any] = {
                "device_id": dev_id,
                "energy_dev_id": resolved_energy_dev_id,
            }
            if args.codes:
                query["codes"] = args.codes
            out["resolved_energy_dev_id"] = resolved_energy_dev_id
            out["properties"] = _api_call(
                args, "GET", "/v1.0/end-user/energy/devices/properties", query=query
            )
        except ConowDeviceError as e:
            out["properties_skipped"] = str(e)
        _print_json(args, out)
        return
    det = _api_call(args, "GET", f"/v1.0/end-user/devices/{dev_id}/detail")
    _print_json(
        args,
        {"route": "public", "dev_id": dev_id, "device_detail": det},
    )


def cmd_device_control(args: argparse.Namespace) -> None:
    if not args.properties and not args.setting:
        raise ConowDeviceError("need --properties (public) or --setting+--energy-dev-id (energy)")

    if args.force_route == "public":
        args.properties = args.properties or "{}"
        return cmd_public_control(args)
    if args.force_route == "energy":
        if not args.setting:
            raise ConowDeviceError("energy route needs --setting")
        return cmd_energy_issue(args)

    if _detect_is_energy(args):
        if not args.setting:
            raise ConowDeviceError(
                "设备识别为能源设备：请提供 --setting；若 topo 返回多个候选，还需要 --energy-dev-id"
            )
        return cmd_energy_issue(args)
    if not args.properties:
        raise ConowDeviceError("公版控制需要 --properties JSON，例如 '{\"switch_led\":true}'")
    return cmd_public_control(args)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--api-key", default=os.environ.get("CONOW_API_KEY", ""), help="sk-")
    p.add_argument(
        "--base-url",
        default=os.environ.get("CONOW_BASE_URL"),
        help=(
            "Gateway base URL. If unset, the CLI auto-derives the data-center "
            "URL from the sk- key prefix (sk-AY -> openapi.tuyacn.com, etc). "
            "Set this only if your deployment provides a dedicated gateway URL."
        ),
    )
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.add_argument("--output", choices=("json",), default="json")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Conow 设备统一 CLI")
    _add_common(ap)
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("detect", help="自动检测是否能源设备 (topo + protocol)")
    _add_common(p)
    p.add_argument("--dev-id", default=os.environ.get("CONOW_DEVICE_ID", ""))
    p.set_defaults(func=cmd_detect)

    p = sp.add_parser("device-overview", help="统一总览：能源多接口或公版 detail")
    _add_common(p)
    p.add_argument("--dev-id", default=os.environ.get("CONOW_DEVICE_ID", ""))
    p.add_argument("--energy-dev-id", default="", help="能源子设备 id；多候选时建议显式传入")
    p.add_argument("--codes", default="", help="能源 properties 的 code 过滤，仅能源分支生效")
    p.add_argument(
        "--force-route",
        choices=("auto", "energy", "public"),
        default="auto",
    )
    p.set_defaults(func=cmd_device_overview)

    p = sp.add_parser("device-control", help="统一下发：公版 issue 或能源 issue")
    _add_common(p)
    p.add_argument("--dev-id", default=os.environ.get("CONOW_DEVICE_ID", ""))
    p.add_argument(
        "--force-route",
        choices=("auto", "energy", "public"),
        default="auto",
    )
    p.add_argument(
        "--properties",
        help='公版：JSON 对象，如 {"switch_led":true}',
    )
    p.add_argument("--energy-dev-id", help="能源子设备 id")
    p.add_argument(
        "--setting",
        help="能源物模型设置 JSON 对象或数组",
    )
    p.set_defaults(func=cmd_device_control)

    p = sp.add_parser("public-detail", help="公版单设备详情")
    _add_common(p)
    p.add_argument("--dev-id", default=os.environ.get("CONOW_DEVICE_ID", ""))
    p.set_defaults(func=cmd_public_detail)

    p = sp.add_parser("public-model", help="公版物模型")
    _add_common(p)
    p.add_argument("--dev-id", default=os.environ.get("CONOW_DEVICE_ID", ""))
    p.set_defaults(func=cmd_public_model)

    p = sp.add_parser("public-control", help="公版属性下发")
    _add_common(p)
    p.add_argument("--dev-id", default=os.environ.get("CONOW_DEVICE_ID", ""))
    p.add_argument("--properties", required=True, help="JSON 对象")
    p.set_defaults(func=cmd_public_control)

    p = sp.add_parser("list-homes", help="列出账号下的家庭")
    _add_common(p)
    p.set_defaults(func=cmd_list_homes)

    p = sp.add_parser("resolve-home", help="按家庭名或家庭 ID 解析 home_id")
    _add_common(p)
    p.add_argument("--home-name", default="", help="家庭名称，支持模糊匹配")
    p.add_argument("--home-id", default="", help="家庭 ID")
    p.set_defaults(func=cmd_resolve_home)

    p = sp.add_parser("list-devices", help="列出账号或家庭下的公版设备")
    _add_common(p)
    p.add_argument("--home-id", default="", help="家庭 ID；省略时列出账号下全部设备")
    p.add_argument("--page-no", type=int, default=1, help="家庭设备分页页码")
    p.add_argument("--page-size", type=int, default=200, help="家庭设备分页大小")
    p.add_argument("--summary-only", action="store_true", help="只输出数量和设备 ID")
    p.set_defaults(func=cmd_list_devices)

    p = sp.add_parser("energy-topo", help="能源拓扑")
    _add_common(p)
    p.add_argument("--dev-id", default=os.environ.get("CONOW_DEVICE_ID", ""))
    p.set_defaults(func=cmd_energy_topo)

    p = sp.add_parser("energy-protocol", help="能源协议/厂商")
    _add_common(p)
    p.add_argument("--dev-id", default=os.environ.get("CONOW_DEVICE_ID", ""))
    p.set_defaults(func=cmd_energy_protocol)

    p = sp.add_parser("energy-model", help="能源物模型")
    _add_common(p)
    p.add_argument("--dev-id", default=os.environ.get("CONOW_DEVICE_ID", ""))
    p.add_argument("--type", dest="type_", help="物模型 type 过滤")
    p.add_argument("--codes", help="逗号分隔 code")
    p.set_defaults(func=cmd_energy_model)

    p = sp.add_parser("energy-properties", help="能源设备属性值")
    _add_common(p)
    p.add_argument("--dev-id", default=os.environ.get("CONOW_DEVICE_ID", ""))
    p.add_argument("--energy-dev-id", default="", help="子设备 id；仅单候选时可省略")
    p.add_argument("--codes", help="逗号分隔")
    p.set_defaults(func=cmd_energy_properties)

    p = sp.add_parser("energy-alarms", help="能源故障/告警 (GET)")
    _add_common(p)
    p.add_argument("--dev-id", default=os.environ.get("CONOW_DEVICE_ID", ""))
    p.add_argument("--start-time", required=True, help="毫秒时间戳")
    p.add_argument("--end-time", required=True, help="毫秒时间戳")
    p.add_argument("--page-num", type=int, default=1)
    p.add_argument("--page-size", type=int, default=20)
    p.add_argument("--weight", type=int, default=0)
    p.add_argument("--event-type", default="")
    p.add_argument("--event-status", type=int)
    p.set_defaults(func=cmd_energy_alarms)

    p = sp.add_parser("energy-indicators", help="能源设备指标元数据")
    _add_common(p)
    p.add_argument("--dev-id", default=os.environ.get("CONOW_DEVICE_ID", ""))
    p.set_defaults(func=cmd_energy_indicators)

    p = sp.add_parser("energy-sdata", help="设备指标时序")
    _add_common(p)
    p.add_argument("--dev-id", default=os.environ.get("CONOW_DEVICE_ID", ""))
    p.add_argument("--indicator-code", "--indicator-codes", dest="indicator_code", required=True)
    p.add_argument("--start-time", "--begin-date", dest="start_time", required=True, help="毫秒时间戳")
    p.add_argument("--end-time", "--end-date", dest="end_time", required=True, help="毫秒时间戳")
    p.add_argument("--query-step", dest="query_step", required=True)
    p.add_argument("--query-type", dest="query_type", required=True)
    p.add_argument("--auto", default="")
    p.set_defaults(func=cmd_energy_sdata)

    p = sp.add_parser("energy-issue", help="能源物模型属性下发")
    _add_common(p)
    p.add_argument("--dev-id", default=os.environ.get("CONOW_DEVICE_ID", ""))
    p.add_argument("--energy-dev-id", default="", help="子设备 id；仅单候选时可省略")
    p.add_argument("--setting", required=True, help="JSON 对象或数组")
    p.set_defaults(func=cmd_energy_issue)

    p = sp.add_parser("energy-controllable", help="能力发现：energy-model(type=setting)∩技能白名单；高层请用 control-plan")
    _add_common(p)
    p.add_argument("--dev-id", default=os.environ.get("CONOW_DEVICE_ID", ""))
    p.add_argument("--energy-dev-id", default="", help="能源子设备 id；多候选时建议显式传入")
    p.set_defaults(func=cmd_energy_controllable)

    p = sp.add_parser(
        "control-plan",
        help="能源设备控制·第1步：只读预览（能力发现+当前值+校验），产出 plan_hash，绝不下发",
    )
    _add_common(p)
    p.add_argument("--dev-id", default=os.environ.get("CONOW_DEVICE_ID", ""))
    p.add_argument("--energy-dev-id", default="", help="能源子设备 id；多候选时建议显式传入")
    p.add_argument("--properties", help='JSON 对象，如 {"inverter_work_mode_setting":"3"}')
    p.add_argument("--settings", help="JSON 对象或数组 [{code,value}]（与 --properties 二选一）")
    p.set_defaults(func=cmd_control_plan)

    p = sp.add_parser(
        "control-confirm",
        help="能源设备控制·第2步：校验 --plan-hash 与参数一致后才经 energy-issue 下发（唯一写口）",
    )
    _add_common(p)
    p.add_argument("--dev-id", default=os.environ.get("CONOW_DEVICE_ID", ""))
    p.add_argument("--energy-dev-id", default="", help="能源子设备 id")
    p.add_argument("--properties", help="JSON 对象（须与 control-plan 完全一致）")
    p.add_argument("--settings", help="JSON 对象或数组（须与 control-plan 完全一致）")
    p.add_argument("--plan-hash", required=True, help="control-plan 返回的 plan_hash")
    p.set_defaults(func=cmd_control_confirm)

    ns = ap.parse_args(argv)
    _resolve_base_url(ns)
    try:
        ns.func(ns)
    except ConowDeviceError as e:
        out = {"success": False, "error": str(e)}
        _print_json(ns, out)
        return 1

    # Top-level gateway business failure (HTTP 200 with success:false, e.g. the
    # 1108 "uri path invalid", a 1106 access error, or a resolve-home not-found)
    # must surface as a non-zero exit while the full payload is still printed.
    # device-overview / detect print objects keyed by route/is_energy_device and
    # deliberately catch per-branch 1108 into a nested `errors` map, so they have
    # no top-level `success` key and correctly stay at exit 0.
    last = getattr(ns, "_last_output", None)
    if isinstance(last, dict) and last.get("success") is False:
        hint = _friendly_gateway_hint(last)
        if hint:
            sys.stderr.write(
                f"error: {last.get('code')} {last.get('msg') or ''}: {hint}\n"
            )
        return 1
    # control-plan with ready=false: exit non-zero so the caller's exit code
    # agrees with `ready` and an agent does not treat a failed plan as runnable.
    if getattr(ns, "_plan_not_ready", False):
        sys.stderr.write(
            "error: control-plan ready=false — fix the flagged items and re-run "
            "control-plan; do NOT call control-confirm.\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
