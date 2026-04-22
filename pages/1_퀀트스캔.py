import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import google.generativeai as genai
import re
import time
import requests
from finvizfinance.quote import finvizfinance 
from deep_translator import GoogleTranslator 

st.set_page_config(page_title="1. 미장 All 퀀트 스캐너", layout="wide", page_icon="📈", initial_sidebar_state="expanded")

# --- Custom Premium CSS ---
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 26px !important; font-weight: 700 !important; color: #e6edf3; }
    [data-testid="stMetricLabel"] { color: #8b949e !important; font-weight: 600 !important; text-transform: uppercase; font-size: 0.85rem !important; letter-spacing: 0.05em; }
    .banner { padding: 1.5rem; border-radius: 8px; margin-bottom: 2rem; box-shadow: 0 4px 15px rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: space-between; }
    .buy-banner { background: linear-gradient(135deg, #0d47a1 0%, #1976d2 100%); color: white; border: 1px solid #1565c0; } 
    .hold-banner { background: linear-gradient(135deg, #052e16 0%, #166534 100%); color: white; border: 1px solid #15803d; }
    .sell-banner { background: linear-gradient(135deg, #450a0a 0%, #991b1b 100%); color: white; border: 1px solid #b91c1c; } 
    .banner-left { flex: 1; text-align: left; padding-right: 20px; border-right: 1px solid rgba(255,255,255,0.2); }
    .banner-right { flex: 1; text-align: center; padding-left: 20px; }
    .banner h2 { margin: 0; padding: 0; font-size: 2.2rem; text-shadow: 0 2px 4px rgba(0,0,0,0.4); }
    .banner p { margin: 8px 0 0 0; font-size: 1.15rem; opacity: 0.95; font-weight: 500;}
    .checklist-box { background-color: #161b22; padding: 20px; border-radius: 8px; border: 1px solid #30363d; height: 100%; display: flex; flex-direction: column; justify-content: space-between; }
    .badge { padding: 5px 10px; border-radius: 5px; font-weight: bold; font-size: 0.9rem; margin-bottom: 10px; display: inline-block; }
    .badge-growth { background-color: rgba(162, 28, 175, 0.2); color: #e879f9; border: 1px solid #c026d3; }
    .badge-value { background-color: rgba(3, 105, 161, 0.2); color: #38bdf8; border: 1px solid #0284c7; }
    .peer-table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.95rem; }
    .peer-table th { background-color: #161b22; color: #8b949e; padding: 12px 8px; text-align: right; border-bottom: 2px solid #30363d; font-weight: 600; cursor: help; }
    .peer-table th:first-child { text-align: left; }
    .peer-table td { padding: 10px 8px; text-align: right; border-bottom: 1px solid #21262d; color: #e6edf3; }
    .peer-table td:first-child { text-align: left; font-weight: bold; }
    .peer-main-row { background-color: rgba(56, 189, 248, 0.1); border-left: 4px solid #38bdf8; }
    .peer-median-row { background-color: #21262d; font-weight: bold; color: #8b949e; border-top: 2px solid #30363d; }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=86400, show_spinner=False)
def get_korean_profile(ticker, eng_name, eng_desc, api_key):
    try:
        if not api_key:
            translator = GoogleTranslator(source='auto', target='ko')
            short_desc = eng_desc.split(". ")[0] + "." if eng_desc else "기업 설명이 없습니다."
            return eng_name, translator.translate(short_desc)

        genai.configure(api_key=api_key)
        valid_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target_model = valid_models[0] if valid_models else 'models/gemini-1.5-flash'
        for name in valid_models:
            if "1.5-flash" in name: target_model = name; break
        
        model = genai.GenerativeModel(target_model)
        prompt = f"""
        미국 주식 티커 {ticker} ({eng_name})의 영문 설명이야: {eng_desc}
        이 정보를 바탕으로 한국 증권사(토스, 네이버 등)에서 보여줄 법한 아주 깔끔한 형태의 '한글 종목명'과 '1줄 비즈니스 요약'을 작성해줘.
        예시) 이오밴스 바이오테라퓨틱스|면역 체계를 활용한 암 치료제 개발 및 상용화에 주력하는 제약바이오 회사
        
        반드시 '한글종목명|1줄요약' 형태로만 대답해. 다른 말은 절대 금지.
        """
        res = model.generate_content(prompt).text.strip()
        if "|" in res:
            return res.split("|")[0].strip(), res.split("|")[1].strip()
        return eng_name, res
    except:
        return eng_name, "기업 요약 정보를 불러올 수 없습니다."

@st.cache_data(ttl=86400, show_spinner=False)
def get_all_us_tickers():
    etf_list = [
        "SPY (SPDR S&P 500 ETF Trust)", "QQQ (Invesco QQQ Trust)", "DIA (SPDR Dow Jones Industrial Average ETF)",
        "TQQQ (ProShares UltraPro QQQ)", "SQQQ (ProShares UltraPro Short QQQ)", "SOXX (iShares Semiconductor ETF)",
        "SOXL (Direxion Daily Semiconductor Bull 3X)", "SOXS (Direxion Daily Semiconductor Bear 3X)",
        "TSLL (Direxion Daily TSLA Bull 2X)", "TSLQ (AXS TSLA Bear Daily ETF)",
        "SCHD (Schwab US Dividend Equity ETF)", "JEPI (JPMorgan Equity Premium Income ETF)",
        "VOO (Vanguard S&P 500 ETF)", "VTI (Vanguard Total Stock Market ETF)", "ARKK (ARK Innovation ETF)",
        "NVDL (GraniteShares 1.5x Long NVDA)", "NVDS (AXS 1.25x NVDA Bear ETF)", 
        "FNGU (MicroSectors FAANG+ Bull 3X)", "UPRO (ProShares UltraPro S&P500)",
        "CONY (GraniteShares 1.5x Long COIN)"
    ]
    tickers = []
    try:
        url = "https://www.sec.gov/files/company_tickers.json"
        headers = {"User-Agent": "AntRichQuantBot/1.0 (antrichquant@google.com)"}
        res = requests.get(url, headers=headers, timeout=5)
        data = res.json()
        for v in data.values():
            tickers.append(f"{v['ticker']} ({v['title'].title()})")
    except: pass
    
    top_stocks = ["AAPL (Apple Inc.)", "MSFT (Microsoft Corp)", "NVDA (NVIDIA Corp)", "TSLA (Tesla Inc.)", "AMZN (Amazon.com Inc.)", "GOOGL (Alphabet Inc.)", "META (Meta Platforms Inc.)"]
    combined = top_stocks + etf_list + tickers
    
    seen = set()
    result = []
    for item in combined:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result

def parse_fz(val, vtype='float'):
    if not isinstance(val, str): return val
    if val == '-' or val == 'N/A' or val == '': return None
    val = val.replace(',', '')
    try:
        if vtype == 'percent': return float(val.replace('%', '')) / 100.0
        elif vtype == 'large_num':
            if 'B' in val: return float(val.replace('B', '')) * 1e9
            if 'M' in val: return float(val.replace('M', '')) * 1e6
            if 'K' in val: return float(val.replace('K', '')) * 1e3
            return float(val)
        else: return float(val)
    except: return None

@st.cache_data(ttl=3600, show_spinner=False)
def get_macro_data():
    try: usdkrw = yf.Ticker("USDKRW=X").history(period="1d")['Close'].iloc[-1]
    except: usdkrw = 1350.0
    try: tnx = yf.Ticker("^TNX").history(period="1d")['Close'].iloc[-1]
    except: tnx = 4.2  
    return float(usdkrw), float(tnx)

@st.cache_data(ttl=86400, show_spinner="AI가 해당 산업의 최적 경쟁사를 탐색 중입니다... 🕵️‍♂️")
def get_dynamic_peers(ticker, name, sector):
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"temperature": 0.1})
        prompt = f"Find 3 major US publicly traded competitors for {name} ({ticker}) in the {sector} sector. Return ONLY the 3 ticker symbols separated by commas (e.g., CVX, XOM, COP). No markdown, no explanation."
        res = model.generate_content(prompt)
        clean_res = res.text.strip().replace(" ", "").replace("\n", "")
        if len(clean_res) > 20: return ""
        return clean_res
    except: return ""

@st.cache_data(ttl=300, show_spinner="경쟁사 멀티플 데이터를 수집 중입니다... 🐢") 
def get_peers_data(ticker, peer_str):
    peer_list = [p.strip().upper() for p in peer_str.split(",") if p.strip()]
    if ticker not in peer_list:
        peer_list = [ticker] + peer_list
    data = []
    
    for p in peer_list:
        info = {}
        fund = {}
        try: info = yf.Ticker(p).info or {}
        except: pass
        if not info.get('forwardPE'):
            try: fund = finvizfinance(p).ticker_fundament()
            except: pass

        fwd_pe = info.get("forwardPE")
        if fwd_pe is None: fwd_pe = parse_fz(fund.get('Forward P/E'))
        
        ps = info.get("priceToSalesTrailing12Months")
        if ps is None: ps = parse_fz(fund.get('P/S'))
        
        ev_ebitda = info.get("enterpriseToEbitda", np.nan)
        ev_rev = info.get("enterpriseToRevenue", np.nan)
        
        price = info.get("currentPrice")
        if price is None: price = parse_fz(fund.get('Price'))

        data.append({
            "Ticker": p,
            "Price": price if price is not None else np.nan,
            "Fwd P/E": fwd_pe if fwd_pe is not None else np.nan,
            "EV/EBITDA": ev_ebitda if pd.notna(ev_ebitda) else np.nan,
            "P/S": ps if ps is not None else np.nan,
            "EV/Rev": ev_rev if pd.notna(ev_rev) else np.nan
        })
        time.sleep(0.5) 
        
    return pd.DataFrame(data)

@st.cache_data(ttl=300, show_spinner="티커 재무 및 차트 데이터를 분석 중입니다... 📡") 
def get_stock_market_data(ticker):
    stock = yf.Ticker(ticker)
    info = {}
    try: info = stock.info or {}
    except: pass
        
    fund_data = {}
    try: fund_data = finvizfinance(ticker).ticker_fundament()
    except: pass
    
    fcf_yf = None
    try:
        cf = stock.cash_flow
        if 'Free Cash Flow' in cf.index:
            fcf_yf = float(cf.loc['Free Cash Flow'].iloc[0])
    except: pass

    hist_daily_5y = pd.DataFrame()
    for attempt in range(2):
        try:
            hist_daily_5y = stock.history(period="5y", interval="1d")
            if not hist_daily_5y.empty: break
        except: time.sleep(1)

    hist = pd.DataFrame()
    hist_weekly = pd.DataFrame()
    
    if not hist_daily_5y.empty:
        hist = hist_daily_5y.tail(504).copy()
        hist_weekly = hist_daily_5y.resample('W-FRI').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()

    hist_10y = pd.DataFrame()
    for attempt in range(2):
        try:
            hist_10y = stock.history(period="10y", interval="1mo")
            if not hist_10y.empty: break
        except: time.sleep(1)
            
    return info, fund_data, fcf_yf, hist, hist_10y, hist_weekly

ex_rate, risk_free_rate = get_macro_data()

PEER_MAP = {
    "ORCL": "MSFT, CRM, SAP", "AAPL": "MSFT, GOOGL, DELL", "MSFT": "AAPL, GOOGL, ORCL",
    "TSLA": "TM, F, GM", "NVDA": "AMD, INTC, TSM", "GOOGL": "META, MSFT, AMZN",
    "AMZN": "WMT, TGT, GOOGL", "META": "GOOGL, SNAP, PINS", "AMD": "NVDA, INTC, QCOM"
}

all_tickers_list = get_all_us_tickers()

if "target_ticker" not in st.session_state:
    st.session_state.target_ticker = "AAPL"

def handle_search():
    val = st.session_state.search_dropdown
    if val and val not in ["🔍 종목을 검색/선택하세요...", "➕ 직접 티커 수동 입력..."]:
        st.session_state.target_ticker = val.split(" ")[0].upper()
        st.session_state.search_dropdown = "🔍 종목을 검색/선택하세요..."

with st.sidebar:
    st.markdown("### ⚙️ 분석 설정")
    
    st.selectbox(
        "🔍 종목 검색 (알파벳을 치면 자동완성 됨)", 
        ["🔍 종목을 검색/선택하세요...", "➕ 직접 티커 수동 입력..."] + all_tickers_list, 
        key="search_dropdown",
        on_change=handle_search,
        help="종목을 선택하면 자동으로 스캔이 시작되며, 검색창은 다음 검색을 위해 비워집니다."
    )
    
    if st.session_state.search_dropdown == "➕ 직접 티커 수동 입력...":
        manual_input = st.text_input("티커를 정확히 입력하고 엔터를 치세요 (예: SOXL)")
        if manual_input:
            st.session_state.target_ticker = manual_input.strip().upper()
            
    ticker_input = st.session_state.target_ticker
    
    st.success(f"🎯 현재 분석 타깃: **{ticker_input}**")
    
    st.divider()
    
    st.markdown("### 🤝 동종 업계 (Peer) 설정")
    default_peers = "MSFT, GOOGL, AAPL" 
    default_g = 15.0
    sgr_caption = "💡 AI 추천 성장률: 정보 없음 (기본값 15.0% 적용)"
    stock_type_label = "분석 중..."
    guide_text = "티커를 입력하면 알맞은 성장률 가이드를 제공합니다."
    
    if ticker_input:
        ticker_for_sidebar = ticker_input
        try:
            info_sb, _, _, _, _, _ = get_stock_market_data(ticker_for_sidebar)
            if ticker_for_sidebar in PEER_MAP:
                default_peers = PEER_MAP[ticker_for_sidebar]
            else:
                company_name_sb = info_sb.get('shortName', ticker_for_sidebar)
                sector_sb_str = info_sb.get('sector', '')
                ai_peers = get_dynamic_peers(ticker_for_sidebar, company_name_sb, sector_sb_str)
                if ai_peers: default_peers = ai_peers
            
            roe_sb = info_sb.get('returnOnEquity', 0)
            payout_sb = info_sb.get('payoutRatio', 0) if info_sb.get('payoutRatio') else 0
            sector_sb = str(info_sb.get('sector', '')).lower()
            industry_sb = str(info_sb.get('industry', '')).lower()
            
            is_value_stock = False
            value_sectors = ["consumer defensive", "utilities", "energy", "real estate", "financial services", "basic materials", "industrials"]
            if any(v_sec in sector_sb for v_sec in value_sectors) or payout_sb >= 0.40:
                is_value_stock = True
            
            if "aerospace" in industry_sb or "defense" in industry_sb:
                is_value_stock = False
            
            if is_value_stock:
                stock_type_label = "🏛️ 전통 가치주 / 배당주"
                guide_text = "성장이 둔화된 성숙한 캐시카우 기업입니다. 워런 버핏식 보수적 평가를 위해 **3% ~ 5%** 내외의 낮은 성장률로 강제 세팅하는 것을 강력히 권장합니다."
                default_g = 5.0
                sgr_caption = f"💡 전통 가치주 보수적 세팅: {default_g}% (강제 고정)"
            else:
                stock_type_label = "🚀 테크 / 고성장주"
                guide_text = "혁신과 성장이 기대되는 기업입니다. 하단의 'SGR 기반(AI추천)' 버튼을 누르시거나, 본인의 기대치에 따라 **10% ~ 20% 이상**의 성장을 가정해 볼 수 있습니다."
                if roe_sb is not None and roe_sb > 0:
                    sgr = max(5.0, min(roe_sb * (1 - payout_sb) * 100, 50.0))
                    default_g = float(round(sgr, 1))
                    sgr_caption = f"💡 자동 추천 성장률(SGR 기반): {default_g}%"
        except: pass

    peer_input = st.text_input("경쟁사 티커 (쉼표로 구분)", value=default_peers, help="AI가 자동으로 찾아낸 경쟁사입니다. 직접 수정하셔도 됩니다.")

    if 'last_ticker' not in st.session_state or st.session_state.last_ticker != ticker_input or st.session_state.get('app_version') != 'v_final_us_grid':
        st.session_state.g_slider = default_g
        st.session_state.last_ticker = ticker_input
        st.session_state.app_version = 'v_final_us_grid'
        
    st.divider()
    
    st.markdown("### 🌐 거시경제(매크로) 연동")
    st.info(f"실시간 美 10년물 국채 금리: **{risk_free_rate:.2f}%**")
    discount_rate = round(risk_free_rate + 5.0, 1) 
    st.caption(f"💡 AI 자동 세팅 할인율: **{discount_rate}%** (국채 금리 + 시장리스크 5%)")
    
    st.divider()
    
    st.markdown("### 🌱 성장률(g) 세팅 가이드")
    st.markdown(f"**🤖 AI 종목 판독:** `{stock_type_label}`")
    st.info(guide_text)
        
    def set_g(val): st.session_state.g_slider = val

    g = st.slider("예상 성장률 (g) %", min_value=0.0, max_value=50.0, step=0.5, key="g_slider", help="기업의 향후 5~10년 기대 성장률")
    c1, c2, c3, c4 = st.columns(4)
    c1.button("5", on_click=set_g, args=(5.0,), width="stretch")
    c2.button("10", on_click=set_g, args=(10.0,), width="stretch")
    c3.button("20", on_click=set_g, args=(20.0,), width="stretch")
    c4.button("30", on_click=set_g, args=(30.0,), width="stretch")
    st.button("🔄 SGR 기반 (AI추천)", on_click=set_g, args=(default_g,), width="stretch")
    st.caption(sgr_caption)

def fmt_price(val):
    if pd.isna(val) or val == "N/A" or val is None or val == 0: return "N/A"
    try:
        v = float(val)
        usd_str = f"${v:,.2f}"
        krw_val = v * ex_rate
        if krw_val >= 1_000_000_000_000: krw_str = f"₩{krw_val/1e12:.1f}조"
        elif krw_val >= 100_000_000: krw_str = f"₩{krw_val/1e8:.0f}억"
        else: krw_str = f"₩{krw_val:,.0f}"
        return f"{usd_str} ({krw_str})"
    except:
        return "N/A"

def fmt_multi(val):
    if pd.isna(val) or val == "N/A" or val is None or val == 0: return "-"
    return f"{val:.2f}배"

def fmt_pct(val):
    if pd.isna(val) or val == "N/A" or val is None: return "N/A"
    return f"{val * 100:.2f}%"

# --- 메인 로직 ---
api_key = st.secrets.get("GEMINI_API_KEY", None)

col_header1, col_header2 = st.columns([3, 1])
with col_header1:
    st.markdown("<h1 style='margin-bottom: 0; font-size: 2.0rem;'>📈 미장 All 퀀트 스캐너</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #8b949e; font-size: 1.05rem; margin-top: 5px;'>월스트리트 DCF + 상대가치 + 스마트머니 하이브리드 엔진</p>", unsafe_allow_html=True)

if ticker_input:
    ticker = ticker_input
    try:
        info, fund_data, fcf_yf, hist, hist_10y, hist_weekly = get_stock_market_data(ticker)
        
        if hist.empty or len(hist) < 20:
            st.error(f"[{ticker}] 차트 데이터를 불러오지 못했습니다. 올바른 티커인지 확인해 주세요.")
        else:
            hist['SMA50'] = hist['Close'].rolling(window=50).mean()
            hist['SMA200'] = hist['Close'].rolling(window=200).mean()
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rs = gain / loss
            hist['RSI'] = 100 - (100 / (1 + rs))
            hist['OBV'] = (np.sign(hist['Close'].diff()) * hist['Volume']).fillna(0).cumsum()

            current_price = info.get('currentPrice')
            if current_price is None: current_price = parse_fz(fund_data.get('Price'))
            if current_price is None: current_price = hist['Close'].iloc[-1]
            
            sma50_val = hist['SMA50'].iloc[-1] if len(hist) >= 50 else np.nan
            sma200_val = hist['SMA200'].iloc[-1] if len(hist) >= 200 else np.nan
            rsi_val = hist['RSI'].iloc[-1]
            
            eps = info.get('trailingEps')
            if eps is None: eps = parse_fz(fund_data.get('EPS (ttm)'))
            
            pbr = info.get('priceToBook')
            if pbr is None: pbr = parse_fz(fund_data.get('P/B'))
            
            roe = info.get('returnOnEquity')
            if roe is None: roe = parse_fz(fund_data.get('ROE'), 'percent')
            
            de_yf = info.get('debtToEquity')
            de_fz = parse_fz(fund_data.get('Debt/Eq'))
            debt_to_equity = de_yf if de_yf is not None else (de_fz * 100 if de_fz is not None else None)
            
            peg_ratio = info.get('pegRatio')
            if peg_ratio is None: peg_ratio = parse_fz(fund_data.get('PEG'))
            
            fcf = fcf_yf if fcf_yf is not None else info.get('freeCashflow')
            
            payout_ratio = info.get('payoutRatio')
            if payout_ratio is None: payout_ratio = parse_fz(fund_data.get('Payout'), 'percent')
            
            shares = info.get('sharesOutstanding')
            if shares is None: shares = parse_fz(fund_data.get('Shs Outstand'), 'large_num')
            
            sector = str(info.get('sector', '')).lower()
            industry = str(info.get('industry', '')).lower()
            
            ev_ebitda = info.get('enterpriseToEbitda', None)
            
            ps_ratio = info.get('priceToSalesTrailing12Months')
            if ps_ratio is None: ps_ratio = parse_fz(fund_data.get('P/S'))
            
            ev_revenue = info.get('enterpriseToRevenue', None)
            
            forward_pe = info.get('forwardPE')
            if forward_pe is None: forward_pe = parse_fz(fund_data.get('Forward P/E'))
            
            short_pct = parse_fz(fund_data.get('Short Float'), 'percent')
            if short_pct is None: short_pct = info.get('shortPercentOfFloat')
            
            insider_pct = parse_fz(fund_data.get('Insider Own'), 'percent')
            if insider_pct is None: insider_pct = info.get('heldPercentInsiders')
            
            inst_pct = parse_fz(fund_data.get('Inst Own'), 'percent')
            if inst_pct is None: inst_pct = info.get('heldPercentInstitutions')
            
            earnings_growth = info.get('earningsGrowth')
            if earnings_growth is None: earnings_growth = parse_fz(fund_data.get('EPS next Y'), 'percent')
            
            company_name = fund_data.get('Company')
            if not company_name or company_name == "-":
                company_name = info.get('longName') or info.get('shortName')
                
            if not company_name or company_name == ticker:
                for item in all_tickers_list:
                    if item.startswith(ticker + " "):
                        match = re.search(r'\((.*?)\)', item)
                        if match:
                            company_name = match.group(1)
                            break
                            
            if not company_name:
                company_name = ticker

            is_main_value_stock = False
            value_sectors = ["consumer defensive", "utilities", "energy", "real estate", "financial services", "basic materials", "industrials"]
            
            if any(v_sec in sector for v_sec in value_sectors) or (payout_ratio is not None and payout_ratio >= 0.40):
                is_main_value_stock = True
                
            if "aerospace" in industry or "defense" in industry:
                is_main_value_stock = False
            
            graham_value = "N/A"
            if eps is not None and eps > 0: graham_value = eps * (8.5 + 2 * g)
                
            dcf_value = "N/A"
            if fcf is not None and fcf > 0 and shares is not None and shares > 0:
                wacc = discount_rate / 100
                g_dec = g / 100
                term_g = 0.025 
                pv_fcf = sum([(fcf * ((1 + g_dec) ** i)) / ((1 + wacc) ** i) for i in range(1, 6)])
                tv = (fcf * ((1 + g_dec) ** 5) * (1 + term_g)) / max((wacc - term_g), 0.001)
                pv_tv = tv / ((1 + wacc) ** 5)
                dcf_value = (pv_fcf + pv_tv) / shares
                
            if not is_main_value_stock and dcf_value != "N/A":
                final_fair_value = dcf_value
                model_used = "DCF(현금흐름할인) 모델"
                badge_html = "<div class='badge badge-growth'>🚀 AI 판독: 테크/성장주 트랙 자동 적용 중</div>"
            else:
                final_fair_value = graham_value
                model_used = "벤저민 그레이엄 모델"
                badge_html = "<div class='badge badge-value'>🏛️ AI 판독: 전통 가치/배당주 트랙 자동 적용 중</div>"
                
            margin_of_safety = "N/A"
            if final_fair_value != "N/A" and current_price is not None:
                margin_of_safety = ((final_fair_value - current_price) / abs(final_fair_value)) * 100

            hist_1y = hist.tail(252).copy()
            high_1y = hist_1y['High'].max()
            low_1y = hist_1y['Low'].min()
            drawdown = ((current_price - high_1y) / high_1y) * 100
            mdd = (hist_1y['Close'] / hist_1y['Close'].cummax() - 1.0).min() * 100
            
            df_wk = pd.DataFrame()
            if not hist_weekly.empty:
                df_wk = hist_weekly.copy()
                df_wk['MA10'] = df_wk['Close'].rolling(window=10).mean()
                df_wk['MA20'] = df_wk['Close'].rolling(window=20).mean()
                df_wk['MA60'] = df_wk['Close'].rolling(window=60).mean()
                df_wk['MA120'] = df_wk['Close'].rolling(window=120).mean()
                df_wk['Prev_Close'] = df_wk['Close'].shift(1)
                tr1 = df_wk['High'] - df_wk['Low']
                tr2 = (df_wk['High'] - df_wk['Prev_Close']).abs()
                tr3 = (df_wk['Low'] - df_wk['Prev_Close']).abs()
                df_wk['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                df_wk['ATR_22'] = df_wk['TR'].ewm(alpha=1/22, adjust=False).mean()
                df_wk['High_22'] = df_wk['High'].rolling(window=22).max()
                df_wk['Calc_Stop'] = df_wk['High_22'] - (df_wk['ATR_22'] * 3.0)
                
                atr_stop = np.zeros(len(df_wk))
                atr_stop[:] = np.nan
                calc_val = df_wk['Calc_Stop'].values
                close_val = df_wk['Close'].values
                for i in range(1, len(df_wk)):
                    if np.isnan(calc_val[i]): continue
                    prev_c, prev_s, cur_c = close_val[i-1], atr_stop[i-1], calc_val[i]
                    if np.isnan(prev_s): atr_stop[i] = cur_c
                    elif prev_c > prev_s: atr_stop[i] = max(cur_c, prev_s)
                    else: atr_stop[i] = cur_c
                df_wk['ATR_Stop'] = atr_stop
                
                ma_stack = df_wk[['MA10', 'MA20', 'MA60']]
                df_wk['Converged'] = ((ma_stack.max(axis=1) - ma_stack.min(axis=1)) / ma_stack.min(axis=1)).round(4) <= 0.0700
                df_wk['Signal_Main'] = (df_wk['Converged'] & (df_wk['Close'] > df_wk['MA20']) & (df_wk['Close'] > df_wk['MA60']) & (df_wk['MA60'] >= df_wk['MA120']) & (df_wk['Close'] > df_wk['ATR_Stop']))
                df_wk['Signal_Main'] = df_wk['Signal_Main'] & (~df_wk['Signal_Main'].shift(1).fillna(False))
                df_wk['Signal_Reentry'] = ((df_wk['Close'] > df_wk['MA60']) & ((df_wk['Prev_Close'] <= df_wk['MA10'].shift(1)) & (df_wk['Close'] > df_wk['MA10'])) & (df_wk['Close'] > df_wk['Open']) & (df_wk['MA20'] > df_wk['MA20'].shift(1)) & (df_wk['Close'] > df_wk['ATR_Stop']) & (~df_wk['Signal_Main']))
                df_wk['Signal_Sell'] = (df_wk['Prev_Close'] >= df_wk['ATR_Stop'].shift(1)) & (df_wk['Close'] < df_wk['ATR_Stop'])

            score = 0; checklist = []
            if margin_of_safety != "N/A":
                if margin_of_safety > 20: score += 2; checklist.append({"status": "pass", "category": "가치", "desc": f"적정주가 대비 안전마진 {margin_of_safety:.1f}%", "score": "+2"})
                elif margin_of_safety > 0: score += 1; checklist.append({"status": "pass", "category": "가치", "desc": f"적정주가 대비 안전마진 {margin_of_safety:.1f}%", "score": "+1"})
                else: checklist.append({"status": "fail", "category": "가치", "desc": "고평가 상태 (안전마진 부족)", "score": "0"})
            else: checklist.append({"status": "info", "category": "가치", "desc": "적정 주가 산출 불가", "score": "-"})
                
            if roe is not None and roe > 0.15: score += 2; checklist.append({"status": "pass", "category": "수익성", "desc": f"ROE 15% 초과 ({roe*100:.1f}%)", "score": "+2"})
            else: checklist.append({"status": "fail", "category": "수익성", "desc": f"ROE 15% 미달", "score": "0"})
                
            if debt_to_equity is not None and debt_to_equity < 100: score += 2; checklist.append({"status": "pass", "category": "건전성", "desc": f"안정적인 부채비율 ({debt_to_equity:.1f}%)", "score": "+2"})
            else: checklist.append({"status": "fail", "category": "건전성", "desc": f"부채비율 높음", "score": "0"})
                
            if pd.notna(sma50_val) and pd.notna(sma200_val):
                if current_price > sma50_val and sma50_val > sma200_val: score += 3; checklist.append({"status": "pass", "category": "일봉 추세", "desc": "정배열 상승", "score": "+3"})
                elif current_price > sma50_val and sma50_val <= sma200_val: score += 1; checklist.append({"status": "info", "category": "일봉 추세", "desc": "바닥 반등 시작", "score": "+1"})
                elif current_price <= sma50_val and current_price > sma200_val: score += 1; checklist.append({"status": "info", "category": "일봉 추세", "desc": "장기 상승장 속 조정 (눌림목)", "score": "+1"})
                else: checklist.append({"status": "fail", "category": "일봉 추세", "desc": "역배열 하락세", "score": "0"})
            else: checklist.append({"status": "fail", "category": "일봉 추세", "desc": "추세 판독 불가 (신규 상장 데이터 부족)", "score": "0"})
                
            if pd.notna(rsi_val) and rsi_val < 70: score += 1; checklist.append({"status": "pass", "category": "단기 수급", "desc": f"RSI 과열 아님 ({rsi_val:.1f})", "score": "+1"})
            else: checklist.append({"status": "fail", "category": "단기 수급", "desc": "RSI 단기 과열", "score": "0"})

            if score >= 8: judgment = "🌟 강력 매수 (Strong Buy)"; banner_class = "buy-banner"; prog_color = "#1976d2"
            elif score >= 5: judgment = "🟢 분할 매수 / 관망 (Accumulate/Hold)"; banner_class = "hold-banner"; prog_color = "#166534"
            else: judgment = "🔴 매도 / 주의 (Sell/Warning)"; banner_class = "sell-banner"; prog_color = "#b91c1c"
            
            exchange = info.get('exchange', 'US Market')
            if exchange == 'NMS': exchange = 'NASDAQ'
            elif exchange == 'NYQ': exchange = 'NYSE'
            
            eng_desc = info.get('longBusinessSummary', '')
            kr_name, kr_summary = get_korean_profile(ticker, company_name, eng_desc, api_key)
            
            st.markdown(f"""
<div class="banner {banner_class}">
    <div class="banner-left">
        <h2 style="margin-bottom: 5px; font-size: 2.2rem;">{kr_name} <span style="font-size:1.2rem; color:#8b949e; font-weight:normal;">미국 · {ticker} · {exchange}</span></h2>
        <p style="font-size: 1.05rem; color: #c9d1d9; margin-top: 10px; margin-bottom: 0; font-weight: 400; background-color: rgba(255,255,255,0.05); padding: 10px; border-radius: 5px; display: inline-block;">💡 {kr_summary}</p>
    </div>
    <div class="banner-right">
        <p style="margin-bottom: 5px; color: rgba(255,255,255,0.8); font-size: 1rem;">퀀트 시스템 최종 평가</p>
        <p style="font-size: 1.4rem; margin-top: 0;">등급: <b>{judgment}</b> &nbsp;|&nbsp; 스코어: <b style="font-size: 1.6rem;">{score}점</b></p>
    </div>
</div>
""", unsafe_allow_html=True)
            
            # 💡 [V6.5 핵심 패치] CSS Grid를 활용하여 왼쪽/오른쪽 박스 높이를 1px 오차 없이 완벽 매칭
            # 글씨 크기도 2포인트(0.2rem 단위)씩 모두 키워 가독성 향상
            items_html = "".join([f'''<div style="display: flex; justify-content: space-between; align-items: center; padding: 15px 18px; margin-bottom: 10px; background-color: #161b22; border-radius: 6px; border-left: 4px solid {'#3fb950' if item["status"] == 'pass' else ('#f85149' if item["status"] == 'fail' else '#d29922')}; border: 1px solid #30363d;">
    <div style="display: flex; align-items: center; gap: 15px; flex: 1;">
        <span style="font-size: 1.3rem;">{'✅' if item["status"] == 'pass' else ('❌' if item["status"] == 'fail' else '💡')}</span>
        <span style="color: {'#3fb950' if item["status"] == 'pass' else ('#f85149' if item["status"] == 'fail' else '#d29922')}; font-weight: bold; font-size: 1.0rem; min-width: 60px; text-align: center;">{item["category"]}</span>
        <span style="color: #c9d1d9; font-size: 1.15rem;">{item["desc"]}</span>
    </div>
    <div style="font-weight: bold; color: {'#3fb950' if item["status"] == 'pass' else ('#f85149' if item["status"] == 'fail' else '#d29922')}; font-size: 1.25rem;">{item["score"]}점</div>
</div>''' for item in checklist])
            
            st.markdown(f"""
<div style="display: grid; grid-template-columns: 1fr 1.8fr; gap: 20px; align-items: stretch; margin-bottom: 20px;">
    <div style="background-color: #161b22; padding: 20px; border-radius: 8px; border: 1px solid #30363d; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; margin: 0;">
        <h3 style='margin:0 0 10px 0; color:#8b949e;'>TOTAL SCORE</h3>
        <h1 style='font-size: 5.5rem; margin:10px 0; color:{prog_color};'>{score}<span style='font-size: 2.5rem; color:#8b949e;'> / 10</span></h1>
    </div>
    <div style="background-color: #161b22; padding: 20px; border-radius: 8px; border: 1px solid #30363d; display: flex; flex-direction: column; justify-content: center; margin: 0;">
        <h3 style='margin:0 0 15px 0; color:#8b949e; font-size: 1.4rem;'>평가 내용</h3>{items_html}
    </div>
</div>
""", unsafe_allow_html=True)
            
            st.markdown(badge_html, unsafe_allow_html=True)
            
            st.markdown("### 2. 주요 기술지표")
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns(4)
                with c1: st.metric(label="현재 주가", value=fmt_price(current_price), delta=f"{drawdown:.2f}% (최고가대비)")
                with c2: st.metric(label=f"적정 주가 ({model_used})", value=fmt_price(final_fair_value) if final_fair_value != "N/A" else "N/A", 
                                   delta=f"{margin_of_safety:.2f}% (안전마진)" if margin_of_safety != "N/A" else None,
                                   help="테크/성장주는 현금흐름할인(DCF) 모델로, 가치/배당주는 그레이엄 모델로 자동 산출됩니다.")
                with c3: st.metric(label="1년 MDD (최대 낙폭)", value=f"{mdd:.2f}%", delta="Max Drawdown", delta_color="inverse")
                with c4: st.metric(label="EPS (주당순이익)", value=fmt_price(eps) if pd.notna(eps) else "N/A", 
                                   help="1주당 회사가 벌어들인 순이익을 의미해요. 숫자가 클수록 회사의 기업 가치가 크고, 배당 줄 수 있는 여유가 늘어났다고 볼 수 있어요.")
                    
            with st.container(border=True):
                c5, c6, c7, c8 = st.columns(4)
                with c5: st.metric(label="PBR", value=f"{pbr:.2f}배" if pd.notna(pbr) and pbr != 'N/A' else "N/A", 
                                   help="주가가 1주당 장부상 순자산가치의 몇 배로 거래되는지 나타냅니다. 1 미만이면 회사를 다 팔아도 남는 돈보다 주가가 싸다는 뜻(저평가)입니다.")
                with c6: st.metric(label="ROE", value=f"{roe*100:.2f}%" if pd.notna(roe) else "N/A", 
                                   help="회사가 주주의 돈(자본)을 굴려서 1년간 얼마를 벌었는지 보여주는 핵심 수익성 지표입니다. (통상 15% 이상이면 우량 기업으로 평가)")
                with c7: st.metric(label="52주 최고가", value=fmt_price(high_1y))
                with c8: st.metric(label="52주 최저가", value=fmt_price(low_1y))
            
            fund_status = "2. 주요 기술지표 브리핑"
            fund_color = "#29b6f6" 
            fund_bg = "41, 182, 246"
            
            fund_desc = ""
            if final_fair_value != "N/A":
                is_undervalued = margin_of_safety > 0
                if is_undervalued:
                    fund_color = "#3fb950"
                    fund_bg = "63, 185, 80"
                    fund_desc += f"현재 주가는 {model_used}로 산출된 적정 주가 대비 **싸게(저평가)** 거래되고 있습니다. "
                else:
                    fund_color = "#f85149"
                    fund_bg = "248, 81, 73"
                    fund_desc += f"현재 주가는 {model_used}로 산출된 적정 주가 대비 **비싸게(고평가)** 거래되고 있습니다. "
            else:
                fund_desc += f"현재 적자 혹은 현금흐름 부족으로 인해 명확한 적정 주가를 산출하기 어렵습니다. "
                
            if roe is not None:
                if roe > 0.15: fund_desc += "ROE가 15%를 초과하여 자본 배분 수익성이 매우 우수하며, "
                else: fund_desc += "ROE가 15% 미만으로 자본 수익성은 평범하거나 다소 아쉬운 수준입니다. "
            fund_desc += f"최근 1년 동안 최고가 대비 최대 {mdd:.1f}% 하락한 변동성이 있었습니다."
            
            st.markdown(f"""
            <div style="padding: 15px; border-radius: 5px; margin-top: 10px; margin-bottom: 20px; border-left: 4px solid {fund_color}; background-color: rgba({fund_bg}, 0.1);">
                <h4 style="margin-top: 0; color: {fund_color};">{fund_status}</h4>
                <p style="margin-bottom: 0; font-size: 0.95rem; color: #c9d1d9;">{fund_desc}</p>
            </div>
            """, unsafe_allow_html=True)
                    
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("### 🤖 수석 비서의 AI 종합 브리핑 (Tier 1)")
            if st.button("✨ 퀀트 데이터 기반 AI 분석 보고서 작성", type="primary", width="stretch"):
                with st.spinner(f"[{ticker}]의 수급 데이터와 경쟁사 비교표를 분석하여 AI 브리핑을 작성 중입니다... 🧠"):
                    try:
                        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                        model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"temperature": 0.7, "max_output_tokens": 8000})
                        
                        # 💡 [핵심 패치 1] NoneType 에러 완벽 방어를 위한 안전 함수 적용
                        ai_median_pe = fmt_multi(median_pe) if not peer_df.empty else "데이터 없음"
                        ai_median_ps = fmt_multi(median_ps) if not peer_df.empty else "데이터 없음"
                        
                        # 💡 [핵심 패치 2] 7단계 전문가 리포트 양식 및 쉼표 없는 해시태그 적용
                        prompt = f"""
                        당신은 월스트리트와 여의도를 섭렵한 최고의 수석 퀀트 애널리스트입니다. 
                        제공된 [{company_name} ({ticker})]의 팩트 데이터와 당신이 보유한 기업 지식을 종합하여, 
                        아래 [지정된 리포트 양식]에 맞춰 완벽한 네이버 블로그용 심층 분석 보고서를 작성해 주세요.

                        [분석용 기초 데이터]
                        - 퀀트 시스템 점수: 10점 만점에 {score}점 ({judgment})
                        - 적용 모델: {model_used} / 공매도 비율: {fmt_pct(short_pct)} / 내부자 보유율: {fmt_pct(insider_pct)}
                        - 펀더멘털: ROE {fmt_pct(roe)} / 배당성향 {fmt_pct(payout_ratio)} 
                        - 밸류에이션: 선행 PER {fmt_multi(forward_pe)}, P/S {fmt_multi(ps_ratio)}, EV/EBITDA {fmt_multi(ev_ebitda)}
                        - 동종 업계(경쟁사) 중앙값: 선행 PER {ai_median_pe}, P/S {ai_median_ps}

                        [🚨 작성 규칙]
                        1. 시작: "대표님, [{company_name}] 4차원 매트릭스 및 수급 종합 분석 보고드립니다."
                        2. 어투: 문장 끝은 반드시 "~함", "~임", "~됨", "~기대됨" 등 간결한 보고서체로 작성할 것. (예: 저평가 상태임. 주의가 필요함.)
                        3. 내용 밀도: 각 항목의 '- 분석 요약:'과 '- 핵심 근거:' 사이에는 절대 빈 줄(엔터)을 넣지 말고 바로 위아래로 붙여서 출력할 것.
                        4. 기호 통제: 이모지는 제목에만 쓰고 본문에는 절대 쓰지 말 것.
                        5. 해시태그 규칙: "블로그용 해시태그" 같은 설명 문구는 절대 쓰지 말고, 오직 태그만 맨 마지막에 쉼표(,) 없이 빈칸(스페이스바)으로 한 칸씩만 띄워서 딱 10개 나열할 것.

                        [지정된 리포트 양식]
                        ### 1. 비즈니스 모델 및 경제적 해자 : [ A / B / C ] 등급
                        - **분석 요약:** (무엇으로 돈을 버는지, 해자의 종류와 대체 불가능한 경쟁 우위 기술력을 작성)
                        - **핵심 근거:** (독점력, 네트워크 효과 등 명확한 근거 작성)

                        ### 2. 재무 건전성 및 수익성 (Alpha Spread 기준) : [ A / B / C ] 등급
                        - **분석 요약:** (마진율, ROE, 부채비율 등 재무적 안전성과 수익 창출 능력을 작성)
                        - **핵심 근거:** (동종 업계 대비 마진율 등)

                        ### 3. 경영진 및 주주 거버넌스 : [ A / B / C ] 등급
                        - **분석 요약:** (자본 배치 능력, 배당 및 주주 환원 정책의 일관성을 작성)
                        - **핵심 근거:** (꾸준한 배당 성장, 내부자 매입 이력 등)

                        ### 4. 밸류에이션 및 안전마진 (Finbox 기준) : [ A / B / C ] 등급
                        - **분석 요약:** (현재 주가가 내재 가치 대비 저평가인지, 역사적 멀티플 하단인지 작성)
                        - **핵심 근거:** (적용 모델 기준 내재 가치 등 팩트 서술)

                        ### 5. 촉매제(Catalyst) 및 리스크 : [ A / B / C ] 등급
                        - **분석 요약:** (주가를 끌어올릴 호재 모멘텀과 발목을 잡을 위험 요소를 작성)
                        - **핵심 근거:** (신제품 출시 기대감, 거시 경제 취약성, 공매도 비율 리스크 등)

                        ### 6. 동종 업계 멀티플 비교
                        - (경쟁사 대비 PER, P/S 수준을 비교하여 상대적 매력도 판정)

                        ### 7. 주요 판매처 및 밸류체인 확인
                        - (핵심 고객사와 글로벌 공급망 내 위치 설명)

                        ---
                        ### 🏆 최종 종합 등급 : [ A / B / C ]
                        - **투자 결론:** (종합 매력도 요약)
                        - **트레이딩 전략:** (진입 타점 및 대응책)

                        #{ticker}주가 #{ticker}전망 #{ticker}실적 #미국주식 #미장시황 #실전매매 #주식분석 #퀀트투자
                        """
                        response = model.generate_content(prompt)
                        st.success("✅ 종합 브리핑 완료!")
                        with st.container(border=True):
                            clean_text = response.text
                            clean_text = re.sub(r'[\U00010000-\U0010ffff]', '', clean_text)
                            clean_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', clean_text)
                            clean_text = clean_text.replace("*", "")
                            
                            # 💡 파이썬 기본 개행(\n)만 HTML 줄바꿈(<br>)으로 바꿔줍니다. (마침표 분리 제거)
                            clean_text = clean_text.replace('\n', '<br>')
                            
                            st.markdown(f"""
<div style="font-size: 20px; line-height: 1.8; color: #e6edf3; padding: 10px;">
{clean_text}
</div>
""", unsafe_allow_html=True)
                    except Exception as e: 
                        st.error(f"🚨 AI 오류: {e}")

    except Exception as e:
        st.error(f"데이터 처리 중 오류가 발생했습니다: {e}")

    except Exception as e:
        st.error(f"데이터 처리 중 오류가 발생했습니다: {e}")
