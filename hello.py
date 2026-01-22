import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import math
import time

# --- 設定 ---
url = "https://docs.google.com/spreadsheets/d/1YLXZWQ6XZz04mi0dx9_6WFbm2-yZQGGIXd3yVEh9kTQ/edit?usp=sharing"

st.set_page_config(page_title="Poker League Master", page_icon="♠️", layout="centered")

# --- デザインCSS（ボタンの余白を削り、行間を極小にする） ---
st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
    input, select, textarea, div[data-baseweb="select"] {
        color: #ffffff !important;
        background-color: #1c2128 !important;
    }
    .stTabs [data-baseweb="tab-list"] { background-color: #161b22; border-radius: 10px; padding: 5px; }
    .stTabs [data-baseweb="tab"] { color: #8b949e; font-weight: bold; font-size: 14px; }
    
    /* ランキング行の極小化 */
    .compact-row { 
        padding: 0px; 
        border-bottom: 1px solid #30363d;
        display: flex;
        align-items: center;
        min-height: 32px;
    }
    
    /* ユーザー名ボタンのスタイル修正（余白排除） */
    div.stButton > button[key^="user_"] {
        background: none !important;
        border: none !important;
        padding: 0 !important;
        margin: 0 !important;
        color: #58a6ff !important;
        height: 32px !important;
        line-height: 32px !important;
        text-align: left !important;
        font-weight: bold !important;
        font-size: 1em !important;
        min-height: 0px !important;
    }
    
    /* カラム間の余白調整 */
    div[data-testid="column"] {
        padding: 0px !important;
    }

    .total-sum-area { background-color: #1c2128; padding: 12px; border-radius: 12px; border: 2px solid #30363d; text-align: center; margin-top: 15px; }

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

# --- データの読み込みと記憶保持 ---
for sheet in ["scores", "players", "leagues"]:
    new_data = load_data(sheet)
    if new_data is not None or f"cache_{sheet}" not in st.session_state:
        st.session_state[f"cache_{sheet}"] = new_data if new_data is not None else pd.DataFrame()

df_scores = st.session_state.cache_scores
df_players = st.session_state.cache_players
df_leagues = st.session_state.cache_leagues

# リーグの自動選択と保持
target_league = st.session_state.get("selected_league")
if not df_leagues.empty:
    l_list = df_leagues["リーグ名"].tolist()
    if len(l_list) == 1:
        target_league = l_list[0]
        st.sidebar.info(f"🏟️ リーグ: {target_league}")
    else:
        idx = l_list.index(target_league) if target_league in l_list else 0
        target_league = st.sidebar.selectbox("🏟️ リーグを選択", l_list, index=idx)
    st.session_state.selected_league = target_league
else:
    st.sidebar.warning("リーグを作成してください")

tab_rank, tab_input, tab_setting = st.tabs(["🏆 ランキング", "💰 スコア入力", "⚙️ 設定"])

# --- 1. ランキング ---
with tab_rank:
    if target_league and not df_scores.empty:
        # 詳細分析画面（表示時のみ）
        if "detail_p" in st.session_state:
            dp = st.session_state.detail_p
            with st.container(border=True):
                c_h, c_c = st.columns([5, 1])
                c_h.subheader(f"📊 {dp} の分析")
                if c_c.button("✖️"):
                    del st.session_state.detail_p
                    st.rerun()
                
                df_p = df_scores[(df_scores["リーグ"] == target_league) & (df_scores["名前"] == dp)].copy()
                df_p["スコア"] = pd.to_numeric(df_p["スコア"], errors='coerce').fillna(0)
                if not df_p.empty:
                    s1, s2, s3, s4 = st.columns(4)
                    s1.metric("平均", f"{df_p['スコア'].mean():,.0f}")
                    sWin = (df_p["スコア"] > 0).mean() * 100
                    s2.metric("勝率", f"{sWin:.1f}%")
                    s3.metric("最大勝", f"{df_p['スコア'].max():+,}")
                    s4.metric("最大負", f"{df_p['スコア'].min():+,}")
                    
                    df_p["日付"] = pd.to_datetime(df_p["日付"], errors='coerce')
                    df_p = df_p.sort_values("日付")
                    df_p["累積"] = df_p["スコア"].cumsum()
                    st.line_chart(df_p.set_index("日付")["累積"])

        # メインランキング
        df_l = df_scores[df_scores["リーグ"] == target_league].copy()
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
                
                for i, row in rank_df.iterrows():
                    v = int(row['スコア'])
                    c = "#58a6ff" if v >= 0 else "#f85149"
                    
                    # コンパクトな1行レイアウト
                    with st.container():
                        st.markdown('<div class="compact-row">', unsafe_allow_html=True)
                        c_r, c_n, c_v = st.columns([0.4, 3, 1.5])
                        c_r.markdown(f'<div style="color:#8b949e; padding-top:4px;">#{i+1}</div>', unsafe_allow_html=True)
                        if c_n.button(row['名前'], key=f"user_{row['名前']}"):
                            st.session_state.detail_p = row['名前']
                            st.rerun()
                        c_v.markdown(f'<div style="text-align:right; color:{c}; font-weight:bold; padding-top:4px;">{v:+,}</div>', unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)

                total = int(df_f["スコア"].sum())
                t_c = "#e6edf3" if total == 0 else ("#58a6ff" if total > 0 else "#f85149")
                st.markdown(f'<div class="total-sum-area"><p style="margin:0; color:#8b949e; font-size:0.8em;">合計差額</p><h2 style="margin:0; color:{t_c}; font-size:1.4em;">{total:+,}</h2></div>', unsafe_allow_html=True)
            else: st.info(f"{period}のデータはありません")
    else: st.info("リーグを選択してください")

# --- 2. スコア入力 ---
with tab_input:
    entries = []
    if target_league and not df_players.empty:
        l_players = df_players[df_players["リーグ"] == target_league]["名前"].tolist()
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
                    f_score = math.floor(raw_pts / div)
                    st.caption(f"換算: {f_score:,}")
                    entries.append({"名前": p_name, "スコア": f_score, "日付": datetime.now().strftime("%Y-%m-%d %H:%M"), "リーグ": target_league})

            ca, cs = st.columns(2)
            if ca.button("➕ 追加"):
                st.session_state.input_rows += 1
                st.rerun()
            if cs.button("🚀 保存"):
                try:
                    with st.spinner('通信中...'):
                        s_df = pd.concat([df_scores, pd.DataFrame(entries)], ignore_index=True)
                        conn.update(spreadsheet=url, worksheet="scores", data=s_df)
                        st.session_state.input_rows = 1
                        for k in list(st.session_state.keys()):
                            if k.startswith(("p_name_", "raw_pts_", "rate_", "cust_")): del st.session_state[k]
                        st.toast("保存完了！")
                        time.sleep(1)
                        st.rerun()
                except: st.error("通信エラー")

# --- 3. 設定 ---
with tab_setting:
    m1, m2, m3 = st.tabs(["👥 プレイヤー", "🏆 リーグ", "📜 履歴"])
    with m1:
        if not df_leagues.empty:
            reg_l = st.selectbox("リーグ", df_leagues["リーグ名"].tolist(), key="reg_l")
            p_n = st.text_input("プレイヤー名")
            if st.button("登録") and p_n:
                try:
                    conn.update(spreadsheet=url, worksheet="players", data=pd.concat([df_players, pd.DataFrame([{"名前": p_n, "リーグ": reg_l}])], ignore_index=True))
                    st.rerun()
                except: st.error("失敗")
    with m2:
        with st.form("l_form", clear_on_submit=True):
            nl = st.text_input("新リーグ名")
            if st.form_submit_button("作成") and nl:
                try:
                    conn.update(spreadsheet=url, worksheet="leagues", data=pd.concat([df_leagues, pd.DataFrame([{"リーグ名": nl}])], ignore_index=True))
                    st.rerun()
                except: st.error("失敗")
    with m3:
        if not df_scores.empty:
            h_df = df_scores.iloc[::-1].head(20)
            for i, row in h_df.iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([5, 1])
                    c1.write(f"📅 {row.get('日付','-')} | {row.get('リーグ','-')}\n**{row.get('名前','-')}**: {int(row.get('スコア',0)):+,}")
                    if c2.button("🗑️", key=f"d_{i}"):
                        try:
                            conn.update(spreadsheet=url, worksheet="scores", data=df_scores.drop(i))
                            st.rerun()
                        except: st.error("失敗")