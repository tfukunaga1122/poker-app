import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import math
import time

# --- 設定 ---
url = "https://docs.google.com/spreadsheets/d/1YLXZWQ6XZz04mi0dx9_6WFbm2-yZQGGIXd3yVEh9kTQ/edit?usp=sharing"

st.set_page_config(page_title="Poker League Master", page_icon="♠️", layout="centered")

# --- デザインCSS（称号を削除し、レイアウトを最適化） ---
st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
    input, select, textarea, div[data-baseweb="select"] {
        color: #ffffff !important;
        background-color: #1c2128 !important;
    }
    .stTabs [data-baseweb="tab-list"] { background-color: #161b22; border-radius: 10px; padding: 5px; }
    .stTabs [data-baseweb="tab"] { color: #8b949e; font-weight: bold; font-size: 14px; }
    
    .compact-row { height: 26px !important; border-bottom: 1px solid #21262d; display: flex; align-items: center; overflow: hidden; }
    div[data-testid="column"] { padding: 0px !important; margin: 0px !important; gap: 0px !important; }
    div[data-testid="stHorizontalBlock"] { gap: 0px !important; }
    
    div.stButton > button[key^="user_"] {
        background: none !important; border: none !important; padding: 0 !important; margin: 0 !important;
        color: #58a6ff !important; height: 26px !important; line-height: 26px !important;
        text-align: left !important; font-weight: bold !important; font-size: 0.95em !important;
    }

    .rank-num { font-size: 0.75em; color: #8b949e; padding-top: 5px; }
    .score-num { font-size: 0.9em; font-weight: bold; text-align: right; padding-top: 5px; }
    .change-up { color: #3fb950; font-size: 0.8em; font-weight: bold; }
    .change-down { color: #f85149; font-size: 0.8em; font-weight: bold; }
    
    .hall-of-fame { background: linear-gradient(135deg, #1c2128, #161b22); padding: 10px; border-radius: 10px; border: 1px solid #d4af37; margin-top: 15px; }
    .zero-check-ok { color: #3fb950; font-weight: bold; font-size: 0.9em; }
    .zero-check-ng { color: #f85149; font-weight: bold; font-size: 0.9em; }
    
    div[data-testid="stStatusWidget"] {
        background-color: rgba(0, 0, 0, 0.75) !important;
        position: fixed !important; top: 0 !important; left: 0 !important;
        width: 100vw !important; height: 100vh !important;
        z-index: 999999 !important; display: flex !important; justify-content: center !important; align-items: center !important;
    }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(sheet_name):
    try:
        data = conn.read(spreadsheet=url, worksheet=sheet_name, ttl=0)
        return data.dropna(how="all") if data is not None else pd.DataFrame()
    except Exception: return None

# --- データ読み込みとキャッシュ保持 ---
for s in ["scores", "players", "leagues"]:
    if f"cache_{s}" not in st.session_state: st.session_state[f"cache_{s}"] = pd.DataFrame()
    d = load_data(s)
    if d is not None: st.session_state[f"cache_{s}"] = d

df_scores, df_players, df_leagues = st.session_state.cache_scores, st.session_state.cache_players, st.session_state.cache_leagues

# リーグ自動選択
t_league = st.session_state.get("selected_league")
if not df_leagues.empty:
    l_list = df_leagues["リーグ名"].tolist()
    if len(l_list) == 1: t_league = l_list[0]
    else:
        idx = l_list.index(t_league) if t_league in l_list else 0
        t_league = st.sidebar.selectbox("🏟️ リーグ", l_list, index=idx)
    st.session_state.selected_league = t_league
else: t_league = None

tab_rank, tab_input, tab_setting = st.tabs(["🏆 ランキング", "💰 入力", "⚙️ 設定"])

# --- 1. ランキング ---
with tab_rank:
    if t_league and not df_scores.empty:
        df_l = df_scores[df_scores["リーグ"] == t_league].copy()
        df_l["スコア"] = pd.to_numeric(df_l["スコア"], errors='coerce').fillna(0)
        df_l["日付"] = pd.to_datetime(df_l["日付"], errors='coerce')
        
        # 分析画面（ユーザー名クリック時）
        if "detail_p" in st.session_state:
            dp = st.session_state.detail_p
            with st.container(border=True):
                c_h, c_c = st.columns([5, 1])
                c_h.write(f"📊 **{dp}** の分析")
                if c_c.button("✖️"): del st.session_state.detail_p; st.rerun()
                df_p = df_l[df_l["名前"] == dp].sort_values("日付")
                if not df_p.empty:
                    s1, s2, s3, s4 = st.columns(4)
                    s1.metric("平均", f"{df_p['スコア'].mean():.0f}")
                    s2.metric("勝率", f"{(df_p['スコア']>0).mean()*100:.0f}%")
                    s3.metric("最高", f"{df_p['スコア'].max():+,}")
                    s4.metric("最低", f"{df_p['スコア'].min():+,}")
                    st.line_chart(df_p.set_index("日付")["スコア"].cumsum())

        # 順位変動の計算
        latest_date = df_l["日付"].max()
        prev_df = df_l[df_l["日付"] < latest_date]
        rank_map = {}
        if not prev_df.empty:
            prev_rank = prev_df.groupby("名前")["スコア"].sum().sort_values(ascending=False).reset_index()
            prev_rank.index += 1
            rank_map = dict(zip(prev_rank["名前"], prev_rank.index))

        period = st.radio("範囲", ["今日", "月間", "全期間"], horizontal=True, label_visibility="collapsed")
        if period == "今日": df_f = df_l[df_l["日付"].dt.date == datetime.now().date()]
        elif period == "月間": df_f = df_l[(df_l["日付"].dt.year == datetime.now().year) & (df_l["日付"].dt.month == datetime.now().month)]
        else: df_f = df_l
        
        if not df_f.empty:
            r_df = df_f.groupby("名前")["スコア"].sum().reset_index().sort_values("スコア", ascending=False).reset_index(drop=True)
            for i, row in r_df.iterrows():
                v = int(row['スコア']); c = "#58a6ff" if v >= 0 else "#f85149"; name = row['名前']
                
                # 順位変動（全期間のみ表示）
                change_html = ""
                if name in rank_map and period == "全期間":
                    diff = rank_map[name] - (i + 1)
                    if diff > 0: change_html = f'<span class="change-up"> ▲{diff}</span>'
                    elif diff < 0: change_html = f'<span class="change-down"> ▼{abs(diff)}</span>'

                st.markdown('<div class="compact-row">', unsafe_allow_html=True)
                c_r, c_n, c_v = st.columns([0.18, 0.57, 0.25])
                c_r.markdown(f'<div class="rank-num">#{i+1}{change_html}</div>', unsafe_allow_html=True)
                if c_n.button(name, key=f"user_{name}"):
                    st.session_state.detail_p = name; st.rerun()
                c_v.markdown(f'<div class="score-num" style="color:{c};">{v:+,}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

            # 殿堂入り
            st.markdown(f'''<div class="hall-of-fame"><div style="font-size:0.7em; color:#d4af37; font-weight:bold; margin-bottom:5px;">🏆 {t_league} 記録</div>
                <div style="display:flex; justify-content:space-around; font-size:0.75em;">
                <div>最高勝利: <b>{int(df_l["スコア"].max()):+,}</b></div>
                <div>最大敗北: <b>{int(df_l["スコア"].min()):+,}</b></div>
                <div>最多参加: <b>{df_l["名前"].value_counts().max()}回</b></div>
                </div></div>''', unsafe_allow_html=True)
    else: st.info("データがありません")

# --- 2. スコア入力 ---
with tab_input:
    entries = [] # 初期化
    if t_league and not df_players.empty:
        l_players = df_players[df_players["リーグ"] == t_league]["名前"].tolist()
        if "input_rows" not in st.session_state: st.session_state.input_rows = 1
        for i in range(st.session_state.input_rows):
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1.5, 1.5])
                p_n = c1.selectbox("選手", l_players, key=f"p_name_{i}")
                raw = c2.number_input("pt", step=10, key=f"raw_pts_{i}")
                rate = c3.selectbox("率", ["1/1", "1/5", "1/10", "1/30", "カスタム"], key=f"rate_{i}")
                div = 5.0 if rate=="1/5" else (10.0 if rate=="1/10" else (30.0 if rate=="1/30" else (st.number_input("÷", 0.1, 1.0, key=f"cust_{i}") if rate=="カスタム" else 1.0)))
                val = math.floor(raw/div)
                st.caption(f"換算: {val:,}")
                entries.append({"名前": p_n, "スコア": val, "日付": datetime.now().strftime("%Y-%m-%d %H:%M"), "リーグ": t_league})
        
        total_in = sum(e["スコア"] for e in entries)
        check_msg = f'<span class="zero-check-ok">合計 $0$ (OK)</span>' if total_in == 0 else f'<span class="zero-check-ng">合計 {total_in:+,} (不一致)</span>'
        st.markdown(f'<div style="text-align:right; margin-bottom:10px;">収支チェック: {check_msg}</div>', unsafe_allow_html=True)

        ca, cs = st.columns(2)
        if ca.button("➕ 追加"): st.session_state.input_rows += 1; st.rerun()
        if cs.button("🚀 保存"):
            try:
                conn.update(spreadsheet=url, worksheet="scores", data=pd.concat([df_scores, pd.DataFrame(entries)], ignore_index=True))
                st.session_state.input_rows = 1
                for k in list(st.session_state.keys()):
                    if k.startswith(("p_name_", "raw_pts_", "rate_", "cust_")): del st.session_state[k]
                st.rerun()
            except: st.error("保存に失敗しました")

# --- 3. 設定 ---
with tab_setting:
    m1, m2, m3 = st.tabs(["👥 選手", "🏆 リーグ", "📜 履歴"])
    with m1:
        if t_league:
            pn = st.text_input("選手名")
            if st.button("登録") and pn:
                conn.update(spreadsheet=url, worksheet="players", data=pd.concat([df_players, pd.DataFrame([{"名前": pn, "リーグ": t_league}])], ignore_index=True)); st.rerun()
    with m2:
        with st.form("lf", clear_on_submit=True):
            nl = st.text_input("新リーグ")
            if st.form_submit_button("作成") and nl:
                conn.update(spreadsheet=url, worksheet="leagues", data=pd.concat([df_leagues, pd.DataFrame({"リーグ名": [nl]})], ignore_index=True)); st.rerun()
    with m3:
        if not df_scores.empty:
            for i, r in df_scores.iloc[::-1].head(10).iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([5, 1])
                    c1.write(f"{r.get('名前')}: {int(r.get('スコア')):+,}")
                    if c2.button("🗑️", key=f"d_{i}"):
                        conn.update(spreadsheet=url, worksheet="scores", data=df_scores.drop(i)); st.rerun()