import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import yfinance as yf
from datetime import datetime, timedelta

app = FastAPI()

# 프론트엔드 통신 허용 (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 데이터 구조 정의 (프론트엔드에서 주식 티커와 함께 API 키도 받아옴)
class AnalysisRequest(BaseModel):
    ticker: str        # 예: AAPL, TSLA
    user_api_key: str  # 사용자가 화면에서 입력한 OpenAI API 키

@app.post("/api/analyze")
async def analyze_stock(request: AnalysisRequest):
    ticker = request.ticker.upper()
    user_key = request.user_api_key.strip()
    
    # 1. API 키 입력 검증
    if not user_key.startswith("sk-"):
        raise HTTPException(status_code=400, detail="유효하지 않은 OpenAI API 키 형식입니다.")

    # 2. Yahoo Finance를 통해 최근 한 달간의 주가 데이터 수집
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        stock_data = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
        
        if stock_data.empty:
            raise HTTPException(status_code=400, detail="주식 데이터를 찾을 수 없습니다. 티커를 확인해주세요.")
            
        recent_prices = stock_data['Close'].round(2).to_dict()
        formatted_prices = {str(k).split()[0]: v for k, v in recent_prices.items()}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"금융 데이터 수집 중 오류: {str(e)}")

    # 과거 패턴 데이터베이스 (샘플 데이터)
    historical_patterns = """
    [역사적 경제 위기 패턴 참고자료]
    1. 2000년 닷컴 버블: 실적 없는 IT 기업들의 주가 폭등 후 VIX 지수 급증하며 3년 만에 나스닥 78% 폭락.
    2. 2008년 금융 위기: 리먼 브라더스 파산 전후로 신용 경색 발생, S&P 500 지수가 수개월에 걸쳐 50% 이상 폭락.
    3. 2020년 코로나 숏스퀴즈: 글로벌 팬데믹 공포로 한 달 만에 30% 폭락 후, 유동성 공급으로 V자 초고속 반등.
    4. 2022년 고금리 인플레이션: 미 연준의 급격한 금리 인상으로 기술주 중심 연간 30% 이상 지속적 우하향 하락장.
    """

    # 3. 사용자가 보낸 API 키로 OpenAI 클라이언트 개체를 실시간 생성
    try:
        dynamic_client = OpenAI(api_key=user_key)
        
        response = dynamic_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "당신은 역사적 통계와 경제 위기 패턴을 분석하는 전문 금융 AI 분석가입니다."
                },
                {
                    "role": "user",
                    "content": f"""
                    [요청 종목]: {ticker}
                    [최근 1개월간의 주가 흐름]: {formatted_prices}
                    [비교할 역사적 패턴]: {historical_patterns}
                    
                    위 두 데이터를 분석하여 아래 형식으로 리포트를 작성해줘.
                    1. 최근 1개월의 흐름이 과거 4가지 패턴 중 어느 것과 가장 유사한지 싱크로율(%)과 이유 분석.
                    2. 과거 패턴을 바탕으로 향후 1~2주간의 주가 방향 예측 (상승/하락/횡보).
                    3. 투자자가 주의해야 할 리스크 요인 1가지.
                    
                    * 답변 끝에는 면책 조항을 포함할 것.
                    """
                }
            ],
            temperature=0.5
        )
        
        return {"analysis": response.choices[0].message.content}
        
    except Exception as e:
        # 사용자가 잘못된 키를 넣었거나 만료된 키일 경우 에러 처리
        raise HTTPException(status_code=401, detail=f"OpenAI API 인증 실패: 키를 확인해주세요. ({str(e)})")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
