import os
import random
import requests
import urllib.parse
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from openai import OpenAI  # 또는 google.genai 사용 가능 [1, 2]

app = Flask(__name__)

# OpenAI 클라이언트 초기화 (환경 변수 사용 권장) [3, 4]
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def kakao_text(text):
    """카카오톡 텍스트 응답 규격 (1000자 제한 및 950자 절삭 안전장치) [5]"""
    safe_text = text[:950] + "..." if len(text) > 950 else text
    return {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": safe_text}}]
        }
    }

# --- 시나리오 1: AI 역사 지식 검색 ---
@app.route("/history-ai", methods=["POST"])
def history_ai():
    data = request.get_json(silent=True) or {}
    # 오픈빌더에서 설정한 파라미터 'history_event' 추출 [6, 7]
    params = data.get("action", {}).get("params", {})
    tt = params.get("history_event", "").strip()

    if not tt:
        return jsonify(kakao_text("어떤 역사적 사건이 궁금하신가요?"))

    try:
        # ChatGPT API 연동 (또는 소스 [1]의 Gemini 방식 활용 가능) [2]
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 친절한 역사 선생님입니다. 사건의 배경, 과정, 결과를 나누어 설명하세요."},
                {"role": "user", "content": tt}
            ],
            max_tokens=800
        )
        result_text = response.choices.message.content.strip()
    except Exception as e:
        result_text = f"역사 정보를 가져오는 중 오류 발생: {str(e)}"

    return jsonify(kakao_text(result_text))

# --- 시나리오 2: 역사 퀴즈 및 이미지 (랜덤 & 이미지 스킬) ---
@app.route("/history-quiz", methods=["POST"])
def history_quiz():
    # 랜덤 숫자 생성 로직 활용 [8, 9]
    quiz_no = random.randint(1, 3)
    
    # 퀴즈 내용과 이미지를 함께 보내는 응답 규격 [10, 11]
    if quiz_no == 1:
        text = "다음 중 조선시대 왕이 아닌 사람은? (1.세종 2.이순신 3.정조)"
        img_url = "https://t1.daumcdn.net/friends/prod/category/M001_friends_ryan2.jpg" # 예시 이미지
    else:
        text = f"랜덤 역사 퀴즈 번호 {quiz_no}: 준비된 퀴즈가 출력됩니다."
        img_url = "https://t1.daumcdn.net/friends/prod/category/M001_friends_ryan2.jpg"

    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [
                {"simpleImage": {"imageUrl": img_url, "altText": "역사 유물 이미지"}},
                {"simpleText": {"text": text}}
            ]
        }
    })

# --- 시나리오 3: 실시간 역사 뉴스 (RSS 크롤링) ---
@app.route("/history-news", methods=["POST"])
def history_news():
    data = request.get_json(silent=True) or {}
    y = data.get("action", {}).get("params", {}).get("search_key", "").strip()

    if not y:
        return jsonify(kakao_text("검색할 역사 키워드를 입력해주세요."))

    # RSS 방식을 활용한 구글 뉴스 가져오기 [12, 13]
    query = urllib.parse.quote(y)
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "xml")
        items = soup.find_all("item")
        titles = [item.title.text for item in items[:5]] # 상위 5개 추출

        if titles:
            result = f"['{y}'] 관련 역사 뉴스입니다:\n\n" + "\n".join([f"{i+1}. {t}" for i, t in enumerate(titles)])
        else:
            result = f"['{y}']에 대한 검색 결과를 찾지 못했습니다."
    except Exception as e:
        result = f"뉴스 조회 중 오류 발생: {str(e)}"

    return jsonify(kakao_text(result))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
