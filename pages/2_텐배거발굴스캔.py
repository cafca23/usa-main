import streamlit as st
import pandas as pd
from finvizfinance.screener.overview import Overview
from finvizfinance.quote import finvizfinance 
from deep_translator import GoogleTranslator  
import yfinance as yf          
import plotly.graph_objects as go 
import google.generativeai as genai

# 1. 웹 페이지 기본 설정
st.set_page_config(page_title="미장 텐버거 스캔", layout="wide", page_icon="🚀")

@st.cache_data(ttl=3600, show_spinner=False)
def get_chart_data(ticker):
    return yf.Ticker(ticker).history(period="3y", interval="1wk")

@st.cache_data(ttl=86400, show_spinner=False)
def get_translated_profile(ticker):
    stock = finvizfinance(ticker)
    eng_desc = stock.ticker_description()
    translator = GoogleTranslator(source='auto', target='ko')
    return eng_desc, translator.translate(eng_desc) 

# ==============================================================
# 💡 [V7.6 핵심 패치] 404 에러 원천 차단: 생존 모델 자동 추적기
# ==============================================================
@st.cache_data(ttl=86400, show_spinner=False)
def get_ai_commentary(ticker, company, sector, eng_desc, strategy_name, api_key):
    genai.configure(api_key=api_key)
    
    valid_models = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            valid_models.append(m.name)
            
    if not valid_models:
        return "⚠️ 구글 API 키는 인식되었으나, 현재 계정에서 사용할 수 있는 텍스트 생성 모델이 할당되지 않았습니다."
        
    target_model = valid_models[0] 
    for name in valid_models:
        if "1.5-flash" in name:
            target_model = name
            break
        elif "flash" in name:
            target_model = name
            
    model = genai.GenerativeModel(target_model) 
    
    prompt = f"""
    너는 월스트리트 최고의 퀀트 트레이더이자 냉철한 분석가야.
    방금 우리 텐베거 스캐너가 '{strategy_name}' 전략을 통해 아래 종목을 1순위 타깃으로 발굴했어.
    
    * 티커: {ticker}
    * 회사명: {company}
    * 섹터: {sector}
    * 비즈니스 모델(영문): {eng_desc}
    
    이 회사의 비즈니스 모델을 분석하고, 왜 이 종목이 텐베거(10배 상승) 잠재력이 있는지 3~4줄로 핵심만 아주 날카롭고 직관적으로 브리핑해줘. 
    말투는 전문가답고 단호하게, "~입니다.", "~해야 합니다." 체로 작성해.
    """
    
    response = model.generate_content(prompt)
    return f"*(동적 연결된 AI 모델: {target_model})*\n\n{response.text}"

# ==============================================================

st.title("🚀 미장 텐버거 스캔")
st.markdown("월가의 숨겨진 원석을 발굴하고, 텐베거(10배 상승) 잠재력이 가장 높은 순서대로 랭킹을 매겨 추천합니다.")
st.divider()

st.sidebar.header("⚙️ 텐베거 셋팅")

api_key = None
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]

if not api_key:
    st.sidebar.warning("⚠️ Secrets 설정에서 키를 찾을 수 없습니다. 아래에 키를 직접 입력하세요.")
    api_key = st.sidebar.text_input("🔑 Google Gemini API Key", type="password")

strategy = st.sidebar.selectbox(
    "어떤 텐베거 전략을 가동하시겠습니까?",
    ("🔥 성장형 (매출성장주)", "💼 수급형 (기관 매집 스몰캡)", "🛡️ 가치형 (흑자 전환 우량주)")
)

