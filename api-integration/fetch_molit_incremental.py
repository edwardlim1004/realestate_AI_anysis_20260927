"""
국토교통부 아파트매매 실거래가 API -> data.js (증분/캐시 업데이트 버전)
------------------------------------------------------------------
핵심 아이디어:
  - 이미 확정된 과거 달(예: 3개월 이전)은 molit_cache.json 에 저장해두고 재사용한다.
  - 실거래 신고는 계약 후 최대 30일 정도 늦게 반영될 수 있으므로,
    REFRESH_WINDOW(기본 3개월)에 해당하는 "최근 달"만 매번 다시 받아온다.
  - 그 결과 최초 1회만 전체(56개 지역 x 61개월)를 받고, 이후에는
    56개 지역 x REFRESH_WINDOW개월 만 API를 호출한다 -> 훨씬 빠르고 가볍다.

사용법은 fetch_molit_fast.py와 동일:
  1) pip install requests
  2) .env 에 MOLIT_SERVICE_KEY 설정
  3) python fetch_molit_incremental.py
  4) molit_fetched.json 생성됨 (merge_into_datajs.py 로 병합)
     + molit_cache.json 이 갱신됨 (다음 실행을 더 빠르게 해줌, 반드시 보존해야 함 -> 깃허브에 커밋)

캐시 파일(molit_cache.json)은 저장소에 함께 커밋해서 GitHub Actions 실행 사이에도
유지되도록 해야 "증분" 효과가 생깁니다. (매번 새 러너에서 돌면 캐시가 없어 매번 전체 수집함)
"""

import os
import json
import math
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import xml.etree.ElementTree as ET
from datetime import date

import requests

from regions_lawd import REGION_LAWD


def load_env_file(path=".env"):
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


load_env_file()
SERVICE_KEY = os.environ.get("MOLIT_SERVICE_KEY", "")
BASE_URL = "http://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"

MONTHS_BACK = 61          # 유지할 전체 윈도우(5년+1개월)
REFRESH_WINDOW = 3        # 매번 무조건 다시 받아오는 "최근 N개월" (신고 지연 대비)
MAX_WORKERS = 4
MAX_RETRIES = 5
CACHE_PATH = "molit_cache.json"


def month_list(n):
    today = date.today()
    y, m = today.year, today.month
    out = []
    for i in range(n - 1, -1, -1):
        yy, mm = y, m - i
        while mm <= 0:
            mm += 12
            yy -= 1
        out.append(f"{yy}{mm:02d}")
    return out


def to_label(ym):
    return f"{ym[:4]}-{ym[4:]}"


def fetch_month(lawd_cd, deal_ymd):
    rows = []
    page = 1
    while True:
        params = {
            "serviceKey": SERVICE_KEY,
            "LAWD_CD": lawd_cd,
            "DEAL_YMD": deal_ymd,
            "pageNo": page,
            "numOfRows": 1000,
        }
        last_err = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = requests.get(BASE_URL, params=params, timeout=15)
                if resp.status_code == 429:
                    raise requests.exceptions.HTTPError("429 Too Many Requests")
                resp.raise_for_status()
                root = ET.fromstring(resp.content)
                break
            except Exception as e:
                last_err = e
                wait = 2.0 * (attempt + 1) if "429" in str(e) else 0.5 * (attempt + 1)
                time.sleep(wait)
        else:
            raise RuntimeError(f"{lawd_cd}/{deal_ymd} 요청 반복 실패: {last_err}")

        result_code = root.findtext(".//resultCode")
        auth_err = root.findtext(".//returnAuthMsg")
        if auth_err:
            raise RuntimeError(f"인증 오류 [{lawd_cd}/{deal_ymd}]: {auth_err}")
        if result_code not in (None, "00", "000"):
            msg = root.findtext(".//resultMsg")
            raise RuntimeError(f"API 오류 [{lawd_cd}/{deal_ymd}]: {result_code} {msg}")

        items = root.findall(".//item")
        if not items:
            break
        for it in items:
            def g(tag):
                el = it.find(tag)
                return el.text.strip() if el is not None and el.text else None

            area = g("excluUseAr")
            price = g("dealAmount")
            if area is None or price is None:
                continue
            try:
                area_f = float(area)
                price_manwon = float(price.replace(",", "").strip())
            except ValueError:
                continue
            rows.append({"area": area_f, "price_manwon": price_manwon})

        total_count = int(root.findtext(".//totalCount", "0"))
        if page * 1000 >= total_count:
            break
        page += 1
    return rows


