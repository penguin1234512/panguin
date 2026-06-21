import os
import random
import requests
import urllib.parse
import httpx
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from openai import OpenAI

app = Flask(__name__)

# Python 3.14 호환 및 Render 프록시 오류 우회를 위한 커스텀 HTTP 클라이언트 설정
custom_http_client = httpx.Client(
    proxy=os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY") or None
)

# Render 환경변수(Environment)에서 OPENAI_API_KEY를 읽어옵니다.
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    http_client=custom_http_client
)

def kakao_text(text):
    """카카오톡 응답 규격 포맷팅 (1000자 초과 방지 안전장치)"""
    safe_text = text[:950] + "..." if len(text) > 950 else text
    return {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": safe_text}}]
        }
    }

@app.route("/", methods=["GET"])
def home():
    return "History Chatbot Server is running successfully on Render!"


# [역사 사건 검색 블록용 라우팅] 5초 제한을 방어하는 동기식 구조
@app.route("/history-ai", methods=["POST"])
def history_ai():
    data = request.get_json(silent=True) or {}
    
    # 카카오 오픈빌더에서 보낸 파라미터(history_event) 추출
    params = data.get("action", {}).get("params", {})
    event_name = params.get("history_event", "").strip()

    # 만약 파라미터가 비어있다면 사용자가 입력한 전체 문장(utterance)을 대안으로 사용
    if not event_name:
        event_name = data.get("userRequest", {}).get("utterance", "").strip()

    # 최종적으로도 질문이 비어있을 경우 예외 처리
    if not event_name or event_name in ["시작", "가보자", "안녕"]:
        return jsonify(kakao_text("궁금한 역사적 사건이나 인물을 입력해 주세요! (예: 이순신 업적)"))

    try:
        # gpt-4o-mini를 활용하여 카카오톡 5초 타임아웃 제한 내에 빠르게 응답 생성
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 고등학교 역사 선생님입니다. 질문에 대해 쉽고 친절하게 핵심 위주로 요약하여 대답하세요. 답변은 3~4문장 내외로 간결해야 합니다."},
                {"role": "user", "content": event_name}
            ],
            max_tokens=400,
            timeout=3.5  # 3.5초 타임아웃 설정으로 카카오톡 엔진이 끊기 전에 안전하게 방어
        )
        result_text = response.choices.message.content.strip()
    except Exception as e:
        # 에러 발생 시 사용자에게 노출할 친절한 멘트
        result_text = f"죄송합니다. 답변을 생성하는 과정에서 잠시 지연이 발생했습니다. 다시 한번 질문해 주시겠어요?"

    # 즉시 카카오톡 봇 응답 규격으로 데이터 반환
    return jsonify(kakao_text(result_text))


# 시나리오 2: 역사 퀴즈 (확장용)
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

# 시나리오 3: 뉴스 검색 (RSS 확장용)
@app.route("/history-news", methods=["POST"])
def history_news():
    data = request.get_json(silent=True) or {}
    search_key = data.get("action", {}).get("params", {}).get("search_key", "").strip()
    if not search_key: return jsonify(kakao_text("검색어를 입력하세요."))

    query = urllib.parse.quote(search_key)
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        r = requests.get(url, timeout=3)
        soup = BeautifulSoup(r.text, "xml")
        titles = [item.title.text for item in soup.find_all("item")[:5]]
        result = f"'{search_key}' 뉴스:\n" + "\n".join([f"{i+1}. {t}" for i, t in enumerate(titles)])
    except Exception as e:
        result = f"뉴스 검색 오류: {str(e)}"
    return jsonify(kakao_text(result))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
