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

# --- デザインCSS（コンパクト表示維持） ---
st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
    input, select, textarea, div[data-baseweb="select"] { color: #ffffff !important; background-color: #1c2128 !important; }
    .stTabs [data-baseweb="tab-list"] { background-color: #161b22; border-radius: 10px; padding: 5px; }
    .stTabs [data-baseweb="tab"] { color: #8b949e; font-weight: bold; font-size: 14px; }
    .compact-row { height: 24px !important; border-bottom: 1px solid #21262d; display: flex; align-items: center; overflow: hidden; }
    div[data-testid="column"] { padding: 0px !important; margin: 0px !important; gap: 0px !important; }
    div.stButton > button[key^="user_"] {
        background: none !important; border: none !important; padding: 0 !important; margin: 0 !important;
        color: #58a6ff !important; height: 24px !important; line-height: 24px !important;
        text-align: left !important; font-weight: bold !important; font-size: 0.9em !important;
    }
    .rank-num { font-size: 0.75em; color: #8b949e; padding-top: 4px; }
    .score-num { font-size: 0.9em; font-weight: bold; text-align: right; padding-top: 4px; }
    .change-up { color: #3fb950; font-size: 0.7em; font-weight: bold; }
    .change-down { color: #f85149; font-size: 0.7em; font-weight: bold; }
    .hall-of-fame { background: linear-gradient(135deg, #1c2128, #161b22); padding: 10px; border-radius: 10px; border: 1px solid #d4af37; margin-top: 15px; }
    .total-sum-area { background-color: #1c2128; padding: 8px; border-radius: 10px; border: 1px solid #30363d; text-align: center; margin-top: 8px; }
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
        
        if not df_l.empty:
            st.markdown(f'''<div class="hall-of-fame"><div style="font-size:0.7em; color:#d4af37; font-weight:bold;">🏆 記録</div>
                <div style="display:flex; justify-content:space-around; font-size:0.75em;">
                <div>最高勝利: <b>{int(df_l["スコア"].max()):+,}</b></div>
                <div>最大敗北: <b>{int(df_l["スコア"].min()):+,}</b></div>
                </div></div>''', unsafe_allow_html=True)

# --- 2. スコア入力（バリデーション強化） ---
with tab_input:
    if t_league and not df_players.empty:
        l_players = df_players[df_players["リーグ"] == t_league]["名前"].tolist()
        if "input_rows" not in st.session_state: st.session_state.input_rows = 1
        entries = []
        has_zero_score = False # 0入力チェック用
        
        for i in range(st.session_state.input_rows):
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1.5, 1.5])
                p_n = c1.selectbox("選手", l_players, key=f"p_name_{i}")
                raw = c2.number_input("pt", step=10, key=f"raw_pts_{i}")
                rate = c3.selectbox("率", ["1/1", "1/5", "1/10", "1/30"], key=f"rate_{i}")
                div = 5.0 if rate=="1/5" else (10.0 if rate=="1/10" else (30.0 if rate=="1/30" else 1.0))
                val = math.floor(raw/div)
                if val == 0: has_zero_score = True
                entries.append({"名前": p_n, "スコア": val, "日付": get_jst_now().strftime("%Y-%m-%d %H:%M"), "リーグ": t_league})
        
        total_in = sum(e["スコア"] for e in entries)
        
        # --- 保存可否の判定ロジック ---
        is_ready = True
        error_msg = ""
        
        if total_in != 0:
            is_ready = False
            error_msg = f"収支が合いません（残: {total_in:+,}）"
        elif has_zero_score:
            is_ready = False
            error_msg = "スコアが0または未入力の選手がいます"
            
        if not is_ready:
            st.warning(f"⚠️ {error_msg}")
        else:
            st.success("✅ 収支一致。保存可能です。")

        ca, cs = st.columns(2)
        if ca.button("➕ 行を追加"):
            st.session_state.input_rows += 1
            st.rerun()
            
        # 判定結果に基づいてボタンを無効化
        if cs.button("🚀 保存", disabled=not is_ready):
            try:
                with st.spinner('保存中...'):
                    conn.update(spreadsheet=url, worksheet="scores", data=pd.concat([df_scores, pd.DataFrame(entries)], ignore_index=True))
                    time.sleep(1)
                    st.cache_data.clear()
                    st.session_state.input_rows = 1
                    for k in list(st.session_state.keys()):
                        if k.startswith(("p_name_", "raw_pts_", "rate_")): del st.session_state[k]
                    st.rerun()
            except: st.error("通信失敗")

# --- 3. 設定 ---
with tab_setting:
    m1, m2, m3 = st.tabs(["👥 選手", "🏆 リーグ", "📜 履歴"])
    with m1:
        pn = st.text_input("選手名登録")
        if st.button("登録") and pn:
            conn.update(spreadsheet=url, worksheet="players", data=pd.concat([df_players, pd.DataFrame([{"名前": pn, "リーグ": t_league}])], ignore_index=True))
            st.cache_data.clear(); st.rerun()
    with m2:
        nl = st.text_input("新リーグ作成")
        if st.button("作成") and nl:
            conn.update(spreadsheet=url, worksheet="leagues", data=pd.concat([df_leagues, pd.DataFrame({"リーグ名": [nl]})], ignore_index=True))
            st.cache_data.clear(); st.rerun()
    with m3:
        if not df_scores.empty:
            for i, r in df_scores.iloc[::-1].head(10).iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([5, 1])
                    c1.write(f"{r.get('名前')}: {int(r.get('スコア')):+,}")
                    if c2.button("🗑️", key=f"d_{i}"):
                        conn.update(spreadsheet=url, worksheet="scores", data=df_scores.drop(i))
                        st.cache_data.clear(); st.rerun()