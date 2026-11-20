#!/usr/bin/env python3
"""Generate a scoped task prompt; no network, execution, or repository mutation."""
import argparse
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MODULES = json.loads((ROOT / "operations/modules.json").read_text(encoding="utf-8"))
p = argparse.ArgumentParser(description=__doc__)
p.add_argument("module", choices=sorted(MODULES))
p.add_argument("goal", help="Task objective")
a = p.parse_args()
m = MODULES[a.module]
print(f"기능: {a.module} — {m['name']}\n목표: {a.goal}")
print("operations/README.md와 해당 모듈 README를 먼저 읽어라.")
print("관련 경로: " + ", ".join(m["paths"]))
print("주의: " + m["scope"])
print("기준 SHA와 실제 상태를 확인하고 operations/templates/task.md를 채워라.")
print("허용 파일을 좁혀 최소 변경하고, 관련 테스트·재현명령·반론·롤백을 PR에 정리하라.")
print("자료 부족은 HOLD. 미실행을 성공으로 보고하지 마라. 연구 승격과 자금집행은 별도 결재다.")
