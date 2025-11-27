# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

LLM Council은 다수의 LLM이 협업하여 사용자 질문에 답변하는 3단계 심의 시스템입니다. 핵심 혁신은 2단계의 익명 동료 평가로, 모델들이 편애 없이 서로를 평가합니다.

## 개발 환경 설정 및 실행

### 의존성 설치

**백엔드 (uv 사용):**
```bash
uv sync
```

**프론트엔드:**
```bash
cd frontend
npm install
cd ..
```

### 환경 변수 설정

프로젝트 루트에 `.env` 파일 생성:
```bash
OPENROUTER_API_KEY=sk-or-v1-...
```

### 애플리케이션 실행

**방법 1: 시작 스크립트 사용**
```bash
./start.sh
```

**방법 2: 수동 실행 (2개 터미널 필요)**

터미널 1 (백엔드):
```bash
uv run python -m backend.main
```

터미널 2 (프론트엔드):
```bash
cd frontend
npm run dev
```

브라우저에서 http://localhost:5173 접속

### 개발 명령어

**프론트엔드:**
```bash
npm run dev      # 개발 서버 시작
npm run build    # 프로덕션 빌드
npm run lint     # ESLint 실행
npm run preview  # 빌드 미리보기
```

**백엔드:**
```bash
# 항상 프로젝트 루트에서 실행 (backend 디렉토리 내부가 아님)
uv run python -m backend.main
```

## 아키텍처

### 백엔드 구조 (`backend/`)

**핵심 모듈:**

1. **`config.py`**
   - `COUNCIL_MODELS`: OpenRouter 모델 ID 리스트 (평의회 멤버)
   - `CHAIRMAN_MODEL`: 최종 답변 종합 모델
   - `OPENROUTER_API_KEY`: `.env`에서 로드
   - 백엔드 포트: **8001** (8000 아님 - 포트 충돌 회피)

2. **`openrouter.py`**
   - `query_model()`: 단일 모델 비동기 쿼리
   - `query_models_parallel()`: `asyncio.gather()`를 통한 병렬 쿼리
   - 우아한 실패 처리: 일부 모델 실패 시에도 성공한 응답으로 계속 진행

3. **`council.py`** - 핵심 로직
   - `stage1_collect_responses()`: 모든 평의회 모델에 병렬 쿼리
   - `stage2_collect_rankings()`:
     - 응답을 "Response A, B, C..." 형태로 익명화
     - `label_to_model` 매핑 생성 (역익명화용)
     - 엄격한 포맷으로 평가/순위 요청
     - 반환: (rankings_list, label_to_model_dict)
   - `stage3_synthesize_final()`: Chairman이 모든 응답과 순위를 종합
   - `parse_ranking_from_text()`: "FINAL RANKING:" 섹션 추출
   - `calculate_aggregate_rankings()`: 모든 평가에서 평균 순위 계산

4. **`storage.py`**
   - `data/conversations/`에 JSON 형식으로 대화 저장
   - 각 대화: `{id, created_at, messages[]}`
   - 메타데이터(label_to_model, aggregate_rankings)는 저장되지 않고 API 응답으로만 반환됨

5. **`main.py`**
   - FastAPI 앱, CORS 활성화 (localhost:5173, localhost:3000)
   - POST `/api/conversations/{id}/message`: 단계별 결과 + 메타데이터 반환

### 프론트엔드 구조 (`frontend/src/`)

**주요 컴포넌트:**

1. **`App.jsx`**
   - 대화 목록 및 현재 대화 관리
   - 메시지 전송 및 메타데이터 저장 처리
   - 메타데이터는 UI 상태에만 저장됨 (백엔드 JSON에는 미저장)

2. **`components/ChatInterface.jsx`**
   - 멀티라인 텍스트 입력 (3행, 크기 조절 가능)
   - Enter: 전송, Shift+Enter: 줄바꿈
   - 사용자 메시지는 `markdown-content` 클래스로 패딩 적용

3. **`components/Stage1.jsx`**
   - 개별 모델 응답을 탭 뷰로 표시
   - ReactMarkdown 렌더링

4. **`components/Stage2.jsx`** - 핵심 기능
   - 각 모델의 원본 평가 텍스트를 탭 뷰로 표시
   - 역익명화는 클라이언트 측에서 표시용으로만 수행 (모델은 익명 레이블 수신)
   - 파싱된 순위를 평가 아래에 표시하여 검증 가능
   - 집계 순위를 평균 위치 및 투표 수와 함께 표시

