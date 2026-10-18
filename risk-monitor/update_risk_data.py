#!/usr/bin/env python3
"""Build an auditable housing-risk dataset for the static GitHub Pages site.

The script downloads only public OECD/BIS data, upserts observations by a
stable key, records revisions, and writes both machine-readable JSON and a JS
wrapper for the buildless dashboard. API keys are neither required nor stored.
"""
from __future__ import annotations

import csv
import io
import json
import math
import os
import tempfile
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "risk-data"
RAW = OUT / "risk_raw.csv"
REVISIONS = OUT / "revision_history.csv"
SUMMARY_JSON = OUT / "risk_summary.json"
SUMMARY_JS = ROOT / "risk-data.js"
SOURCE_REGISTRY = OUT / "source_registry.csv"

COUNTRIES = {"KOR": "한국", "USA": "미국", "JPN": "일본", "GBR": "영국", "CHN": "중국"}
OECD_CODES = set(COUNTRIES)
BIS_CODES = {"KOR": "KR", "USA": "US", "JPN": "JP", "GBR": "GB", "CHN": "CN"}

OECD_URL = (
    "https://sdmx.oecd.org/public/rest/data/"
    "OECD.ECO.MPD,DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES/all"
)
BIS_CREDIT_URL = "https://data.bis.org/static/bulk/WS_CREDIT_GAP_csv_flat.zip"
BIS_DSR_URL = "https://data.bis.org/static/bulk/WS_DSR_csv_flat.zip"

RAW_FIELDS = [
    "Provider", "Dataset", "Series_ID", "Indicator", "Country", "Frequency",
    "Period", "Value", "Unit", "Source_Updated", "Retrieved_UTC", "Source_URL",
    "Observation_Key", "Data_Status",
]
REVISION_FIELDS = [
    "Change_ID", "Observation_Key", "Changed_UTC", "Old_Value", "New_Value",
    "Provider", "Series_ID", "Period", "Source_URL",
]

