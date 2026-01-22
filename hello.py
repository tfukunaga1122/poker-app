import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import base64
import math
import time

# --- 設定 ---
url = "https://docs.google.com/spreadsheets/d/1YLXZWQ6XZz04mi0dx9_6WFbm2-yZQGGIXd3yVEh9kTQ/edit?usp=sharing"

st.set_page_config(page_title="Poker League Master", page_icon="♠️", layout="centered")

# --- デザインCSS ---
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
    
    /* ロード中に画面を暗くする設定 */
    div[data-testid="stStatusWidget"] {
        background-color: rgba(0, 0, 0, 0.7) !important;
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        z-index: 999999 !important;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
    }
    div[data-testid="stStatusWidget"] > div {
        background-color: transparent !important;
        border: none !important;
        color: white !important;
        font-size: 1.2em !important;
    }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(sheet_name):
    with st.spinner(f'{sheet_name}を読み込み中...'):
        try: return conn.read(spreadsheet=url, worksheet=sheet_name, ttl=0)
        except: return pd.DataFrame()

def save_data(df, sheet_name):
    with st.spinner('データを保存中...'):
        conn.update(spreadsheet=url, worksheet=sheet_name, data=df)
        time.sleep(1) 

# データ読み込み
df_scores = load_data("scores")
df_players = load_data("players")
df_leagues = load_data("leagues")
df_trash = load_data("trash")

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
            df_l["日付"] = pd.to_datetime(df_l["日付"])
            period = st.radio("表示期間", ["今日", "週間", "月間"], horizontal=True)
            now = datetime.now()
            if period == "今日": df_filtered = df_l[df_l["日付"].dt.date == now.date()]
            elif period == "週間": df_filtered = df_l[df_l["日付"] >= (now - timedelta(days=now.weekday()))]
            else: df_filtered = df_l[(df_l["日付"].dt.year == now.year) & (df_l["日付"].dt.month == now.month)]
            
            if not df_filtered.empty:
                df_filtered["スコア"] = pd.to_numeric(df_filtered["スコア"], errors='coerce').fillna(0)
                ranking = df_filtered.groupby("名前")["スコア"].sum().reset_index()
                ranking = ranking.sort_values("スコア", ascending=False).reset_index(drop=True)
                ranking.index += 1
                if not df_players.empty:
                    ranking = ranking.merge(df_players[["名前", "アイコン"]], on="名前", how="left")
                
                for i, row in ranking.iterrows():
                    c1, c2, c3 = st.columns([1, 4, 2])
                    with c1:
                        if pd.notna(row.get("アイコン")) and row["アイコン"]:
                            st.image(row["アイコン"], width=45)
                        else: st.write(f"#{i}")
                    c2.markdown(f"**{row['名前']}**")
                    color = "#58a6ff" if row['スコア'] >= 0 else "#f85149"
                    # 【修正箇所】row['スコ2'] を row['スコア'] に修正しました
                    c3.markdown(f"<span style='color:{color}; font-size:1.2em; font-weight:bold;'>{int(row['スコア']):+,}</span>", unsafe_allow_html=True)
                    st.divider()

                total_sum = int(df_filtered["スコア"].sum())
                sum_color = "#e6edf3" if total_sum == 0 else ("#58a6ff" if total_sum > 0 else "#f85149")
                st.markdown(f'<div class="total-sum-area"><p style="margin:0; color:#8b949e; font-size:0.9em;">合計差額</p><h2 style="margin:0; color:{sum_color};">{total_sum:+,}</h2></div>', unsafe_allow_html=True)
            else: st.info("データがありません")
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
                save_data(pd.concat([df_scores, pd.DataFrame(entries)], ignore_index=True), "scores")
                st.success("保存完了！")
                st.session_state.input_rows = 1
                for key in list(st.session_state.keys()):
                    if key.startswith(("p_name_", "raw_pts_", "rate_", "cust_")): del st.session_state[key]
                st.rerun()
    else:
        st.info("左メニューからリーグを選択してください")

# --- 3. 設定 ---
with tab_setting:
    m_tab1, m_tab2, m_tab3 = st.tabs(["👥 プレイヤー管理", "🏟️ リーグ管理", "🗑️ ごみ箱"])
    
    with m_tab1:
        st.subheader("プレイヤー一括登録")
        if not df_leagues.empty:
            reg_l = st.selectbox("登録先リーグ", df_leagues["リーグ名"].tolist(), key="p_reg_league")
            if "p_reg_rows" not in st.session_state: st.session_state.p_reg_rows = 1
            new_players_list = []
            for j in range(st.session_state.p_reg_rows):
                with st.container(border=True):
                    st.write(f"新規プレイヤー #{j+1}")
                    c_n, c_i = st.columns([3, 2])
                    p_n = c_n.text_input("名前", key=f"p_reg_name_{j}")
                    p_img = c_i.file_uploader("アイコン", type=['jpg', 'png', 'jpeg'], key=f"p_reg_img_{j}")
                    p_icon_data = ""
                    if p_img:
                        encoded = base64.b64encode(p_img.read()).decode()
                        p_icon_data = f"data:image/png;base64,{encoded}"
                    new_players_list.append({"名前": p_n, "リーグ": reg_l, "アイコン": p_icon_data})
            
            c_p_add, c_p_save = st.columns(2)
            if c_p_add.button("➕ 登録枠を追加", key="add_reg_slot"):
                st.session_state.p_reg_rows += 1
                st.rerun()
            if c_p_save.button("🚀 まとめて登録", key="save_reg_players"):
                valid_players = [p for p in new_players_list if p["名前"].strip() != ""]
                if valid_players:
                    save_data(pd.concat([df_players, pd.DataFrame(valid_players)], ignore_index=True), "players")
                    st.success(f"{len(valid_players)}名のプレイヤーを登録しました")
                    st.session_state.p_reg_rows = 1
                    for key in list(st.session_state.keys()):
                        if key.startswith(("p_reg_name_", "p_reg_img_")): del st.session_state[key]
                    st.rerun()
                else: st.error("登録する名前を入力してください")
        else: st.warning("先に「リーグ管理」からリーグを作成してください")

    with m_tab2:
        st.subheader("リーグの新設")
        new_l_name = st.text_input("新しいリーグ名", key="new_l_name")
        if st.button("リーグを作成"):
            if new_l_name:
                save_data(pd.concat([df_leagues, pd.DataFrame({"リーグ名": [new_l_name]})], ignore_index=True), "leagues")
                st.success(f"リーグ「{new_l_name}」を作成しました")
                if "new_l_name" in st.session_state: del st.session_state["new_l_name"]
                st.rerun()

    with m_tab3:
        st.subheader("削除履歴")
        if not df_trash.empty:
            for i, row in df_trash.iterrows():
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    col1.write(f"{row['名前']} ({int(row['スコア']):+,}) - {row['リーグ']}")
                    if col2.button("復元", key=f"res_trash_{i}"):
                        save_data(pd.concat([df_scores, row.drop("削除日時").to_frame().T], ignore_index=True), "scores")
                        save_data(df_trash.drop(i), "trash")
                        st.rerun()
        else: st.write("ごみ箱は空です")