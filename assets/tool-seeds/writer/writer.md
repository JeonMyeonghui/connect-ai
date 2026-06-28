# Writer 도구 모음

| 도구 | 기능 | 설정 파일 |
|------|------|----------|
| `draft_script.py` | 영상 스크립트 초안 (후크·본론·CTA) | `draft_script.json` |
| `hook_generator.py` | 첫 5초 후킹 오프닝 5가지 패턴 | `hook_generator.json` |
| `caption_writer.py` | 플랫폼별 SNS 캡션 한 번에 생성 | `caption_writer.json` |

## 빠른 시작

```bash
# 1. 스크립트 초안
python draft_script.py   # → draft_script.json 생성 → TOPIC 입력 → 재실행

# 2. 후크 아이디어
python hook_generator.py  # → TOPIC 입력 → 5가지 패턴 후크

# 3. SNS 캡션
python caption_writer.py  # → TOPIC 입력 → YouTube·인스타·트위터·LinkedIn 일괄 생성
```

## 공통 설정 항목

- `OLLAMA_URL`: LM Studio는 `http://127.0.0.1:1234`
- `MODEL`: 비우면 자동 선택 (설치된 모델 중 첫 번째)
- 출력 파일은 누적 저장 (덮어쓰지 않음)
