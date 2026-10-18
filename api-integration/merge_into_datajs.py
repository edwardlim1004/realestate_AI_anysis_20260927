"""
molit_fetched.json / jeonse_fetched.json 을 기존 data.js 구조에 병합해서
새 data.js 를 만드는 스크립트.

사용법:
  python merge_into_datajs.py

전제:
  - 이 폴더에 기존 data.js 사본이 있어야 함 (realestate-dashboard/data.js 복사해서 넣기)
  - fetch_molit.py 실행 결과인 molit_fetched.json 이 같은 폴더에 있어야 함

--------------------------------------------------------------------------
[임대수익률 모델 — 학술적 배경]
단순 전세가율(J/P)은 "금리·전환율 환경"을 반영하지 못한다는 한계가 있다.
  - Himmelberg, Mayer & Sinai (2005, JEP) : 임대료 대비 가격은 금리(r)·세금(δ)·
    기대상승률(g)을 반영한 "사용자비용"으로 평가해야 왜곡되지 않는다.
  - 이현탁 (2019, 국토연구 103호, 식2)   : 전세보증금(J)은 전월세전환율(k)을 매개로
    해야 월세(M)·반전세보증금(D)과 비교 가능한 "연간 환산 임대료"가 된다.
        k = 12M / (J - D)  =>  연간 환산 임대료 R = k * J
  - Gallin (2008, REE)                : 임대료-가격 괴리는
    단기 노이즈가 아니라 향후 수년간 실질 매매가 변화에 평균회귀적 예측력을 가진다.

이를 반영해 이 스크립트는 fetch_jeonse_incremental.py가 계산한
  kLocal(지역별 전월세전환율) · rentalYieldPct(내재 임대수익률) · spreadPct(시나리오 참고값)
를 받는다. 지역 간 종합점수에는 오래된 고정 금리를 최신 공식값처럼 쓰지 않고
내재 임대수익률의 상대 백분위를 반영한다. 상세 근거는 README_API연동.md 참고.

동작:
  - 실거래 API로 얻은 history/avg84/avgPrice/gapPct/fairSeries/trades 는 실데이터로 교체
  - jeonse_fetched.json 이 있으면 jeonseRate·kLocal·rentalYieldPct·spreadPct 를 실데이터로 갱신
  - jeonse 데이터가 없는 지역은 기존 jeonseRate에 기본 전환율(DEFAULT_K)을 적용해 추정치로 보강
  - valuation/liquidity/jeonse(임대수익률) 점수는 API 데이터 기준으로 재계산,
    momentum/risk 점수는 기존 방식 유지
  - composite/signal 은 5개 점수를 가중합산해 재계산
  - 갭 변화 국면(gapPhase)을 모멘텀·밸류에이션갭 조합으로 분류해 추가 (참고용 정성 라벨)
"""

import json
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

