"""3단계 LLM 위원회 조율 시스템.

LLM Council의 핵심 로직이 담긴 파일입니다.
여러 AI가 협업하여 최고의 답변을 만드는 3단계 프로세스를 관리합니다.

전체 흐름:
1단계: 5명의 AI에게 같은 질문을 던져서 각자의 답변을 받음
2단계: 각 AI가 다른 AI들의 답변을 익명으로 평가하고 순위를 매김
3단계: 의장 AI가 모든 정보를 종합해서 최종 답변 작성
"""

# typing: 데이터 타입을 명시하는 도구
from typing import List, Dict, Any, Tuple
# openrouter: AI 모델들과 통신하는 함수들 (병렬 쿼리, 단일 쿼리)
from .openrouter import query_models_parallel, query_model
# config: 설정 값들 (어떤 AI 모델들을 사용할지, 의장은 누구인지)
from .config import COUNCIL_MODELS, CHAIRMAN_MODEL


async def stage1_collect_responses(user_query: str) -> List[Dict[str, Any]]:
    """
    Stage 1: 모든 위원회 모델(council models)로부터 개별 응답을 수집합니다.

    🎯 목적: 다양한 AI 모델의 관점을 모으기
    비유: 5명의 전문가에게 동시에 같은 질문을 하는 것

    왜 여러 AI?: 각 AI 모델마다 장단점이 다름
                하나의 AI보다 여러 AI의 의견을 종합하면 더 좋은 답 나옴

    Args:
        user_query: 사용자가 입력한 질문 (예: "파이썬이 뭔가요?")

    Returns:
        각 모델의 답변 리스트
        예시: [
            {"model": "gpt-4", "response": "파이썬은..."},
            {"model": "claude-3", "response": "파이썬은..."},
            ...
        ]
    """
    # 1단계: 질문을 메시지 형식으로 변환
    # AI에게 보내는 표준 형식: [{"role": "user", "content": "질문 내용"}]
    messages = [{"role": "user", "content": user_query}]

    # 2단계: 모든 AI 모델에게 동시에 같은 질문 보내기
    # COUNCIL_MODELS: config.py에 정의된 AI 모델 리스트 (예: 5개 모델)
    # await: 모든 AI가 답변할 때까지 기다림
    # 병렬로 보내는 이유: 순차적으로 하면 5배 더 오래 걸림
    responses = await query_models_parallel(COUNCIL_MODELS, messages)

    # 3단계: 받은 답변들을 정리
    # responses = {"gpt-4": {답변1}, "claude-3": {답변2}, ...} 형태
    stage1_results = []  # 빈 리스트 준비

    # responses.items(): 딕셔너리를 (모델이름, 답변) 쌍으로 순회
    for model, response in responses.items():
        # 답변이 성공적으로 도착한 경우만 처리 (실패한 AI는 제외)
        if response is not None:
            stage1_results.append({
                "model": model,  # AI 모델 이름
                "response": response.get('content', '')  # AI가 작성한 실제 답변 텍스트
            })

    # 4단계: 정리된 답변 리스트 반환
    return stage1_results


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Stage 2: 각 모델이 익명화된 응답들의 순위를 매깁니다.

    🎯 목적: 편견 없는 공정한 평가
    비유: 올림픽 심사위원들이 선수 이름을 모르고 연기만 보고 점수를 주는 것

    핵심 혁신 - 익명 평가:
    - 원래 모델 이름을 숨기고 "Response A", "Response B" 같은 라벨만 보여줌
    - AI들이 서로 누가 썼는지 모르니까 편애할 수 없음
    - 오직 답변의 질만으로 평가하게 됨

    왜 익명으로?: GPT가 Claude 답변이라는 걸 알면 경쟁사라 낮게 평가할 수 있음
                  익명화하면 순수하게 답변의 질만 보고 판단함

    Args:
        user_query: 사용자의 원래 질문
        stage1_results: 1단계에서 받은 각 AI의 답변들

    Returns:
        (각 AI의 평가 내용, 익명 라벨↔모델 이름 매핑표)
    """
    # === 1단계: 익명화 준비 ===
    # 답변들에 A, B, C... 라벨 붙이기
    # chr(65) = 'A', chr(66) = 'B', chr(67) = 'C' ...
    # len(stage1_results)개 만큼의 라벨 생성
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...
    # 예시: stage1_results가 5개면 labels = ['A', 'B', 'C', 'D', 'E']

    # === 2단계: 역방향 매핑표 만들기 ===
    # 나중에 "Response A가 1등이야" → "실제로는 GPT-4가 1등이구나" 알아내기 위함
    # label_to_model = {"Response A": "gpt-4", "Response B": "claude-3", ...}
    label_to_model = {
        f"Response {label}": result['model']
        for label, result in zip(labels, stage1_results)
    }

    # === 3단계: 익명화된 답변 텍스트 만들기 ===
    # AI들에게 보여줄 때는 모델 이름 대신 "Response A", "Response B"만 보여줌
    # "\n\n".join(): 각 답변을 두 줄 띄워서 합침
    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])
    # 결과 예시:
    # Response A:
    # 파이썬은 프로그래밍 언어입니다...
    #
    # Response B:
    # 파이썬은 1991년에 만들어진...
    #
    # ...

    ranking_prompt = f"""당신은 다음 질문에 대한 서로 다른 응답들을 평가해야 합니다:

