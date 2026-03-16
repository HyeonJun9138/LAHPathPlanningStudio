"""AI assistant API endpoint — proxies requests to OpenAI GPT.

Provides a single POST endpoint ``/api/ai/chat`` that accepts a user
message and an active-tab identifier, prepends a tab-specific system
prompt (in Korean), and streams the response back from the OpenAI API.
"""

from __future__ import annotations

import os
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/ai", tags=["ai"])

# ---------------------------------------------------------------------------
# OpenAI configuration
# ---------------------------------------------------------------------------
OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY",
    "sk-proj-placeholder-key",
)
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4.1-mini"


# ---------------------------------------------------------------------------
# Tab-specific system prompts (Korean)
# ---------------------------------------------------------------------------
TAB_PROMPTS: dict[str, str] = {
    "dashboard": (
        "당신은 LAH 경로계획 연구 플랫폼의 AI 어시스턴트입니다. "
        "현재 사용자는 대시보드 탭에 있습니다. "
        "프로젝트 현황, 학습 진행도, 주요 메트릭 요약을 도와주세요. "
        "한국어로 답변하세요."
    ),
    "resources": (
        "당신은 LAH 경로계획 연구 플랫폼의 AI 어시스턴트입니다. "
        "현재 사용자는 리소스 관리 탭에 있습니다. "
        "GPU/CPU 사용량, 메모리 관리, 학습 리소스 최적화를 도와주세요. "
        "한국어로 답변하세요."
    ),
    "terrain": (
        "당신은 LAH 경로계획 연구 플랫폼의 AI 어시스턴트입니다. "
        "현재 사용자는 지형 분석 탭에 있습니다. "
        "DEM 데이터, 경사도, 거칠기, 곡률 등 지형 파생 데이터 분석을 도와주세요. "
        "한국어로 답변하세요."
    ),
    "hazard": (
        "당신은 LAH 경로계획 연구 플랫폼의 AI 어시스턴트입니다. "
        "현재 사용자는 위협 분석 탭에 있습니다. "
        "위협 배치, 탐지 확률, 위험 지도 생성 및 분석을 도와주세요. "
        "한국어로 답변하세요."
    ),
    "mission": (
        "당신은 LAH 경로계획 연구 플랫폼의 AI 어시스턴트입니다. "
        "현재 사용자는 임무 설정 탭에 있습니다. "
        "출발점/목표점 설정, 관측 박스, 안전 대기점, 대체 착륙장 설정을 도와주세요. "
        "한국어로 답변하세요."
    ),
    "candidate": (
        "당신은 LAH 경로계획 연구 플랫폼의 AI 어시스턴트입니다. "
        "현재 사용자는 후보 경유점 탭에 있습니다. "
        "후보 생성 전략, 프리미티브 유형, 특성 벡터 분석을 도와주세요. "
        "한국어로 답변하세요."
    ),
    "training": (
        "당신은 LAH 경로계획 연구 플랫폼의 AI 어시스턴트입니다. "
        "현재 사용자는 학습 탭에 있습니다. "
        "PPO 하이퍼파라미터, 보상 설계, 학습 곡선 분석, 커리큘럼 학습을 도와주세요. "
        "한국어로 답변하세요."
    ),
    "evaluation": (
        "당신은 LAH 경로계획 연구 플랫폼의 AI 어시스턴트입니다. "
        "현재 사용자는 평가 탭에 있습니다. "
        "성공률, 경로 길이, 위험 노출, 추론 지연시간 등 평가 메트릭을 도와주세요. "
        "한국어로 답변하세요."
    ),
    "simulation": (
        "당신은 LAH 경로계획 연구 플랫폼의 AI 어시스턴트입니다. "
        "현재 사용자는 시뮬레이션 탭에 있습니다. "
        "에피소드 재생, 경로 시각화, 3D 뷰 분석을 도와주세요. "
        "한국어로 답변하세요."
    ),
    "compare": (
        "당신은 LAH 경로계획 연구 플랫폼의 AI 어시스턴트입니다. "
        "현재 사용자는 비교 분석 탭에 있습니다. "
        "모델 간 성능 비교, A* 베이스라인 대비 분석, 통계적 유의성 검정을 도와주세요. "
        "한국어로 답변하세요."
    ),
    "reports": (
        "당신은 LAH 경로계획 연구 플랫폼의 AI 어시스턴트입니다. "
        "현재 사용자는 보고서 탭에 있습니다. "
        "연구 보고서 작성, 결과 요약, 차트 해석을 도와주세요. "
        "한국어로 답변하세요."
    ),
    "settings": (
        "당신은 LAH 경로계획 연구 플랫폼의 AI 어시스턴트입니다. "
        "현재 사용자는 설정 탭에 있습니다. "
        "시스템 설정, 환경 구성, API 키 관리를 도와주세요. "
        "한국어로 답변하세요."
    ),
}

DEFAULT_SYSTEM_PROMPT = (
    "당신은 LAH 경로계획 연구 플랫폼의 AI 어시스턴트입니다. "
    "지형 기반 경로계획, 강화학습, 군용 헬기 임무계획에 대해 도와주세요. "
    "한국어로 답변하세요."
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Incoming chat message from the frontend."""
    message: str
    active_tab: str = "dashboard"
    conversation_history: list[dict] = []


class ChatResponse(BaseModel):
    """Response returned to the frontend."""
    response: str
    model: str = DEFAULT_MODEL
    usage: Optional[dict] = None


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse)
async def chat_with_ai(request: ChatRequest) -> ChatResponse:
    """Proxy a chat message to OpenAI and return the assistant reply."""
    system_prompt = TAB_PROMPTS.get(request.active_tab, DEFAULT_SYSTEM_PROMPT)

    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    # Append conversation history (last 10 turns max)
    for msg in request.conversation_history[-10:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": request.message})

    payload = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "max_tokens": 2000,
        "temperature": 0.7,
    }

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                OPENAI_API_URL,
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        assistant_message = data["choices"][0]["message"]["content"]
        usage = data.get("usage")

        return ChatResponse(
            response=assistant_message,
            model=DEFAULT_MODEL,
            usage=usage,
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"OpenAI API error: {exc.response.text}",
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to OpenAI API: {exc}",
        )
    except (KeyError, IndexError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unexpected OpenAI response format: {exc}",
        )
