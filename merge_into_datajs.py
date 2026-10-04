"""
molit_fetched.json (fetch_molit.py의 결과) 를 기존 data.js 구조에 병합해서
새 data.js 를 만드는 스크립트.

사용법:
  python merge_into_datajs.py

전제:
  - 이 폴더에 기존 data.js 사본이 있어야 함 (realestate-dashboard/data.js 복사해서 넣기)
  - fetch_molit.py 실행 결과인 molit_fetched.json 이 같은 폴더에 있어야 함

동작:
  - 실거래 API로 얻은 history/avg84/avgPrice/gapPct/fairSeries/trades 는 실데이터로 교체
  - trendN(모멘텀), riskN(리스크), jeonseRate(전세가율), zone, topApt 등은
    기존 값을 그대로 유지 (전세가율/리스크는 별도 API 연동 전까지 수동 관리)
  - valuation/liquidity 점수는 API 데이터 기준으로 재계산, momentum/risk/jeonse 점수는 기존 방식 유지
  - composite/signal 은 5개 점수를 가중합산해 재계산
"""

import json
import os
import re

WEIGHTS = {"valuation": 0.35, "momentum": 0.15, "liquidity": 0.15, "risk": 0.20, "jeonse": 0.15}


def load_existing_data_js(path="data.js"):
    text = open(path, encoding="utf-8").read()
    start = text.index("=") + 1
    end = text.rindex(";")
    return json.loads(text[start:end])


def percentile_scores(values, higher_is_better=True):
    order = sorted(range(len(values)), key=lambda i: values[i])
    n = len(values)
    scores = [0] * n
    for rank, idx in enumerate(order):
        pct = rank / (n - 1) * 100 if n > 1 else 50
        scores[idx] = pct if higher_is_better else 100 - pct
    return scores


def main():
    existing = load_existing_data_js("data.js")
    fetched = json.load(open("molit_fetched.json", encoding="utf-8"))

    jeonse_fetched = {}
    if os.path.exists("jeonse_fetched.json"):
        jeonse_fetched = json.load(open("jeonse_fetched.json", encoding="utf-8"))
        print(f"전세가율 실데이터 {len(jeonse_fetched)}개 지역 로드됨")
    else:
        print("[안내] jeonse_fetched.json 이 없어 전세가율은 기존 값을 유지합니다.")

    region_by_name = {r["name"]: r for r in existing["regions"]}

    # 1) 실데이터 필드 갱신 (매매 시세)
    for name, d in fetched["regions"].items():
        if name not in region_by_name:
            print(f"[경고] data.js에 없는 지역명: {name} (건너뜀)")
            continue
        r = region_by_name[name]
        r["history"] = d["history"]
        r["fairSeries"] = d["fairSeries"]
        r["fairValueNow"] = d["fairValueNow"]
        r["gapPct"] = d["gapPct"]
        r["avg84"] = d["avg84"]
        r["avgPrice"] = d["avgPrice"]
        r["trades"] = d["trades"]
        r["scores"]["valuation"] = d["scores_partial"]["valuation"]
        r["scores"]["liquidity"] = d["scores_partial"]["liquidity"]

    # 1-b) 전세가율 실데이터 갱신 (표본이 있는 지역만 교체, 나머지는 기존 값 유지)
    for name, d in jeonse_fetched.items():
        if name in region_by_name:
            region_by_name[name]["jeonseRate"] = d["jeonseRate"]

    existing["months"] = fetched["months"]

    # 2) 전세가율 점수는 56개 지역 전체 기준 백분위로 재계산 (실데이터+유지값 혼합 기준)
    jeonse_vals = [r["jeonseRate"] for r in existing["regions"]]
    jeonse_scores = percentile_scores(jeonse_vals, higher_is_better=True)
    for i, r in enumerate(existing["regions"]):
        r["scores"]["jeonse"] = round(jeonse_scores[i], 1)

    # 3) 리스크/모멘텀 점수는 기존 값 유지, composite/signal만 재계산
    for r in existing["regions"]:
        s = r["scores"]
        composite = (
            s["valuation"] * WEIGHTS["valuation"]
            + s["momentum"] * WEIGHTS["momentum"]
            + s["liquidity"] * WEIGHTS["liquidity"]
            + s["risk"] * WEIGHTS["risk"]
            + s["jeonse"] * WEIGHTS["jeonse"]
        )
        s["composite"] = round(composite, 1)
        if composite >= 62:
            r["signal"], r["signalText"] = "buy", "🟢 매수고려"
        elif composite >= 42:
            r["signal"], r["signalText"] = "warning", "🟡 주의"
        else:
            r["signal"], r["signalText"] = "watch", "🔴 관망"

    with open("data.js", "w", encoding="utf-8") as f:
        f.write("const ENHANCED_DATA = ")
        json.dump(existing, f, ensure_ascii=False)
        f.write(";\n")

    print("완료: data.js 가 실거래 데이터 기준으로 갱신되었습니다.")
    print("이 data.js 를 GitHub 저장소의 기존 data.js에 덮어쓰기(commit) 하면 사이트에 즉시 반영됩니다.")


if __name__ == "__main__":
    main()