with st.spinner('월가 퀀트 알고리즘 해독 및 텐베거 랭킹 부여 중...'):
    try:
        foverview = Overview()
        
        if "성장형" in strategy:
            desc = "🔥 **[성장형 1위 추천 근거 (니시노 다다스 로직)]**\n\n'당장의 적자를 두려워 마라! 오직 폭발하는 매출(Sales) 성장에 주목하라.'\n\n순이익이 마이너스라도 매출이 30% 이상 폭주하는 기업 중, 시가총액이 가장 작아 세력의 타깃이 되기 쉬운 진정한 **'깃털 같은 유니콘' 1순위 (시가총액 오름차순)** 입니다."
            filters_dict = {
                'Market Cap.': '+Small (over $300mln)',
                'Sales growthqtr over qtr': 'Over 30%', 
                'Gross Margin': 'Over 50%',             
                '50-Day Simple Moving Average': 'Price above SMA50'
            }
            sort_col = 'Market Cap'
            sort_asc = True

        elif "수급형" in strategy:
            desc = "💼 **[수급형 1위 추천 근거]**\n\n기관이 매집 중이면서 최근 시장의 돈이 가장 격렬하게 몰려들고 있는 종목을 1위로 올립니다.\n\n당장 내일 튀어 오를 **단기 모멘텀 최강자 (거래량 내림차순)** 입니다."
            filters_dict = {
                'Market Cap.': '+Small (over $300mln)',
                'InstitutionalOwnership': 'Over 50%', 
                'InstitutionalTransactions': 'Positive (>0%)', 
                'Average Volume': 'Over 500K',        
                '50-Day Simple Moving Average': 'Price above SMA50'
            }
            sort_col = 'Volume'
            sort_asc = False

        else: 
            desc = "🛡️ **[가치형 1위 추천 근거]**\n\n흑자를 내고 있는데 시장에서 가장 심하게 외면받아 가격이 비정상적으로 싼 상태입니다.\n\n이러한 **극단적 딥밸류(Deep Value) 종목을 1순위 (PER 오름차순)** 로 바닥에서 긁어모읍니다."
            filters_dict = {
                'Market Cap.': '+Small (over $300mln)',
                'Debt/Equity': 'Under 1',               
                'Operating Margin': 'Positive (>0%)',   
                'P/B': 'Low (<1)',                      
                'P/E': 'Low (<15)',                     
                '50-Day Simple Moving Average': 'Price above SMA50'
            }
            sort_col = 'P/E'
            sort_asc = True
        
        foverview.set_filter(filters_dict=filters_dict)
        df = foverview.screener_view()
        
        if df.empty:
            st.warning("⚠️ 조건을 만족하는 종목이 없습니다.")
        else:
            if sort_col in df.columns:
                df['_sort_val'] = pd.to_numeric(df[sort_col], errors='coerce')
                df = df.sort_values(by='_sort_val', ascending=sort_asc).dropna(subset=['_sort_val'])
                df = df.drop(columns=['_sort_val'])

            df.insert(0, '🏆 랭킹', range(1, len(df) + 1))
            st.info(desc)
            
            result_df = df[['🏆 랭킹', 'Ticker', 'Company', 'Sector', 'Industry', 'Market Cap', 'P/E', 'Price', 'Volume']].copy()
            
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

            result_df['Market Cap'] = result_df['Market Cap'].apply(format_mcap)
            result_df['Price'] = result_df['Price'].apply(lambda x: f"${float(x):,.2f}" if pd.notna(x) else x)
            result_df['Volume'] = result_df['Volume'].apply(lambda x: f"{float(x):,.0f}주" if pd.notna(x) else x)
            result_df['P/E'] = result_df['P/E'].apply(lambda x: f"{float(x):.1f}배" if pd.notna(x) else "N/A (적자)")

            result_df = result_df.rename(columns={
                'Ticker': '종목코드', 'Company': '회사명', 'Sector': '섹터(업종)', 
                'Industry': '세부산업', 'Market Cap': '시가총액', 
                'P/E': 'PER (저평가 지수)', 'Price': '현재가', 'Volume': '거래량'
            })

            st.dataframe(result_df, width='stretch', hide_index=True)

            st.divider()
            st.subheader("🎯 텐베거 앤트리치 분석")
            
            ticker_list = result_df['종목코드'].tolist()
            company_list = result_df['회사명'].tolist()
            sector_list = result_df['섹터(업종)'].tolist()
            
            display_options = [f"{t} ({c})" for t, c in zip(ticker_list, company_list)]
            selected_option = st.selectbox("정밀 분석할 타깃을 선택하세요:", display_options)
            
            if selected_option:
                selected_ticker = selected_option.split(" ")[0]
                selected_idx = ticker_list.index(selected_ticker)
                selected_company = company_list[selected_idx]
                selected_sector = sector_list[selected_idx]
                
                with st.spinner("비즈니스 모델 해독 및 AI 브리핑 작성 중..."):
                    try:
                        eng_desc, kor_desc = get_translated_profile(selected_ticker)
                        st.markdown(f"#### 🔎 [{selected_ticker}] 비즈니스 모델")
                        st.info(kor_desc)
                        
                        # 💡 월스트리트 스마트머니(기관/내부자) 수급 동향 추출
                        try:
                            fund_data = finvizfinance(selected_ticker).ticker_fundament()
                            inst_own = fund_data.get('Inst Own', 'N/A')
                            inst_trans = fund_data.get('Inst Trans', 'N/A')
                            insider_own = fund_data.get('Insider Own', 'N/A')
                            short_float = fund_data.get('Short Float', 'N/A')
                        except:
                            inst_own, inst_trans, insider_own, short_float = "N/A", "N/A", "N/A", "N/A"

                        st.markdown("#### 🕵️‍♂️ 스마트머니 (기관/세력) 수급 동향")
                        with st.container(border=True):
                            sc1, sc2, sc3, sc4 = st.columns(4)
                            
                            # 💡 [핵심 패치] 기관 보유율(Inst Own) 4단계 평가 로직
                            own_delta = None
                            own_color = "off"
                            if inst_own != "N/A" and "%" in inst_own:
                                try:
                                    own_val = float(inst_own.replace("%", "").replace(",", ""))
                                    if own_val < 20:
                                        own_delta = "🌱 개미 놀이터 (야생의 영역)"
                                        own_color = "off"
                                    elif own_val < 40:
                                        own_delta = "🔥 텐배거 발진 구간 (스마트머니 진입)"
                                        own_color = "normal"
                                    elif own_val <= 70:
                                        own_delta = "⭐️ 우량주 황금비율 (안정적 성장기)"
                                        own_color = "normal"
                                    else:
                                        own_delta = "⚠️ 과열/블루칩 (상승 여력 제한적)"
                                        own_color = "inverse"
                                except: pass
                            
                            sc1.metric("💼 기관 보유율 (Inst Own)", inst_own, delta=own_delta, delta_color=own_color, help="전체 유통 주식 중 월가 기관투자자가 쥐고 있는 물량의 비율입니다. 높을수록 큰 자본이 들어와 있다는 뜻입니다.")
                            
                            trans_delta = None
                            trans_color = "normal"
                            if inst_trans != "N/A" and "%" in inst_trans:
                                try:
                                    trans_val = float(inst_trans.replace("%", "").replace(",", ""))
                                    trans_delta = "매집 중 (비중 확대)" if trans_val > 0 else "이탈 중 (비중 축소)"
                                    trans_color = "normal" if trans_val > 0 else "inverse"
                                except: pass
                                
                            sc2.metric("📈 최근 기관 매매 (Inst Trans)", inst_trans, delta=trans_delta, delta_color=trans_color, help="최근 분기 동안 기관투자자들이 이 주식을 추가로 사 모으고 있는지(+) 내다 팔고 있는지(-) 보여줍니다.")
                            sc3.metric("👔 내부자 보유율 (Insider Own)", insider_own, help="CEO, 창업자 등 회사 내부자가 자사주를 얼마나 쥐고 있는지 보여줍니다.")
                            sc4.metric("📉 공매도 잔고 (Short Float)", short_float, help="유통 주식 중 하락에 베팅한 공매도 세력의 물량 비율입니다. 10%가 넘어가면 숏스퀴즈(급등) 혹은 강한 하락 베팅 위험이 공존합니다.")

                        if api_key:
                            st.markdown(f"#### 🤖 퀀트 앤트리치 브리핑")
                            try:
                                ai_comment = get_ai_commentary(selected_ticker, selected_company, selected_sector, eng_desc, strategy, api_key)
                                st.success(ai_comment)
                            except Exception as ai_error:
                                st.error(f"⚠️ AI 연동 중 오류 발생: {ai_error}")
                        else:
                            st.warning("⚠️ 사이드바에 API 키를 입력해주시면 AI 브리핑이 활성화됩니다.")
                            
                    except Exception as e:
                        st.error(f"기업 정보를 불러오는 데 실패했습니다: {e}")

                with st.spinner('월가 실시간 주봉 차트 렌더링 중...'):
                    try:
                        stock_data = get_chart_data(selected_ticker)
                        
                        if not stock_data.empty:
                            stock_data['MA10'] = stock_data['Close'].rolling(window=10).mean()
                            stock_data['MA20'] = stock_data['Close'].rolling(window=20).mean()
                            stock_data['MA60'] = stock_data['Close'].rolling(window=60).mean()
                            stock_data['MA120'] = stock_data['Close'].rolling(window=120).mean()

                            fig = go.Figure(data=[go.Candlestick(x=stock_data.index,
                                            open=stock_data['Open'], high=stock_data['High'],
                                            low=stock_data['Low'], close=stock_data['Close'],
                                            increasing_line_color='red', increasing_fillcolor='red',   
                                            decreasing_line_color='blue', decreasing_fillcolor='blue', 
                                            name="주가")])
                            
                            fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data['MA10'], line=dict(color='orange', width=1.5), name='10주선 (단기생명선)'))
                            fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data['MA20'], line=dict(color='green', width=1.5), name='20주선 (스윙추세선)'))
                            fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data['MA60'], line=dict(color='gray', width=2), name='60주선 (장기수급선)'))
                            fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data['MA120'], line=dict(color='purple', width=2.5), name='120주선 (경기바닥선)'))

                            fig.update_layout(
                                title=f"📊 {selected_ticker} 주봉 차트",
                                xaxis_rangeslider_visible=False,
                                height=750,  
                                margin=dict(l=0, r=0, t=40, b=0)
                            )
                            
                            st.plotly_chart(fig, width='stretch')
                        else:
                            st.error("차트 데이터를 불러올 수 없습니다.")
                    except Exception as e:
                        st.error("차트 데이터를 일시적으로 불러올 수 없습니다.")

    except Exception as e:
        st.error(f"❌ 접속 지연 또는 오류 발생 (상세 에러: {e})")
