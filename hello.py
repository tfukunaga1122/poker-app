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

# --- プロ仕様・VIPネオンデザインCSS ---
st.markdown("""
    <style>
    .stApp { background: radial-gradient(circle at top, #0f172a 0%, #020617 100%) !important; color: #f8fafc !important; }
    .neon-title {
        font-family: 'Arial Black', sans-serif; font-size: 1.6rem; font-weight: 900; text-align: center;
        background: linear-gradient(to bottom, #fff 20%, #f472b6 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        filter: drop-shadow(0 0 10px #f472b6); margin-bottom: 20px;
    }
    
    .stTabs [data-baseweb="tab-list"] { background-color: rgba(15, 23, 42, 0.9); border-radius: 10px; padding: 2px; border: 1px solid rgba(56, 189, 248, 0.2); }
    .stTabs [data-baseweb="tab"] { color: #64748b; font-size: 12px; height: 32px; }
    
    .rank-card {
        background: rgba(30, 41, 59, 0.4); border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        padding: 4px 6px; margin-bottom: 2px; display: flex; align-items: center;
    }
    .player-name { color: #e2e8f0; font-weight: 600; font-size: 0.8rem; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }

    div.stButton > button[key^="detail_"] {
        background: rgba(14, 165, 233, 0.1) !important; border: 1px solid rgba(14, 165, 233, 0.5) !important;
        color: #38bdf8 !important; font-size: 0.6rem !important; padding: 0px 4px !important;
        height: 18px !important; min-height: 18px !important; border-radius: 3px !important; width: fit-content !important;
    }

    div.stButton > button[key="god_fix_v2"] {
        background: linear-gradient(135deg, #fbbf24 0%, #b45309 100%) !important;
        color: white !important; font-weight: bold !important; border: none !important;
        box-shadow: 0 0 15px rgba(251, 191, 36, 0.5); border-radius: 10px !important;
    }

    .db-card { background: rgba(15, 23, 42, 0.95); border: 1px solid #0ea5e9; border-radius: 15px; padding: 12px; margin: 10px 0; box-shadow: 0 0 15px rgba(14, 165, 233, 0.3); }
    .score-plus { color: #4ade80; font-weight: 700; font-size: 0.85rem; text-align: right; }
    .score-minus { color: #fb7185; font-weight: 700; font-size: 0.85rem; text-align: right; }
    
    .monitor-panel {
        background: rgba(15, 23, 42, 0.9); border: 1px solid #fbbf24; border-radius: 15px;
        padding: 15px; text-align: center; margin-top: 15px;
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

with st.sidebar:
    st.markdown("### 🏟️ 設定")
    if not df_leagues.empty:
        t_league = st.sidebar.selectbox("リーグ", df_leagues["リーグ名"].tolist())
    if st.button("🔄 同期"): st.cache_data.clear(); st.rerun()

tab_rank, tab_input, tab_setting = st.tabs(["🏆 ランキング", "💰 スコア入力", "⚙️ 設定"])

# --- 1. ランキング ＆ 神の調整 ---
with tab_rank:
    if not df_scores.empty:
        df_l = df_scores[df_scores["リーグ"] == t_league].copy()
        df_l["スコア"] = pd.to_numeric(df_l["スコア"], errors='coerce').fillna(0)
        df_l["日付"] = pd.to_datetime(df_l["日付"], errors='coerce')
        now_jst = get_jst_now()

        # 詳細分析
        if "detail_p" in st.session_state:
            dp = st.session_state.detail_p
            df_p = df_l[df_l["名前"] == dp].sort_values("日付")
            with st.container():
                st.markdown(f'<div class="db-card">', unsafe_allow_html=True)
                ch, cl = st.columns([5, 1])
                ch.markdown(f"#### 💎 {dp} の分析")
                if cl.button("✖", key="close_db"): del st.session_state.detail_p; st.rerun()
                if not df_p.empty:
                    k1, k2, k3 = st.columns(3)
                    k1.markdown(f'<div style="text-align:center;"><div style="font-size:0.6rem; color:#94a3b8;">勝率</div><div style="color:#38bdf8; font-weight:800;">{(df_p["スコア"] > 0).mean()*100:.1f}%</div></div>', unsafe_allow_html=True)
                    k2.markdown(f'<div style="text-align:center;"><div style="font-size:0.6rem; color:#94a3b8;">平均</div><div style="color:#38bdf8; font-weight:800;">{int(df_p["スコア"].mean()):+}</div></div>', unsafe_allow_html=True)
                    k3.markdown(f'<div style="text-align:center;"><div style="font-size:0.6rem; color:#94a3b8;">最高</div><div style="color:#38bdf8; font-weight:800;">+{int(df_p["スコア"].max())}</div></div>', unsafe_allow_html=True)
                    
                    st.markdown('<div style="font-size:0.7rem; color:#94a3b8; margin-top:10px;">累計収支推移</div>', unsafe_allow_html=True)
                    st.line_chart(df_p.set_index("日付")["スコア"].cumsum(), height=150)
                    
                    st.markdown('<div style="font-size:0.7rem; color:#94a3b8; margin-top:5px; margin-bottom:5px;">増減履歴</div>', unsafe_allow_html=True)
                    # 一回ごとの増減額を表示するデータ一覧
                    df_history = df_p[['日付', 'スコア']].copy().sort_values("日付", ascending=False)
                    df_history['日付'] = df_history['日付'].dt.strftime('%m/%d %H:%M')
                    st.dataframe(
                        df_history,
                        column_config={
                            "日付": "日時",
                            "スコア": st.column_config.NumberColumn("増減", format="%+d")
                        },
                        hide_index=True,
                        use_container_width=True,
                        height=150
                    )
                st.markdown('</div>', unsafe_allow_html=True)

        # 期間選択
        period = st.radio("表示期間", ["今日", "昨日", "今月", "前月", "全期間"], index=0, horizontal=True, label_visibility="collapsed")
        
        target_date_obj = now_jst.date()
        if period == "今日": df_f = df_l[df_l["日付"].dt.date == target_date_obj]
        elif period == "昨日": 
            target_date_obj = (now_jst - timedelta(days=1)).date()
            df_f = df_l[df_l["日付"].dt.date == target_date_obj]
        elif period == "今月": df_f = df_l[(df_l["日付"].dt.year == now_jst.year) & (df_l["日付"].dt.month == now_jst.month)]
        elif period == "前月":
            lm = now_jst.replace(day=1) - timedelta(days=1)
            df_f = df_l[(df_l["日付"].dt.year == lm.year) & (df_l["日付"].dt.month == lm.month)]
        else: df_f = df_l
        
        if not df_f.empty:
            rank_df = df_f.groupby("名前")["スコア"].sum().reset_index().sort_values("スコア", ascending=False).reset_index(drop=True)
            for i, row in rank_df.iterrows():
                v = int(row['スコア']); style = "score-plus" if v >= 0 else "score-minus"
                st.markdown(f'<div class="rank-card">', unsafe_allow_html=True)
                c_r, c_n, c_s, c_b = st.columns([0.1, 0.45, 0.3, 0.15])
                c_r.markdown(f'<div style="color:#fbbf24; font-weight:900; font-size:0.8rem;">#{i+1}</div>', unsafe_allow_html=True)
                c_n.markdown(f'<div class="player-name">{row["名前"]}</div>', unsafe_allow_html=True)
                c_s.markdown(f'<div class="{style}">{v:+,}</div>', unsafe_allow_html=True)
                with c_b:
                    if st.button("詳細", key=f"detail_{row['名前']}"): st.session_state.detail_p = row['名前']; st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            
            # --- 神の調整パネル ---
            all_time_diff = int(df_l["スコア"].sum())
            if period in ["今日", "昨日"]:
                st.markdown(f'<div class="monitor-panel">', unsafe_allow_html=True)
                m_color = "#4ade80" if all_time_diff == 0 else "#fb7185"
                st.markdown(f'<span style="color:#94a3b8; font-size:0.7rem;">📊 リーグ累計の収支差額</span><br><h2 style="color:{m_color}; margin:0;">{all_time_diff:+}</h2>', unsafe_allow_html=True)
                
                if all_time_diff != 0:
                    btn_label = f"⚖️ {period}のメンバーで累計を調整"
                    if st.button(btn_label, key="god_fix_v2", use_container_width=True):
                        try:
                            top_p = rank_df.iloc[0]["名前"]
                            last_p = rank_df.iloc[-1]["名前"]
                            adjustment = -all_time_diff
                            # ロジック：余剰(+)なら1位から徴収、不足(-)なら最下位に付与
                            target = top_p if all_time_diff > 0 else last_p
                            save_date = target_date_obj.strftime("%Y-%m-%d") + " 23:59"
                            
                            new_row = pd.DataFrame([{"名前": target, "スコア": adjustment, "リーグ": t_league, "日付": save_date}])
                            conn.update(spreadsheet=url, worksheet="scores", data=pd.concat([df_scores, new_row], ignore_index=True))
                            st.cache_data.clear()
                            st.success("調整完了！再読み込みします...")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"エラーが発生しました: {e}")
                st.markdown('</div>', unsafe_allow_html=True)
        else: st.info(f"{period}の記録はありません。")

# --- 2. スコア入力 ---
with tab_input:
    if not df_players.empty:
        l_players = df_players[df_players["リーグ"] == t_league]["名前"].tolist()
        if "input_rows" not in st.session_state: st.session_state.input_rows = 1
        entries = []
        has_zero = False
        for i in range(st.session_state.input_rows):
            with st.container(border=True):
                c1, c2, c3 = st.columns([1.5, 1, 1])
                p_n = c1.selectbox(f"選手 {i+1}", l_players, key=f"p_name_{i}")
                raw = c2.number_input("pt", step=10, key=f"raw_pts_{i}")
                rate = c3.selectbox("率", ["1/1", "1/5", "1/10", "1/30"], key=f"rate_{i}")
                div = 1.0; div = 5.0 if rate=="1/5" else (10.0 if rate=="1/10" else (30.0 if rate=="1/30" else 1.0))
                val = int(math.trunc(raw / div / 10) * 10)
                if val == 0: has_zero = True
                st.caption(f"換算: {val:+}")
                entries.append({"名前": p_n, "スコア": val, "日付": get_jst_now().strftime("%Y-%m-%d %H:%M"), "リーグ": t_league})
        
        can_save = not has_zero and len(entries) > 0
        c_add, c_del, c_save = st.columns([1, 1, 2])
        if c_add.button("➕ プレイヤー追加"): st.session_state.input_rows += 1; st.rerun()
        if c_del.button("➖ プレイヤー削除", disabled=st.session_state.input_rows <= 1): st.session_state.input_rows -= 1; st.rerun()
        if c_save.button("🚀 自分の記録を保存", disabled=not can_save, use_container_width=True):
            conn.update(spreadsheet=url, worksheet="scores", data=pd.concat([df_scores, pd.DataFrame(entries)], ignore_index=True))
            st.cache_data.clear(); st.session_state.input_rows = 1; st.toast("保存成功！"); time.sleep(1); st.rerun()

# --- 3. 設定 ---
with tab_setting:
    m1, m2, m3 = st.tabs(["👤 登録", "🏆 リーグ", "📜 削除"])
    with m1:
        pn = st.text_input("選手名")
        if st.button("登録") and pn:
            conn.update(spreadsheet=url, worksheet="players", data=pd.concat([df_players, pd.DataFrame([{"名前": pn, "リーグ": t_league}])], ignore_index=True))
            st.cache_data.clear(); st.rerun()
    with m2:
        nl = st.text_input("リーグ名")
        if st.button("作成") and nl:
            conn.update(spreadsheet=url, worksheet="leagues", data=pd.concat([df_leagues, pd.DataFrame({"リーグ名": [nl]})], ignore_index=True))
            st.cache_data.clear(); st.rerun()
    with m3:
        if not df_scores.empty:
            for i, r in df_scores.iloc[::-1].head(10).iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([4, 1])
                    c1.write(f"**{r.get('名前')}** \n{int(r.get('スコア')):+}")
                    if c2.button("🗑️", key=f"d_{i}"):
                        conn.update(spreadsheet=url, worksheet="scores", data=df_scores.drop(i))
                        st.cache_data.clear(); st.rerun()

