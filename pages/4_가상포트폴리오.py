import streamlit as st
import pandas as pd
import yfinance as yf
import os
from datetime import datetime

# ==============================================================
# 0. 웹 페이지 기본 설정
# ==============================================================
st.set_page_config(page_title="앤트리치 가상 포트폴리오", layout="wide", page_icon="📊")

st.title("📊 앤트리치 가상 포트폴리오 추적기")
st.markdown("텐배거 스캐너와 딥밸류 관제탑에서 발굴한 사냥감을 가상 매수하고, **실시간 승률과 수익금**을 추적하여 블로그에 증명하십시오.")
st.divider()

# ==============================================================
# 1. 데이터 저장소 (CSV) 연동
# ==============================================================
# 가상 매수 기록을 저장할 파일 이름
DB_FILE = "antrich_portfolio.csv"

# 파일이 없으면 새로 생성하는 함수
def load_portfolio():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE)
    else:
        return pd.DataFrame(columns=["매수일", "종목코드", "매수단가", "수량", "매수전략"])

def save_portfolio(df):
    df.to_csv(DB_FILE, index=False)

# 포트폴리오 데이터 불러오기
df_port = load_portfolio()

# ==============================================================
# 2. 🛒 신규 가상 매수 입력창 (사이드바)
# ==============================================================
st.sidebar.header("🛒 신규 타깃 가상 매수")
st.sidebar.markdown("스캐너에서 찾은 종목을 포트폴리오에 편입합니다.")

with st.sidebar.form("buy_form", clear_on_submit=True):
    new_ticker = st.text_input("종목코드 (예: TSLA, NVDA)").upper()
    new_price = st.number_input("매수단가 (달러 $)", min_value=0.01, step=1.0, format="%.2f")
    new_qty = st.number_input("매수수량 (주)", min_value=1, step=1)
    new_strategy = st.selectbox("발굴 출처 (태그)", ["텐배거 스캐너", "딥밸류 스나이퍼", "수급/실시간 검색어", "개인 분석"])
    
    submit_btn = st.form_submit_button("✅ 가상 계좌에 담기", use_container_width=True)
    
    if submit_btn:
        if new_ticker:
            today_str = datetime.now().strftime("%Y-%m-%d")
            new_trade = pd.DataFrame([{
                "매수일": today_str, 
                "종목코드": new_ticker, 
                "매수단가": new_price, 
                "수량": new_qty, 
                "매수전략": new_strategy
            }])
            df_port = pd.concat([df_port, new_trade], ignore_index=True)
            save_portfolio(df_port)
            st.sidebar.success(f"{new_ticker} 편입 완료!")
            st.rerun() # 화면 새로고침
        else:
            st.sidebar.error("종목코드를 입력하세요.")

# ==============================================================
# 3. 📈 실시간 수익률 추적 엔진
# ==============================================================
if df_port.empty:
    st.info("💡 아직 가상 포트폴리오에 담긴 종목이 없습니다. 좌측 사이드바에서 종목을 편입해 보세요!")
else:
    with st.spinner("월스트리트 실시간 현재가와 내 포트폴리오 수익률을 동기화 중입니다..."):
        # 실시간 가격을 담을 리스트
        current_prices = []
        company_names = []
        
        # yfinance로 현재가 싹쓸이
        # (종목이 많아지면 한 번에 다운받는 것이 좋지만, 우선 직관적으로 개별 조회)
        for ticker in df_port["종목코드"]:
            try:
                stock = yf.Ticker(ticker)
                curr_p = stock.history(period="1d")['Close'].iloc[-1]
                name = stock.info.get('shortName', ticker)
                current_prices.append(curr_p)
                company_names.append(name)
            except:
                current_prices.append(0.0)
                company_names.append("알 수 없음")

        # 계산 로직
        df_track = df_port.copy()
        df_track["종목명"] = company_names
        df_track["현재가"] = current_prices
        
        df_track["투자원금"] = df_track["매수단가"] * df_track["수량"]
        df_track["평가금액"] = df_track["현재가"] * df_track["수량"]
        df_track["평가손익"] = df_track["평가금액"] - df_track["투자원금"]
        df_track["수익률(%)"] = (df_track["평가손익"] / df_track["투자원금"]) * 100

        # 전체 요약 통계
        total_invest = df_track["투자원금"].sum()
        total_value = df_track["평가금액"].sum()
        total_profit = total_value - total_invest
        total_yield = (total_profit / total_invest * 100) if total_invest > 0 else 0

        # ==============================================================
        # 4. 📊 대시보드 출력 (블로그 캡처용)
        # ==============================================================
        col1, col2, col3 = st.columns(3)
        col1.metric("💰 총 투자 원금", f"${total_invest:,.2f}")
        col2.metric("📈 총 평가 금액", f"${total_value:,.2f}", f"${total_profit:+,.2f} ({total_yield:+.2f}%)")
        
        # 승률 계산 (수익인 종목 수 / 전체 종목 수)
        win_count = len(df_track[df_track["평가손익"] > 0])
        win_rate = (win_count / len(df_track)) * 100
        col3.metric("🎯 스캐너 적중률 (승률)", f"{win_rate:.1f}%", f"{len(df_track)}전 {win_count}승")
        
        st.markdown("### 📋 개별 종목 실시간 트래킹 (블로그 인증용)")
        
        # 블로그 캡처 시 깔끔하게 보이도록 데이터 포맷팅 및 정렬
        df_display = df_track[["매수일", "종목코드", "종목명", "매수전략", "매수단가", "현재가", "수량", "투자원금", "평가금액", "평가손익", "수익률(%)"]].copy()
        
        # 달러 기호 및 콤마 포맷팅
        currency_cols = ["매수단가", "현재가", "투자원금", "평가금액", "평가손익"]
        for col in currency_cols:
            df_display[col] = df_display[col].apply(lambda x: f"${x:,.2f}")
            
        df_display["수량"] = df_display["수량"].apply(lambda x: f"{x}주")
        
        # 수익률 포맷팅 (+/- 기호 포함)
        df_display["수익률(%)"] = df_display["수익률(%)"].apply(lambda x: f"{x:+.2f}%")

        # 스타일러를 통해 수익률이 +면 빨간색, -면 파란색으로 색상 입히기 (국장 스타일)
        def color_profit(val):
            if isinstance(val, str) and '%' in val:
                num = float(val.replace('%', '').replace('+', ''))
                color = '#ff4b4b' if num > 0 else '#0068c9' if num < 0 else 'gray'
                return f'color: {color}; font-weight: bold;'
            if isinstance(val, str) and '$' in val and ('+' in val or '-' in val):
                # 평가손익 달러에도 색상 적용
                if val.startswith('$-'): return 'color: #0068c9;'
                else: return 'color: #ff4b4b;'
            return ''

        # 우측 정렬 및 색상 적용
        styled_display = df_display.style.map(color_profit).set_properties(
            subset=["매수단가", "현재가", "수량", "투자원금", "평가금액", "평가손익", "수익률(%)"], 
            **{'text-align': 'right'}
        )

        st.dataframe(styled_display, width='stretch', hide_index=True)

        # 종목 삭제 기능 (익절/손절 시)
        st.divider()
        with st.expander("🗑️ 종목 청산 (포트폴리오에서 삭제)"):
            del_ticker = st.selectbox("삭제할 종목 선택", df_port["종목코드"].tolist())
            if st.button(f"[{del_ticker}] 포트폴리오에서 삭제"):
                df_port = df_port[df_port["종목코드"] != del_ticker]
                save_portfolio(df_port)
                st.success("삭제되었습니다. 화면을 새로고침합니다.")
                st.rerun()
