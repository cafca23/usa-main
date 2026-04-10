import streamlit as st
import pandas as pd
import numpy as np
import urllib.request
import json
from finvizfinance.screener.overview import Overview
from finvizfinance.quote import finvizfinance 
from deep_translator import GoogleTranslator  
import yfinance as yf          
import plotly.graph_objects as go 
import google.generativeai as genai

# ==============================================================
# 0. 웹 페이지 기본 설정
# ==============================================================
st.set_page_config(page_title="앤트리치 딥밸류 관제탑", layout="wide", page_icon="🦅")

# ==============================================================
# 1. 💡 공통 캐시 도우미 함수 (속도 최적화)
# ==============================================================
@st.cache_data(ttl=3600, show_spinner=False)
def get_chart_data(ticker, period="5y"):
    return yf.Ticker(ticker).history(period=period, interval="1wk")

@st.cache_data(ttl=86400, show_spinner=False)
def get_translated_profile(ticker):
    stock = finvizfinance(ticker)
    eng_desc = stock.ticker_description()
    translator = GoogleTranslator(source='auto', target='ko')
    return eng_desc, translator.translate(eng_desc) 

def format_days_to_ym(days):
    if pd.isna(days) or days == 0: return "0일"
    days = int(days)
    years, months = days // 365, (days % 365) // 30
    if years > 0: return f"{days}일 ({years}년 {months}개월)" if months > 0 else f"{days}일 ({years}년)"
    return f"{days}일 ({months}개월)" if months > 0 else f"{days}일"

# ==============================================================
# 2. 💡 AI 동적 엔진 (가치 트랩 판독 기능 탑재)
# ==============================================================
@st.cache_data(ttl=86400, show_spinner=False)
def get_dynamic_ai_model(api_key):
    genai.configure(api_key=api_key)
    valid_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    if not valid_models: return None, "⚠️ 텍스트 생성 모델을 찾을 수 없습니다."
    
    target_model = valid_models[0]
    for name in valid_models:
        if "1.5-flash" in name: target_model = name; break
        elif "flash" in name: target_model = name
    return target_model, None

@st.cache_data(ttl=86400, show_spinner=False)
def get_ai_commentary_sniper(ticker, company, sector, eng_desc, api_key):
    target_model, err = get_dynamic_ai_model(api_key)
    if err: return err
    
    try:
        news_data = yf.Ticker(ticker).news[:5] 
        recent_news = "\n".join([f"- {n['title']}" for n in news_data]) if news_data else "최근 주요 뉴스 없음"
    except:
        recent_news = "뉴스 검색 실패"

    model = genai.GenerativeModel(target_model) 
    
    prompt = f"""
    너는 워런 버핏과 찰리 멍거 수준의 통찰력을 가진 월스트리트 가치투자 애널리스트야.
    이 기업은 재무 숫자는 튼튼하지만, 최근 고점 대비 -50% 이상 크게 폭락했어. 
    이것이 '위장된 축복(일시적 악재)'인지, 아니면 절대 피해야 할 '가치 트랩(Value Trap)'인지 판별해야 해.

    [기업 정보]
    * 티커: {ticker}
    * 회사명: {company}
    * 비즈니스 모델: {eng_desc}

    [최근 실시간 뉴스 헤드라인]
    {recent_news}

    위 정보와 너의 지식(검색엔진 수준의 과거 데이터)을 바탕으로 다음 3가지 치명적 레드플래그가 발생했는지 검사해:
    1. 경쟁자에게 시장 점유율을 영구적으로 뺏김 (구조적 침체)
    2. 핵심 비즈니스 모델의 붕괴 (시대적 도태)
    3. 분식회계, CEO 리스크, 치명적 소송 등 범죄/도덕성 문제

    [출력 형식]
    1. 🚨 판정: [✅ 일시적 악재 (바겐세일)] 또는 [❌ 가치 트랩 위험!! (매수 금지)] 중 하나를 최상단에 명시.
    2. 🔍 분석: 폭락의 진짜 이유와 위 3가지 레드플래그 해당 여부를 3~4줄로 아주 날카롭게 브리핑해줘.
    """
    
    return f"*(동적 연결: {target_model})*\n\n{model.generate_content(prompt).text}"

# ==============================================================
# 3. 🖥️ 사이드바 공통 설정
# ==============================================================
st.sidebar.title("🦅 앤트리치 딥밸류 관제탑")
st.sidebar.markdown("우량주 스나이핑 및 MDD 정밀 타점 통합 컨트롤러")
st.sidebar.divider()

