"""대화를 위한 JSON 기반 저장소.

이 파일은 사용자와 AI의 대화를 파일로 저장하고 불러오는 역할을 합니다.
마치 도서관 사서가 책을 보관하고 찾아주는 것처럼, 대화 내용을 관리합니다.

저장 방식: JSON 파일 형식으로 data/conversations/ 폴더에 저장
각 대화는 고유 ID를 가진 별도의 파일로 저장됩니다.
"""

# json: JSON 형식의 데이터를 읽고 쓰는 도구 (데이터를 텍스트 파일로 저장)
import json
# os: 운영체제(윈도우, 맥 등)와 상호작용하는 도구 (파일 경로, 폴더 만들기 등)
import os
# datetime: 날짜와 시간을 다루는 도구
from datetime import datetime
# typing: 데이터 타입을 명시하는 도구
from typing import List, Dict, Any, Optional
# Path: 파일 경로를 다루는 현대적인 도구
from pathlib import Path
# config에서 데이터를 저장할 폴더 경로를 가져옴
from .config import DATA_DIR


def ensure_data_dir():
    """
    데이터 디렉토리가 존재하는지 확인합니다.

    쉽게 말해: 대화를 저장할 폴더가 있는지 확인하고, 없으면 만드는 함수
    비유: 책을 보관할 서랍이 있는지 확인하고, 없으면 새로 만드는 것
    """
    # Path(DATA_DIR): 폴더 경로 객체 생성
    # mkdir(): 폴더 만들기
    # parents=True: 중간 폴더들도 자동으로 만들어줌 (예: a/b/c를 만들 때 a, b도 자동 생성)
    # exist_ok=True: 이미 폴더가 있어도 오류 안 나고 무시함
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def get_conversation_path(conversation_id: str) -> str:
    """
    대화의 파일 경로를 가져옵니다.

    쉽게 말해: 특정 대화가 저장된 파일의 전체 경로(주소)를 알려주는 함수
    비유: 도서관에서 특정 책이 어느 서랍 몇 번에 있는지 알려주는 것

    Args:
        conversation_id: 대화의 고유 ID (예: "abc-123-def-456")

    Returns:
        파일 전체 경로 (예: "data/conversations/abc-123-def-456.json")
    """
    # os.path.join(): 폴더 경로와 파일 이름을 운영체제에 맞게 합침
    # 윈도우: data\conversations\abc-123.json
    # 맥/리눅스: data/conversations/abc-123.json
    # f"{conversation_id}.json": conversation_id에 .json을 붙여서 파일 이름 만들기
    return os.path.join(DATA_DIR, f"{conversation_id}.json")


