import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import math
import time

# --- 設定 ---
url = "https://docs.google.com/spreadsheets/d/1YLXZWQ6XZz04mi0dx9_6WFbm2-yZQGGIXd3yVEh9kTQ/edit?usp=sharing"

st.set_page_config(page_title="Poker League Master", page_icon="♠️", layout="centered")

# --- デザインCSS（ロード中を暗くする） ---
st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
    input, select, textarea, div[data-baseweb="select"] {
        color: #ffffff !important;
        background-color: #1c2128 !important;
    }
    .stTabs [data-baseweb="tab-list"] { background-color: #161b22; border-radius: 10px; padding: 5px; }
    .stTabs [data-baseweb="tab"] { color: #8b949e; font-weight: bold; font-size: 16px; }
    .stTabs [aria-selected="true"] { color: #58a6ff !important; border-bottom: 2px solid #58a6ff !important; }
    .stButton>button { width: 100%; border-radius: 12px; background: linear-gradient(135deg, #238636, #2ea043); color: white; border: none; font-weight: bold; height: 3.5em; margin-top: 10px; }
    .total-sum-area { background-color: #1c2128; padding: 20px; border-radius: 15px; border: 2px solid #30363d; text-align: center; margin-top: 30px; }
    
    div[data-testid="stStatusWidget"] {
        background-color: rgba(0, 0, 0, 0.7) !important;
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
    with st.spinner(f'{sheet_name}を読み込み中...'):
        try:
            data = conn.read(spreadsheet=url, worksheet=sheet_name, ttl=0)
            return data.dropna(how="all")
        except Exception:
            return pd.DataFrame() # 失敗しても空の表を返す（NameError対策）

# データ読み込み（初期化を確実に行う）
df_scores = load_data("scores")
df_players = load_data("players")
df_leagues = load_data("leagues")
df_trash = load_data("trash")

# サイドバーに更新ボタンを追加
if st.sidebar.button("🔄 データを再読み込み"):
    st.cache_data.clear()
    st.rerun()

st.title("♠️ Poker League Master")

if not df_leagues.empty:
    target_league = st.sidebar.selectbox("🏟️ リーグを選択", df_leagues["リーグ名"].tolist())
else:
    st.sidebar.warning("「設定」からリーグを作成してください")
    target_league = None

tab_rank, tab_input, tab_setting = st.tabs(["🏆 ランキング", "💰 スコア入力", "⚙️ 設定"])

# --- 1. ランキング ---
with tab_rank:
    if target_league and not df_scores.empty:
        df_l = df_scores[df_scores["リーグ"] == target_league].copy()
        if not df_l.empty:
            # 【修正】日付エラー対策：不正な日付はNaTにして除外する
            df_l["日付"] = pd.to_datetime(df_l["日付"], errors='coerce')
            df_l = df_l.dropna(subset=["日付"])
            
            period = st.radio("表示期間", ["今日", "週間", "月間"], horizontal=True)
            now = datetime.now()
            if period == "今日": df_filtered = df_l[df_l["日付"].dt.date == now.date()]
            elif period == "週間": df_filtered = df_l[df_l["日付"] >= (now - timedelta(days=now.weekday()))]
            else: df_filtered = df_l[(df_l["日付"].dt.year == now.year) & (df_l["日付"].dt.month == now.month)]
            
            if not df_filtered.empty and "スコア" in df_filtered.columns:
                df_filtered["スコア"] = pd.to_numeric(df_filtered["スコア"], errors='coerce').fillna(0)
                ranking = df_filtered.groupby("名前")["スコア"].sum().reset_index()
                ranking = ranking.sort_values("スコア", ascending=False).reset_index(drop=True)
                ranking.index += 1
                
                for i, row in ranking.iterrows():
                    c1, c2, c3 = st.columns([1, 4, 2])
                    c1.write(f"#{i}")
                    c2.markdown(f"**{row['名前']}**")
                    score_val = row.get('スコア', 0)
                    color = "#58a6ff" if score_val >= 0 else "#f85149"
                    c3.markdown(f"<span style='color:{color}; font-size:1.2em; font-weight:bold;'>{int(score_val):+,}</span>", unsafe_allow_html=True)
                    st.divider()

                total_sum = int(df_filtered["スコア"].sum())
                sum_color = "#e6edf3" if total_sum == 0 else ("#58a6ff" if total_sum > 0 else "#f85149")
                st.markdown(f'<div class="total-sum-area"><p style="margin:0; color:#8b949e; font-size:0.9em;">合計差額</p><h2 style="margin:0; color:{sum_color};">{total_sum:+,}</h2></div>', unsafe_allow_html=True)
            else: st.info("表示可能なデータがありません")
        else: st.info("このリーグのスコアデータはありません")
    else: st.info("左メニューからリーグを選択してください")

# --- 2. スコア入力 ---
with tab_input:
    if df_leagues.empty:
        st.error("先に「設定」タブから「リーグ管理」を行ってください")
    elif df_players.empty:
        st.error("先に「設定」タブから「プレイヤー管理」を行ってください")
    elif target_league:
        league_players = df_players[df_players["リーグ"] == target_league]["名前"].tolist()
        if not league_players: 
            st.warning(f"リーグ「{target_league}」にプレイヤーが登録されていません")
        else:
            if "input_rows" not in st.session_state: st.session_state.input_rows = 1
            entries = []
            for i in range(st.session_state.input_rows):
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 2, 2])
                    p_name = c1.selectbox("プレイヤー", league_players, key=f"p_name_{i}")
                    raw_pts = c2.number_input("ポイント", step=10, key=f"raw_pts_{i}")
                    rate = c3.selectbox("レート", ["1/1", "1/5", "1/10", "1/30", "カスタム"], key=f"rate_{i}")
                    div = 1
                    if rate == "1/5": div = 5
                    elif rate == "1/10": div = 10
                    elif rate == "1/30": div = 30
                    elif rate == "カスタム": div = st.number_input("割る数", min_value=0.1, value=1.0, key=f"cust_{i}")
                    final_score = math.floor(raw_pts / div)
                    st.caption(f"スコア換算: {final_score:,}")
                    entries.append({"名前": p_name, "スコア": final_score, "日付": datetime.now().strftime("%Y-%m-%d %H:%M"), "リーグ": target_league})

            col_add, col_save = st.columns(2)
            if col_add.button("➕ プレイヤーを追加"):
                st.session_state.input_rows += 1
                st.rerun()
            if col_save.button("🚀 まとめて保存"):
                if entries:
                    new_data = pd.DataFrame(entries)
                    updated_scores = pd.concat([df_scores, new_data], ignore_index=True)
                    conn.update(spreadsheet=url, worksheet="scores", data=updated_scores)
                    st.toast("保存完了！リセットします。", icon="🚀")
                    st.session_state.input_rows = 1
                    for key in list(st.session_state.keys()):
                        if key.startswith(("p_name_", "raw_pts_", "rate_", "cust_")): del st.session_state[key]
                    time.sleep(1)
                    st.rerun()
    else:
        st.info("左メニューからリーグを選択してください")

# --- 3. 設定 ---
with tab_setting:
    m_tab1, m_tab2, m_tab3 = st.tabs(["👥 プレイヤー管理", "🏟️ リーグ管理", "🗑️ ごみ箱"])
    # （以降の管理コードは省略しますが、これまでの正常なロジックを維持してください）