질문: {user_query}

다음은 서로 다른 모델들의 응답입니다 (익명 처리됨):

{responses_text}

당신의 과제:
1. 먼저 각 응답을 개별적으로 평가하십시오. 각 응답에 대해 장점과 단점을 설명해야 합니다.
2. 그런 다음, 답변의 맨 마지막에 최종 순위를 제공하십시오.

중요: 최종 순위는 반드시 아래 형식을 정확히 따라야 합니다:
- "FINAL RANKING:"이라는 줄로 시작하십시오 (모두 대문자, 콜론 포함).
- 그 다음, 가장 좋은 응답부터 가장 나쁜 응답 순서로 번호를 매겨 나열하십시오.
- 각 줄은 '번호, 마침표, 공백, 그리고 오직 응답 라벨'로만 구성되어야 합니다 (예: "1. Response A").
- 순위 섹션에는 다른 텍스트나 설명을 절대 추가하지 마십시오.

전체 답변의 올바른 형식 예시:

Response A는 X에 대해 자세히 설명하지만 Y를 놓쳤습니다...
Response B는 정확하지만 Z에 대한 깊이가 부족합니다...
Response C는 가장 포괄적인 답변을 제공합니다...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

이제 평가와 순위를 작성해 주십시오:"""

    # === 4단계: 평가 요청 메시지 준비 ===
    # ranking_prompt를 AI에게 보낼 메시지 형식으로 변환
    messages = [{"role": "user", "content": ranking_prompt}]

    # === 5단계: 모든 AI에게 동시에 평가 요청 ===
    # 같은 AI 모델들이 이번엔 평가자 역할을 함
    # 비유: 1단계에서는 "답변자", 2단계에서는 "심사위원"
    responses = await query_models_parallel(COUNCIL_MODELS, messages)

    # === 6단계: 받은 평가들 정리 ===
    stage2_results = []  # 빈 리스트 준비

    # 각 AI의 평가 내용을 순회
    for model, response in responses.items():
        # 평가를 성공적으로 받은 경우만 처리
        if response is not None:
            full_text = response.get('content', '')  # AI가 쓴 전체 평가 텍스트
            # parse_ranking_from_text(): "FINAL RANKING:" 부분에서 순위만 추출하는 함수
            # 예: "1. Response C\n2. Response A..." → ["Response C", "Response A", ...]
            parsed = parse_ranking_from_text(full_text)

            stage2_results.append({
                "model": model,            # 어떤 AI가 평가했는지
                "ranking": full_text,      # AI가 작성한 전체 평가 내용 (장단점 설명 포함)
                "parsed_ranking": parsed   # 순위 부분만 추출한 것 (리스트 형태)
            })

    # === 7단계: 평가 결과와 매핑표 반환 ===
    # label_to_model: 나중에 "Response A = gpt-4"임을 알아내기 위한 매핑표
    return stage2_results, label_to_model


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Stage 3: 의장이 최종 응답을 종합합니다.

    🎯 목적: 모든 정보를 종합해서 최고의 답변 만들기
    비유: 재판장이 증인들의 증언과 변호사들의 의견을 모두 듣고 최종 판결을 내리는 것

    왜 의장이 필요?: 5명의 답변이 다 다르면 사용자가 혼란스러움
                    전문가(의장 AI)가 핵심만 골라서 하나의 명확한 답으로 정리해줌

    의장이 받는 정보:
    - 1단계: 각 AI가 뭐라고 답했는지
    - 2단계: 각 AI가 다른 답변들을 어떻게 평가했는지
    - 위 정보를 보고 어떤 답변이 좋은지, 왜 좋은지 판단 가능

    Args:
        user_query: 사용자의 원래 질문
        stage1_results: 5개 AI의 개별 답변들
        stage2_results: 5개 AI가 작성한 평가 및 순위

    Returns:
        의장이 작성한 최종 종합 답변
    """
    # === 1단계: 의장에게 보여줄 1단계 정보 정리 ===
    # 각 모델의 답변을 보기 좋게 텍스트로 합치기
    # "\n\n".join(): 각 답변 사이에 빈 줄 2개 넣어서 구분
    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {result['response']}"
        for result in stage1_results
    ])
    # 결과 예시:
    # Model: gpt-4
    # Response: 파이썬은...
    #
    # Model: claude-3
    # Response: 파이썬은...

    # === 2단계: 의장에게 보여줄 2단계 정보 정리 ===
    # 각 모델의 평가 내용을 보기 좋게 텍스트로 합치기
    stage2_text = "\n\n".join([
        f"Model: {result['model']}\nRanking: {result['ranking']}"
        for result in stage2_results
    ])
    # 결과 예시:
    # Model: gpt-4
    # Ranking: Response A는 자세하지만... FINAL RANKING: 1. Response C ...
    #
    # Model: claude-3
    # Ranking: Response C가 가장 포괄적... FINAL RANKING: 1. Response C ...

    chairman_prompt = f"""당신은 LLM 위원회의 의장입니다. 여러 AI 모델이 사용자의 질문에 대한 응답을 제공했고, 이후 서로의 응답에 순위를 매겼습니다.

원래 질문: {user_query}

1단계 - 개별 응답:
{stage1_text}

2단계 - 동료 평가 순위:
{stage2_text}

의장으로서 당신의 임무는 이 모든 정보를 종합하여 사용자의 원래 질문에 대한 하나의 포괄적이고 정확한 답변을 만드는 것입니다. 다음 사항을 고려하십시오:
- 개별 응답들과 그들의 통찰력
- 동료 평가 순위와 그것이 응답 품질에 대해 드러내는 것
- 합의 또는 불일치의 패턴

위원회의 집단 지혜를 대표하는 명확하고 논리적인 최종 답변을 제공하십시오:"""

    # === 3단계: 의장에게 보낼 메시지 준비 ===
    messages = [{"role": "user", "content": chairman_prompt}]

    # === 4단계: 의장 AI에게 요청 보내기 ===
    # CHAIRMAN_MODEL: config.py에서 설정한 의장 AI (보통 가장 강력한 모델)
    # query_model(): 단일 AI에게 요청 (병렬 아님, 의장은 1명뿐이니까)
    response = await query_model(CHAIRMAN_MODEL, messages)

    # === 5단계: 의장의 응답 확인 ===
    if response is None:
        # 의장 AI가 실패한 경우 (네트워크 오류, 타임아웃 등)
        # 오류 메시지를 반환해서 사용자에게 알림
        return {
            "model": CHAIRMAN_MODEL,
            "response": "오류: 최종 종합 답변을 생성할 수 없습니다."
        }

    # === 6단계: 의장의 최종 답변 반환 ===
    return {
        "model": CHAIRMAN_MODEL,                    # 누가 답변했는지 (의장)
        "response": response.get('content', '')     # 의장이 작성한 최종 답변 텍스트
    }


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    모델의 응답에서 FINAL RANKING 섹션을 파싱합니다.

    🎯 목적: AI가 쓴 긴 평가 글에서 순위 부분만 깔끔하게 추출하기
    비유: 긴 리포트에서 결론 부분만 찾아서 정리하는 것

    왜 필요?: AI가 "Response A는 좋고... Response B는... FINAL RANKING: 1. Response C..."
             이렇게 길게 쓰는데, 우리는 순위 부분만 필요함

    Args:
        ranking_text: AI가 작성한 전체 평가 텍스트 (장단점 설명 + 순위)

    Returns:
        순위대로 정렬된 리스트 (예: ["Response C", "Response A", "Response B"])
    """
    # re: 정규식(Regular Expression) 모듈 - 텍스트 패턴 찾기 도구
    import re

    # === 1단계: "FINAL RANKING:" 키워드가 있는지 확인 ===
    if "FINAL RANKING:" in ranking_text:
        # === 2단계: "FINAL RANKING:" 이후의 텍스트만 분리 ===
        # split(): 특정 문자열을 기준으로 나누기
        # 예: "설명... FINAL RANKING: 1. Response C..." → ["설명...", " 1. Response C..."]
        parts = ranking_text.split("FINAL RANKING:")

        if len(parts) >= 2:  # "FINAL RANKING:"으로 성공적으로 나눴다면
            ranking_section = parts[1]  # 두 번째 부분 = 순위 섹션

            # === 3단계: 번호가 매겨진 형식 찾기 시도 ===
            # 정규식 패턴 설명: r'\d+\.\s*Response [A-Z]'
            # \d+: 숫자 1개 이상 (1, 2, 3...)
            # \.: 마침표 (.)
            # \s*: 공백 0개 이상
            # Response [A-Z]: "Response" + 대문자 알파벳 (A, B, C...)
            # 예: "1. Response C", "2.Response A" 같은 패턴 찾기
            numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)

            if numbered_matches:
                # 찾았다면 각 매치에서 "Response X" 부분만 추출
                # 예: ["1. Response C", "2. Response A"] → ["Response C", "Response A"]
                return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]

            # === 4단계: 번호 없이 "Response X"만 찾기 (폴백) ===
            # 일부 AI가 형식을 안 지킬 수 있으니 대비
            matches = re.findall(r'Response [A-Z]', ranking_section)
            return matches

    # === 5단계: "FINAL RANKING:"이 없는 경우 전체 텍스트에서 찾기 ===
    # 최후의 폴백: 순서대로 나오는 "Response X" 패턴 추출
    matches = re.findall(r'Response [A-Z]', ranking_text)
    return matches


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    모든 모델에 걸쳐 집계된 순위를 계산합니다.

    🎯 목적: 여러 AI의 평가를 종합해서 "진짜 순위" 계산하기
    비유: 올림픽에서 5명의 심사위원 점수를 평균내서 최종 순위 결정하는 것

    왜 집계가 필요?: 5명의 AI가 각자 다르게 평가할 수 있음
                    GPT-4: "C가 1등, A가 2등..."
                    Claude: "A가 1등, C가 2등..."
                    → 평균을 내면 누가 진짜 좋은 답변인지 알 수 있음

    Args:
        stage2_results: 5개 AI가 각자 매긴 순위들
        label_to_model: "Response A" → "gpt-4" 변환표

    Returns:
        평균 순위가 좋은 순서대로 정렬된 리스트
        예: [{"model": "claude-3", "average_rank": 1.2}, ...]
    """
    # defaultdict: 자동으로 빈 리스트를 만들어주는 딕셔너리
    # 일반 dict는 없는 키에 접근하면 에러, defaultdict는 자동으로 기본값 생성
    from collections import defaultdict

    # === 1단계: 각 모델이 받은 순위들을 모으기 ===
    # model_positions = {"gpt-4": [1, 2, 3, 1, 2], "claude-3": [2, 1, 1, 3, 1], ...}
    model_positions = defaultdict(list)  # 빈 리스트를 기본값으로 하는 딕셔너리

    # === 2단계: 각 AI의 평가를 순회하며 순위 정보 수집 ===
    for ranking in stage2_results:
        ranking_text = ranking['ranking']  # AI가 쓴 전체 평가 텍스트

        # 평가 텍스트에서 순위 부분만 추출
        # 예: "Response C가 좋고... FINAL RANKING: 1. Response C..." → ["Response C", "Response A", ...]
        parsed_ranking = parse_ranking_from_text(ranking_text)

        # enumerate(리스트, start=1): 리스트를 (번호, 값) 쌍으로 만듦
        # 예: ["Response C", "Response A"] → [(1, "Response C"), (2, "Response A")]
        for position, label in enumerate(parsed_ranking, start=1):
            # label_to_model에 해당 라벨이 있는지 확인 (안전장치)
            if label in label_to_model:
                # "Response C" → "gpt-4" 같이 실제 모델 이름으로 변환
                model_name = label_to_model[label]
                # 해당 모델이 받은 순위를 기록
                # 예: gpt-4가 1등을 받았으면 model_positions["gpt-4"]에 1 추가
                model_positions[model_name].append(position)

    # === 3단계: 각 모델의 평균 순위 계산 ===
    aggregate = []  # 결과를 담을 빈 리스트

    # model_positions.items(): (모델이름, [순위들]) 쌍으로 순회
    for model, positions in model_positions.items():
        if positions:  # 순위 정보가 있는 경우만 처리
            # 평균 계산: 모든 순위를 더하고 개수로 나눔
            # 예: [1, 2, 3, 1, 2] → (1+2+3+1+2) / 5 = 1.8
            avg_rank = sum(positions) / len(positions)

            aggregate.append({
                "model": model,                          # 모델 이름
                "average_rank": round(avg_rank, 2),      # 평균 순위 (소수점 2자리)
                "rankings_count": len(positions)         # 몇 명이 평가했는지
            })

    # === 4단계: 평균 순위로 정렬 (낮을수록 좋음) ===
    # 1.2 평균이 2.5 평균보다 좋음 → 낮은 숫자가 앞으로
    # key=lambda x: x['average_rank']: average_rank 필드를 기준으로 정렬
    aggregate.sort(key=lambda x: x['average_rank'])

    # === 5단계: 정렬된 결과 반환 ===
    return aggregate


