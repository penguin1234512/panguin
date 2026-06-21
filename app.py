import os
import random
import threading  # 백그라운드 처리를 위한 쓰레드 추가
import requests
import urllib.parse
import httpx       # Python 3.14 하위 호환성 우회를 위해 추가
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from openai import OpenAI

app = Flask(__name__)

# [수정] Python 3.14 및 httpx 환경에서 proxies 매칭 오류를 우회하기 위한 안전한 HTTP 클라이언트 수동 선언
custom_http_client = httpx.Client(
    proxy=os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY") or None
)

# Render 환경변수에서 API 키를 읽어오되, 커스텀 클라이언트를 주입하여 터지는 현상을 방지합니다.
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


# 백그라운드에서 OpenAI를 호출하고 카카오로 결과를 쏴주는 함수
def process_openai_callback(event_name, callback_url):
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

    # 카카오 캘백 URL로 최종 결과 전송
    callback_payload = kakao_text(result_text)
    try:
        requests.post(callback_url, json=callback_payload, timeout=10)
    except Exception as e:
        print(f"Callback 전송 실패: {e}")


# 시나리오 1: 역사 지식 검색 (지연 응답 적용)
@app.route("/history-ai", methods=["POST"])
def history_ai():
    data = request.get_json(silent=True) or {}
    params = data.get("action", {}).get("params", {})
    event_name = params.get("history_event", "").strip()

    if not event_name:
        return jsonify(kakao_text("궁금한 역사적 사건을 알려주세요."))

    # 카카오에서 제공하는 캘백 URL 추출
    callback_url = data.get("userRequest", {}).get("callbackUrl")

    if callback_url:
        # 백그라운드 쓰레드를 생성하여 OpenAI 호출 진행 (타임아웃 방지)
        threading.Thread(target=process_openai_callback, args=(event_name, callback_url)).start()
        
        # 5초 이내에 카카오 챗봇에 먼저 던져줄 임시 대기 메시지
        return jsonify({
            "version": "2.0",
            "useCallback": True,  # 나중에 캘백으로 답장 주겠다고 카카오에 선언
            "template": {
                "outputs": [{"simpleText": {"text": f"⏳ '{event_name}'에 대해 열심히 생각하고 있습니다! 잠시만 기다려주세요..."}}]
            }
        })
    else:
        # 만약 스킬 테스트 등에서 callbackUrl이 넘어오지 않을 때를 대비한 예외 처리
        return jsonify(kakao_text("기본 응답 설정을 확인해 주세요. (Callback 불가 환경)"))


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
        r = requests.get(url, timeout=4)  # 타임아웃을 4초로 줄여 안전장치 확보
        soup = BeautifulSoup(r.text, "xml")
        titles = [item.title.text for item in soup.find_all("item")[:5]]
        result = f"'{search_key}' 뉴스:\n" + "\n".join([f"{i+1}. {t}" for i, t in enumerate(titles)])
    except Exception as e:
        result = f"뉴스 검색 오류: {str(e)}"
    return jsonify(kakao_text(result))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