api_key = st.secrets.get("GEMINI_API_KEY", None)
if not api_key:
    st.sidebar.warning("⚠️ Secrets 키 없음. 수동 입력하세요.")
    api_key = st.sidebar.text_input("🔑 Google Gemini API Key", type="password")

st.sidebar.header("⚙️ MDD 분석 설정")
target_mdd = st.sidebar.number_input("📉 목표 분석 하락률 (%)", min_value=-90.0, max_value=-5.0, value=-50.0, step=5.0)
buffer = st.sidebar.slider("🎯 하락률 오차 범위 (±%)", min_value=1.0, max_value=10.0, value=5.0, step=1.0)

# ==============================================================
# 4. 🚀 메인 대시보드 (스캐너 ➔ AI ➔ 차트 ➔ MDD 폭포수 전개)
# ==============================================================
st.title("🛡️ USA 우량주 바닥 스나이퍼 & 타점 계산기")
st.markdown("펀더멘탈은 변하지 않았으나 억울하게 **-50% 이상 폭락한 우량 기업**을 발굴하고, 즉시 **MDD 분할매수 타점**을 조준합니다.")
st.divider()

with st.spinner('월가 낙폭과대 딥밸류 종목 스캔 중...'):
    try:
        foverview = Overview()
        desc = "🩸 **[피가 낭자할 때 사라 (낙폭과대 우량주)]**\n\n시가총액 20억 달러(약 2조 8,000억원) 이상, 고점 대비 절반(-50%) 이하 폭락, 부채비율 1 이하의 흑자 기업입니다. **(시가총액 내림차순)**"
        filters_dict = {'Market Cap.': '+Mid (over $2bln)', '52-Week High/Low': '50% or more below High', 'Debt/Equity': 'Under 1', 'Operating Margin': 'Positive (>0%)', 'Average Volume': 'Over 500K'}
        foverview.set_filter(filters_dict=filters_dict)
        df = foverview.screener_view()
        
        if df.empty: 
            st.warning("⚠️ 현재 시장에 조건을 만족하는 억울한 우량주가 없습니다.")
        else:
            df['_sort_val'] = pd.to_numeric(df['Market Cap'], errors='coerce')
            df = df.sort_values(by='_sort_val', ascending=False).dropna(subset=['_sort_val']).drop(columns=['_sort_val'])
            df.insert(0, '🏆 랭킹', range(1, len(df) + 1))
            st.info(desc)
            
            res_df = df[['🏆 랭킹', 'Ticker', 'Company', 'Sector', 'Industry', 'Market Cap', 'P/E', 'Price', 'Volume']].copy()
            
            def format_mcap(val):
                try:
                    v = float(val)
                    usd_str = f"${v:,.0f}" 
                    krw_val = v * 1400     
                    if krw_val >= 1_000_000_000_000: krw_str = f"(약 {krw_val / 1_000_000_000_000:.1f}조원)"
                    elif krw_val >= 100_000_000: krw_str = f"(약 {krw_val / 100_000_000:.0f}억원)"
                    else: krw_str = f"(약 {krw_val:,.0f}원)"
                    return f"{usd_str} {krw_str}"
                except:
                    return val

            res_df['Market Cap'] = res_df['Market Cap'].apply(format_mcap)
            res_df['Price'] = res_df['Price'].apply(lambda x: f"${float(x):,.2f}" if pd.notna(x) else x)
            res_df['Volume'] = res_df['Volume'].apply(lambda x: f"{float(x):,.0f}주" if pd.notna(x) else x)
            res_df['P/E'] = res_df['P/E'].apply(lambda x: f"{float(x):.1f}배" if pd.notna(x) else "N/A (적자)")

            res_df = res_df.rename(columns={
                'Ticker': '종목코드', 'Company': '회사명', 'Sector': '섹터(업종)', 
                'Industry': '세부산업', 'Market Cap': '시가총액', 
                'P/E': 'PER (저평가 지수)', 'Price': '현재가', 'Volume': '거래량'
            })

            # 💡 [핵심 패치] 데이터프레임 스타일러를 이용해 숫자 컬럼들만 우측 정렬 강제 적용
            styled_df = res_df.style.set_properties(
                subset=['시가총액', 'PER (저평가 지수)', '현재가', '거래량'], 
                **{'text-align': 'right'}
            )

            st.dataframe(
                styled_df, 
                width='stretch', 
                hide_index=True,
                column_config={
                    "종목코드": st.column_config.TextColumn("종목코드", help="미국 증시에 상장된 고유 티커(알파벳)입니다."),
                    "회사명": st.column_config.TextColumn("회사명", help="해당 기업의 공식 영문 명칭입니다."),
                    "섹터(업종)": st.column_config.TextColumn("섹터(업종)", help="기업이 속한 대분류 산업군입니다. (예: 테크, 헬스케어 등)"),
                    "세부산업": st.column_config.TextColumn("세부산업", help="기업이 속한 소분류 세부 비즈니스 영역입니다."),
                    "시가총액": st.column_config.TextColumn("시가총액", help="기업의 전체 덩치(발행주식수 × 주가)입니다. 괄호 안은 원화 환산 추정치입니다."),
                    "PER (저평가 지수)": st.column_config.TextColumn("PER (저평가 지수)", help="주가수익비율. 1주당 순이익 대비 주가가 몇 배로 거래되는지 나타냅니다."),
                    "현재가": st.column_config.TextColumn("현재가", help="현재 거래되는 주식의 1주당 가격(달러)입니다."),
                    "거래량": st.column_config.TextColumn("거래량", help="최근 하루 동안 거래된 주식의 총 수량입니다.")
                }
            )

            st.divider()
            st.subheader("🎯 딥밸류 타점 조준 (AI 브리핑 ➔ 차트 ➔ MDD 계산기)")
            
            sel_opt = st.selectbox("정밀 분석할 타깃을 선택하세요:", [f"{t} ({c})" for t, c in zip(res_df['종목코드'], res_df['회사명'])])
            
            if sel_opt:
                t_tkr = sel_opt.split(" ")[0]
                t_idx = res_df['종목코드'].tolist().index(t_tkr)
                
                # --- 1. AI 비즈니스 & 턴어라운드 브리핑 ---
                with st.spinner("비즈니스 모델 해독 및 실시간 뉴스 기반 가치 트랩 분석 중..."):
                    try:
                        eng_desc, kor_desc = get_translated_profile(t_tkr)
                        st.markdown(f"#### 🔎 [{t_tkr}] 비즈니스 모델")
                        st.info(kor_desc)
                        
                        if api_key:
                            st.markdown(f"#### 🤖 퀀트 AI 가치 트랩 판독 리포트")
                            try: st.success(get_ai_commentary_sniper(t_tkr, res_df['회사명'].iloc[t_idx], res_df['섹터(업종)'].iloc[t_idx], eng_desc, api_key))
                            except Exception as e: st.error(f"⚠️ 오류: {e}")
                    except Exception as e:
                        st.error("기업 정보를 불러오는 데 실패했습니다.")

                # --- 2. 5년 장기 주봉 차트 ---
                with st.spinner('월가 실시간 5년치 주봉 차트 렌더링 중...'):
                    try:
                        sd = get_chart_data(t_tkr, "5y")
                        if not sd.empty:
                            sd['MA20'], sd['MA60'], sd['MA120'], sd['MA200'] = sd['Close'].rolling(20).mean(), sd['Close'].rolling(60).mean(), sd['Close'].rolling(120).mean(), sd['Close'].rolling(200).mean()
                            
                            fig = go.Figure(data=[go.Candlestick(
                                x=sd.index, open=sd['Open'], high=sd['High'], low=sd['Low'], close=sd['Close'], name="주가",
                                increasing_line_color='red', increasing_fillcolor='red',   
                                decreasing_line_color='blue', decreasing_fillcolor='blue'
                            )])
                            
                            fig.add_trace(go.Scatter(x=sd.index, y=sd['MA20'], line=dict(color='green', width=1.5, dash='dot'), name='20주선'))
                            fig.add_trace(go.Scatter(x=sd.index, y=sd['MA60'], line=dict(color='blue', width=2), name='60주선'))
                            fig.add_trace(go.Scatter(x=sd.index, y=sd['MA120'], line=dict(color='yellow', width=3), name='120주선 (경기바닥선)'))
                            fig.add_trace(go.Scatter(x=sd.index, y=sd['MA200'], line=dict(color='white', width=3), name='200주선 (최후지옥선)'))
                            fig.update_layout(title=f"📊 {t_tkr} 장기 주봉 차트 (딥밸류 스나이핑)", xaxis_rangeslider_visible=False, height=600)
                            st.plotly_chart(fig, width='stretch')
                    except Exception as e:
                        st.error("차트 데이터를 불러올 수 없습니다.")

                # --- 3. MDD & 분할매수 계산기 ---
                st.divider()
                st.markdown(f"### ⏱️ [{t_tkr}] MDD 및 기계적 분할매수 타점 분석")
                with st.spinner("역대 최고점 대비 하락장(MDD) 데이터를 계산 중입니다..."):
                    try:
                        mdd_data = yf.Ticker(t_tkr).history(period="max")
                        if not mdd_data.empty:
                            df_mdd = mdd_data[['Close']].copy().dropna()
                            df_mdd['Peak'] = df_mdd['Close'].cummax()
                            df_mdd['Drawdown'] = (df_mdd['Close'] - df_mdd['Peak']) / df_mdd['Peak']
                            
                            curr_p, curr_peak = df_mdd['Close'].iloc[-1], df_mdd['Peak'].iloc[-1]
                            curr_dd = df_mdd['Drawdown'].iloc[-1] * 100
                            
                            peak_dates = df_mdd[df_mdd['Drawdown'] == 0].index
                            periods = [{'start': peak_dates[i], 'end': peak_dates[i+1], 'max_drop': df_mdd.loc[peak_dates[i]:peak_dates[i+1], 'Drawdown'].min() * 100, 'days': (peak_dates[i+1] - peak_dates[i]).days} for i in range(len(peak_dates) - 1)]
                            periods_df = pd.DataFrame(periods)
                            
                            max_mdd_val = periods_df['max_drop'].min() if not periods_df.empty else curr_dd
                            max_days_val = periods_df['days'].max() if not periods_df.empty else 0

                            c1, c2, c3, c4 = st.columns(4)
                            c1.metric("현재가", f"${curr_p:.2f}")
                            c2.metric("MDD (고점대비 하락률)", f"{curr_dd:.2f}%", delta=f"고점 이후 {format_days_to_ym((df_mdd.index[-1]-peak_dates[-1]).days)}째", delta_color="inverse")
                            c3.metric("역대 최악 폭락 (MAX MDD)", f"{max_mdd_val:.2f}%")
                            c4.metric("역대 최장 회복기간", format_days_to_ym(max_days_val))

                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.markdown("##### 📍 기계적 분할 매수 타점")
                                t_data = []
                                for l in np.arange(-20, -85, -5):
                                    tp = curr_peak * (1 + (l/100))
                                    pct = (len(df_mdd[df_mdd['Drawdown'] >= (l/100)]) / len(df_mdd)) * 100
                                    status = "🔥 진입 시작" if pct >= 75.0 and curr_p <= tp else "🎯 진입 타겟" if pct >= 75.0 else "⚠️ 관망" if curr_p <= tp else "⏳ 대기 중"
                                    t_data.append({"목표 하락률": f"{l}%", "단가": f"${tp:.2f}", "상태": status})
                                
                                t_df = pd.DataFrame(t_data)
                                
                                def highlight_target(row):
                                    if "진입" in row['상태']:
                                        return ['background-color: #00FF00; color: black; font-weight: bold;'] * len(row)
                                    return [''] * len(row)
                                
                                st.dataframe(t_df.style.apply(highlight_target, axis=1), width='stretch', hide_index=True)

                            with col_b:
                                st.markdown("##### 📊 하락 깊이별 매수 메리트")
                                m_data = [{"MDD 깊이": f"{m}%", "매수 메리트 (역사적 하위)": f"{(len(df_mdd[df_mdd['Drawdown'] >= (m/100)]) / len(df_mdd)) * 100:.1f}%"} for m in np.arange(0, -95, -5)]
                                st.dataframe(pd.DataFrame(m_data), width='stretch', hide_index=True)

                            target_periods = periods_df[(periods_df['max_drop'] >= target_mdd - buffer) & (periods_df['max_drop'] <= target_mdd + buffer)]
                            if not target_periods.empty:
                                st.info(f"💡 **앤트리치 퀀트 멘탈세팅:** 통계상 **{target_mdd}%** 부근으로 하락했을 때, 전고점 탈환까지 평균 **{format_days_to_ym(int(target_periods['days'].mean()))}**이 걸렸습니다. 자금 투입 시 이 기간을 염두에 두고 호흡을 조절하세요!")
                            else:
                                st.warning(f"⚠️ 역사상 {target_mdd}% 수준의 하락 후 완전히 회복된 기록이 아직 없습니다.")
                    except Exception as e:
                        st.error(f"MDD 데이터를 불러오는 중 오류가 발생했습니다. ({e})")
                        
    except Exception as e:
        st.error(f"❌ 스크리너 접속 지연 또는 오류 발생 (상세 에러: {e})")
