# Connect AI — CLAUDE.md

> AI 개발 에이전트가 이 코드베이스를 즉시 파악하고 안전하게 수정할 수 있도록 작성된 레퍼런스.

---

## ⚠️ 디렉토리 정책 (반드시 준수)

| 경로 | 용도 | 주의사항 |
|------|------|----------|
| `d:\claude\ex1\connect-ai` | **최종 업로드용** (GitHub 동기화) | 검증된 코드만 커밋. 신중하게 수정. |
| `d:\claude\work\` | **개발 실험 작업 공간** | 초안·실험·리팩토링 중간 작업 |
| `d:\claude\temp\` | **일회성 임시 파일** | 테스트 출력, 스크래치 스크립트, 로그 |

**규칙:**
- 임시 파일·실험 코드는 절대 `d:\claude\ex1\connect-ai`에 만들지 않음
- 프로젝트 내 임시 파일이 필요하면 `_temp/` 폴더 사용 (gitignore 처리됨)
- `d:\claude\ex1\connect-ai`에 커밋하기 전 반드시 `npm run compile` 빌드 확인

---

## 토큰 최적화 — 로컬 AI 활용 전략

Ollama(`gemma4:e2b` @ 11434)와 LM Studio(@ 1234)가 항상 실행 중.
**단순·반복 작업은 로컬 AI에게, 복잡한 판단은 Claude에게** 위임해 토큰을 아낀다.

### 로컬 AI를 써야 하는 작업 (d:\claude\work\ 스크립트 활용)

| 작업 | 스크립트 | Claude 대신 쓰는 이유 |
|------|----------|----------------------|
| 빠른 코드 질문 | `ask.ps1 "질문"` | 단답형, 토큰 낭비 없음 |
| extension.ts 섹션 요약 | `summarize.ps1 <파일> <from> <to>` | 17K줄 통째 올리지 않음 |
| 함수 위치 찾기 | `find-fn.ps1 "기능 설명"` | 관련 줄만 추려서 Claude에 전달 |
| 커밋 메시지 생성 | `commit-msg.ps1` | diff → 메시지 자동화 |

### Claude를 써야 하는 작업

- 다중 파일에 걸친 버그 수정 / 리팩토링
- 아키텍처 설계·검토
- 보안 취약점 분석
- 새 기능의 구현 전략 수립

### 대형 파일 작업 패턴

extension.ts(17K줄)를 다룰 때:
1. `find-fn.ps1`로 관련 줄 번호 확인
2. `Read` 도구로 해당 범위만 읽기 (전체 X)
3. Claude에는 해당 섹션만 전달

---

## 1. 프로젝트 개요

**connect-ai-lab** v2.89.x — VS Code / Cursor 확장 프로그램.  
로컬 LLM(Ollama, LM Studio)으로 구동되는 AI 회사 에이전트 팀. 완전 오프라인, 100% 로컬.

- **GitHub**: https://github.com/JeonMyeonghui/connect-ai.git
- **로컬 경로**: `d:\claude\ex1\connect-ai`
- **브랜치**: `main` (단일 브랜치 전략)

---

## 2. 파일 구조

```
connect-ai/
├── src/
│   ├── extension.ts       ← 핵심 로직 전체 (~17,000줄, 단일 파일)
│   ├── agents.ts          ← 에이전트 정의 (AGENTS map, AgentDef interface)
│   ├── paths.ts           ← 경로 유틸리티 (_getBrainDir, getCompanyDir 등)
│   └── system-specs.ts    ← 시스템 사양 감지 (RAM·CPU·모델 메모리 추정)
├── assets/
│   ├── prompts/           ← LLM 시스템 프롬프트 (.md 파일)
│   ├── tool-seeds/        ← Python 도구 시드 파일 (<agent>/<tool>.py)
│   ├── agents/            ← 에이전트 프로필 이미지
│   └── pixel/characters/  ← 픽셀 아트 캐릭터
├── out/
│   └── extension.js       ← 빌드 결과물 (esbuild, git 제외)
├── package.json           ← VS Code 설정 스키마 + 명령 선언
├── tsconfig.json
├── system_schema.json     ← AI 에이전트 도구 스키마
├── ARCHITECTURE.md        ← Brain-GitHub 동기화 아키텍처 레퍼런스
└── .claude/settings.json  ← Claude Code 권한 설정
```

**핵심 파일 2개**: `package.json` (설정 선언) + `src/extension.ts` (모든 로직)

---

## 3. 에이전트 구조

`src/agents.ts`에 정의. 10개 에이전트:

| ID | 이름 | 역할 |
|----|------|------|
| `ceo` | CEO | 오케스트레이션·작업 분해·의사결정 |
| `youtube` | 레오 | 유튜브 채널 기획·운영 |
| `instagram` | Instagram | 인스타 콘텐츠·인게이지먼트 |
| `designer` | Designer | 브랜드·썸네일·비주얼 |
| `developer` | Developer | 코드·자동화·API 통합 |
| `business` | Business | 수익화·가격·전략 |
| `secretary` | 영숙 | 일정·할일·텔레그램 보고 |
| `editor` | 루나 | 영상 BGM 생성·사운드 디자인 |
| `writer` | Writer | 카피·스크립트·후크 |
| `researcher` | Researcher | 트렌드·데이터 리서치 |

에이전트 추가/수정 → `src/agents.ts`만 변경.

---

## 4. 핵심 아키텍처 패턴

### 4-A. HTTP 로컬 서버 (포트 4825)
`extension.ts` 내 `http.createServer()`로 구동. Brain Pack 주입 API:
```
POST http://127.0.0.1:4825/api/brain-inject
POST http://127.0.0.1:4825/api/company-chat (회사 모드 채팅)
POST http://127.0.0.1:4825/api/dispatch     (에이전트 작업 위임)
```

### 4-B. Git 동기화
- `_safeGitAutoSync()` — Brain Pack 주입 후 자동 호출 (blocking)
- `_syncSecondBrain()` — 사용자 수동 메뉴 호출 (async)
- 충돌 전략: `-X ours` (로컬 우선)
- 보안: `gitExec()` argv 형식 사용 (셸 인젝션 차단)

### 4-C. LLM 호출
- Ollama: `http://127.0.0.1:11434`
- LM Studio: `http://127.0.0.1:1234`
- 설정: `connectAiLab.ollamaUrl`, `connectAiLab.defaultModel`
- 에이전트별 모델 오버라이드: `~/.connect-ai-brain/_agents/model_map.json`