def aggregate(rows):
    all_prices = [r["price_manwon"] / 10000.0 for r in rows]
    area84_prices = [r["price_manwon"] / 10000.0 for r in rows if 80 <= r["area"] <= 90]
    return {
        "avgAll": (sum(all_prices) / len(all_prices)) if all_prices else None,
        "avg84": (sum(area84_prices) / len(area84_prices)) if area84_prices else None,
        "count": len(rows),
    }


def fill_gaps(series):
    series = list(series)
    n = len(series)
    for i in range(n):
        if series[i] is None:
            prev_v = next((series[j] for j in range(i - 1, -1, -1) if series[j] is not None), None)
            next_v = next((series[j] for j in range(i + 1, n) if series[j] is not None), None)
            if prev_v is not None and next_v is not None:
                series[i] = (prev_v + next_v) / 2
            else:
                series[i] = prev_v or next_v or 0.0
    return series


def compute_fair_value(history):
    n_fit = len(history) - 12
    xs = list(range(n_fit))
    ys = [math.log(max(v, 0.01)) for v in history[:n_fit]]
    n = len(xs)
    sx, sy = sum(xs), sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    slope = (n * sxy - sx * sy) / (n * sxx - sx * sx)
    intercept = (sy - slope * sx) / n
    fair_series = [math.exp(intercept + slope * m) for m in range(len(history))]
    return fair_series, fair_series[-1]


def percentile_scores(values, higher_is_better=True):
    order = sorted(range(len(values)), key=lambda i: values[i])
    n = len(values)
    scores = [0] * n
    for rank, idx in enumerate(order):
        pct = rank / (n - 1) * 100 if n > 1 else 50
        scores[idx] = pct if higher_is_better else 100 - pct
    return scores


