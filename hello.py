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

# --- 究極のスタイリッシュCSS ---
st.markdown("""
    <style>
    /* 全体背景とフォント */
    .stApp {
        background: radial-gradient(circle at top, #0f172a 0%, #020617 100%) !important;
        color: #f8fafc !important;
    }
    
    /* タブのデザインをアプリ風に */
    .stTabs [data-baseweb="tab-list"] {
        background-color: rgba(30, 41, 59, 0.5);
        border-radius: 12px;
        padding: 4px;
        gap: 8px;
        margin-bottom: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        border-radius: 8px;
        color: #94a3b8;
        font-weight: 600;
        transition: all 0.3s;
    }
    .stTabs [data-baseweb="tab"]:hover { color: #38bdf8; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #0ea5e9 !important;
        color: white !important;
        box-shadow: 0 4px 12px rgba(14, 165, 233, 0.3);
    }

    /* ランキング行：カード型モバイルデザイン */
    .rank-card {
        background: rgba(30, 41, 59, 0.4);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 12px 16px;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        transition: transform 0.2s;
    }
    
    /* 名前ボタン：指に優しい大きな押し領域 */
    div.stButton > button[key^="user_"] {
        background: rgba(14, 165, 233, 0.1) !important;
        border: 1px solid rgba(14, 165, 233, 0.3) !important;
        color: #38bdf8 !important;
        width: 100% !important;
        padding: 8px 16px !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        font-size: 1rem !important;
        text-align: left !important;
        transition: all 0.2s !important;
    }
    div.stButton > button[key^="user_"]:active {
        transform: scale(0.95);
        background: rgba(14, 165, 233, 0.3) !important;
    }

    /* 数字の装飾 */
    .rank-num { font-family: 'Inter', sans-serif; font-weight: 800; color: #64748b; font-size: 0.9rem; min-width: 25px; }
    .score-plus { color: #4ade80; font-family: 'Courier New', monospace; font-weight: 700; font-size: 1.1rem; }
    .score-minus { color: #f87171; font-family: 'Courier New', monospace; font-weight: 700; font-size: 1.1rem; }

    /* 入力欄のカスタマイズ */
    div[data-baseweb="input"], div[data-baseweb="select"] {
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 10px !important;
    }
    
    /* 合計エリア */
    .total-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #38bdf8;
        border-radius: 16px;
        padding: 20px;
        text-align: center;
        margin: 20px 0;
        box-shadow: 0 0 20px rgba(14, 165, 233, 0.15);
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

# サイドバー設定
with st.sidebar:
    st.markdown("### 🏟️ League Select")
    if not df_leagues.empty:
        l_list = df_leagues["リーグ名"].tolist()
        t_league = st.selectbox("参加中のリーグ", l_list, label_visibility="collapsed")
    if st.button("🔄 データを同期"):
        st.cache_data.clear()
        st.rerun()

st.title("♠️ Poker League")

tab_rank, tab_input, tab_setting = st.tabs(["🏆 Rank", "💰 Input", "⚙️ Admin"])

# --- 1. ランキング ---
with tab_rank:
    if not df_scores.empty:
        df_l = df_scores[df_scores["リーグ"] == t_league].copy()
        df_l["スコア"] = pd.to_numeric(df_l["スコア"], errors='coerce').fillna(0)
        df_l["日付"] = pd.to_datetime(df_l["日付"], errors='coerce')

        # 詳細ポップアップ（スマホで見やすく調整）
        if "detail_p" in st.session_state:
            dp = st.session_state.detail_p
            with st.container(border=True):
                c_h, c_c = st.columns([5, 1])
                c_h.markdown(f"### 📊 {dp}")
                if c_c.button("×"): del st.session_state.detail_p; st.rerun()
                df_p = df_l[df_l["名前"] == dp].sort_values("日付")
                if not df_p.empty:
                    st.line_chart(df_p.set_index("日付")["スコア"].cumsum())

        period = st.segmented_control("期間", ["今日", "今月", "前月", "全期間"], default="今月")
        
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
                score_class = "score-plus" if v >= 0 else "score-minus"
                
                # HTMLカスタムレイアウト
                st.markdown(f'<div class="rank-card">', unsafe_allow_html=True)
                c_r, c_n, c_v = st.columns([0.1, 0.65, 0.25])
                c_r.markdown(f'<div class="rank-num">#{i+1}</div>', unsafe_allow_html=True)
                with c_n:
                    if st.button(row['名前'], key=f"user_{row['名前']}"):
                        st.session_state.detail_p = row['名前']; st.rerun()
                c_v.markdown(f'<div class="{score_class}">{v:+,}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            total = int(df_f["スコア"].sum())
            st.markdown(f'<div class="total-card"><span style="color:#94a3b8; font-size:0.8rem;">TOTAL BALANCE</span><h2 style="margin:0; color:#38bdf8;">{total:+,}</h2></div>', unsafe_allow_html=True)
        else: st.info("No data found for this period.")

# --- 2. スコア入力 ---
with tab_input:
    if not df_players.empty:
        l_players = df_players[df_players["リーグ"] == t_league]["名前"].tolist()
        if "input_rows" not in st.session_state: st.session_state.input_rows = 2
        entries = []
        has_zero = False
        
        for i in range(st.session_state.input_rows):
            with st.container(border=True):
                c1, c2, c3 = st.columns([1.5, 1, 1])
                p_n = c1.selectbox(f"Player {i+1}", l_players, key=f"p_name_{i}")
                raw = c2.number_input("pts", step=10, key=f"raw_pts_{i}")
                rate = c3.selectbox("Rate", ["1/1", "1/5", "1/10", "1/30"], key=f"rate_{i}")
                div = 5.0 if rate=="1/5" else (10.0 if rate=="1/10" else (30.0 if rate=="1/30" else 1.0))
                val = math.floor(raw/div)
                if val == 0: has_zero = True
                entries.append({"名前": p_n, "スコア": val, "日付": get_jst_now().strftime("%Y-%m-%d %H:%M"), "リーグ": t_league})
        
        total_in = sum(e["スコア"] for e in entries)
        can_save = not has_zero
        
        if has_zero: st.error("⚠️ スコア0の選手が含まれています")
        elif total_in != 0: st.warning(f"⚖️ 収支差額: {total_in:+,}")
        else: st.success("✅ 収支一致")

        c_add, c_save = st.columns(2)
        if c_add.button("➕ Playerを追加"):
            st.session_state.input_rows += 1; st.rerun()
        if c_save.button("🚀 この内容で保存", disabled=not can_save, use_container_width=True):
            conn.update(spreadsheet=url, worksheet="scores", data=pd.concat([df_scores, pd.DataFrame(entries)], ignore_index=True))
            st.cache_data.clear(); st.session_state.input_rows = 2; st.toast("Success!"); time.sleep(1); st.rerun()

# --- 3. 管理設定 ---
with tab_setting:
    m1, m2, m3 = st.tabs(["👤 Players", "🏟️ League", "📜 History"])
    with m1:
        pn = st.text_input("Player Name")
        if st.button("Add Player") and pn:
            conn.update(spreadsheet=url, worksheet="players", data=pd.concat([df_players, pd.DataFrame([{"名前": pn, "リーグ": t_league}])], ignore_index=True))
            st.cache_data.clear(); st.rerun()
    with m2:
        nl = st.text_input("New League Name")
        if st.button("Create League") and nl:
            conn.update(spreadsheet=url, worksheet="leagues", data=pd.concat([df_leagues, pd.DataFrame({"リーグ名": [nl]})], ignore_index=True))
            st.cache_data.clear(); st.rerun()
    with m3:
        if not df_scores.empty:
            for i, r in df_scores.iloc[::-1].head(10).iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([4, 1])
                    c1.write(f"**{r.get('名前')}** ({r.get('日付')})  \n{int(r.get('スコア')):+,} pts")
                    if c2.button("🗑️", key=f"d_{i}"):
                        conn.update(spreadsheet=url, worksheet="scores", data=df_scores.drop(i))
                        st.cache_data.clear(); st.rerun()