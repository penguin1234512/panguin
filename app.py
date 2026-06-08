import os
import random
import requests
import urllib.parse
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from openai import OpenAI

app = Flask(__name__)

# Render 환경변수에서 API 키를 읽어옵니다.
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

# 시나리오 1: 역사 지식 검색
@app.route("/history-ai", methods=["POST"])
def history_ai():
    data = request.get_json(silent=True) or {}
    params = data.get("action", {}).get("params", {})
    event_name = params.get("history_event", "").strip()

    if not event_name:
        return jsonify(kakao_text("궁금한 역사적 사건을 알려주세요."))

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 역사 선생님입니다. 사건의 배경과 결과를 친절히 설명하세요."},
                {"role": "user", "content": event_name}
            ],
            max_tokens=800
        )
        result_text = response.choices.message.content.strip()
    except Exception as e:
        result_text = f"AI 호출 오류: {str(e)}"
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
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "xml") # RSS 파싱을 위해 lxml 필요
        titles = [item.title.text for item in soup.find_all("item")[:5]]
        result = f"'{search_key}' 뉴스:\n" + "\n".join([f"{i+1}. {t}" for i, t in enumerate(titles)])
    except Exception as e:
        result = f"뉴스 검색 오류: {str(e)}"
    return jsonify(kakao_text(result))

if __name__ == "__main__":
    # Render 환경의 포트 설정을 준수합니다.
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
