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

# --- VIPダッシュボード対応・超圧縮デザインCSS ---
st.markdown("""
    <style>
    .stApp { background: radial-gradient(circle at top, #0f172a 0%, #020617 100%) !important; color: #f8fafc !important; }
    
    .neon-title {
        font-family: 'Arial Black', sans-serif; font-size: 1.8rem; font-weight: 900; text-align: center;
        background: linear-gradient(to bottom, #fff 20%, #f472b6 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        filter: drop-shadow(0 0 10px #f472b6); margin-bottom: 20px;
    }

    /* タブ */
    .stTabs [data-baseweb="tab-list"] { background-color: rgba(15, 23, 42, 0.9); border-radius: 12px; padding: 4px; border: 1px solid rgba(56, 189, 248, 0.2); }
    .stTabs [data-baseweb="tab"] { color: #64748b; font-weight: bold; font-size: 13px; height: 36px; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] { background: #0ea5e9 !important; color: white !important; border-radius: 8px; }

    /* ランキング行：4列レイアウト */
    .rank-card {
        background: rgba(30, 41, 59, 0.4); border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        padding: 6px 10px; margin-bottom: 2px; display: flex; align-items: center; justify-content: space-between;
    }
    
    /* 名前テキスト（ボタン解除） */
    .player-name { color: #e2e8f0; font-weight: 600; font-size: 0.9rem; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }

    /* 詳細ボタン：極小・シアン枠 */
    div.stButton > button[key^="detail_"] {
        background: rgba(14, 165, 233, 0.05) !important; border: 1px solid rgba(14, 165, 233, 0.5) !important;
        color: #38bdf8 !important; font-size: 0.7rem !important; padding: 0px 8px !important;
        height: 22px !important; line-height: 20px !important; border-radius: 4px !important; width: auto !important;
    }
    div.stButton > button[key^="detail_"]:active { background: #38bdf8 !important; color: #fff !important; }

    /* ダッシュボードカード */
    .db-card {
        background: rgba(15, 23, 42, 0.8); border: 1px solid #0ea5e9; border-radius: 15px;
        padding: 15px; margin: 10px 0; box-shadow: 0 0 20px rgba(14, 165, 233, 0.2);
    }
    .stat-val { color: #38bdf8; font-weight: 800; font-size: 1.1rem; }
    .stat-label { color: #94a3b8; font-size: 0.7rem; }

    .rank-num { color: #fbbf24; font-weight: 900; font-size: 0.85rem; min-width: 25px; }
    .score-plus { color: #4ade80; font-weight: 700; font-size: 0.95rem; text-align: right; }
    .score-minus { color: #fb7185; font-weight: 700; font-size: 0.95rem; text-align: right; }
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

with st.sidebar:
    st.markdown("### 🏟️ リーグ設定")
    if not df_leagues.empty:
        t_league = st.sidebar.selectbox("現在のリーグ", df_leagues["リーグ名"].tolist())
    if st.button("🔄 データを同期"):
        st.cache_data.clear(); st.rerun()

tab_rank, tab_input, tab_setting = st.tabs(["🏆 ランキング", "💰 スコア入力", "⚙️ 設定"])

# --- 1. ランキング ---
with tab_rank:
    if not df_scores.empty:
        df_l = df_scores[df_scores["リーグ"] == t_league].copy()
        df_l["スコア"] = pd.to_numeric(df_l["スコア"], errors='coerce').fillna(0)
        df_l["日付"] = pd.to_datetime(df_l["日付"], errors='coerce')

        # --- VIPダッシュボード表示ロジック ---
        if "detail_p" in st.session_state:
            dp = st.session_state.detail_p
            df_p = df_l[df_l["名前"] == dp].sort_values("日付")
            
            with st.container():
                st.markdown(f'<div class="db-card">', unsafe_allow_html=True)
                c_head, c_close = st.columns([5, 1])
                c_head.markdown(f"### 💎 {dp} の分析")
                if c_close.button("✖", key="close_db"):
                    del st.session_state.detail_p; st.rerun()
                
                if not df_p.empty:
                    # 統計計算
                    avg = df_p['スコア'].mean()
                    wr = (df_p['スコア'] > 0).mean() * 100
                    total_g = len(df_p)
                    trend = df_p['スコア'].tail(5).tolist()
                    trend_icons = "".join(["🔥" if x > 0 else "❄️" for x in trend])

                    k1, k2, k3 = st.columns(3)
                    k1.markdown(f'<div class="stat-label">勝率</div><div class="stat-val">{wr:.1f}%</div>', unsafe_allow_html=True)
                    k2.markdown(f'<div class="stat-label">平均pt</div><div class="stat-val">{avg:+.1f}</div>', unsafe_allow_html=True)
                    k3.markdown(f'<div class="stat-label">参加数</div><div class="stat-val">{total_g}回</div>', unsafe_allow_html=True)
                    
                    st.markdown(f'<div style="margin-top:10px;"><span class="stat-label">直近5戦:</span> {trend_icons}</div>', unsafe_allow_html=True)
                    st.line_chart(df_p.set_index("日付")["スコア"].cumsum())
                st.markdown('</div>', unsafe_allow_html=True)

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
                
                # 順位 | 名前 | スコア | 詳細ボタン
                st.markdown(f'<div class="rank-card">', unsafe_allow_html=True)
                c_rank, c_name, c_score, c_btn = st.columns([0.1, 0.45, 0.25, 0.2])
                c_rank.markdown(f'<div class="rank-num">#{i+1}</div>', unsafe_allow_html=True)
                c_name.markdown(f'<div class="player-name">{row["名前"]}</div>', unsafe_allow_html=True)
                c_score.markdown(f'<div class="{style}">{v:+,}</div>', unsafe_allow_html=True)
                with c_btn:
                    if st.button("詳細", key=f"detail_{row['名前']}", use_container_width=True):
                        st.session_state.detail_p = row['名前']; st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
        else: st.info("記録がありません。")

# --- 2. スコア入力（削除機能付） ---
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
        
        if has_zero: st.error("❌ 0点の選手がいます")
        elif total_in != 0: st.warning(f"⚖️ 収支差額: {total_in:+,}")
        else: st.success("✅ 収支一致")

        c_add, c_del, c_save = st.columns([1, 1, 2])
        if c_add.button("➕ 追加"): st.session_state.input_rows += 1; st.rerun()
        if c_del.button("➖ 削除", disabled=st.session_state.input_rows <= 1): st.session_state.input_rows -= 1; st.rerun()
        if c_save.button("🚀 保存", disabled=not can_save, use_container_width=True):
            conn.update(spreadsheet=url, worksheet="scores", data=pd.concat([df_scores, pd.DataFrame(entries)], ignore_index=True))
            st.cache_data.clear(); st.session_state.input_rows = 2; st.toast("Success!"); time.sleep(1); st.rerun()

# --- 3. 設定 ---
with tab_setting:
    m1, m2, m3 = st.tabs(["👤 選手", "🏆 リーグ", "📜 履歴"])
    with m1:
        pn = st.text_input("選手登録")
        if st.button("追加") and pn:
            conn.update(spreadsheet=url, worksheet="players", data=pd.concat([df_players, pd.DataFrame([{"名前": pn, "リーグ": t_league}])], ignore_index=True))
            st.cache_data.clear(); st.rerun()
    with m2:
        nl = st.text_input("リーグ作成")
        if st.button("作成") and nl:
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