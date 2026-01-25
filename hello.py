import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import math
import time

# --- 基本設定 ---
url = "https://docs.google.com/spreadsheets/d/1YLXZWQ6XZz04mi0dx9_6WFbm2-yZQGGIXd3yVEh9kTQ/edit?usp=sharing"
st.set_page_config(page_title="POKER LEAGUE PRO", page_icon="♠️", layout="centered")

def get_jst_now():
    return datetime.utcnow() + timedelta(hours=9)

# --- 超スマホ特化型・横一行ネオンデザインCSS ---
st.markdown("""
    <style>
    /* 全体背景 */
    .stApp { background: radial-gradient(circle at top, #0f172a 0%, #020617 100%) !important; color: #f8fafc !important; }
    
    /* ネオンタイトル */
    .neon-title {
        font-family: 'Impact', sans-serif; font-size: 1.8rem; font-weight: 900; text-align: center;
        background: linear-gradient(to bottom, #fff 20%, #f472b6 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        filter: drop-shadow(0 0 8px #f472b6); margin-bottom: 15px; letter-spacing: 2px;
    }

    /* タブ */
    .stTabs [data-baseweb="tab-list"] { background-color: rgba(15, 23, 42, 0.9); border-radius: 12px; padding: 4px; border: 1px solid rgba(56, 189, 248, 0.2); }
    .stTabs [data-baseweb="tab"] { color: #64748b; font-weight: bold; font-size: 13px; height: 34px; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] { background: #0ea5e9 !important; color: white !important; border-radius: 8px; }

    /* ランキング行：極薄・横一列 */
    .rank-card {
        background: rgba(30, 41, 59, 0.4); border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        padding: 4px 8px; margin-bottom: 2px; display: flex; align-items: center; justify-content: space-between;
    }
    
    /* 名前ボタン：幅をスリム化 & ネオンブルー */
    div.stButton > button[key^="user_"] {
        background: rgba(14, 165, 233, 0.1) !important; border: 1px solid rgba(14, 165, 233, 0.4) !important;
        color: #38bdf8 !important; font-weight: 700 !important; border-radius: 6px !important;
        padding: 0px 8px !important; height: 26px !important; font-size: 0.8rem !important;
        width: 100% !important; max-width: 120px !important; /* 横幅を制限 */
        text-align: center !important; overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
    }
    div.stButton > button[key^="user_"]:active { transform: scale(0.96); background: #0ea5e9 !important; color: white !important; }

    /* 順位・スコアのテキスト */
    .rank-num { color: #fbbf24; font-weight: 900; font-size: 0.8rem; min-width: 24px; text-align: left; }
    .score-plus { color: #4ade80; font-weight: 700; font-size: 0.9rem; text-align: right; min-width: 65px; }
    .score-minus { color: #fb7185; font-weight: 700; font-size: 0.9rem; text-align: right; min-width: 65px; }

    /* 合計カード */
    .total-card {
        background: rgba(15, 23, 42, 0.9); border: 1px solid #fbbf24; border-radius: 12px;
        padding: 10px; text-align: center; margin-top: 10px;
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

st.markdown('<div class="neon-title">POKER LEAGUE PRO</div>', unsafe_allow_html=True)

# サイドバー
with st.sidebar:
    st.markdown("### 🏟️ 設定")
    if not df_leagues.empty:
        t_league = st.selectbox("リーグ選択", df_leagues["リーグ名"].tolist())
    if st.button("🔄 データを同期"):
        st.cache_data.clear(); st.rerun()

tab_rank, tab_input, tab_setting = st.tabs(["🏆 ランキング", "💰 スコア入力", "⚙️ 設定"])

# --- 1. ランキング（横一列・超圧縮） ---
with tab_rank:
    if not df_scores.empty:
        df_l = df_scores[df_scores["リーグ"] == t_league].copy()
        df_l["スコア"] = pd.to_numeric(df_l["スコア"], errors='coerce').fillna(0)
        df_l["日付"] = pd.to_datetime(df_l["日付"], errors='coerce')

        period = st.segmented_control("表示期間", ["今日", "今月", "前月", "全期間"], default="今月")
        
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
                
                # コンテナを使用して横一行に配置
                st.markdown(f'<div class="rank-card">', unsafe_allow_html=True)
                c_rank, c_name, c_score = st.columns([0.15, 0.50, 0.35])
                c_rank.markdown(f'<div class="rank-num">#{i+1}</div>', unsafe_allow_html=True)
                with c_name:
                    # 名前の長さに合わせてスリムなボタンを表示
                    if st.button(row['名前'], key=f"user_{row['名前']}", use_container_width=True):
                        st.session_state.detail_p = row['名前']; st.rerun()
                c_score.markdown(f'<div class="{style}">{v:+,}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            total = int(df_f["スコア"].sum())
            st.markdown(f'<div class="total-card"><span style="color:#94a3b8; font-size:0.7rem;">合計収支</span><h3 style="margin:0; color:#fbbf24;">{total:+,}</h3></div>', unsafe_allow_html=True)
        else: st.info("記録がありません。")

# --- 2. スコア入力（削除機能あり） ---
with tab_input:
    if not df_players.empty:
        l_players = df_players[df_players["リーグ"] == t_league]["名前"].tolist()
        if "input_rows" not in st.session_state: st.session_state.input_rows = 2
        
        entries = []
        has_zero = False
        for i in range(st.session_state.input_rows):
            with st.container(border=True):
                c1, c2, c3 = st.columns([1.5, 1, 1])
                p_n = c1.selectbox(f"選手 {i+1}", l_players, key=f"p_name_{i}")
                raw = c2.number_input("pt", step=10, key=f"raw_pts_{i}")
                rate = c3.selectbox("レート", ["1/1", "1/5", "1/10", "1/30"], key=f"rate_{i}")
                div = 5.0 if rate=="1/5" else (10.0 if rate=="1/10" else (30.0 if rate=="1/30" else 1.0))
                val = math.floor(raw/div)
                if val == 0: has_zero = True
                entries.append({"名前": p_n, "スコア": val, "日付": get_jst_now().strftime("%Y-%m-%d %H:%M"), "リーグ": t_league})
        
        total_in = sum(e["スコア"] for e in entries)
        can_save = not has_zero
        
        if has_zero: st.error("❌ スコア0の選手がいます")
        elif total_in != 0: st.warning(f"⚖️ 差額: {total_in:+,}")
        else: st.success("✅ 収支一致")

        c_add, c_del, c_save = st.columns([1, 1, 2])
        if c_add.button("➕ 追加", use_container_width=True):
            st.session_state.input_rows += 1; st.rerun()
        if c_del.button("➖ 削除", use_container_width=True, disabled=st.session_state.input_rows <= 1):
            st.session_state.input_rows -= 1; st.rerun()
        if c_save.button("🚀 保存", disabled=not can_save, use_container_width=True):
            conn.update(spreadsheet=url, worksheet="scores", data=pd.concat([df_scores, pd.DataFrame(entries)], ignore_index=True))
            st.cache_data.clear(); st.session_state.input_rows = 2; st.toast("保存成功！"); time.sleep(1); st.rerun()

# --- 3. 設定 ---
with tab_setting:
    m1, m2, m3 = st.tabs(["👤 選手登録", "🏆 リーグ作成", "📜 履歴削除"])
    with m1:
        pn = st.text_input("選手名を入力")
        if st.button("登録する") and pn:
            conn.update(spreadsheet=url, worksheet="players", data=pd.concat([df_players, pd.DataFrame([{"名前": pn, "リーグ": t_league}])], ignore_index=True))
            st.cache_data.clear(); st.rerun()
    with m2:
        nl = st.text_input("リーグ名を入力")
        if st.button("作成する") and nl:
            conn.update(spreadsheet=url, worksheet="leagues", data=pd.concat([df_leagues, pd.DataFrame({"リーグ名": [nl]})], ignore_index=True))
            st.cache_data.clear(); st.rerun()
    with m3:
        if not df_scores.empty:
            for i, r in df_scores.iloc[::-1].head(10).iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([4, 1])
                    c1.write(f"**{r.get('名前')}** \n{int(r.get('スコア')):+,} pts")
                    if c2.button("🗑️", key=f"d_{i}"):
                        conn.update(spreadsheet=url, worksheet="scores", data=df_scores.drop(i))
                        st.cache_data.clear(); st.rerun()