import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import math
import time

# --- 基本設定 ---
url = "https://docs.google.com/spreadsheets/d/1YLXZWQ6XZz04mi0dx9_6WFbm2-yZQGGIXd3yVEh9kTQ/edit?usp=sharing"

st.set_page_config(page_title="POKER LEAGUE PRO", page_icon="♠️", layout="centered")

# --- 日本時間取得 ---
def get_jst_now():
    return datetime.utcnow() + timedelta(hours=9)

# --- オンラインカジノ・ネオンPROデザインCSS ---
st.markdown("""
    <style>
    /* ベース背景：漆黒 */
    .stApp {
        background: radial-gradient(circle at top, #0f172a 0%, #020617 100%) !important;
        color: #f8fafc !important;
    }
    
    /* POKER LEAGUE PRO ネオンタイトル */
    .neon-title {
        font-family: 'Impact', sans-serif;
        font-size: 2.5rem;
        font-weight: 900;
        text-align: center;
        background: linear-gradient(to bottom, #fff 20%, #f472b6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        filter: drop-shadow(0 0 10px #f472b6) drop-shadow(0 0 20px #f472b6);
        margin-bottom: 30px;
        letter-spacing: 3px;
    }

    /* タブ：サイバーデザイン */
    .stTabs [data-baseweb="tab-list"] {
        background-color: rgba(15, 23, 42, 0.9);
        border-radius: 15px;
        padding: 5px;
        border: 1px solid rgba(56, 189, 248, 0.2);
    }
    .stTabs [data-baseweb="tab"] {
        color: #64748b;
        font-weight: bold;
        transition: 0.3s;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%) !important;
        color: white !important;
        border-radius: 10px;
        box-shadow: 0 0 15px rgba(14, 165, 233, 0.4);
    }

    /* ランキングカード：高級感のある半透明 */
    .rank-card {
        background: rgba(30, 41, 59, 0.6);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 18px;
        padding: 16px;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    }
    
    /* プレイヤーボタン */
    div.stButton > button[key^="user_"] {
        background: rgba(14, 165, 233, 0.1) !important;
        border: 1px solid rgba(14, 165, 233, 0.4) !important;
        color: #38bdf8 !important;
        font-weight: 800 !important;
        border-radius: 10px !important;
        padding: 10px 20px !important;
    }
    div.stButton > button[key^="user_"]:hover {
        background: #0ea5e9 !important;
        color: white !important;
        box-shadow: 0 0 20px rgba(14, 165, 233, 0.6);
    }

    /* スコア表示 */
    .score-plus { color: #4ade80; font-weight: 800; font-size: 1.3rem; text-shadow: 0 0 8px rgba(74, 222, 128, 0.4); }
    .score-minus { color: #fb7185; font-weight: 800; font-size: 1.3rem; text-shadow: 0 0 8px rgba(251, 113, 133, 0.4); }
    .rank-num { color: #fbbf24; font-weight: 900; font-size: 1.1rem; margin-right: 12px; }

    /* 合計収支カード */
    .total-card {
        background: linear-gradient(135deg, #1e293b 0%, #020617 100%);
        border: 2px solid #fbbf24;
        border-radius: 20px;
        padding: 25px;
        text-align: center;
        box-shadow: 0 0 30px rgba(251, 191, 36, 0.15);
    }

    /* 入力エリアのコンテナ */
    div[data-testid="stExpander"], .stContainer {
        background-color: rgba(30, 41, 59, 0.3) !important;
        border-radius: 15px !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
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

# --- タイトル ---
st.markdown('<div class="neon-title">POKER LEAGUE PRO</div>', unsafe_allow_html=True)

# サイドバー
with st.sidebar:
    st.markdown("### 🏟️ リーグ選択")
    if not df_leagues.empty:
        t_league = st.selectbox("表示するリーグ", df_leagues["リーグ名"].tolist(), label_visibility="collapsed")
    if st.button("🔄 データを同期", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

tab_rank, tab_input, tab_setting = st.tabs(["🏆 ランキング", "💰 スコア入力", "⚙️ 設定"])

# --- 1. ランキング ---
with tab_rank:
    if not df_scores.empty:
        df_l = df_scores[df_scores["リーグ"] == t_league].copy()
        df_l["スコア"] = pd.to_numeric(df_l["スコア"], errors='coerce').fillna(0)
        df_l["日付"] = pd.to_datetime(df_l["日付"], errors='coerce')

        period = st.segmented_control("期間切替", ["今日", "今月", "前月", "全期間"], default="今月")
        
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
                v = int(row['スコア'])
                style = "score-plus" if v >= 0 else "score-minus"
                
                st.markdown(f'<div class="rank-card">', unsafe_allow_html=True)
                c_r, c_n, c_v = st.columns([0.15, 0.55, 0.3])
                c_r.markdown(f'<div class="rank-num">#{i+1}</div>', unsafe_allow_html=True)
                with c_n:
                    if st.button(row['名前'], key=f"user_{row['名前']}", use_container_width=True):
                        st.session_state.detail_p = row['名前']; st.rerun()
                c_v.markdown(f'<div class="{style}" style="text-align:right;">{v:+,}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            total = int(df_f["スコア"].sum())
            st.markdown(f'<div class="total-card"><span style="color:#94a3b8; font-size:0.85rem;">合計収支</span><h2 style="margin:0; color:#fbbf24; font-size:2rem;">{total:+,}</h2></div>', unsafe_allow_html=True)
        else:
            st.info("この期間の記録はまだありません。")

# --- 2. スコア入力（行の削除機能追加） ---
with tab_input:
    if not df_players.empty:
        l_players = df_players[df_players["リーグ"] == t_league]["名前"].tolist()
        # 初回は2人分表示
        if "input_rows" not in st.session_state: st.session_state.input_rows = 2
        
        entries = []
        has_zero = False
        
        for i in range(st.session_state.input_rows):
            with st.container(border=True):
                c1, c2, c3 = st.columns([1.5, 1, 1])
                p_n = c1.selectbox(f"プレイヤー {i+1}", l_players, key=f"p_name_{i}")
                raw = c2.number_input("ポイント", step=10, key=f"raw_pts_{i}")
                rate = c3.selectbox("レート", ["1/1", "1/5", "1/10", "1/30"], key=f"rate_{i}")
                div = 5.0 if rate=="1/5" else (10.0 if rate=="1/10" else (30.0 if rate=="1/30" else 1.0))
                val = math.floor(raw/div)
                if val == 0: has_zero = True
                st.caption(f"換算収支: {val:+,}")
                entries.append({"名前": p_n, "スコア": val, "日付": get_jst_now().strftime("%Y-%m-%d %H:%M"), "リーグ": t_league})
        
        total_in = sum(e["スコア"] for e in entries)
        can_save = not has_zero
        
        if has_zero: st.error("❌ スコアが0のプレイヤーがいます（入力してください）")
        elif total_in != 0: st.warning(f"⚖️ 収支が合っていません（差額: {total_in:+,}）")
        else: st.success("✅ 収支が一致しています")

        # --- 操作ボタン群 ---
        c_add, c_del, c_save = st.columns([1, 1, 2])
        with c_add:
            if st.button("➕ 追加", use_container_width=True):
                st.session_state.input_rows += 1
                st.rerun()
        with c_del:
            # 1人以下の時は削除ボタンを無効化
            if st.button("➖ 削除", use_container_width=True, disabled=st.session_state.input_rows <= 1):
                st.session_state.input_rows -= 1
                st.rerun()
        with c_save:
            if st.button("🚀 保存する", disabled=not can_save, use_container_width=True):
                conn.update(spreadsheet=url, worksheet="scores", data=pd.concat([df_scores, pd.DataFrame(entries)], ignore_index=True))
                st.cache_data.clear()
                st.session_state.input_rows = 2 # 保存後は2人に戻す
                for k in list(st.session_state.keys()):
                    if k.startswith(("p_name_", "raw_pts_", "rate_")): del st.session_state[k]
                st.toast("記録を保存しました！")
                time.sleep(1)
                st.rerun()

# --- 3. 設定 ---
with tab_setting:
    m1, m2, m3 = st.tabs(["👤 プレイヤー登録", "🏆 リーグ作成", "📜 履歴・削除"])
    with m1:
        pn = st.text_input("新しいプレイヤーの名前")
        if st.button("登録する", use_container_width=True) and pn:
            conn.update(spreadsheet=url, worksheet="players", data=pd.concat([df_players, pd.DataFrame([{"名前": pn, "リーグ": t_league}])], ignore_index=True))
            st.cache_data.clear(); st.rerun()
    with m2:
        nl = st.text_input("新しいリーグの名前")
        if st.button("作成する", use_container_width=True) and nl:
            conn.update(spreadsheet=url, worksheet="leagues", data=pd.concat([df_leagues, pd.DataFrame({"リーグ名": [nl]})], ignore_index=True))
            st.cache_data.clear(); st.rerun()
    with m3:
        if not df_scores.empty:
            st.markdown("### 直近の記録（最新10件）")
            for i, r in df_scores.iloc[::-1].head(10).iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([4, 1])
                    c1.markdown(f"**{r.get('名前')}** <small>{r.get('日付')}</small>  \n**{int(r.get('スコア')):+,}** pts", unsafe_allow_html=True)
                    if c2.button("🗑️", key=f"d_{i}", help="この記録を削除"):
                        conn.update(spreadsheet=url, worksheet="scores", data=df_scores.drop(i))
                        st.cache_data.clear(); st.rerun()