def main():
    if not SERVICE_KEY:
        raise SystemExit(".env 파일에 MOLIT_SERVICE_KEY=발급받은키 를 추가해주세요.")

    months = month_list(MONTHS_BACK)        # 오래된 순 -> 최신 순, YYYYMM
    refresh_set = set(months[-REFRESH_WINDOW:])
    month_labels = [to_label(m) for m in months]

    cache = {}
    if os.path.exists(CACHE_PATH):
        cache = json.load(open(CACHE_PATH, encoding="utf-8"))

    targets = list(REGION_LAWD.keys())

    # 캐시에 없거나, "최근 N개월"에 해당해서 매번 새로 받아야 하는 (region, month) 만 수집 대상으로 선정
    need_fetch = []
    for name in targets:
        region_cache = cache.get(name, {})
        for ym in months:
            label = to_label(ym)
            if ym in refresh_set or label not in region_cache:
                need_fetch.append((name, ym))

    total_months_possible = len(targets) * len(months)
    print(f"전체 윈도우: {len(targets)}개 지역 x {len(months)}개월 = {total_months_possible}건")
    print(f"이번에 실제로 호출할 (지역,월): {len(need_fetch)}건 "
          f"({'최초 전체 수집' if len(need_fetch) > total_months_possible*0.5 else '증분 업데이트'})")

    # (region, code, month) 단위 태스크로 펼쳐서 병렬 처리
    tasks = []
    for name, ym in need_fetch:
        for code in REGION_LAWD[name]:
            tasks.append((name, code, ym))

    raw = defaultdict(list)  # (region, ym) -> rows
    done = 0
    errors = []
    if tasks:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            future_map = {ex.submit(fetch_month, code, ym): (name, code, ym) for (name, code, ym) in tasks}
            for fut in as_completed(future_map):
                name, code, ym = future_map[fut]
                done += 1
                try:
                    rows = fut.result()
                    raw[(name, ym)].extend(rows)
                except Exception as e:
                    errors.append((name, code, ym, str(e)))
                if done % 100 == 0 or done == len(tasks):
                    print(f"  진행률: {done}/{len(tasks)}")

    if errors:
        print(f"\n[경고] {len(errors)}건 호출 실패 (해당 월은 캐시 유지 또는 결측 처리됨)")
        for e in errors[:10]:
            print("  ", e)

    # 캐시 갱신: 새로 받은 (region, month) 만 반영, 나머지는 기존 캐시 유지
    for name, ym in need_fetch:
        label = to_label(ym)
        rows = raw.get((name, ym))
        if rows is None and (name, ym) in [(n, y) for (n, y, *_r) in errors]:
            continue  # 호출 실패 -> 캐시에 없던 값이면 비워두고, 있던 값이면 그대로 둠(건드리지 않음)
        agg = aggregate(rows or [])
        cache.setdefault(name, {})[label] = agg

    # 윈도우 밖으로 밀려난 오래된 달은 캐시에서 정리(파일 크기 관리)
    valid_labels = set(month_labels)
    for name in list(cache.keys()):
        for label in list(cache[name].keys()):
            if label not in valid_labels:
                del cache[name][label]

    json.dump(cache, open(CACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # 캐시(이제 완전한 61개월)로부터 최종 결과 조립
    results = {}
    for name in targets:
        region_cache = cache.get(name, {})
        monthly_all = [region_cache.get(lbl, {}).get("avgAll") for lbl in month_labels]
        monthly_84 = [region_cache.get(lbl, {}).get("avg84") for lbl in month_labels]
        monthly_count = [region_cache.get(lbl, {}).get("count", 0) for lbl in month_labels]

        monthly_all = fill_gaps(monthly_all)
        monthly_84 = fill_gaps(monthly_84)
        fair_series, fair_now = compute_fair_value(monthly_84)
        gap_pct = (monthly_84[-1] - fair_now) / fair_now * 100.0

        jul_cnt = monthly_count[-2] if len(monthly_count) >= 2 else 0
        aug_cnt = monthly_count[-1] if len(monthly_count) >= 1 else 0
        vol_change = ((aug_cnt - jul_cnt) / jul_cnt * 100) if jul_cnt else 0

        results[name] = {
            "history": [round(v, 3) for v in monthly_84],
            "historyAll": [round(v, 3) for v in monthly_all],
            "fairSeries": [round(v, 3) for v in fair_series],
            "fairValueNow": round(fair_now, 2),
            "gapPct": round(gap_pct, 2),
            "avg84": round(monthly_84[-1], 1),
            "avgPrice": round(monthly_all[-1], 1),
            "trades": f"{jul_cnt + aug_cnt}건 ({months[-2][4:]}월: {jul_cnt} / {months[-1][4:]}월: {aug_cnt})",
            "volChange": vol_change,
        }

    names = list(results.keys())
    gap_vals = [results[n]["gapPct"] for n in names]
    vol_vals = [results[n]["volChange"] for n in names]
    val_scores = percentile_scores(gap_vals, higher_is_better=False)
    liq_scores = percentile_scores(vol_vals, higher_is_better=True)
    for i, n in enumerate(names):
        results[n]["scores_partial"] = {
            "valuation": round(val_scores[i], 1),
            "liquidity": round(liq_scores[i], 1),
        }

    json.dump({"months": month_labels, "regions": results},
               open("molit_fetched.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n완료: molit_fetched.json 갱신 (API 호출 {len(tasks)}건으로 56개 지역 전체 최신화)")


if __name__ == "__main__":
    main()
