# Business 도구 모음

| 도구 | 기능 | 설정 파일 |
|------|------|----------|
| `revenue_tracker.py` | 수익 데이터 → 트렌드 분석 + LLM 인사이트 | `revenue_tracker.json` |
| `kpi_report.py` | KPI 입력 → 주간/월간 보고서 자동 생성 | `kpi_report.json` |

## 빠른 시작

```bash
python revenue_tracker.py  # → revenue_tracker.json 생성 → 수익 데이터 입력 → 재실행
python kpi_report.py       # → kpi_report.json 생성 → KPI 수치 입력 → 재실행
```

## revenue_tracker.json 예시

```json
{
  "REVENUE_DATA": [
    {"period": "2026-04", "amount": 850000, "source": "유튜브 광고"},
    {"period": "2026-05", "amount": 1200000, "source": "유튜브 광고"},
    {"period": "2026-06", "amount": 980000, "source": "유튜브 광고"}
  ],
  "CURRENCY": "원",
  "GOAL": 2000000
}
```

## kpi_report.json 예시

```json
{
  "KPIS": [
    {"name": "구독자", "current": 3200, "previous": 2900, "target": 10000, "unit": "명"},
    {"name": "월 수익", "current": 980000, "previous": 1200000, "target": 3000000, "unit": "원"}
  ],
  "PERIOD": "2026년 6월 4주차",
  "WINS": ["영상 2개 업로드 완료", "구독자 300명 증가"],
  "BLOCKERS": ["편집 시간 부족"]
}
```