SOURCE_ROWS = [
    {
        "ID": "OECD_AHP", "Type": "official_data", "Use": "PIR, PTR, real house-price index",
        "Reference": "OECD Analytical House Prices Indicators, DSD_AN_HOUSE_PRICES",
        "Exact_Location": "Measures HPI_YDH_AVG, HPI_RPI_AVG and RHP; quarterly observations",
        "URL": "https://data-explorer.oecd.org/vis?df[ds]=DisseminateFinalDMZ&df[id]=DSD_AN_HOUSE_PRICES%40DF_HOUSE_PRICES",
    },
    {
        "ID": "BIS_CREDIT_GAP", "Type": "official_data", "Use": "credit-to-GDP gap",
        "Reference": "BIS credit-to-GDP gaps",
        "Exact_Location": "Private non-financial sector; all lenders; actual minus HP trend",
        "URL": "https://data.bis.org/topics/CREDIT_GAPS",
    },
    {
        "ID": "BIS_DSR", "Type": "official_data", "Use": "household debt-service ratio",
        "Reference": "BIS debt service ratios",
        "Exact_Location": "Households and NPISHs; quarterly; per cent",
        "URL": "https://data.bis.org/topics/DSR",
    },
    {
        "ID": "BORIO_LOWE_2002", "Type": "paper", "Use": "credit and asset-price early warning",
        "Reference": "Borio & Lowe (2002), Asset prices, financial and monetary stability",
        "Exact_Location": "BIS Working Papers No 114, especially sections III-IV",
        "URL": "https://www.bis.org/publ/work114.htm",
    },
    {
        "ID": "HIMMELBERG_2005", "Type": "paper", "Use": "user-cost interpretation of price/rent",
        "Reference": "Himmelberg, Mayer & Sinai (2005), Assessing High House Prices",
        "Exact_Location": "Journal of Economic Perspectives 19(4), pp. 74-76",
        "URL": "https://www.aeaweb.org/articles?id=10.1257/089533005775196769",
    },
    {
        "ID": "PSY_2015", "Type": "paper", "Use": "GSADF/BSADF bubble dating",
        "Reference": "Phillips, Shi & Yu (2015), Testing for Multiple Bubbles",
        "Exact_Location": "International Economic Review 56(4); GSADF and BSADF procedures",
        "URL": "https://onlinelibrary.wiley.com/doi/10.1111/iere.12132",
    },
    {
        "ID": "DALLAS_FED_WP165", "Type": "paper", "Use": "housing exuberance implementation",
        "Reference": "Mack, Martinez-Garcia & Huber, Episodes of Exuberance in Housing Markets",
        "Exact_Location": "Dallas Fed Globalization and Monetary Policy Institute WP 165, section 3",
        "URL": "https://www.dallasfed.org/~/media/documents/research/international/wpapers/2013/0165.pdf",
    },
    {
        "ID": "IMF_HAR_2019", "Type": "report", "Use": "House Prices at Risk",
        "Reference": "IMF Global Financial Stability Report, April 2019, chapter 2",
        "Exact_Location": "Downside Risks to House Prices, quantile-regression framework",
        "URL": "https://www.imf.org/en/Publications/GFSR/Issues/2019/03/27/Global-Financial-Stability-Report-April-2019",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def code(value: str) -> str:
    return (value or "").split(":", 1)[0].strip()


def get_bytes(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "EdwardHousingRiskMonitor/1.0", "Accept": "text/csv,*/*"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def csv_text(rows: list[dict], fields: list[str]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=fields,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def write_if_changed(path: Path, text: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text(encoding="utf-8-sig") if path.exists() else None
    if old == text:
        return False
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return True


def fetch_oecd(start_period: str) -> list[dict]:
    query = urllib.parse.urlencode({
        "startPeriod": start_period,
        "dimensionAtObservation": "AllDimensions",
        "format": "csvfilewithlabels",
    })
    url = f"{OECD_URL}?{query}"
    rows = csv.DictReader(io.StringIO(get_bytes(url).decode("utf-8-sig")))
    mapping = {
        "HPI_YDH_AVG": ("PIR_LTA", "price-to-income, % of long-term average"),
        "HPI_RPI_AVG": ("PTR_LTA", "price-to-rent, % of long-term average"),
        "RHP": ("REAL_HPI", "real house-price index"),
    }
    retrieved = utc_now()
    result = []
    for row in rows:
        if row.get("REF_AREA") not in OECD_CODES or row.get("FREQ") != "Q":
            continue
        measure = row.get("MEASURE", "")
        if measure not in mapping:
            continue
        try:
            value = float(row["OBS_VALUE"])
        except (KeyError, TypeError, ValueError):
            continue
        indicator, unit = mapping[measure]
        country, period = row["REF_AREA"], row["TIME_PERIOD"]
        key = f"OECD|AHP|{measure}|{country}|Q|{period}"
        result.append({
            "Provider": "OECD", "Dataset": "Analytical house prices", "Series_ID": measure,
            "Indicator": indicator, "Country": country, "Frequency": "Q", "Period": period,
            "Value": value, "Unit": unit, "Source_Updated": "", "Retrieved_UTC": retrieved,
            "Source_URL": OECD_URL, "Observation_Key": key, "Data_Status": "Official_API",
        })
    return result


def zip_rows(url: str) -> csv.DictReader:
    archive = zipfile.ZipFile(io.BytesIO(get_bytes(url)))
    names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
    if not names:
        raise RuntimeError(f"CSV missing in {url}")
    return csv.DictReader(io.TextIOWrapper(archive.open(names[0]), encoding="utf-8-sig", newline=""))


def fetch_bis_credit(start_period: str) -> list[dict]:
    reverse = {value: key for key, value in BIS_CODES.items()}
    retrieved, result = utc_now(), []
    for row in zip_rows(BIS_CREDIT_URL):
        bis_country = code(row.get("BORROWERS_CTY:Borrowers' country", ""))
        if bis_country not in reverse:
            continue
        if code(row.get("FREQ:Frequency", "")) != "Q":
            continue
        if code(row.get("TC_BORROWERS:Borrowing sector", "")) != "P":
            continue
        if code(row.get("TC_LENDERS:Lending sector", "")) != "A":
            continue
        if code(row.get("CG_DTYPE:Credit gap data type", "")) != "C":
            continue
        period = row.get("TIME_PERIOD:Time period or range", "")
        if period < start_period:
            continue
        try:
            value = float(row["OBS_VALUE:Observation Value"])
        except (KeyError, TypeError, ValueError):
            continue
        country = reverse[bis_country]
        series = f"Q.{bis_country}.P.A.C"
        result.append({
            "Provider": "BIS", "Dataset": "Credit-to-GDP gaps", "Series_ID": series,
            "Indicator": "CREDIT_GAP_PP", "Country": country, "Frequency": "Q", "Period": period,
            "Value": value, "Unit": "percentage points of GDP", "Source_Updated": "",
            "Retrieved_UTC": retrieved, "Source_URL": BIS_CREDIT_URL,
            "Observation_Key": f"BIS|CREDIT_GAP|{series}|{period}", "Data_Status": "Official_Bulk_CSV",
        })
    return result


def fetch_bis_dsr(start_period: str) -> list[dict]:
    reverse = {value: key for key, value in BIS_CODES.items()}
    retrieved, result = utc_now(), []
    for row in zip_rows(BIS_DSR_URL):
        bis_country = code(row.get("BORROWERS_CTY:Borrowers' country", ""))
        if bis_country not in reverse:
            continue
        if code(row.get("FREQ:Frequency", "")) != "Q":
            continue
        if code(row.get("DSR_BORROWERS:Borrowers", "")) != "H":
            continue
        period = row.get("TIME_PERIOD:Time period or range", "")
        if period < start_period:
            continue
        try:
            value = float(row["OBS_VALUE:Observation Value"])
        except (KeyError, TypeError, ValueError):
            continue
        country = reverse[bis_country]
        series = f"Q.{bis_country}.H"
        result.append({
            "Provider": "BIS", "Dataset": "Debt service ratios", "Series_ID": series,
            "Indicator": "DSR_PCT", "Country": country, "Frequency": "Q", "Period": period,
            "Value": value, "Unit": "per cent", "Source_Updated": "", "Retrieved_UTC": retrieved,
            "Source_URL": BIS_DSR_URL, "Observation_Key": f"BIS|DSR|{series}|{period}",
            "Data_Status": "Official_Bulk_CSV",
        })
    return result


def upsert(old_rows: list[dict], incoming: list[dict]) -> tuple[list[dict], list[dict], int]:
    current = {row["Observation_Key"]: row for row in old_rows if row.get("Observation_Key")}
    revisions = []
    changed = 0
    stamp = utc_now()
    for row in incoming:
        row = {field: row.get(field, "") for field in RAW_FIELDS}
        row["Value"] = str(row["Value"])
        key = row["Observation_Key"]
        before = current.get(key)
        if before is None:
            current[key] = row
            changed += 1
            continue
        try:
            same_value = math.isclose(float(before["Value"]), float(row["Value"]), rel_tol=0, abs_tol=1e-10)
        except (TypeError, ValueError):
            same_value = before.get("Value") == row.get("Value")
        if same_value and before.get("Unit") == row.get("Unit"):
            continue
        revisions.append({
            "Change_ID": f"{stamp}|{key}", "Observation_Key": key, "Changed_UTC": stamp,
            "Old_Value": before.get("Value", ""), "New_Value": row.get("Value", ""),
            "Provider": row["Provider"], "Series_ID": row["Series_ID"], "Period": row["Period"],
            "Source_URL": row["Source_URL"],
        })
        current[key] = row
        changed += 1
    ordered = sorted(current.values(), key=lambda r: (r["Country"], r["Indicator"], r["Period"], r["Series_ID"]))
    return ordered, revisions, changed


def percentile(history: list[float], value: float, min_periods: int = 20) -> float | None:
    if len(history) < min_periods:
        return None
    return round(sum(item <= value for item in history) / len(history) * 100, 1)


def period_key(period: str) -> tuple[int, int]:
    try:
        year, quarter = period.split("-Q")
        return int(year), int(quarter)
    except (ValueError, AttributeError):
        return 0, 0


def state_for(score: float | None) -> str:
    if score is None:
        return "N/A"
    if score >= 80:
        return "RED"
    if score >= 65:
        return "AMBER"
    if score >= 50:
        return "WATCH"
    return "GREEN"


def build_summary(rows: list[dict]) -> dict:
    values = defaultdict(list)
    raw_lookup = {}
    for row in rows:
        try:
            value = float(row["Value"])
        except (TypeError, ValueError):
            continue
        key = (row["Country"], row["Indicator"])
        values[key].append((row["Period"], value, row["Observation_Key"] ))
        raw_lookup[row["Observation_Key"]] = row

    scored = defaultdict(dict)
    metric_values = defaultdict(dict)
    for (country, indicator), observations in values.items():
        observations.sort(key=lambda item: period_key(item[0]))
        base_history = []
        level_by_period = {period: value for period, value, _ in observations}
        for index, (period, value, source_key) in enumerate(observations):
            metric = value
            if indicator == "REAL_HPI":
                previous = observations[index - 4][1] if index >= 4 else None
                metric = (value / previous - 1) * 100 if previous else None
            if metric is None:
                continue
            base_history.append(metric)
            risk_score = percentile(base_history, metric)
            metric_name = "REAL_HPI_YOY" if indicator == "REAL_HPI" else indicator
            scored[(country, metric_name)][period] = {
                "score": risk_score, "value": round(metric, 4), "sourceKey": source_key,
            }
            metric_values[(country, metric_name)][period] = metric

    results = {}
    for country in COUNTRIES:
        country_periods = sorted(
            {period for (cty, _), series in scored.items() if cty == country for period in series},
            key=period_key,
        )
        latest_seen = {}
        history = []
        for period in country_periods:
            for metric in ("PIR_LTA", "PTR_LTA", "CREDIT_GAP_PP", "DSR_PCT", "REAL_HPI_YOY"):
                point = scored.get((country, metric), {}).get(period)
                if point and point["score"] is not None:
                    latest_seen[metric] = {**point, "period": period}
            valuation_items = [latest_seen.get("PIR_LTA"), latest_seen.get("PTR_LTA")]
            credit_items = [latest_seen.get("CREDIT_GAP_PP"), latest_seen.get("DSR_PCT")]
            valuation_scores = [item["score"] for item in valuation_items if item]
            credit_scores = [item["score"] for item in credit_items if item]
            valuation = round(sum(valuation_scores) / len(valuation_scores), 1) if valuation_scores else None
            credit = round(sum(credit_scores) / len(credit_scores), 1) if credit_scores else None
            momentum = latest_seen.get("REAL_HPI_YOY", {}).get("score")
            pillars = [item for item in (valuation, credit, momentum) if item is not None]
            composite = round(sum(pillars) / len(pillars), 1) if len(pillars) >= 3 else None
            if composite is not None:
                history.append({
                    "period": period, "score": composite, "state": state_for(composite),
                    "valuation": valuation, "credit": credit, "momentum": momentum,
                })

        current = history[-1] if history else {
            "period": "", "score": None, "state": "N/A", "valuation": None,
            "credit": None, "momentum": None,
        }
        def latest(metric: str):
            return latest_seen.get(metric)

        tiles = {
            "valuation": {
                "label": "가격평가", "score": current["valuation"], "status": "OK" if current["valuation"] is not None else "WAITING_DATA",
                "value": {
                    "PIR_LTA": latest("PIR_LTA"), "PTR_LTA": latest("PTR_LTA"),
                },
                "meaning": "OECD PIR·PTR의 각 국가 자체 역사분포상 위치. 높을수록 과거보다 고평가 신호가 강합니다.",
                "calculation": "PIR와 PTR 각각의 expanding percentile을 계산한 뒤 동일가중 평균",
                "literature": ["OECD_AHP", "HIMMELBERG_2005"],
                "limitations": "국가 평균이며 서울만의 고평가 수준은 아닙니다. 점수는 하락확률이 아닙니다.",
            },
            "credit": {
                "label": "신용취약성", "score": current["credit"], "status": "OK" if current["credit"] is not None else "WAITING_DATA",
                "value": {
                    "CREDIT_GAP_PP": latest("CREDIT_GAP_PP"), "DSR_PCT": latest("DSR_PCT"),
                },
                "meaning": "신용/GDP 갭과 가계 DSR이 해당 국가 과거보다 높은지 보여줍니다.",
                "calculation": "BIS 신용갭·가계 DSR expanding percentile의 동일가중 평균",
                "literature": ["BIS_CREDIT_GAP", "BIS_DSR", "BORIO_LOWE_2002"],
                "limitations": "분기·국가 자료이며 발표시차가 있습니다. 바젤 규제 임계값을 붕괴확률로 해석하지 않습니다.",
            },
            "momentum": {
                "label": "실질가격 모멘텀", "score": current["momentum"], "status": "OK" if current["momentum"] is not None else "WAITING_DATA",
                "value": {"REAL_HPI_YOY": latest("REAL_HPI_YOY")},
                "meaning": "실질 주택가격 전년동기비가 해당 국가의 과거분포에서 얼마나 높은지 나타냅니다.",
                "calculation": "100 × (실질주택가격지수_t / 지수_t-4 - 1), expanding percentile",
                "literature": ["OECD_AHP"],
                "limitations": "전국 평균이며 거래량·서울 아파트 구성효과를 직접 반영하지 않습니다.",
            },
            "liquidity": {
                "label": "유동성", "score": None, "status": "WAITING_DATA", "value": None,
                "meaning": "Marshall K와 실질 원화 M2 갭을 별도 축으로 연결할 자리입니다.",
                "calculation": "ECOS 원자료 연결 후 월간 HP λ=129,600, 끝점 잠정치 표시",
                "literature": [],
                "limitations": "현재 공개 사이트에는 ECOS 장기 원자료가 없어 종합점수에서 제외했습니다.",
            },
            "gsadf": {
                "label": "GSADF 버블검정", "score": None, "status": "WAITING_DATA", "value": None,
                "meaning": "실질가격·PIR·PTR가 정상적 상승과 다른 폭발적 상태인지 통계적으로 검사합니다.",
                "calculation": "PSY GSADF/BSADF; 표본별 임계값 2,000회 Monte Carlo; 최소 지속기간 적용",
                "literature": ["PSY_2015", "DALLAS_FED_WP165"],
                "limitations": "엄격 임계값 계산 전에는 ON/OFF 경보를 내지 않습니다.",
            },
            "har": {
                "label": "HaR 하방위험", "score": None, "status": "WAITING_DATA", "value": None,
                "meaning": "향후 1~3년 실질주택가격의 하방 5% 분위수를 추정하는 모듈입니다.",
                "calculation": "IMF House Prices at Risk 방식의 분위수회귀와 표본외 검증",
                "literature": ["IMF_HAR_2019"],
                "limitations": "충분한 설명변수와 약 60개 분기 검증 전에는 하락률을 표시하지 않습니다.",
            },
        }
        results[country] = {
            "name": COUNTRIES[country],
            "composite": {
                "score": current["score"], "state": current["state"], "coverage": "3/4" if current["score"] is not None else "<3/4",
                "latestPeriod": current["period"], "meaning": "유효한 가격평가·신용·모멘텀 역사백분위의 동일가중 평균",
                "warning": "0~100은 위기 또는 폭락 확률이 아니라 해당 국가의 과거 관측치 대비 위험 백분위입니다.",
            },
            "tiles": tiles,
            "history": history,
        }

    registry = {row["ID"]: row for row in SOURCE_ROWS}
    crises = [
        {"start": "1997-Q3", "end": "1999-Q1", "label": "아시아 외환위기", "scope": "KOR", "source": "https://www.imf.org/external/pubs/ft/fandd/1998/06/imfstaff.htm"},
        {"start": "2007-Q3", "end": "2009-Q2", "label": "글로벌 금융위기", "scope": "GLOBAL", "source": "https://www.federalreservehistory.org/essays/great-recession-and-its-aftermath"},
        {"start": "2020-Q1", "end": "2020-Q2", "label": "COVID-19 충격", "scope": "GLOBAL", "source": "https://www.imf.org/en/Publications/WEO/Issues/2020/06/24/WEOUpdateJune2020"},
    ]
    latest_raw_period = max((row["Period"] for row in rows), key=period_key, default="")
    return {
        "schemaVersion": "1.0", "generatedAtUTC": utc_now(), "latestRawPeriod": latest_raw_period,
        "method": {
            "normalization": "expanding historical percentile, minimum 20 quarters",
            "composite": "equal-weight mean of available valuation, credit, liquidity and momentum pillars; minimum 3 pillars",
            "bands": {"GREEN": "0-49.9", "WATCH": "50-64.9", "AMBER": "65-79.9", "RED": "80-100"},
            "note": "Operating display bands, not paper-defined crash probabilities.",
        },
        "countries": results, "crisisEvents": crises, "sources": registry,
        "downloads": {
            "raw": "risk-data/risk_raw.csv", "revisions": "risk-data/revision_history.csv",
            "registry": "risk-data/source_registry.csv",
        },
    }


def main() -> int:
    old = read_csv(RAW)
    if old:
        newest_year = max((period_key(row.get("Period", ""))[0] for row in old), default=2020)
        start_year = max(1998, newest_year - 3)
    else:
        start_year = 1998
    start_period = f"{start_year}-Q1"
    incoming = []
    errors = []
    for name, fetcher in (
        ("OECD", fetch_oecd), ("BIS_CREDIT", fetch_bis_credit), ("BIS_DSR", fetch_bis_dsr),
    ):
        try:
            rows = fetcher(start_period)
            if not rows:
                raise RuntimeError("no target observations")
            incoming.extend(rows)
            print(f"{name}: OK {len(rows)}")
        except Exception as exc:  # retain prior official observations on a provider outage
            errors.append(f"{name}: {type(exc).__name__}: {str(exc)[:160]}")
            print(f"{name}: REVIEW {type(exc).__name__}")
    if not incoming and not old:
        raise SystemExit("No official observations available: " + " | ".join(errors))

    merged, revisions, changed_count = upsert(old, incoming)
    existing_revisions = read_csv(REVISIONS)
    all_revisions = existing_revisions + revisions
    if (
        old and changed_count == 0 and SUMMARY_JSON.exists() and SUMMARY_JS.exists()
        and SOURCE_REGISTRY.exists() and not errors
    ):
        print(f"RESULT: NO_CHANGE; observations={len(merged)}; revisions={len(all_revisions)}")
        return 0
    summary = build_summary(merged)
    summary["update"] = {
        "startPeriodRequested": start_period,
        "insertedOrRevised": changed_count,
        "providerWarnings": errors,
        "policy": "No file rewrite when official values and generated outputs are unchanged.",
    }

    changed = False
    changed |= write_if_changed(RAW, csv_text(merged, RAW_FIELDS))
    changed |= write_if_changed(REVISIONS, csv_text(all_revisions, REVISION_FIELDS))
    registry_fields = ["ID", "Type", "Use", "Reference", "Exact_Location", "URL"]
    changed |= write_if_changed(SOURCE_REGISTRY, csv_text(SOURCE_ROWS, registry_fields))

    json_text = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    js_text = "const RISK_MONITOR_DATA = " + json.dumps(summary, ensure_ascii=False, separators=(",", ":")) + ";\n"
    changed |= write_if_changed(SUMMARY_JSON, json_text)
    changed |= write_if_changed(SUMMARY_JS, js_text)
    print(f"RESULT: {'CHANGED' if changed else 'NO_CHANGE'}; observations={len(merged)}; revisions={len(all_revisions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
