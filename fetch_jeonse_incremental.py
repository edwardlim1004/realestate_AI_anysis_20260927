"""
국토교통부 아파트 전월세 실거래가 API -> 전세가율 (증분/캐시 업데이트 버전)
fetch_molit_incremental.py 와 동일한 원리: 최근 REFRESH_WINDOW개월만 다시 받고
나머지는 jeonse_cache.json 에 저장된 값을 재사용한다.

실행 전 fetch_molit_incremental.py 를 먼저 실행해 molit_fetched.json 을 만들어두세요.
"""

import os
import json
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
BASE_URL = "http://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"

JEONSE_MONTHS = 6
REFRESH_WINDOW = 2
MAX_WORKERS = 5
MAX_RETRIES = 4
CACHE_PATH = "jeonse_cache.json"


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
            deposit = g("deposit")
            monthly_rent = g("monthlyRent")
            if area is None or deposit is None:
                continue
            try:
                area_f = float(area)
                deposit_manwon = float(deposit.replace(",", "").strip())
                rent_manwon = float((monthly_rent or "0").replace(",", "").strip())
            except ValueError:
                continue
            if rent_manwon > 0:
                continue
            rows.append({"area": area_f, "deposit_manwon": deposit_manwon})

        total_count = int(root.findtext(".//totalCount", "0"))
        if page * 1000 >= total_count:
            break
        page += 1
    return rows


def main():
    if not SERVICE_KEY:
        raise SystemExit(".env 파일에 MOLIT_SERVICE_KEY=발급받은키 를 추가해주세요.")
    if not os.path.exists("molit_fetched.json"):
        raise SystemExit("먼저 fetch_molit_incremental.py 를 실행해서 molit_fetched.json 을 만들어주세요.")

    molit = json.load(open("molit_fetched.json", encoding="utf-8"))
    sale_avg84 = {name: d["avg84"] for name, d in molit["regions"].items()}

    months = month_list(JEONSE_MONTHS)
    refresh_set = set(months[-REFRESH_WINDOW:])
    targets = list(REGION_LAWD.keys())

    cache = {}
    if os.path.exists(CACHE_PATH):
        cache = json.load(open(CACHE_PATH, encoding="utf-8"))

    need_fetch = []
    for name in targets:
        region_cache = cache.get(name, {})
        for ym in months:
            label = to_label(ym)
            if ym in refresh_set or label not in region_cache:
                need_fetch.append((name, ym))

    tasks = [(name, code, ym) for (name, ym) in need_fetch for code in REGION_LAWD[name]]
    print(f"전체 윈도우: {len(targets)}개 지역 x {len(months)}개월, 이번 호출: {len(tasks)}건")

    raw = defaultdict(list)
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
                if done % 50 == 0 or done == len(tasks):
                    print(f"  진행률: {done}/{len(tasks)}")

    if errors:
        print(f"\n[경고] {len(errors)}건 실패")
        for e in errors[:10]:
            print("  ", e)

    for name, ym in need_fetch:
        label = to_label(ym)
        key = (name, ym)
        if key not in raw and any(n == name and y == ym for n, y, *_ in errors):
            continue  # 실패했고 기존 캐시 있으면 유지
        rows = raw.get(key, [])
        deposits = [r["deposit_manwon"] / 10000.0 for r in rows if 80 <= r["area"] <= 90]
        cache.setdefault(name, {})[label] = {
            "avgDeposit": (sum(deposits) / len(deposits)) if deposits else None,
            "sampleSize": len(deposits),
        }

    valid_labels = {to_label(ym) for ym in months}
    for name in list(cache.keys()):
        for label in list(cache[name].keys()):
            if label not in valid_labels:
                del cache[name][label]

    json.dump(cache, open(CACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # 캐시(6개월치)를 합쳐서 지역별 전세가율 산출
    results = {}
    for name in targets:
        region_cache = cache.get(name, {})
        all_deposits_weighted = []
        total_sample = 0
        for label in region_cache:
            entry = region_cache[label]
            if entry.get("avgDeposit") is not None and entry.get("sampleSize", 0) > 0:
                all_deposits_weighted.append((entry["avgDeposit"], entry["sampleSize"]))
                total_sample += entry["sampleSize"]
        if not all_deposits_weighted or name not in sale_avg84 or not sale_avg84[name]:
            print(f"[{name}] 표본 부족 - 건너뜀(기존 값 유지)")
            continue
        weighted_avg = sum(v * w for v, w in all_deposits_weighted) / total_sample
        jeonse_rate = weighted_avg / sale_avg84[name] * 100.0
        results[name] = {
            "jeonseRate": round(jeonse_rate, 1),
            "jeonseAvgDeposit": round(weighted_avg, 2),
            "sampleSize": total_sample,
        }
        print(f"[{name}] 표본 {total_sample}건 -> 전세가율 {jeonse_rate:.1f}%")

    json.dump(results, open("jeonse_fetched.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n완료: jeonse_fetched.json 갱신 ({len(results)}개 지역, API 호출 {len(tasks)}건)")


if __name__ == "__main__":
    main()
