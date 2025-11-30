"""LLM 요청을 위한 OpenRouter API 클라이언트.

이 파일은 OpenRouter라는 서비스를 통해 다양한 AI 모델(GPT, Claude 등)과
통신하는 역할을 합니다. 마치 여러 AI 모델에게 질문을 보내고 답변을 받는
우체부 같은 역할입니다.
"""

# httpx: 인터넷을 통해 다른 서버와 통신하는 도구 (HTTP 요청을 보내는 라이브러리)
import httpx
# typing: 변수나 함수가 어떤 타입(종류)의 데이터를 다루는지 명시하는 도구
from typing import List, Dict, Any, Optional
# config에서 API 키와 URL을 가져옴 (비밀번호와 주소 같은 것)
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    OpenRouter API를 통해 단일 모델에 쿼리합니다.

    쉽게 말해: 한 명의 AI에게 질문을 보내고 답변을 받는 함수
    비유: 특정 전문가에게 편지를 보내고 답장을 기다리는 것

    Args:
        model: 어떤 AI 모델을 사용할지 (예: "openai/gpt-4o", "anthropic/claude-3.5-sonnet")
        messages: AI에게 보낼 대화 내용 (사용자 질문 등)
        timeout: 답변을 기다리는 최대 시간 (초 단위, 기본 120초 = 2분)

    Returns:
        AI의 답변 내용, 실패하면 None
    """
    # 1단계: 인증 정보 준비 (신분증 제시하듯이)
    # Authorization: API 키를 이용한 인증 (출입증 같은 것)
    # Content-Type: 우리가 JSON 형식으로 데이터를 보낸다고 알려줌
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",  # "Bearer"는 토큰 방식 인증을 의미
        "Content-Type": "application/json",  # JSON = 데이터를 주고받는 표준 형식
    }

    # 2단계: 보낼 데이터 준비 (편지 내용 작성)
    payload = {
        "model": model,        # 어떤 AI 모델을 사용할지
        "messages": messages,  # 실제 대화 내용 (질문 등)
    }

    # 3단계: 실제 요청 보내기 (편지 발송)
    try:
        # async with: 인터넷 연결을 열고 작업 후 자동으로 닫음 (문 열고 나가면 자동으로 닫히는 것처럼)
        # AsyncClient: 비동기 방식으로 인터넷 요청을 보내는 도구 (여러 작업을 동시에 할 수 있게 해줌)
        async with httpx.AsyncClient(timeout=timeout) as client:
            # POST 요청: 서버에 데이터를 보내는 방식 (편지를 보내는 것)
            response = await client.post(
                OPENROUTER_API_URL,  # 어디로 보낼지 (주소)
                headers=headers,     # 인증 정보
                json=payload         # 보낼 내용
            )
            # raise_for_status(): 에러가 있으면 예외를 발생시킴 (문제가 있으면 즉시 알림)
            response.raise_for_status()

            # 4단계: 받은 응답 처리 (답장 읽기)
            # JSON 형식의 응답을 Python 딕셔너리로 변환
            data = response.json()
            # OpenRouter API는 'choices' 배열의 첫 번째 항목에 실제 답변이 들어있음
            message = data['choices'][0]['message']

            # 5단계: 필요한 정보만 추출해서 반환
            return {
                'content': message.get('content'),  # AI가 작성한 실제 답변 텍스트
                'reasoning_details': message.get('reasoning_details')  # 일부 모델이 제공하는 사고 과정 (선택사항)
            }

    # 예외 처리: 오류가 발생하면 (편지가 안 가거나, 답장이 안 오거나)
    except Exception as e:
        # 어떤 모델에서 무슨 오류가 났는지 출력 (디버깅용)
        print(f"모델 {model} 쿼리 중 오류 발생: {e}")
        # None을 반환 = "답변을 못 받았어요"라는 의미
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    여러 모델에 병렬로 쿼리합니다.

    쉽게 말해: 여러 명의 AI에게 동시에 같은 질문을 보내고 각자의 답변을 받는 함수
    비유: 여러 전문가에게 동시에 편지를 보내고 모든 답장을 기다리는 것

    왜 병렬로?: 한 명씩 순서대로 물어보면 시간이 오래 걸림
                5명에게 물어보면 순차적으로는 10분, 병렬로는 2분 정도 소요
                (각 AI가 2분 걸린다고 가정)

    Args:
        models: 사용할 AI 모델들의 이름 리스트 (예: ["gpt-4", "claude-3", "gemini-pro"])
        messages: 모든 모델에게 보낼 같은 질문/메시지

    Returns:
        각 모델의 이름과 그 모델의 답변을 짝지은 딕셔너리
        예시: {"gpt-4": {답변1}, "claude-3": {답변2}, "gemini-pro": None}
              (gemini-pro는 실패한 경우)
    """
    # asyncio: 비동기 작업을 관리하는 도구 (여러 일을 동시에 처리)
    import asyncio

    # 1단계: 각 모델에 대한 작업(task)을 만듦
    # query_model을 각 모델마다 실행하는 작업 목록 생성
    # 비유: 각 전문가에게 보낼 편지를 준비하는 것
    tasks = [query_model(model, messages) for model in models]
    # 예시: models = ["gpt-4", "claude-3"]이면
    #       tasks = [query_model("gpt-4", messages), query_model("claude-3", messages)]

    # 2단계: 모든 작업을 동시에 시작하고 모두 끝날 때까지 기다림
    # asyncio.gather(): 여러 비동기 작업을 동시에 실행하고 모든 결과를 모아줌
    # *tasks: tasks 리스트의 각 항목을 개별 인자로 전달 (리스트를 풀어서 전달)
    # await: 모든 작업이 완료될 때까지 기다림
    # 비유: 우체부가 모든 답장이 올 때까지 기다리는 것
    responses = await asyncio.gather(*tasks)
    # responses = [답변1, 답변2, None, 답변4, ...]  (순서는 models 순서와 동일)

    # 3단계: 모델 이름과 그 모델의 답변을 짝지어서 딕셔너리로 만듦
    # zip(): 두 리스트의 같은 위치 항목끼리 짝지음
    # 예시: models = ["gpt-4", "claude-3"]
    #       responses = [{답변1}, {답변2}]
    #       결과 = {"gpt-4": {답변1}, "claude-3": {답변2}}
    return {model: response for model, response in zip(models, responses)}