WEIGHTS = {"valuation": 0.35, "momentum": 0.15, "liquidity": 0.15, "risk": 0.20, "jeonse": 0.15}
MORTGAGE_RATE_PCT = 4.39   # 과거 시나리오 표시용. 지역 순위 점수에는 직접 사용하지 않음.
DEFAULT_K = 0.045          # 월세 표본이 없는 지역의 기본 전월세전환율(연 4.5%)


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
    previous_core = json.dumps(
        {"months": existing.get("months", []), "regions": existing.get("regions", [])},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    previous_meta = existing.get("meta", {})
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

    # 1-b) 전세 스프레드 지표 갱신
    #    - jeonse_fetched.json에 있으면: 실데이터(kLocal, rentalYieldPct, spreadPct) 그대로 사용
    #    - 없으면: 기존 jeonseRate에 기본 전환율(DEFAULT_K)을 적용해 추정치로 보강 (jeonseEstimated=True로 표시)
    for r in existing["regions"]:
        name = r["name"]
        d = jeonse_fetched.get(name)
        if d is not None:
            r["jeonseRate"] = d["jeonseRate"]
            r["jeonseAvgDeposit"] = d["jeonseAvgDeposit"]
            r["kLocal"] = d["kLocal"]
            r["kSamples"] = d.get("kSamples", 0)
            r["rentalYieldPct"] = d["rentalYieldPct"]
            r["spreadPct"] = d["spreadPct"]
            r["jeonseEstimated"] = False
        elif r.get("kLocal") is not None and r.get("rentalYieldPct") is not None:
            # 공급자 장애 또는 cache-only 재계산 때 이미 검증된 마지막 전월세
            # 파생값을 보존한다. 신규 공식값이 없다는 이유로 기본값으로 덮지 않는다.
            r["jeonseEstimated"] = bool(r.get("jeonseEstimated", False))
        else:
            implied_rent = r.get("jeonseAvgDeposit", r["jeonseRate"] / 100.0 * r["avg84"]) * DEFAULT_K
            rental_yield = implied_rent / r["avg84"] * 100.0 if r["avg84"] else 0.0
            r["kLocal"] = DEFAULT_K
            r["kSamples"] = 0
            r["rentalYieldPct"] = round(rental_yield, 2)
            r["spreadPct"] = round(rental_yield - MORTGAGE_RATE_PCT, 2)
            r["jeonseEstimated"] = True

    existing["months"] = fetched["months"]

    # 2) 임대 점수 = 내재 임대수익률의 56개 지역 내 백분위.
    # 모든 지역에 같은 고정 주담대 금리를 빼면 순위가 같으므로, 오래된 금리를
    # 최신 공식값처럼 보이지 않게 지역 순위 계산에서는 금리 차감을 제외한다.
    yield_vals = [r["rentalYieldPct"] for r in existing["regions"]]
    spread_scores = percentile_scores(yield_vals, higher_is_better=True)
    for i, r in enumerate(existing["regions"]):
        r["scores"]["jeonse"] = round(spread_scores[i], 1)

    # 2-b) 갭 변화 국면(gapPhase) 분류 — 참고용 정성 라벨 (조태진 2015의 경고: 갭 축소=가격상승 신호로
    #      단순화하면 안 됨 → 모멘텀(trendN)과 밸류에이션갭(gapPct)을 함께 봐서 국면을 구분한다)
    for r in existing["regions"]:
        trend = r.get("trendN", 0)
        gap = r.get("gapPct", 0)
        if gap > 3 and trend <= 0.8:
            r["gapPhase"] = "거품성 갭 확대 우려"
        elif gap < -3 and trend < 0:
            r["gapPhase"] = "침체성 조정 중"
        elif gap < -1 and trend >= 0.8:
            r["gapPhase"] = "건전한 회복(임대수요 기반 추정)"
        else:
            r["gapPhase"] = "중립/혼조"

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
            r["signal"], r["signalText"] = "buy", "🔵 상대우위"
        elif composite >= 42:
            r["signal"], r["signalText"] = "warning", "🟡 중립"
        else:
            r["signal"], r["signalText"] = "watch", "🔴 재검증"

    evaluation_months = [
        value.get("evaluationMonth") for value in fetched.get("regions", {}).values()
        if value.get("evaluationMonth")
    ]
    meta_without_time = {
        "latestObservationMonth": fetched["months"][-1] if fetched.get("months") else "",
        "evaluationMonth": max(evaluation_months) if evaluation_months else "",
        "currentMonthProvisional": True,
        "saleSource": "국토교통부 아파트매매 실거래가 공개 API",
        "rentSource": "국토교통부 아파트 전월세 실거래가 공개 API",
        "priceStatistic": "전용 80~90㎡ 월별 단순평균; 거래구성 변화 미통제",
        "modelStatus": "RESEARCH_ONLY",
        "unverifiedComponents": ["momentum", "risk"],
        "mortgageRateScenarioPct": MORTGAGE_RATE_PCT,
    }
    current_core = json.dumps(
        {"months": existing.get("months", []), "regions": existing.get("regions", [])},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    prior_meta_without_time = {key: value for key, value in previous_meta.items() if key != "generatedAtKST"}
    substantive_change = current_core != previous_core or meta_without_time != prior_meta_without_time
    generated_at = previous_meta.get("generatedAtKST") if not substantive_change else None
    existing["meta"] = {
        "generatedAtKST": generated_at
        or datetime.now(ZoneInfo("Asia/Seoul")).replace(microsecond=0).isoformat(),
        **meta_without_time,
    }

    with open("data.js", "w", encoding="utf-8") as f:
        f.write("const ENHANCED_DATA = ")
        json.dump(existing, f, ensure_ascii=False)
        f.write(";\n")

    print("완료: data.js 가 실거래 데이터 기준으로 갱신되었습니다.")
    print("이 data.js 를 GitHub 저장소의 기존 data.js에 덮어쓰기(commit) 하면 사이트에 즉시 반영됩니다.")


if __name__ == "__main__":
    main()
