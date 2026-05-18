import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
import requests

app = FastAPI()

# 프론트엔드 통신 허용 (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 프론트엔드에서 넘겨받을 데이터 구조 정의
class AnalysisRequest(BaseModel):
    ticker: str         # 분석할 종목 (예: AAPL, NVDA, ^IXIC 등)
    OPENAI_API_KEY: str # 사용자가 화면에서 직접 입력한 OpenAI API 키

@app.post("/api/analyze")
async def total_stock_analysis(request: AnalysisRequest):
    ticker = request.ticker.upper()
    api_key = request.OPENAI_API_KEY.strip()
    
    # 1. API 키 기본 검증
    if not api_key.startswith("sk-"):
        raise HTTPException(status_code=400, detail="유효하지 않은 OpenAI API 키 형식입니다.")

    # 2. [기능 1] Yahoo Finance를 통한 최근 1개월 주가 및 기술적 지표 수집/계산
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=50) # RSI와 이동평균선 계산을 위해 여유있게 50일 확보
        
        df = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
        
        if df.empty:
            raise HTTPException(status_code=400, detail="주식 데이터를 찾을 수 없습니다. 티кер(Symbol)를 확인해주세요.")
            
        # 데이터가 너무 많으면 GPT 토큰을 많이 먹으므로 최근 30일 데이터만 슬라이싱
        df_recent = df.tail(30)
        
        # [기술적 지표 추가 계산] 5일, 20일 이동평균선(MA)
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        
        # [기술적 지표 추가 계산] RSI (상대강도지수 - 과매수/과매도 판단 지표)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # 최근 1달간의 요약 데이터 생성
        current_price = float(df['Close'].iloc[-1])
        highest_price = float(df_recent['High'].max())
        lowest_price = float(df_recent['Low'].min())
        latest_rsi = float(df['RSI'].iloc[-1])
        latest_ma5 = float(df['MA5'].iloc[-1])
        latest_ma20 = float(df['MA20'].iloc[-1])
        
        # GPT 주입용 일별 종가 및 지표 텍스트 정제
        price_trend = {}
        for idx, row in df_recent.iterrows():
            date_str = str(idx).split()[0]
            price_trend[date_str] = {
                "Close": round(float(row['Close']), 2),
                "Volume": int(row['Volume'])
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"금융 데이터 수집 및 지표 계산 중 오류: {str(e)}")

    # 3. [기능 2] 실시간 뉴스 키워드 수集 (yfinance의 기본 news 기능 활용)
    news_summary = []
    try:
        ticker_obj = yf.Ticker(ticker)
        raw_news = ticker_obj.news[:3] # 최신 뉴스 3개만 추출
        for article in raw_news:
            news_summary.append({
                "title": article.get("title"),
                "publisher": article.get("publisher")
            })
    except Exception:
        news_summary = ["최신 뉴스를 가져오는 데 실패했습니다."]

    # 4. [기능 3] 서버 보관용 역사적 경제 대공황/위기 패턴 데이터베이스
    historical_database = """
    [역사적 경제 패턴 DB]
    - 2000년 닷컴 버블: 실적 불투명한 기술주의 묻지마 폭등 후 밸류에이션 붕괴 (나스닥 -78%)
    - 2008년 금융 위기: 리먼 파산 및 서브프라임 모기지발 신용 경색 및 시스템 자산 붕괴 (S&P500 -50%)
    - 2020년 코로나 팬데믹: 돌발적 대외 악재로 인한 단기 패닉 셀링 후 무제한 유동성 공급으로 V자 반등
    - 2022년 고금리 긴축: 인플레이션 억제를 위한 중앙은행의 급격한 금리 인상과 성장주 자금 이탈 (나스닥 -30%)
    """

    # 5. [기능 4] 사용자가 제공한 OPENAI_API_KEY로 GPT-4o-mini 호출 및 융합 분석
    try:
        # 사용자가 입력창에 넣은 키를 바탕으로 클라이언트 동적 생성
        dynamic_client = OpenAI(api_key=api_key)
        
        prompt_content = f"""
        당신은 역사적 통계, 기술적 지표, 그리고 시황 뉴스를 종합하여 판단하는 월가 출신의 '수석 매크로 투자 전략가'입니다.
        아래 제공된 고차원 데이터들을 분석하여 개인 투자자를 위한 [종합 매크로 예측 리포트]를 작성하세요.
        
        [1. 분석 대상 종목]: {ticker}
        
        [2. 최근 1개월 핵심 요약 지표]:
        - 현재가: {current_price}
        - 1개월 최고가: {highest_price} / 최저가: {lowest_price}
        - 최근 14일 RSI (상대강도지수): {round(latest_rsi, 2)} (참고: 70 이상 과매수, 30 이하 과매도)
        - 이동평균선: 5일 이평선({round(latest_ma5, 2)}), 20일 이평선({round(latest_ma20, 2)})
        
        [3. 최근 1개월 일별 종가 및 거래량 흐름]:
        {price_trend}
        
        [4. 최신 관련 뉴스 헤드라인]:
        {news_summary}
        
        [5. 대조할 역사적 경제 위기 패턴]:
        {historical_database}
        
        --------------------------------------------------
        위 데이터를 연계하여 반드시 아래의 템플릿 양식에 맞춰 한글로 답변하세요.
        
        ■ [1] 기술적 지표 및 뉴스 분석
        - 최근 이동평균선 정배열/역배열 상태와 RSI 수치 기반의 현재 주가 위치 평가.
        - 최신 뉴스 내용이 시장에 미치는 심리적 영향(호재/악재) 해석.
        
        ■ [2] 역사적 데자뷔 패턴 매칭 (가장 중요)
        - 최근 1달간의 주가/거래량/변동성 흐름이 과거 4대 패턴 중 어느 시기와 가장 유사한지 싱크로율(0~100%)을 매기고, 경제학적 근거를 설명할 것.
        
        ■ [3] 시나리오별 주가 예측 (향후 1달)
        - 메인 시나리오 (예측 방향: 상승/하락/횡보 중 택1) 및 타겟 목표가 제시.
        - 리스크 발생 시의 차선 시나리오와 지지선 제시.
        
        ■ [4] 투자자 행동 전략 지침
        - 현재 포지션에서 매수/매도/관망 중 어떤 스탠스를 취해야 하는지 구체적인 비중 조절 제안.
        
        * 리포트 최하단에는 반드시 투자 면책 조항을 포함하세요.
        """
        
        response = dynamic_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 최고 권위의 주식·매크로 경제 분석 AI입니다. 리포트 양식을 엄격히 준수하며 깊이 있는 통찰을 제공합니다."},
                {"role": "user", "content": prompt_content}
            ],
            temperature=0.4 # 일관성 있고 전문적인 답변을 위해 온도를 낮춤
        )
        
        return {"analysis": response.choices[0].message.content}
        
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"OpenAI API 호출 또는 인증 실패: 키를 확인해 주세요. ({str(e)})")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
