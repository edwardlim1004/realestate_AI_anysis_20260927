"""Fail-closed bridge from the isolated liquidity module to the core monitor."""
from __future__ import annotations

import json
import math
from pathlib import Path


def _waiting_tile(status: str, module: dict | None = None) -> dict:
    metadata = module or {
        "mode": status,
        "validationPassed": False,
        "passedGates": 0,
        "totalGates": 9,
        "summaryUrl": "risk-data/liquidity/summary.json",
        "validationUrl": "risk-data/liquidity/validation.json",
        "backtestUrl": "risk-data/liquidity/backtest.json",
        "rawUrl": "risk-data/liquidity/raw.csv",
        "revisionsUrl": "risk-data/liquidity/revision_history.csv",
    }
    return {
        "label": "유동성",
        "score": None,
        "status": status,
        "value": None,
        "meaning": "Marshall K·실질 M2 갭·유동성 폭을 독립 모듈에서 계산하며, 검증 중에는 종합점수와 격리합니다.",
        "calculation": "50% Marshall K 갭 + 30% 실질 M2 갭 + 20% M2·Lf·L 실질증가율 폭; one-sided HP와 expanding 백분위",
        "literature": ["BOK_ECOS_LIQUIDITY", "BOK_LIQUIDITY_GUIDE", "RAVN_UHLIG_2002", "BIS_HP_GUIDE"],
        "limitations": "SHADOW 상태입니다. 표본외 백테스트·빈티지 안정성·사람 검토와 승인 지문 일치 전에는 숫자를 공개하거나 종합점수에 넣지 않습니다.",
        "module": metadata,
    }


def load_for_core(root: Path) -> dict:
    summary_path = root / "risk-data" / "liquidity" / "summary.json"
    if not summary_path.exists():
        return {"active": False, "history": {}, "tile": _waiting_tile("SHADOW_WAITING_DATA")}
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {"active": False, "history": {}, "tile": _waiting_tile("SHADOW_INVALID_OUTPUT")}

    validation = summary.get("validation", {})
    activation = summary.get("activation", {})
    metadata = {
        "mode": summary.get("mode", "SHADOW_INVALID_OUTPUT"),
        "validationPassed": validation.get("passed") is True,
        "passedGates": validation.get("passedGateCount", 0),
        "totalGates": validation.get("totalGateCount", 0),
        "latestPeriod": summary.get("latestPeriod"),
        "summaryUrl": "risk-data/liquidity/summary.json",
        "validationUrl": "risk-data/liquidity/validation.json",
        "backtestUrl": "risk-data/liquidity/backtest.json",
        "rawUrl": "risk-data/liquidity/raw.csv",
        "revisionsUrl": "risk-data/liquidity/revision_history.csv",
    }
    approved = activation.get("approvedValidationFingerprint")
    current_fingerprint = validation.get("validationFingerprint")
    active_contract = (
        summary.get("schemaVersion") == "1.0"
        and summary.get("mode") == "ACTIVE"
        and validation.get("passed") is True
        and activation.get("enabled") is True
        and activation.get("fingerprintMatched") is True
        and isinstance(approved, str)
        and approved == current_fingerprint
    )
    score = summary.get("publicScore")
    if not isinstance(score, (int, float)) or isinstance(score, bool) or not math.isfinite(score) or not 0 <= score <= 100:
        active_contract = False

    history = {}
    if active_contract:
        for row in summary.get("history", []):
            value = row.get("score")
            period = row.get("period")
            if isinstance(period, str) and isinstance(value, (int, float)) and math.isfinite(value) and 0 <= value <= 100:
                history[period] = round(float(value), 2)
        if not history or summary.get("latestPeriod") not in history:
            active_contract = False

    if not active_contract:
        status = summary.get("mode", "SHADOW_INVALID_OUTPUT")
        if status == "ACTIVE":
            status = "SHADOW_CONTRACT_REJECTED"
        return {"active": False, "history": {}, "tile": _waiting_tile(status, metadata)}

    current = summary.get("current", {})
    values = {}
    labels = {
        "marshallKGap": "MARSHALL_K_GAP",
        "realM2Gap": "REAL_M2_GAP",
        "breadth": "LIQUIDITY_BREADTH",
    }
    for name, point in current.get("components", {}).items():
        if name not in labels:
            continue
        values[labels[name]] = {
            "period": point.get("period"),
            "value": point.get("value"),
            "score": point.get("score"),
            "sourceKey": f"ECOS|KOR_LIQUIDITY|{labels[name]}|{point.get('period', '')}",
        }
    tile = _waiting_tile("OK", metadata)
    tile.update({
        "score": round(float(score), 2),
        "status": "OK",
        "value": values,
        "limitations": "전국 통화지표이며 서울 주택시장 전용 지표가 아닙니다. 끝점 HP 갭은 신규 관측과 공식수정치에 따라 바뀔 수 있습니다.",
    })
    return {"active": True, "history": history, "tile": tile}

