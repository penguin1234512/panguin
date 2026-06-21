import os
import httpx
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

# Python 3.14 호환 및 Render 프록시 네트워크 우회를 위한 커스텀 클라이언트 세팅
custom_http_client = httpx.Client(
    proxy=os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY") or None
)

# Render의 Environment(환경변수)에 등록해 둔 OPENAI_API_KEY를 자동으로 읽어옵니다.
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    http_client=custom_http_client
)

def kakao_text(text):
    """카카오톡 말풍선 규격에 맞게 텍스트 포맷팅 (1000자 초과 방지)"""
    safe_text = text[:950] + "..." if len(text) > 950 else text
    return {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": safe_text}}]
        }
    }

@app.route("/", methods=["GET"])
def home():
    return "History AI Server is running!"


# 카카오 오픈빌더 스킬과 연결되는 메인 주소 (URL 끝에 /history-ai 입력)
@app.route("/history-ai", methods=["POST"])
def history_ai():
    data = request.get_json(silent=True) or {}
    
    # 1. 오픈빌더 파라미터(history_event)에서 검색 키워드 추출
    params = data.get("action", {}).get("params", {})
    event_name = params.get("history_event", "").strip()

    # 2. 만약 파라미터 주머니가 비어있다면, 사용자가 카톡창에 직접 타이핑한 전체 문장(utterance)을 통째로 대안 사용
    if not event_name:
        event_name = data.get("userRequest", {}).get("utterance", "").strip()

    # 3. 데이터가 아예 없거나 기본 명령어인 경우 가이드 문구 출력
    if not event_name or event_name in ["시작", "가보자", "안녕"]:
        return jsonify(kakao_text("궁금한 역사적 사건이나 인물을 입력해 주세요! (예: 이순신 업적)"))

    try:
        # gpt-4o-mini 모델을 사용하여 카카오톡 5초 제한 시간 내에 빠르게 지식 검색 및 요약
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 고등학교 역사 선생님입니다. 질문에 대해 쉽고 친절하게 핵심 위주로 요약하여 대답하세요. 답변은 3~4문장 내외로 간결해야 합니다."},
                {"role": "user", "content": event_name}
            ],
            max_tokens=400,
            timeout=4.5  # 카카오톡 타임아웃 제한(5초)에 걸리지 않도록 4.5초 타이핑 가드 설정
        )
        result_text = response.choices.message.content.strip()
    except Exception as e:
        # API 오류 및 타임아웃 발생 시 예외 처리
        result_text = "죄송합니다. 답변을 생성하는 과정에서 잠시 지연이 발생했습니다. 다시 한번 질문을 입력해 주시겠어요?"

    return jsonify(kakao_text(result_text))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
