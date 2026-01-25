import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import math
import time

# --- 設定 ---
url = "https://docs.google.com/spreadsheets/d/1YLXZWQ6XZz04mi0dx9_6WFbm2-yZQGGIXd3yVEh9kTQ/edit?usp=sharing"

st.set_page_config(page_title="Poker League Master", page_icon="♠️", layout="centered")

# --- 日本時間取得 ---
def get_jst_now():
    return datetime.utcnow() + timedelta(hours=9)

# --- デザインCSS（背景をネイビーに変更し視認性を強化） ---
st.markdown("""
    <style>
    /* 全体背景を深いネイビーに */
    .stApp { 
        background-color: #0a1120 !important; 
        color: #e6edf3; 
    }
    
    input, select, textarea, div[data-baseweb="select"] { 
        color: #ffffff !important; 
        background-color: #161b22 !important; 
    }
    
    .stTabs [data-baseweb="tab-list"] { background-color: #111927; border-radius: 10px; padding: 5px; }
    .stTabs [data-baseweb="tab"] { color: #8b949e; font-weight: bold; font-size: 14px; }
    
    /* 【改善】ランキング行：背景をミッドナイトブルーにし、視認性を向上 */
    .compact-row { 
        height: 30px !important; 
        background-color: #161e2e !important; /* 行の背景をネイビーに */
        border-bottom: 1px solid #1f2937; 
        display: flex; 
        align-items: center; 
        overflow: hidden;
        margin-bottom: 2px !important; /* 行間の隙間 */
        border-radius: 4px; /* 角丸 */
        padding: 0 10px !important;
    }
    
    div[data-testid="column"] { padding: 0px !important; margin: 0px !important; gap: 0px !important; }

    /* 名前ボタン：色は維持しつつホバー効果を強化 */
    div.stButton > button[key^="user_"] {
        background: none !important;
        border: none !important;
        padding: 0 !important;
        margin: 0 !important;
        color: #58a6ff !important; 
        height: 30px !important;
        line-height: 30px !important;
        text-align: left !important;
        font-weight: bold !important;
        font-size: 1.0em !important;
    }
    div.stButton > button[key^="user_"]:hover {
        color: #79c0ff !important;
        text-decoration: underline !important;
    }

    /* クッキリした白に変更 */
    .rank-num { font-size: 0.85em; color: #ffffff; padding-top: 2px; font-weight: bold; }
    .score-num { font-size: 1.0em; font-weight: bold; text-align: right; padding-top: 2px; }
    
    .hall-of-fame { 
        background: linear-gradient(135deg, #161e2e, #0a1120); 
        padding: 10px; 
        border-radius: 10px; 
        border: 1px solid #d4af37; 
        margin-top: 15px; 
    }
    .total-sum-area { 
        background-color: #161e2e; 
        padding: 8px; 
        border-radius: 10px; 
        border: 1px solid #30363d; 
        text-align: center; 
        margin-top: 8px; 
    }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=300)
def load_all_data():
    try:
        scores = conn.read(spreadsheet=url, worksheet="scores").dropna(how="all")
        players = conn.read(spreadsheet=url, worksheet="players").dropna(how="all")
        leagues = conn.read(spreadsheet=url, worksheet="leagues").dropna(how="all")
        return scores, players, leagues
    except: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_scores, df_players, df_leagues = load_all_data()

if st.sidebar.button("🔄 データを強制更新"):
    st.cache_data.clear()
    st.rerun()

st.title("♠️ Poker League Master")

t_league = st.session_state.get("selected_league")
if not df_leagues.empty:
    l_list = df_leagues["リーグ名"].tolist()
    idx = l_list.index(t_league) if t_league in l_list else 0
    t_league = st.sidebar.selectbox("🏟️ リーグ", l_list, index=idx)
    st.session_state.selected_league = t_league

tab_rank, tab_input, tab_setting = st.tabs(["🏆 ランキング", "💰 入力", "⚙️ 設定"])

# --- 1. ランキング ---
with tab_rank:
    if t_league and not df_scores.empty:
        df_l = df_scores[df_scores["リーグ"] == t_league].copy()
        df_l["スコア"] = pd.to_numeric(df_l["スコア"], errors='coerce').fillna(0)
        df_l["日付"] = pd.to_datetime(df_l["日付"], errors='coerce')

        if "detail_p" in st.session_state:
            dp = st.session_state.detail_p
            with st.container(border=True):
                c_h, c_c = st.columns([5, 1])
                c_h.write(f"📊 **{dp}**")
                if c_c.button("✖️"): del st.session_state.detail_p; st.rerun()
                df_p = df_l[df_l["名前"] == dp].sort_values("日付")
                if not df_p.empty:
                    s1, s2, s3, s4 = st.columns(4)
                    s1.metric("平均", f"{df_p['スコア'].mean():.0f}")
                    s2.metric("勝率", f"{(df_p['スコア']>0).mean()*100:.1f}%")
                    s3.metric("最勝", f"{df_p['スコア'].max():+}")
                    s4.metric("最負", f"{df_p['スコア'].min():+}")
                    st.line_chart(df_p.set_index("日付")["スコア"].cumsum())

        period = st.radio("範囲", ["今日", "今月", "前月", "全期間"], horizontal=True, label_visibility="collapsed")
        now_jst = get_jst_now()
        if period == "今日": df_f = df_l[df_l["日付"].dt.date == now_jst.date()]
        elif period == "今月": df_f = df_l[(df_l["日付"].dt.year == now_jst.year) & (df_l["日付"].dt.month == now_jst.month)]
        elif period == "前月":
            lm = now_jst.replace(day=1) - timedelta(days=1)
            df_f = df_l[(df_l["日付"].dt.year == lm.year) & (df_l["日付"].dt.month == lm.month)]
        else: df_f = df_l
        
        if not df_f.empty:
            rank_df = df_f.groupby("名前")["スコア"].sum().reset_index().sort_values("スコア", ascending=False).reset_index(drop=True)
            for i, row in rank_df.iterrows():
                v = int(row['スコア']); c = "#58a6ff" if v >= 0 else "#f85149"
                st.markdown('<div class="compact-row">', unsafe_allow_html=True)
                c_r, c_n, c_v = st.columns([0.15, 0.6, 0.25])
                c_r.markdown(f'<div class="rank-num">#{i+1}</div>', unsafe_allow_html=True)
                if c_n.button(row['名前'], key=f"user_{row['名前']}"): st.session_state.detail_p = row['名前']; st.rerun()
                c_v.markdown(f'<div class="score-num" style="color:{c};">{v:+,}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            total = int(df_f["スコア"].sum())
            tc = "#58a6ff" if total > 0 else ("#f85149" if total < 0 else "#e6edf3")
            st.markdown(f'<div class="total-sum-area"><p style="margin:0; font-size:0.7em;">合計</p><h3 style="margin:0; color:{tc};">{total:+,}</h3></div>', unsafe_allow_html=True)
        else: st.info("データがありません")