### 4-D. Telegram 비서 (영숙)
- 폴링 방식 (`_tryAcquireTelegramLock()` — 멀티윈도우 충돌 방지)
- 히스토리: `~/.connect-ai-brain/_agents/secretary/telegram_history.json`
- 설정 저장: `~/.connect-ai-brain/_agents/secretary/tools/`

### 4-E. 지식 폴더 구조
```
~/.connect-ai-brain/          ← localBrainPath 설정
├── .git/
├── 00_Raw/                   ← Brain Pack 원본
├── 10_Wiki/                  ← P-Reinforce 구조화 지식
└── _company/                 ← 회사 폴더 (또는 별도 경로)
    ├── _agents/              ← 에이전트 설정/기억
    ├── _shared/              ← 공유 데이터 (tracker.json 등)
    └── identity.md           ← 회사 정체성 파일
```

---

## 5. VS Code 설정 키 (package.json contributes.configuration)

| 키 | 용도 | 기본값 |
|----|------|--------|
| `connectAiLab.ollamaUrl` | LLM 서버 주소 | `http://127.0.0.1:11434` |
| `connectAiLab.defaultModel` | 기본 AI 모델 | `""` (자동 감지) |
| `connectAiLab.localBrainPath` | 지식 폴더 경로 | `~/.connect-ai-brain` |
| `connectAiLab.secondBrainRepo` | GitHub 저장소 URL | `""` |
| `connectAiLab.companyRepo` | 회사 GitHub 저장소 | `""` |
| `connectAiLab.companyDir` | 회사 폴더 경로 | `<brain>/_company/` |
| `connectAiLab.requestTimeout` | AI 응답 대기(초) | `300` |
| `connectAiLab.autoCycleEnabled` | 24시간 자율 사이클 | `true` |
| `connectAiLab.dailyBriefingTime` | 데일리 브리핑 시간 | `"09:00"` |
| `connectAiLab.secretaryBridgeMode` | 비서 브릿지 모드 | `"off"` |

**⚠️ 설정은 `vscode.ConfigurationTarget.Global`에 저장됨** (워크스페이스 아님)

---

## 6. 빌드 & 배포 워크플로우

```bash
# 1. 컴파일 (esbuild → out/extension.js)
npm run compile

# 2. VSIX 패키징
npx vsce package --no-dependencies --allow-star-activation

# 3. GitHub 커밋 & 푸시
git add src/ package.json assets/ system_schema.json
git commit -m "feat(2.89.X): 변경 내용 요약"
git push origin main

# 4. GitHub 릴리즈 (선택)
gh release create v2.89.X connect-ai-lab-2.89.X.vsix -t "Release v2.89.X"
```

### 버전 규칙
- `package.json`의 `"version"` 필드 수정
- 커밋 메시지: `feat(2.89.X)`, `fix(2.89.X)`, `chore(2.89.X)` 형식

---

## 7. 개발 규칙

### 코드 수정 시
1. `src/extension.ts`는 매우 큰 파일(17,000줄). 수정할 섹션을 먼저 Grep으로 찾고 최소 범위만 수정.
2. 새 에이전트 추가 → `src/agents.ts`의 `AGENTS` map + `AGENT_ORDER` 배열
3. 경로 함수 추가 → `src/paths.ts`
4. 빌드 확인: 수정 후 반드시 `npm run compile` 실행
5. `out/` 디렉토리는 git에 올리지 않음 (`.gitignore`)

### 보안 원칙
- `gitExec(args[])` 사용 — 셸 문자열 보간 금지
- `safeResolveInside()` — 경로 트래버설 방지
- `safeBasename()` — 파일명 새니타이즈
- `MAX_HTTP_BODY = 5MB` 캡 유지

### 금지 사항
- `shell: true` + 사용자 입력 직접 삽입 → 인젝션 위험
- `vscode.ConfigurationTarget.Workspace` 사용 (Global만 사용)
- `out/extension.js` 직접 편집 (컴파일 결과물)

---

## 8. 자주 쓰는 Grep 패턴

```bash
# 특정 명령 등록 위치 찾기
grep -n "registerCommand" src/extension.ts

# 에이전트 라우팅 로직
grep -n "agentId\|specialistId\|SPECIALIST_IDS" src/extension.ts

# git 동기화 함수
grep -n "_safeGitAutoSync\|_syncSecondBrain" src/extension.ts

# Telegram 관련
grep -n "telegram\|_runTelegram" src/extension.ts

# 캘린더 관련
grep -n "_getCalendarAccessToken\|_createCalendarEvent" src/extension.ts
```

---

## 9. 디버깅

```bash
# VS Code에서 F5 → Extension Development Host 실행
# 개발자 도구: Help → Toggle Developer Tools → Console 탭

# 로그 확인 (확장 채널)
# VS Code 출력 패널 → "Connect AI" 채널 선택

# 포트 4825 확인
netstat -an | findstr 4825
```