5. **`components/Stage3.jsx`**
   - Chairman의 최종 종합 답변
   - 녹색 배경(#f0fff0)으로 결론 강조

**스타일링:**
- 라이트 모드 테마
- 주요 색상: #4a90e2 (파란색)
- `index.css`에 `.markdown-content` 글로벌 스타일 (12px 패딩)

## 주요 설계 결정

### Stage 2 프롬프트 포맷
엄격한 형식으로 파싱 가능한 출력 보장:
```
1. 각 응답을 개별적으로 평가
2. "FINAL RANKING:" 헤더 제공
3. 번호 리스트 형식: "1. Response C", "2. Response A" 등
4. 순위 섹션 이후 추가 텍스트 금지
```

### 역익명화 전략
- 모델이 받는 것: "Response A", "Response B" 등
- 백엔드가 생성: `{"Response A": "openai/gpt-5.1", ...}` 매핑
- 프론트엔드가 표시: 가독성을 위해 모델 이름을 **굵게** 표시
- 사용자는 원래 평가가 익명 레이블을 사용했음을 알 수 있음
- 이를 통해 편향 방지하면서 투명성 유지

### 오류 처리 철학
- 일부 모델 실패 시 성공한 응답으로 계속 진행 (우아한 성능 저하)
- 단일 모델 실패로 전체 요청 실패하지 않음
- 모든 모델이 실패하지 않는 한 사용자에게 오류 노출 안 함

## 중요한 구현 세부사항

### 상대 임포트
모든 백엔드 모듈은 상대 임포트 사용 (예: `from .config import ...`). `python -m backend.main` 실행 시 Python 모듈 시스템이 올바르게 작동하는 데 필수적입니다.

### 포트 설정
- 백엔드: 8001 (충돌 회피를 위해 8000에서 변경됨)
- 프론트엔드: 5173 (Vite 기본값)
- 변경 시 `backend/main.py`와 `frontend/src/api.js` 모두 업데이트 필요

### 마크다운 렌더링
모든 ReactMarkdown 컴포넌트는 올바른 간격을 위해 `<div className="markdown-content">`로 감싸야 합니다. 이 클래스는 `index.css`에 전역적으로 정의되어 있습니다.

### 모델 설정
모델은 `backend/config.py`에 하드코딩되어 있습니다. Chairman은 평의회 멤버와 같거나 다를 수 있습니다.

## 일반적인 문제

1. **모듈 임포트 오류**: 항상 프로젝트 루트에서 `python -m backend.main`으로 백엔드 실행 (backend 디렉토리 내부가 아님)
2. **CORS 문제**: 프론트엔드는 `main.py` CORS 미들웨어의 허용 원본과 일치해야 함
3. **순위 파싱 실패**: 모델이 형식을 따르지 않으면 폴백 정규식이 순서대로 "Response X" 패턴 추출
4. **메타데이터 누락**: 메타데이터는 임시적 (저장되지 않음), API 응답에서만 사용 가능

## 테스팅

`test_openrouter.py`를 사용하여 API 연결 확인 및 평의회에 추가하기 전에 다른 모델 식별자 테스트. 스크립트는 스트리밍/비스트리밍 모드 모두 테스트합니다.

## 데이터 흐름 요약

```
사용자 쿼리
    ↓
Stage 1: 병렬 쿼리 → [개별 응답들]
    ↓
Stage 2: 익명화 → 병렬 순위 쿼리 → [평가 + 파싱된 순위]
    ↓
집계 순위 계산 → [평균 위치로 정렬]
    ↓
Stage 3: Chairman이 전체 컨텍스트로 종합
    ↓
반환: {stage1, stage2, stage3, metadata}
    ↓
프론트엔드: 탭 + 검증 UI로 표시
```

지연 시간 최소화를 위해 가능한 모든 흐름이 비동기/병렬로 처리됩니다.

## 기술 스택

- **백엔드:** FastAPI (Python 3.10+), async httpx, OpenRouter API
- **프론트엔드:** React + Vite, react-markdown
- **저장소:** `data/conversations/`의 JSON 파일
- **패키지 관리:** Python은 uv, JavaScript는 npm
