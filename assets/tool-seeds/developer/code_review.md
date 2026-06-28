# Code Review — 코드 리뷰

git diff를 로컬 LLM이 분석해서 버그·보안·품질 리뷰 보고서를 작성합니다.

## 설정 (code_review.json)

```json
{
  "REPO_PATH": "d:\\projects\\my-app",
  "DIFF_TARGET": "staged",
  "FOCUS": "보안,버그",
  "MAX_DIFF_CHARS": 6000,
  "OLLAMA_URL": "http://127.0.0.1:11434",
  "MODEL": ""
}
```

| `DIFF_TARGET` 옵션 | 의미 |
|-------------------|------|
| `staged` | 스테이징된 변경사항 (기본) |
| `unstaged` | 스테이징 안 된 변경사항 |
| `HEAD~1` | 마지막 커밋 |
| `abc1234` | 특정 커밋 해시 |

## 실행

```bash
python code_review.py
```

파일: `code_review_report.md`