async def generate_conversation_title(user_query: str) -> str:
    """
    첫 사용자 메시지를 기반으로 대화에 대한 짧은 제목을 생성합니다.

    🎯 목적: 대화 목록에서 쉽게 찾을 수 있도록 간단한 제목 만들기
    비유: 이메일의 제목처럼 대화 내용을 한눈에 알아볼 수 있게 요약

    왜 필요?: "새 대화"라는 제목만 있으면 나중에 어떤 대화인지 모름
              "파이썬 설명 요청", "React 에러 해결" 같은 제목이 훨씬 유용함

    왜 gemini-flash 사용?: 제목은 간단한 작업이라 빠르고 저렴한 모델로 충분
                          위원회 모델들은 복잡한 답변용으로 남겨둠

    Args:
        user_query: 첫 사용자 메시지 (예: "파이썬이 뭔가요?")

    Returns:
        짧은 제목 (예: "파이썬 설명 요청")
    """
    # === 1단계: 제목 생성 요청 프롬프트 작성 ===
    # AI에게 "3-5 단어로 짧게, 따옴표 없이" 같은 규칙을 명확히 알려줌
    title_prompt = f"""다음 질문을 요약하는 매우 짧은 제목(최대 3-5 단어)을 생성하십시오.
제목은 간결하고 설명적이어야 합니다. 제목에 따옴표나 구두점을 사용하지 마십시오.

질문: {user_query}

제목:"""

    # === 2단계: AI에게 보낼 메시지 형식으로 변환 ===
    messages = [{"role": "user", "content": title_prompt}]

    # === 3단계: 빠른 AI 모델에게 제목 생성 요청 ===
    # google/gemini-2.5-flash: 빠르고 저렴한 모델 (제목 정도는 충분히 처리 가능)
    # timeout=30.0: 30초 안에 응답 안 오면 포기 (제목은 빨리 만들어져야 함)
    response = await query_model("google/gemini-2.5-flash", messages, timeout=30.0)

    # === 4단계: 응답 실패 시 기본값 반환 ===
    if response is None:
        # AI가 실패하면 그냥 "새 대화"라고 표시 (문제 없음, 나중에 수동으로 바꿀 수 있음)
        return "새 대화"

    # === 5단계: AI가 생성한 제목 가져오기 ===
    # get('content', '새 대화'): content 필드 가져오되, 없으면 '새 대화' 기본값
    # strip(): 앞뒤 공백 제거
    title = response.get('content', '새 대화').strip()

    # === 6단계: 제목 정리 - 따옴표 제거 ===
    # AI가 가끔 "파이썬 설명" 이렇게 따옴표를 넣는 경우가 있음
    # strip('"\''):  앞뒤의 큰따옴표(")와 작은따옴표(') 모두 제거
    title = title.strip('"\'')

    # === 7단계: 너무 길면 자르기 ===
    # UI에서 제목이 너무 길면 화면을 벗어날 수 있음
    # 50자 넘으면 47자까지만 남기고 "..." 붙임
    if len(title) > 50:
        title = title[:47] + "..."

    # === 8단계: 최종 제목 반환 ===
    return title