def create_conversation(conversation_id: str) -> Dict[str, Any]:
    """
    새 대화를 생성합니다.

    쉽게 말해: 새로운 대화방을 만들고 빈 노트를 준비하는 함수
    비유: 새 공책을 펴서 첫 페이지에 날짜와 제목을 적어두는 것

    Args:
        conversation_id: 대화의 고유 식별자 (UUID 형식, 절대 겹치지 않는 랜덤 ID)

    Returns:
        새로 만든 대화 정보 (ID, 생성 시간, 제목, 빈 메시지 리스트)
    """
    # 1단계: 저장할 폴더가 있는지 확인 (없으면 만들기)
    ensure_data_dir()

    # 2단계: 새 대화의 기본 구조 만들기
    conversation = {
        "id": conversation_id,  # 대화 고유 ID
        "created_at": datetime.utcnow().isoformat(),  # 현재 시간을 ISO 형식 문자열로 (예: "2025-01-15T10:30:00")
        "title": "새 대화",  # 기본 제목 (나중에 첫 질문 기반으로 자동 생성)
        "messages": []  # 메시지를 담을 빈 리스트 (아직 대화 시작 전)
    }

    # 3단계: 파일로 저장
    path = get_conversation_path(conversation_id)  # 저장할 파일 경로 가져오기
    # with open(): 파일을 열고 작업 후 자동으로 닫음
    # 'w': write 모드 = 쓰기 모드 (파일이 없으면 새로 만들고, 있으면 덮어씀)
    # as f: 열린 파일을 f라는 이름으로 사용
    with open(path, 'w', encoding='utf-8') as f:
        # json.dump(): Python 딕셔너리를 JSON 형식으로 파일에 저장
        # indent=2: 들여쓰기를 2칸씩 해서 사람이 읽기 좋게 저장
        # ensure_ascii=False: 한글 등 유니코드 문자를 그대로 저장
        json.dump(conversation, f, indent=2, ensure_ascii=False)

    # 4단계: 만든 대화 정보를 반환
    return conversation


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    저장소에서 대화를 로드합니다.

    쉽게 말해: 저장된 대화 파일을 찾아서 내용을 읽어오는 함수
    비유: 도서관에서 특정 번호의 책을 찾아서 내용을 펴보는 것

    Args:
        conversation_id: 찾을 대화의 고유 ID

    Returns:
        대화 내용 전체 (ID, 제목, 메시지들), 파일이 없으면 None
    """
    # 1단계: 파일 경로 확인
    path = get_conversation_path(conversation_id)

    # 2단계: 파일이 실제로 존재하는지 확인
    # os.path.exists(): 파일/폴더가 있는지 True/False로 반환
    if not os.path.exists(path):
        # 파일이 없으면 None 반환 (대화를 찾을 수 없음)
        return None

    # 3단계: 파일 읽기
    # 'r': read 모드 = 읽기 모드
    with open(path, 'r', encoding='utf-8') as f:
        # json.load(): JSON 파일을 읽어서 Python 딕셔너리로 변환
        return json.load(f)


def save_conversation(conversation: Dict[str, Any]):
    """
    대화를 저장소에 저장합니다.

    쉽게 말해: 수정된 대화 내용을 파일에 다시 저장하는 함수
    비유: 공책에 메모를 추가하고 서랍에 다시 보관하는 것

    Args:
        conversation: 저장할 대화 전체 (ID, 제목, 메시지들 포함)
    """
    # 1단계: 저장할 폴더가 있는지 확인
    ensure_data_dir()

    # 2단계: 파일 경로 가져오기 (대화 ID로부터)
    path = get_conversation_path(conversation['id'])

    # 3단계: 파일에 저장
    # 'w': write 모드 = 쓰기 모드 (기존 내용 덮어쓰기)
    with open(path, 'w', encoding='utf-8') as f:
        # conversation 딕셔너리를 JSON 형식으로 파일에 저장
        # indent=2: 들여쓰기로 읽기 좋게
        # ensure_ascii=False: 한글 그대로 저장
        json.dump(conversation, f, indent=2, ensure_ascii=False)


def list_conversations() -> List[Dict[str, Any]]:
    """
    모든 대화 목록을 조회합니다 (메타데이터만).

    쉽게 말해: 저장된 모든 대화의 목록을 가져오는 함수 (대화 내용은 제외, 요약 정보만)
    비유: 도서관에서 모든 책의 목록(제목, 날짜, 페이지 수)만 보여주는 것

    왜 메타데이터만?: 전체 대화를 다 읽으면 느리고 메모리 많이 사용
                    목록 화면에는 제목, 날짜, 메시지 개수만 있으면 충분

    Returns:
        대화 요약 정보 리스트 (각각 ID, 생성일, 제목, 메시지 개수 포함)
    """
    # 1단계: 데이터 폴더가 있는지 확인
    ensure_data_dir()

    # 2단계: 빈 리스트 준비 (여기에 대화 정보들을 담을 것)
    conversations = []

    # 3단계: 데이터 폴더의 모든 파일 확인
    # os.listdir(): 폴더 안의 모든 파일/폴더 이름 리스트로 반환
    for filename in os.listdir(DATA_DIR):
        # .json으로 끝나는 파일만 처리 (대화 파일만)
        if filename.endswith('.json'):
            # 파일 전체 경로 만들기
            path = os.path.join(DATA_DIR, filename)

            # 파일 열어서 읽기
            with open(path, 'r', encoding='utf-8') as f:
                # JSON 파일 내용을 딕셔너리로 변환
                data = json.load(f)

                # 메타데이터만 추출해서 리스트에 추가
                # data.get("title", "새 대화"): title이 없으면 "새 대화"를 기본값으로 사용
                conversations.append({
                    "id": data["id"],                          # 대화 고유 ID
                    "created_at": data["created_at"],          # 생성 날짜/시간
                    "title": data.get("title", "새 대화"),     # 대화 제목
                    "message_count": len(data["messages"])    # 메시지 개수 (len = 리스트 길이)
                })

    # 4단계: 생성 시간으로 정렬 (최신 대화가 먼저 오도록)
    # key=lambda x: x["created_at"]: 정렬 기준은 created_at 필드
    # reverse=True: 역순 정렬 (최신이 먼저)
    conversations.sort(key=lambda x: x["created_at"], reverse=True)

    # 5단계: 정렬된 목록 반환
    return conversations


def add_user_message(conversation_id: str, content: str):
    """
    대화에 사용자 메시지를 추가합니다.

    쉽게 말해: 사용자가 입력한 질문을 대화 기록에 추가하는 함수
    비유: 공책에 "질문: 파이썬이 뭔가요?" 라고 적는 것

    Args:
        conversation_id: 어느 대화에 추가할지 (대화 ID)
        content: 사용자가 입력한 질문/메시지 내용
    """
    # 1단계: 대화 파일 불러오기
    conversation = get_conversation(conversation_id)
    # 대화가 없으면 에러 발생 (존재하지 않는 대화에는 메시지를 추가할 수 없음)
    if conversation is None:
        raise ValueError(f"대화 {conversation_id}를 찾을 수 없습니다")

    # 2단계: 메시지 리스트에 사용자 메시지 추가
    conversation["messages"].append({
        "role": "user",       # 역할: 사용자
        "content": content    # 내용: 사용자가 입력한 텍스트
    })

    # 3단계: 수정된 대화를 파일에 다시 저장
    save_conversation(conversation)


def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any]
):
    """
    대화에 모든 3단계를 포함한 어시스턴트 메시지를 추가합니다.

    쉽게 말해: AI 위원회의 답변(1단계~3단계 모두)을 대화 기록에 추가하는 함수
    비유: 공책에 "답변: [5명 AI 답변] → [평가 결과] → [최종 답변]" 을 모두 적는 것

    왜 3단계를 모두 저장?: 나중에 어떤 AI가 뭐라고 했는지, 어떻게 평가했는지 다시 볼 수 있도록

    Args:
        conversation_id: 어느 대화에 추가할지
        stage1: 1단계 - 5개 AI 모델의 개별 답변들
        stage2: 2단계 - 각 AI가 다른 AI들을 평가한 순위들
        stage3: 3단계 - 의장 AI가 종합한 최종 답변
    """
    # 1단계: 대화 파일 불러오기
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"대화 {conversation_id}를 찾을 수 없습니다")

    # 2단계: 메시지 리스트에 어시스턴트(AI) 메시지 추가
    conversation["messages"].append({
        "role": "assistant",  # 역할: AI 어시스턴트
        "stage1": stage1,     # 1단계 결과 (개별 답변들)
        "stage2": stage2,     # 2단계 결과 (평가 및 순위)
        "stage3": stage3      # 3단계 결과 (최종 종합 답변)
    })

    # 3단계: 수정된 대화를 파일에 다시 저장
    save_conversation(conversation)


def update_conversation_title(conversation_id: str, title: str):
    """
    대화의 제목을 업데이트합니다.

    쉽게 말해: 대화의 제목을 바꾸는 함수
    비유: 공책 표지에 적힌 제목을 지우고 새로 쓰는 것

    언제 사용?: 첫 번째 질문을 보고 AI가 자동으로 제목을 생성했을 때
              "새 대화" → "파이썬 설명 요청" 같이 바뀜

    Args:
        conversation_id: 어느 대화의 제목을 바꿀지
        title: 새로운 제목
    """
    # 1단계: 대화 파일 불러오기
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"대화 {conversation_id}를 찾을 수 없습니다")

    # 2단계: 제목 필드 업데이트
    conversation["title"] = title

    # 3단계: 수정된 대화를 파일에 다시 저장
    save_conversation(conversation)
