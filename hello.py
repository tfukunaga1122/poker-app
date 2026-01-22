import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import math
import time

# --- 設定 ---
url = "https://docs.google.com/spreadsheets/d/1YLXZWQ6XZz04mi0dx9_6WFbm2-yZQGGIXd3yVEh9kTQ/edit?usp=sharing"

st.set_page_config(page_title="Poker League Master", page_icon="♠️", layout="centered")

# --- デザインCSS（行間を狭くし、ロード画面を調整） ---
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
    
    /* ランキングの行間を狭くする設定 */
    .ranking-row { 
        padding: 5px 0px; 
        border-bottom: 1px solid #30363d;
        display: flex;
        align-items: center;
    }
    .total-sum-area { background-color: #1c2128; padding: 15px; border-radius: 15px; border: 2px solid #30363d; text-align: center; margin-top: 20px; }

    /* ロード中（spinner）の設定 */
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
    try:
        data = conn.read(spreadsheet=url, worksheet=sheet_name, ttl=0)
        return data.dropna(how="all") if data is not None else pd.DataFrame()
    except Exception:
        return None

# --- データの読み込みと保持 ---
for sheet in ["scores", "players", "leagues"]:
    new_data = load_data(sheet)
    if new_data is not None or f"cache_{sheet}" not in st.session_state:
        st.session_state[f"cache_{sheet}"] = new_data if new_data is not None else pd.DataFrame()

df_scores = st.session_state.cache_scores
df_players = st.session_state.cache_players
df_leagues = st.session_state.cache_leagues

# 更新ボタン
if st.sidebar.button("🔄 データを最新に更新"):
    st.cache_data.clear()
    st.rerun()

st.title("♠️ Poker League Master")

# リーグ選択の自動化と記憶
target_league = st.session_state.get("selected_league")
if not df_leagues.empty:
    league_list = df_leagues["リーグ名"].tolist()
    if len(league_list) == 1:
        target_league = league_list[0]
        st.sidebar.info(f"🏟️ リーグ: {target_league}")
    else:
        idx = 0
        if target_league in league_list: idx = league_list.index(target_league)
        target_league = st.sidebar.selectbox("🏟️ リーグを選択", league_list, index=idx)
    st.session_state.selected_league = target_league
else:
    st.sidebar.warning("「設定」からリーグを作成してください")
    target_league = None

tab_rank, tab_input, tab_setting = st.tabs(["🏆 ランキング", "💰 スコア入力", "⚙️ 設定"])

# --- 1. ランキング ---
with tab_rank:
    if target_league and not df_scores.empty:
        # 1. リーグで絞り込み
        df_l = df_scores[df_scores["リーグ"] == target_league].copy()
        
        # 2. 【復活】日付による切り替え
        period = st.radio("表示範囲", ["今日", "月間", "全期間"], horizontal=True)
        
        if not df_l.empty:
            # 日付列を安全に変換（エラーは無視）
            df_l["日付"] = pd.to_datetime(df_l["日付"], errors='coerce')
            now = datetime.now()
            
            if period == "今日":
                df_filtered = df_l[df_l["日付"].dt.date == now.date()]
            elif period == "月間":
                df_filtered = df_l[(df_l["日付"].dt.year == now.year) & (df_l["日付"].dt.month == now.month)]
            else:
                df_filtered = df_l
            
            if not df_filtered.empty:
                # スコア計算
                df_filtered["スコア"] = pd.to_numeric(df_filtered["スコア"], errors='coerce').fillna(0)
                ranking = df_filtered.groupby("名前")["スコア"].sum().reset_index()
                ranking = ranking.sort_values("スコア", ascending=False).reset_index(drop=True)
                ranking.index += 1
                
                st.subheader(f"🏆 {target_league} ({period})")
                
                # 【改善】行間を狭くして表示
                for i, row in ranking.iterrows():
                    score_val = int(row['スコア'])
                    color = "#58a6ff" if score_val >= 0 else "#f85149"
                    
                    # HTMLを使って1行をコンパクトに
                    st.markdown(f"""
                        <div class="ranking-row">
                            <div style="flex: 0.5;">#{i}</div>
                            <div style="flex: 3; font-weight: bold;">{row['名前']}</div>
                            <div style="flex: 1.5; text-align: right; color: {color}; font-weight: bold; font-size: 1.1em;">
                                {score_val:+,}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                total_sum = int(df_filtered["スコア"].sum())
                sum_color = "#e6edf3" if total_sum == 0 else ("#58a6ff" if total_sum > 0 else "#f85149")
                st.markdown(f'<div class="total-sum-area"><p style="margin:0; color:#8b949e; font-size:0.85em;">合計差額</p><h2 style="margin:0; color:{sum_color}; font-size:1.5em;">{total_sum:+,}</h2></div>', unsafe_allow_html=True)
            else:
                st.info(f"{period}のデータはまだありません")
        else:
            st.info("スコアデータがありません")
    else:
        st.info("リーグを選択してください")

# --- 2. スコア入力 ---
with tab_input:
    entries = []
    if not target_league:
        st.error("リーグを作成してください")
    elif df_players.empty:
        st.error("プレイヤーを登録してください")
    else:
        league_players = df_players[df_players["リーグ"] == target_league]["名前"].tolist()
        if league_players:
            if "input_rows" not in st.session_state: st.session_state.input_rows = 1
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
                    with st.spinner('保存中...'):
                        save_df = pd.concat([df_scores, pd.DataFrame(entries)], ignore_index=True)
                        conn.update(spreadsheet=url, worksheet="scores", data=save_df)
                        st.session_state.input_rows = 1
                        for key in list(st.session_state.keys()):
                            if key.startswith(("p_name_", "raw_pts_", "rate_", "cust_")): del st.session_state[key]
                        st.toast("保存しました！")
                        time.sleep(1)
                        st.rerun()

# --- 3. 設定 ---
with tab_setting:
    m_tab1, m_tab2, m_tab3 = st.tabs(["👥 プレイヤー管理", "🏆 リーグ管理", "📜 追加履歴"])
    
    with m_tab1:
        st.subheader("プレイヤー一括登録")
        if not df_leagues.empty:
            reg_l = st.selectbox("登録先リーグ", df_leagues["リーグ名"].tolist(), key="p_reg_league")
            if "p_reg_rows" not in st.session_state: st.session_state.p_reg_rows = 1
            new_players_list = []
            for j in range(st.session_state.p_reg_rows):
                with st.container(border=True):
                    p_n = st.text_input(f"プレイヤー名 #{j+1}", key=f"p_reg_name_{j}")
                    new_players_list.append({"名前": p_n, "リーグ": reg_l})
            c_p_add, c_p_save = st.columns(2)
            if c_p_add.button("➕ 登録枠を追加", key="add_reg_slot"):
                st.session_state.p_reg_rows += 1
                st.rerun()
            if c_p_save.button("🚀 まとめて登録", key="save_reg_players"):
                valid_players = [p for p in new_players_list if p["名前"].strip() != ""]
                if valid_players:
                    updated_players = pd.concat([df_players, pd.DataFrame(valid_players)], ignore_index=True)
                    conn.update(spreadsheet=url, worksheet="players", data=updated_players)
                    st.session_state.p_reg_rows = 1
                    for key in list(st.session_state.keys()):
                        if key.startswith("p_reg_name_"): del st.session_state[key]
                    st.toast("登録完了しました")
                    time.sleep(1)
                    st.rerun()

    with m_tab2:
        st.subheader("リーグの新設")
        with st.form("league_form", clear_on_submit=True):
            new_l_name = st.text_input("新しいリーグ名")
            submitted = st.form_submit_button("リーグを作成")
            if submitted and new_l_name:
                updated_leagues = pd.concat([df_leagues, pd.DataFrame({"リーグ名": [new_l_name]})], ignore_index=True)
                conn.update(spreadsheet=url, worksheet="leagues", data=updated_leagues)
                st.toast(f"リーグ「{new_l_name}」を作成しました")
                time.sleep(1)
                st.rerun()

    with m_tab3:
        st.subheader("スコア追加履歴")
        if not df_scores.empty:
            history_df = df_scores.iloc[::-1] 
            for i, row in history_df.iterrows():
                with st.container(border=True):
                    col1, col2 = st.columns([4, 1])
                    p_name_val = row.get('名前', '不明')
                    p_score_val = row.get('スコア', 0)
                    p_date_val = row.get('日付', '-')
                    col1.write(f"📅 {p_date_val} | **{p_name_val}**: {int(p_score_val):+,}")
                    if col2.button("削除", key=f"del_score_{i}"):
                        updated_scores = df_scores.drop(i)
                        conn.update(spreadsheet=url, worksheet="scores", data=updated_scores)
                        st.rerun()
        else:
            st.write("履歴はまだありません。")