async def run_full_council(user_query: str) -> Tuple[List, List, Dict, Dict]:
    """
    완전한 3단계 위원회 프로세스를 실행합니다.

    🎯 목적: 전체 LLM Council 시스템을 하나의 함수로 실행
    비유: 오케스트라 지휘자처럼 모든 단계를 조율하고 최종 결과를 내놓음

    왜 이 함수가 필요?: 1단계, 2단계, 3단계를 각각 따로 호출하면 복잡함
                       이 함수 하나만 호출하면 전체 프로세스가 자동으로 진행됨

    전체 흐름 요약:
    1. 5개 AI에게 질문 → 5개 답변 받음
    2. 5개 AI가 서로 평가 → 순위표 5개 받음
    3. 순위 평균 계산 → 누가 제일 좋은 답변인지 파악
    4. 의장이 모든 정보 보고 최종 답변 작성
    5. 모든 결과를 프론트엔드로 보냄

    Args:
        user_query: 사용자의 질문 (예: "파이썬이 뭔가요?")

    Returns:
        4개 항목 튜플:
        - stage1_results: 5개 AI의 개별 답변
        - stage2_results: 5개 AI의 평가 및 순위
        - stage3_result: 의장의 최종 종합 답변
        - metadata: 추가 정보 (익명화 매핑, 집계 순위)
    """
    # === 1단계: 개별 응답 수집 ===
    # 5개 AI 모델에게 동시에 질문을 보내고 각자의 답변을 받음
    # 비유: 5명의 전문가에게 동시에 질문지를 보내는 것
    stage1_results = await stage1_collect_responses(user_query)

    # === 안전장치: 모든 AI가 실패한 경우 처리 ===
    # 네트워크 오류, API 키 문제 등으로 모든 AI가 응답 못 할 수 있음
    if not stage1_results:
        # 빈 결과와 오류 메시지를 반환해서 사용자에게 알림
        return [], [], {
            "model": "error",
            "response": "모든 모델이 응답에 실패했습니다. 다시 시도해 주십시오."
        }, {}

    # === 2단계: 순위 수집 ===
    # 각 AI가 다른 AI들의 답변을 익명으로 평가하고 순위를 매김
    # 비유: 5명의 전문가가 서로의 답변을 모르는 상태에서 채점하는 것
    # 반환값 2개:
    # - stage2_results: 각 AI가 작성한 평가 내용
    # - label_to_model: "Response A" = "gpt-4" 같은 변환표
    stage2_results, label_to_model = await stage2_collect_rankings(user_query, stage1_results)

    # === 집계된 순위 계산 ===
    # 5명의 심사위원 점수를 평균내서 최종 순위 결정
    # 예: GPT-4가 [1등, 2등, 1등, 3등, 1등] 받았으면 평균 1.6등
    #     Claude가 [2등, 1등, 2등, 1등, 2등] 받았으면 평균 1.6등
    # → 평균이 낮을수록 좋은 답변
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)

    # === 3단계: 최종 답변 종합 ===
    # 의장 AI가 모든 정보를 보고 하나의 완전한 답변으로 종합
    # 의장이 보는 정보:
    # - stage1_results: 각 AI가 뭐라고 답했는지
    # - stage2_results: 각 AI가 다른 답변을 어떻게 평가했는지
    # 비유: 재판장이 증인들의 증언과 변호사들의 의견을 모두 듣고 판결 내리는 것
    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results
    )

    # === 메타데이터 준비 ===
    # 프론트엔드에서 UI를 그릴 때 필요한 추가 정보
    # - label_to_model: "Response A"가 실제로 어떤 AI인지 보여주기 위함
    # - aggregate_rankings: 평균 순위를 표시하기 위함
    metadata = {
        "label_to_model": label_to_model,          # {"Response A": "gpt-4", ...}
        "aggregate_rankings": aggregate_rankings    # [{"model": "claude", "average_rank": 1.2}, ...]
    }

    # === 최종 결과 반환 ===
    # 4개 항목을 튜플로 묶어서 반환
    # main.py가 이 결과를 받아서 프론트엔드로 전달함
    return stage1_results, stage2_results, stage3_result, metadata
