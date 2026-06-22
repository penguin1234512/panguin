import os
import httpx
import traceback
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

# Render 프록시 네트워크 및 Python 가드를 우회하기 위한 httpx 클라이언트 세팅
custom_http_client = httpx.Client(
    proxy=os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY") or None
)

# OpenAI 클라이언트 초기화
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    http_client=custom_http_client
)

def kakao_text(text):
    """카카오톡 말풍선 규격 포맷팅 (1000자 초과 방지 마진 설정)"""
    safe_text = text[:900] + "..." if len(text) > 900 else text
    return {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": safe_text}}]
        }
    }

def kakao_error_report(route_name, error, detail):
    """서버 내부 에러 발생 시 카톡창에 간결하게 에러 보고"""
    # 3초 타임아웃 에러 시 사용자가 알기 쉽게 가벼운 메시지로 변환
    if "timeout" in str(error).lower():
        error_msg = f"⏱️ [{route_name}] 답변 생성 시간이 3초를 초과했습니다. 잠시 후 다시 시도해주세요."
    else:
        error_msg = f"❌ [{route_name}] 에러 발생!\n원인: {str(error)}"
    
    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": error_msg}}]
        }
    })

@app.route("/", methods=["GET"])
def home():
    return "History Fast-Response Server is running!"


# 1. 역사 지식 검색 엔드포인트 (타임아웃 2.8초 최적화)
@app.route("/history-ai", methods=["POST"])
def history_ai():
    data = request.get_json(silent=True) or {}
    
    params = data.get("action", {}).get("params", {}) or {}
    event_name = params.get("history_event", "").strip()

    if not event_name:
        user_request = data.get("userRequest", {}) or {}
        event_name = user_request.get("utterance", "").strip()

    if not event_name:
        return jsonify(kakao_text("궁금한 역사 키워드가 전달되지 않았습니다."))

    try:
        # 응답 속도를 올리기 위해 max_tokens를 줄이고, 프롬프트를 극도로 압축
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "너는 역사 교사다. 질문에 2문장(100자 내외)으로 핵심만 아주 짧고 빠르게 답해라. 미사여구 금지."},
                {"role": "user", "content": event_name}
            ],
            max_tokens=150, # 토큰이 작을수록 생성 속도가 비약적으로 빨라집니다.
            timeout=2.8     # 카카오톡 5초 제한 및 사용자 요구에 맞춰 2.8초로 컷
        )
        return jsonify(kakao_text(response.choices[0].message.content.strip()))
    except Exception as e:
        return kakao_error_report("history-ai", e, traceback.format_exc())


# 2. 역사 뉴스 크롤링 엔드포인트 (타임아웃 2.8초 최적화)
@app.route("/news", methods=["POST"])
def get_history_news():
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "너는 역사 뉴스 알리미다. 최신 발굴 소식 2개만 제목 위주로 핵심만 아주 짧게 요약해."},
                {"role": "user", "content": "가장 최신의 역사 관련 뉴스, 문화재 발굴 소식 2개만 한 줄 요약 형태로 아주 짧게 줘."}
            ],
            max_tokens=200,
            timeout=2.8
        )
        result_text = "📰 [최신 역사 뉴스]\n\n" + response.choices[0].message.content.strip()
        return jsonify(kakao_text(result_text))
    except Exception as e:
        return kakao_error_report("news", e, traceback.format_exc())


# 3. 역사 도서 크롤링 엔드포인트 (타임아웃 2.8초 최적화)
@app.route("/books", methods=["POST"])
def get_history_books():
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "너는 역사 도서 추천 봇이다. 딱 1~2권만 제목과 저자만 한 줄로 말해."},
                {"role": "user", "content": "추천 역사 도서 2권만 [도서명 / 저자 / 요약] 구조로 아주 짧게 줘."}
            ],
            max_tokens=150,
            timeout=2.8
        )
        result_text = "📚 [추천 역사 도서]\n\n" + response.choices[0].message.content.strip()
        return jsonify(kakao_text(result_text))
    except Exception as e:
        return kakao_error_report("books", e, traceback.format_exc())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
