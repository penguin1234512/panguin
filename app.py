import os
import httpx
import traceback
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

# Render 프록시 네트워크 및 Python 3.14+ 가드를 우회하기 위한 httpx 클라이언트 세팅
custom_http_client = httpx.Client(
    proxy=os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY") or None
)

# Render 대시보드 환경변수(Environment)에 등록해 둔 OPENAI_API_KEY를 자동으로 가져옵니다.
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
    """서버 내부 에러 발생 시 카톡창에 상세 로그를 강제로 박아버리는 디버깅용 함수"""
    error_msg = f"❌ [{route_name}] 서버 에러 발생!\n\n원인: {str(error)}\n\n상세 정보:\n{str(detail)[:400]}"
    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": error_msg}}]
        }
    })

@app.route("/", methods=["GET"])
def home():
    return "History Multi-Function Debug Server is running!"


# 1. 역사 지식 검색 엔드포인트 (오픈빌더 스킬 URL: 서버주소/history-ai)
@app.route("/history-ai", methods=["POST"])
def history_ai():
    data = request.get_json(silent=True) or {}
    params = data.get("action", {}).get("params", {})
    event_name = params.get("history_event", "").strip()

    if not event_name:
        event_name = data.get("userRequest", {}).get("utterance", "").strip()

    if not event_name:
        return jsonify(kakao_text("궁금한 역사 키워드가 전달되지 않았습니다."))

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 고등학교 역사 선생님입니다. 질문에 대해 핵심 위주로 3문장 내외로 간결하게 요약하여 대답하세요."},
                {"role": "user", "content": event_name}
            ],
            max_tokens=300,
            timeout=4.3
        )
        return jsonify(kakao_text(response.choices.message.content.strip()))
    except Exception as e:
        return kakao_error_report("history-ai", e, traceback.format_exc())


# 2. 역사 뉴스 크롤링 엔드포인트 (오픈빌더 스킬 URL: 서버주소/news)
@app.route("/news", methods=["POST"])
def get_history_news():
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 최신 역사학계 소식과 문화재 발굴 뉴스를 전하는 크롤러 엔진입니다."},
                {"role": "user", "content": "현재 기준 가장 최신의 역사 관련 뉴스, 문화재 발굴 소식 3개를 요약과 함께 리스트 형태로 알려줘."}
            ],
            max_tokens=350,
            timeout=4.3
        )
        result_text = "📰 [최신 역사 뉴스 브리핑]\n\n" + response.choices.message.content.strip()
        return jsonify(kakao_text(result_text))
    except Exception as e:
        return kakao_error_report("news", e, traceback.format_exc())


# 3. 역사 도서 크롤링 엔드포인트 (오픈빌더 스킬 URL: 서버주소/books)
@app.route("/books", methods=["POST"])
def get_history_books():
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "너는 역사 도서 추천 봇이야. 제목과 한줄 요약만 딱 2권 짧게 말해."},
                {"role": "user", "content": "고등학생이 읽기 좋은 추천 역사 도서 2권만 [도서명 / 저자 / 한줄요약] 구조로 콤팩트하게 줘."}
            ],
            max_tokens=250,
            timeout=4.3
        )
        result_text = "📚 [추천 역사 도서 목록]\n\n" + response.choices.message.content.strip()
        return jsonify(kakao_text(result_text))
    except Exception as e:
        return kakao_error_report("books", e, traceback.format_exc())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
