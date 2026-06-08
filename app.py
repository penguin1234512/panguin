import os
import random
import requests
import urllib.parse
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from openai import OpenAI

app = Flask(__name__)

# [수정됨] 제공해주신 OpenAI API 키를 직접 설정합니다.
client = OpenAI(api_key="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")

def kakao_text(text):
    """카카오톡 텍스트 응답 규격 생성 및 1000자 초과 방지 안전장치 [1]"""
    # 950자에서 자르고 말줄임표를 추가하여 전송 오류를 방지합니다.
    safe_text = text[:950] + "..." if len(text) > 950 else text
    return {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": safe_text}}]
        }
    }

@app.route("/", methods=["GET"])
def home():
    return "History Chatbot Server is running."

# --- 시나리오 1: AI 역사 지식 검색 (ChatGPT 연동) ---
@app.route("/history-ai", methods=["POST"])
def history_ai():
    data = request.get_json(silent=True) or {}
    # 오픈빌더 파라미터 'history_event' 추출 [3]
    params = data.get("action", {}).get("params", {})
    event_name = params.get("history_event", "").strip()

    if not event_name:
        return jsonify(kakao_text("궁금한 역사적 사건이나 인물을 입력해주세요."))

    try:
        # GPT-4o-mini 모델을 사용하여 역사 정보 생성 [4]
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 역사 전문가입니다. 사건의 배경, 과정, 결과를 나누어 친절하게 설명하세요."},
                {"role": "user", "content": event_name}
            ],
            temperature=0.7,
            max_tokens=800
        )
        result_text = response.choices.message.content.strip()
    except Exception as e:
        result_text = f"역사 정보를 가져오는 중 오류 발생: {str(e)}"

    return jsonify(kakao_text(result_text))

# --- 시나리오 2: 역사 퀴즈 (랜덤 숫자 및 이미지 활용) ---
@app.route("/history-quiz", methods=["POST"])
def history_quiz():
    # 1~10 사이의 랜덤 숫자를 활용한 퀴즈 번호 생성 [5, 6]
    quiz_id = random.randint(1, 3)
    
    # 예시 이미지 URL (라이언 이미지 활용) [7, 8]
    img_url = "https://t1.daumcdn.net/friends/prod/category/M001_friends_ryan2.jpg"
    
    quiz_data = {
        1: "다음 중 조선의 제1대 왕은 누구일까요? (1.태조 2.세종 3.정조)",
        2: "3.1 운동이 일어난 해는 언제일까요? (1.1910년 2.1919년 3.1945년)",
        3: "임진왜란 당시 거북선을 활용해 승리한 장군은? (1.강감찬 2.을지문덕 3.이순신)"
    }
    
    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [
                {"simpleImage": {"imageUrl": img_url, "altText": "역사 퀴즈 이미지"}},
                {"simpleText": {"text": quiz_data.get(quiz_id, "문제를 불러오지 못했습니다.")}}
            ]
        }
    })

# --- 시나리오 3: 실시간 역사 뉴스 (RSS 크롤링) ---
@app.route("/history-news", methods=["POST"])
def history_news():
    data = request.get_json(silent=True) or {}
    # 파라미터 'search_key' 추출 [9]
    search_key = data.get("action", {}).get("params", {}).get("search_key", "").strip()

    if not search_key:
        return jsonify(kakao_text("검색할 역사 키워드를 알려주세요."))

    # RSS 방식을 활용한 구글 뉴스 크롤링 [10]
    query = urllib.parse.quote(search_key)
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "xml")
        items = soup.find_all("item")
        titles = [f"{i+1}. {item.title.text}" for i, item in enumerate(items[:5])]

        if titles:
            result = f"['{search_key}'] 관련 최신 소식입니다:\n\n" + "\n".join(titles)
        else:
            result = f"['{search_key}']에 대한 검색 결과를 찾지 못했습니다."
    except Exception as e:
        result = f"뉴스 조회 중 오류 발생: {str(e)}"

    return jsonify(kakao_text(result))

if __name__ == "__main__":
    # 서버 실행 설정 [11]
    app.run(host="0.0.0.0", port=5000, debug=True)
2. requirements.txt (필수 라이브러리)
GitHub 저장소의 루트 디렉토리에 이 파일을 함께 올려야 서버가 정상적으로 설치됩니다
.
Flask==3.0.3
gunicorn==22.0.0
requests==2.32.3
beautifulsoup4==4.12.3
openai
lxml
