import os
import random
import requests
import urllib.parse
import httpx       # Python 3.14 하위 호환성 우회를 위해 유지
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from openai import OpenAI

app = Flask(__name__)

# Python 3.14 및 httpx 환경에서 proxies 매칭 오류를 우회하기 위한 안전한 HTTP 클라이언트 선언
custom_http_client = httpx.Client(
    proxy=os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY") or None
)

# Render 환경변수에서 API 키를 읽어옵니다.
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    http_client=custom_http_client
)

def kakao_text(text):
    """카카오톡 응답 규격 및 1000자 제한 안전장치"""
    safe_text = text[:950] + "..." if len(text) > 950 else text
    return {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": safe_text}}]
        }
    }

@app.route("/", methods=["GET"])
def home():
    return "History Chatbot Server is running on Render!"


# [수정] 백그라운드 쓰레드와 콜백을 완전히 제거하고, 5초 이내에 직접 동기식으로 즉시 대답하는 함수
@app.route("/history-ai", methods=["POST"])
def history_ai():
    data = request.get_json(silent=True) or {}
    params = data.get("action", {}).get("params", {})
    event_name = params.get("history_event", "").strip()

    if not event_name:
        return jsonify(kakao_text("궁금한 역사적 사건을 알려주세요."))

    try:
        # 5초 타임아웃을 안전하게 지키기 위해 max_tokens를 최적화하고 GPT 프롬프트를 간결화합니다.
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 역사 선생님입니다. 질문에 대해 핵심 위주로 명확하고 친절하게 대답하세요."},
                {"role": "user", "content": event_name}
            ],
            max_tokens=400,
            timeout=3.5  # 3.5초가 지나도 GPT가 답을 못 주면 예외 처리로 빠지게 설계 (카카오 5초 제한 방어)
        )
        result_text = response.choices.message.content.strip()
    except Exception as e:
        # 타임아웃 또는 API 에러 발생 시 처리
        result_text = "죄송합니다. 답변을 준비하는 과정에서 잠시 지연이 발생했습니다. 다시 한번 질문해 주시겠어요?"

    # 대기 메시지 없이 곧바로 카카오톡 엔진에 생성된 AI 답변을 반환합니다.
    return jsonify(kakao_text(result_text))


# 시나리오 2: 역사 퀴즈 (이미지 포함)
@app.route("/history-quiz", methods=["POST"])
def history_quiz():
    quiz_id = random.randint(1, 3)
    img_url = "https://t1.daumcdn.net/friends/prod/category/M001_friends_ryan2.jpg"
    quiz_data = {
        1: "조선의 제1대 왕은? (1.태조 2.세종 3.정조)",
        2: "3.1 운동은 몇 년도인가요? (1.1910 2.1919 3.1945)",
        3: "거북선을 만든 장군은? (1.강감찬 2.이순신 3.을지문덕)"
    }
    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [
                {"simpleImage": {"imageUrl": img_url, "altText": "퀴즈 이미지"}},
                {"simpleText": {"text": quiz_data.get(quiz_id)}}
            ]
        }
    })

# 시나리오 3: 뉴스 검색 (RSS)
@app.route("/history-news", methods=["POST"])
def history_news():
    data = request.get_json(silent=True) or {}
    search_key = data.get("action", {}).get("params", {}).get("search_key", "").strip()
    if not search_key: return jsonify(kakao_text("검색어를 입력하세요."))

    query = urllib.parse.quote(search_key)
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        r = requests.get(url, timeout=3)  # 타임아웃을 3초로 안정화
        soup = BeautifulSoup(r.text, "xml")
        titles = [item.title.text for item in soup.find_all("item")[:5]]
        result = f"'{search_key}' 뉴스:\n" + "\n".join([f"{i+1}. {t}" for i, t in enumerate(titles)])
    except Exception as e:
        result = f"뉴스 검색 오류: {str(e)}"
    return jsonify(kakao_text(result))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
