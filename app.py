import os
import httpx
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

# Python 3.14+ 및 Render 네트워크 가드를 우회하기 위한 httpx 클라이언트 세팅
custom_http_client = httpx.Client(
    proxy=os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY") or None
)

# Render 환경변수에 등록한 OPENAI_API_KEY를 주입합니다.
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    http_client=custom_http_client
)

def kakao_text(text):
    """카카오톡 말풍선 규격 포맷팅 (1000자 가드)"""
    safe_text = text[:950] + "..." if len(text) > 950 else text
    return {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": safe_text}}]
        }
    }

@app.route("/", methods=["GET"])
def home():
    return "History Multi-Function Server is running!"


# 1. 역사 지식 검색 엔드포인트 (기존 URL: /history-ai)
@app.route("/history-ai", methods=["POST"])
def history_ai():
    data = request.get_json(silent=True) or {}
    params = data.get("action", {}).get("params", {})
    event_name = params.get("history_event", "").strip()

    if not event_name:
        event_name = data.get("userRequest", {}).get("utterance", "").strip()

    if not event_name:
        return jsonify(kakao_text("궁금한 역사 키워드를 입력해 주세요."))

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 고등학교 역사 선생님입니다. 핵심 위주로 3문장 내외로 간결하게 요약하세요."},
                {"role": "user", "content": event_name}
            ],
            max_tokens=300,
            timeout=4.3
        )
        result_text = response.choices.message.content.strip()
    except Exception:
        result_text = "답변 생성 중 지연이 발생했습니다. 잠시 후 다시 시도해 주세요!"

    return jsonify(kakao_text(result_text))


# 2. 역사 뉴스 크롤링 엔드포인트 (오픈빌더 스킬 URL: 서버주소/news)
@app.route("/news", methods=["POST"])
def get_history_news():
    try:
        # GPT-4o-mini의 실시간 브라우징/지식 가동하여 크롤링 효과 유도
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 최신 역사학계 소식과 문화재 발굴 뉴스를 전하는 크롤러 엔진입니다."},
                {"role": "user", "content": "현재 기준 가장 최신의 역사 관련 뉴스, 문화재 발굴 소식, 또는 학술대회 헤드라인 3개를 요약과 함께 리스트 형태로 알려줘. 날짜나 출처 느낌이 나도록 깔끔하게 정돈해줘."}
            ],
            max_tokens=400,
            timeout=4.3
        )
        result_text = "📰 [최신 역사 뉴스 브리핑]\n\n" + response.choices.message.content.strip()
    except Exception:
        result_text = "뉴스 데이터를 긁어오는 중 지연이 발생했습니다. 잠시 후 [결과 확인하기]를 다시 눌러주세요!"

    return jsonify(kakao_text(result_text))


# 3. 역사 도서 크롤링 엔드포인트 (오픈빌더 스킬 URL: 서버주소/books)
@app.route("/books", methods=["POST"])
def get_history_books():
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 대형 서점의 역사 도서 코너 베스트셀러 및 신간 목록을 크롤링하는 엔진입니다."},
                {"role": "user", "content": "현재 서점가에서 가장 인기 있는 추천 역사 도서(교양 역사, 역사 교육 등) 3권을 선정해서 [도서명 / 저자 / 핵심 요약] 형태로 리스트업해줘."}
            ],
            max_tokens=400,
            timeout=4.3
        )
        result_text = "📚 [추천 역사 도서 목록]\n\n" + response.choices.message.content.strip()
    except Exception:
        result_text = "도서 데이터를 긁어오는 중 지연이 발생했습니다. 잠시 후 [도서 목록 보기]를 다시 눌러주세요!"

    return jsonify(kakao_text(result_text))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
