import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import math
import time

# --- 設定 ---
url = "https://docs.google.com/spreadsheets/d/1YLXZWQ6XZz04mi0dx9_6WFbm2-yZQGGIXd3yVEh9kTQ/edit?usp=sharing"

st.set_page_config(page_title="Poker League Master", page_icon="♠️", layout="centered")

# --- デザインCSS（行間を物理限界まで詰める） ---
st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
    input, select, textarea, div[data-baseweb="select"] {
        color: #ffffff !important;
        background-color: #1c2128 !important;
    }
    .stTabs [data-baseweb="tab-list"] { background-color: #161b22; border-radius: 10px; padding: 5px; }
    .stTabs [data-baseweb="tab"] { color: #8b949e; font-weight: bold; font-size: 14px; }
    
    /* 1. ランキング行の極小化（高さを26pxに固定） */
    .compact-row { 
        height: 26px !important;
        border-bottom: 1px solid #30363d;
        display: flex;
        align-items: center;
        overflow: hidden;
    }
    
    /* 2. Streamlit標準のカラム余白を強制削除 */
    div[data-testid="column"] {
        padding: 0px !important;
        flex: none !important;
    }
    
    /* 3. ボタンコンテナの余白を完全に消去 */
    div.stButton {
        margin: 0px !important;
        padding: 0px !important;
        line-height: 1 !important;
    }

    /* 4. ユーザー名ボタンのスタイル（文字の高さに合わせる） */
    div.stButton > button[key^="user_"] {
        background: none !important;
        border: none !important;
        padding: 0 !important;
        margin: 0 !important;
        color: #58a6ff !important;
        height: 26px !important;
        min-height: 26px !important;
        line-height: 26px !important;
        text-align: left !important;
        font-weight: bold !important;
        font-size: 0.95em !important;
        display: block !important;
    }

    .total-sum-area { background-color: #1c2128; padding: 10px; border-radius: 12px; border: 2px solid #30363d; text-align: center; margin-top: 10px; }

    div[data-testid="stStatusWidget"] {
        background-color: rgba(0, 0, 0, 0.75) !important;
        position: fixed !important;
        top: 0 !important; left: 0 !important;
        width: 100vw !important; height: 100vh !important;
        z-index: 999999 !important;
        display: flex !important; justify-content: center !important; align-items: center !important;
    }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(sheet_name):
    try:
        data = conn.read(spreadsheet=url, worksheet=sheet_name, ttl=0)
        return data.dropna(how="all") if data is not None else pd.DataFrame()
    except Exception:
        return None

# --- データ読み込み ---
for s in ["scores", "players", "leagues"]:
    if f"cache_{s}" not in st.session_state or load_data(s) is not None:
        new_d = load_data(s)
        if new_d is not None: st.session_state[f"cache_{s}"] = new_d

df_scores = st.session_state.cache_scores
df_players = st.session_state.cache_players
df_leagues = st.session_state.cache_leagues

# リーグの自動選択
t_league = st.session_state.get("selected_league")
if not df_leagues.empty:
    l_list = df_leagues["リーグ名"].tolist()
    if len(l_list) == 1:
        t_league = l_list[0]
        st.sidebar.info(f"🏟️ {t_league}")
    else:
        idx = l_list.index(t_league) if t_league in l_list else 0
        t_league = st.sidebar.selectbox("🏟️ リーグ", l_list, index=idx)
    st.session_state.selected_league = t_league
else:
    st.sidebar.warning("リーグ未作成")

tab_rank, tab_input, tab_setting = st.tabs(["🏆 ランキング", "💰 入力", "⚙️ 設定"])

# --- 1. ランキング ---
with tab_rank:
    if t_league and not df_scores.empty:
        # 詳細分析
        if "detail_p" in st.session_state:
            dp = st.session_state.detail_p
            with st.container(border=True):
                c_h, c_c = st.columns([5, 1])
                c_h.write(f"📊 **{dp}**")
                if c_c.button("✖️"):
                    del st.session_state.detail_p
                    st.rerun()
                df_p = df_scores[(df_scores["リーグ"] == t_league) & (df_scores["名前"] == dp)].copy()
                df_p["スコア"] = pd.to_numeric(df_p["スコア"], errors='coerce').fillna(0)
                if not df_p.empty:
                    s1, s2, s3, s4 = st.columns(4)
                    s1.metric("平均", f"{df_p['スコア'].mean():.0f}")
                    sWin = (df_p["スコア"] > 0).mean() * 100
                    s2.metric("勝率", f"{sWin:.0f}%")
                    s3.metric("最勝", f"{df_p['スコア'].max():+}")
                    s4.metric("最負", f"{df_p['スコア'].min():+}")
                    df_p["日付"] = pd.to_datetime(df_p["日付"], errors='coerce')
                    st.line_chart(df_p.sort_values("日付").set_index("日付")["スコア"].cumsum())

        # ランキング本体
        df_l = df_scores[df_scores["リーグ"] == t_league].copy()
        period = st.radio("範囲", ["今日", "月間", "全期間"], horizontal=True, label_visibility="collapsed")
        
        if not df_l.empty:
            df_l["日付"] = pd.to_datetime(df_l["日付"], errors='coerce')
            now = datetime.now()
            if period == "今日": df_f = df_l[df_l["日付"].dt.date == now.date()]
            elif period == "月間": df_f = df_l[(df_l["日付"].dt.year == now.year) & (df_l["日付"].dt.month == now.month)]
            else: df_f = df_l
            
            if not df_f.empty:
                df_f["スコア"] = pd.to_numeric(df_f["スコア"], errors='coerce').fillna(0)
                rank_df = df_f.groupby("名前")["スコア"].sum().reset_index().sort_values("スコア", ascending=False).reset_index(drop=True)
                
                # 超コンパクト表示
                for i, row in rank_df.iterrows():
                    v = int(row['スコア'])
                    color = "#58a6ff" if v >= 0 else "#f85149"
                    
                    st.markdown('<div class="compact-row">', unsafe_allow_html=True)
                    c_r, c_n, c_v = st.columns([0.15, 0.6, 0.25])
                    c_r.write(f"#{i+1}")
                    if c_n.button(row['名前'], key=f"user_{row['名前']}"):
                        st.session_state.detail_p = row['名前']
                        st.rerun()
                    c_v.markdown(f'<div style="text-align:right; color:{color}; font-weight:bold;">{v:+,}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)

                total = int(df_f["スコア"].sum())
                tc = "#e6edf3" if total == 0 else ("#58a6ff" if total > 0 else "#f85149")
                st.markdown(f'<div class="total-sum-area"><p style="margin:0; font-size:0.7em;">合計差額</p><h3 style="margin:0; color:{tc};">{total:+,}</h3></div>', unsafe_allow_html=True)
            else: st.info("データなし")
    else: st.info("リーグを選択")

# --- 2. スコア入力 ---
with tab_input:
    entries = []
    if t_league and not df_players.empty:
        l_players = df_players[df_players["リーグ"] == t_league]["名前"].tolist()
        if l_players:
            if "input_rows" not in st.session_state: st.session_state.input_rows = 1
            for i in range(st.session_state.input_rows):
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1.5, 1.5])
                    p_name = c1.selectbox("プレイヤー", l_players, key=f"p_name_{i}")
                    raw_pts = c2.number_input("pt", step=10, key=f"raw_pts_{i}")
                    rate = c3.selectbox("レート", ["1/1", "1/5", "1/10", "1/30", "カスタム"], key=f"rate_{i}")
                    div = 1.0
                    if rate == "1/5": div = 5.0
                    elif rate == "1/10": div = 10.0
                    elif rate == "1/30": div = 30.0
                    elif rate == "カスタム": div = st.number_input("÷", min_value=0.1, value=1.0, key=f"cust_{i}")
                    entries.append({"名前": p_name, "スコア": math.floor(raw_pts/div), "日付": datetime.now().strftime("%Y-%m-%d %H:%M"), "リーグ": t_league})

            ca, cs = st.columns(2)
            if ca.button("➕ 追加"):
                st.session_state.input_rows += 1
                st.rerun()
            if cs.button("🚀 保存"):
                try:
                    with st.spinner('保存中...'):
                        conn.update(spreadsheet=url, worksheet="scores", data=pd.concat([df_scores, pd.DataFrame(entries)], ignore_index=True))
                        st.session_state.input_rows = 1
                        for k in list(st.session_state.keys()):
                            if k.startswith(("p_name_", "raw_pts_", "rate_", "cust_")): del st.session_state[k]
                        st.rerun()
                except: st.error("通信失敗")

# --- 3. 設定 ---
with tab_setting:
    m1, m2, m3 = st.tabs(["👥 選手", "🏆 リーグ", "📜 履歴"])
    with m1:
        if not df_leagues.empty:
            reg_l = st.selectbox("リーグ", df_leagues["リーグ名"].tolist(), key="reg_l")
            p_n = st.text_input("名前")
            if st.button("登録") and p_n:
                conn.update(spreadsheet=url, worksheet="players", data=pd.concat([df_players, pd.DataFrame([{"名前": p_n, "リーグ": reg_l}])], ignore_index=True))
                st.rerun()
    with m2:
        with st.form("l_form", clear_on_submit=True):
            nl = st.text_input("新リーグ名")
            if st.form_submit_button("作成") and nl:
                conn.update(spreadsheet=url, worksheet="leagues", data=pd.concat([df_leagues, pd.DataFrame({"リーグ名": [nl]})], ignore_index=True))
                st.rerun()
    with m3:
        if not df_scores.empty:
            h_df = df_scores.iloc[::-1].head(15)
            for i, row in h_df.iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([5, 1])
                    c1.write(f"{row.get('名前','-')}: {int(row.get('スコア',0)):+,}")
                    if c2.button("🗑️", key=f"d_{i}"):
                        conn.update(spreadsheet=url, worksheet="scores", data=df_scores.drop(i))
                        st.rerun()