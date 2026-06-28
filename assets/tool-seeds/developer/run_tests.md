# Run Tests — 테스트 실행 + LLM 실패 분석

테스트를 실행하고, 실패 시 LLM이 원인을 분석해서 수정 힌트를 제공합니다.  
npm/pytest/make 자동 감지.

## 설정 (run_tests.json)

```json
{
  "REPO_PATH": "d:\\projects\\my-app",
  "TEST_CMD": "",
  "OLLAMA_URL": "http://127.0.0.1:11434",
  "MODEL": "",
  "TIMEOUT": 120
}
```

`TEST_CMD`를 비우면 자동 감지:
- `package.json` 있으면 → `npm test`
- `pytest.ini` / `pyproject.toml` 있으면 → `pytest -v`

## 실행

```bash
python run_tests.py
```

파일: `run_tests_report.md`
