"""LLM Council을 위한 FastAPI 백엔드."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import uuid
import json
import asyncio

from . import storage
from .council import run_full_council, generate_conversation_title, stage1_collect_responses, stage2_collect_rankings, stage3_synthesize_final, calculate_aggregate_rankings

app = FastAPI(title="LLM Council API")

# 로컬 개발을 위한 CORS 활성화
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateConversationRequest(BaseModel):
    """새 대화를 생성하는 요청."""
    pass


class SendMessageRequest(BaseModel):
    """대화에서 메시지를 보내는 요청."""
    content: str


class ConversationMetadata(BaseModel):
    """목록 보기를 위한 대화 메타데이터."""
    id: str
    created_at: str
    title: str
    message_count: int


class Conversation(BaseModel):
    """모든 메시지를 포함하는 전체 대화."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]


@app.get("/")
async def root():
    """헬스 체크 엔드포인트."""
    return {"status": "ok", "service": "LLM Council API"}


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """모든 대화 목록 조회 (메타데이터만)."""
    return storage.list_conversations()


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """새 대화를 생성합니다."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id)
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """모든 메시지를 포함한 특정 대화를 가져옵니다."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")
    return conversation


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    메시지를 보내고 3단계 위원회 프로세스를 실행합니다.
    모든 단계를 포함한 완전한 응답을 반환합니다.
    """
    # 대화가 존재하는지 확인
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")

    # 첫 번째 메시지인지 확인
    is_first_message = len(conversation["messages"]) == 0

    # 사용자 메시지 추가
    storage.add_user_message(conversation_id, request.content)

    # 첫 번째 메시지인 경우 제목 생성
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    # 3단계 위원회 프로세스 실행
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        request.content
    )

    # 모든 단계를 포함한 어시스턴트 메시지 추가
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result
    )

    # 메타데이터를 포함한 완전한 응답 반환
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    메시지를 보내고 3단계 위원회 프로세스를 스트리밍합니다.
    각 단계가 완료될 때마다 Server-Sent Events를 반환합니다.
    """
    # 대화가 존재하는지 확인
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")

    # 첫 번째 메시지인지 확인
    is_first_message = len(conversation["messages"]) == 0

    async def event_generator():
        try:
            # 사용자 메시지 추가
            storage.add_user_message(conversation_id, request.content)

            # 병렬로 제목 생성 시작 (아직 await하지 않음)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # 1단계: 응답 수집
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = await stage1_collect_responses(request.content)
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # 2단계: 순위 수집
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_model = await stage2_collect_rankings(request.content, stage1_results)
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # 3단계: 최종 답변 종합
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(request.content, stage1_results, stage2_results)
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # 제목 생성이 시작되었으면 대기
            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # 완전한 어시스턴트 메시지 저장
            storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result
            )

            # 완료 이벤트 전송
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # 오류 이벤트 전송
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
