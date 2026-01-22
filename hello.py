import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import base64
import math

# --- 設定 ---
url = "https://docs.google.com/spreadsheets/d/1YLXZWQ6XZz04mi0dx9_6WFbm2-yZQGGIXd3yVEh9kTQ/edit?usp=sharing"

st.set_page_config(page_title="Poker League Master", page_icon="♠️", layout="centered")

# --- 視認性を劇的に改善するCSS ---
st.markdown("""
    <style>
    /* 全体の背景と文字色 */
    .stApp { background-color: #0d1117; color: #e6edf3; }
    
    /* 入力欄（Selectbox, NumberInput等）の文字色を強制的に白系にする */
    div[data-baseweb="select"] > div, 
    div[data-baseweb="input"] input,
    .stNumberInput input {
        color: #ffffff !important;
        background-color: #1c2128 !important;
    }
    
    /* 選択されていない時のラベルやプレースホルダーの色 */
    label, .stCaption { color: #8b949e !important; }

    /* タブのデザイン改善 */
    .stTabs [data-baseweb="tab-list"] { background-color: #161b22; border-radius: 10px; padding: 5px; }
    .stTabs [data-baseweb="tab"] { color: #8b949e; font-weight: bold; }
    .stTabs [aria-selected="true"] { color: #58a6ff !important; border-bottom: 2px solid #58a6ff !important; }

    /* ボタンのデザイン */
    .stButton>button { width: 100%; border-radius: 10px; background: linear-gradient(135deg, #238636, #2ea043); color: white; border: none; font-weight: bold; height: 3.5em; }
    
    /* テーブルのデザイン */
    .stTable { background-color: #161b22; color: white; border-radius: 10px; }
    
    /* 合計差額のエリア */
    .total-sum-area {
        background-color: #1c2128;
        padding: 15px;
        border-radius: 15px;
        border: 1px solid #30363d;
        text-align: center;
        margin-top: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(sheet_name):
    try: return conn.read(spreadsheet=url, worksheet=sheet_name, ttl=0)
    except: return pd.DataFrame()

def save_data(df, sheet_name):
    conn.update(spreadsheet=url, worksheet=sheet_name, data=df)

# データ読み込み
df_scores = load_data("scores")
df_players = load_data("players")
df_leagues = load_data("leagues")
df_trash = load_data("trash")

# リーグ選択
st.title("♠️ Poker League Master")
if not df_leagues.empty:
    target_league = st.sidebar.selectbox("🏟️ リーグ切替", df_leagues["リーグ名"].tolist())
else:
    st.sidebar.warning("設定からリーグを作成してください")
    target_league = None

# --- ナビゲーション ---
tab_rank, tab_input, tab_setting = st.tabs(["🏆 Ranking", "💰 Input", "⚙️ Settings"])

# --- 1. Ranking ---
with tab_rank:
    if target_league and not df_scores.empty:
        df_l = df_scores[df_scores["リーグ"] == target_league].copy()
        df_l["日付"] = pd.to_datetime(df_l["日付"])
        
        period = st.radio("期間", ["今日", "週間", "月間"], horizontal=True)
        now = datetime.now()
        if period == "今日": df_filtered = df_l[df_l["日付"].dt.date == now.date()]
        elif period == "週間": df_filtered = df_l[df_l["日付"] >= (now - timedelta(days=now.weekday()))]
        else: df_filtered = df_l[(df_l["日付"].dt.year == now.year) & (df_l["日付"].dt.month == now.month)]
        
        if not df_filtered.empty:
            # スコアを数値化して集計
            df_filtered["スコア"] = pd.to_numeric(df_filtered["スコア"], errors='coerce').fillna(0)
            ranking = df_filtered.groupby("名前")["スコア"].sum().reset_index()
            ranking = ranking.sort_values("スコア", ascending=False).reset_index(drop=True)
            ranking.index += 1
            
            if not df_players.empty:
                ranking = ranking.merge(df_players[["名前", "アイコン"]], on="名前", how="left")
            
            # ランキング表示
            for i, row in ranking.iterrows():
                c1, c2, c3 = st.columns([1, 4, 2])
                with c1:
                    if pd.notna(row.get("アイコン")) and row["アイコン"]:
                        st.image(row["アイコン"], width=45)
                    else: st.write(f"#{i}")
                c2.markdown(f"**{row['名前']}**")
                color = "#58a6ff" if row['スコア'] >= 0 else "#f85149"
                c3.markdown(f"<span style='color:{color}; font-size:1.2em; font-weight:bold;'>{int(row['スコア']):,}</span>", unsafe_allow_html=True)
                st.divider()

            # --- 合計差額の表示 ---
            total_sum = int(df_filtered["スコア"].sum())
            sum_color = "#e6edf3" if total_sum == 0 else ("#58a6ff" if total_sum > 0 else "#f85149")
            st.markdown(f"""
                <div class="total-sum-area">
                    <p style="margin:0; color:#8b949e; font-size:0.9em;">表示中データの合計差額</p>
                    <h2 style="margin:0; color:{sum_color};">{total_sum:+,}</h2>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("集計対象のデータがありません")
    else:
        st.write("データがありません")

# --- 2. Input (複数人同時入力 & 整数化) ---
with tab_input:
    if target_league and not df_players.empty:
        league_players = df_players[df_players["リーグ"] == target_league]["名前"].tolist()
        
        if not league_players:
            st.warning("このリーグに登録されたプレイヤーがいません")
        else:
            if "input_rows" not in st.session_state: st.session_state.input_rows = 1
            
            new_scores_list = []
            for i in range(st.session_state.input_rows):
                with st.container(border=True):
                    st.write(f"Entry #{i+1}")
                    c1, c2, c3 = st.columns([2, 2, 2])
                    p_name = c1.selectbox("Player", league_players, key=f"name_{i}")
                    raw_points = c2.number_input("Points", step=10, key=f"raw_{i}")
                    rate = c3.selectbox("Rate", ["1/1", "1/5", "1/10", "1/30", "Custom"], key=f"rate_{i}")
                    
                    divisor = 1
                    if rate == "1/5": divisor = 5
                    elif rate == "1/10": divisor = 10
                    elif rate == "1/30": divisor = 30
                    elif rate == "Custom":
                        divisor = st.number_input("Divisor", min_value=0.1, value=1.0, key=f"custom_{i}")
                    
                    # 小数点以下を切り捨てて整数にする
                    final_score = math.floor(raw_points / divisor)
                    st.caption(f"スコア換算: {final_score:,}")
                    new_scores_list.append({"名前": p_name, "スコア": final_score, "日付": datetime.now().strftime("%Y-%m-%d %H:%M"), "リーグ": target_league})

            col_add, col_save = st.columns(2)
            if col_add.button("➕ Playerを追加"):
                st.session_state.input_rows += 1
                st.rerun()
            
            if col_save.button("🚀 まとめて保存"):
                new_df = pd.DataFrame(new_scores_list)
                save_data(pd.concat([df_scores, new_df], ignore_index=True), "scores")
                st.success(f"{len(new_scores_list)}名のスコアを保存しました！")
                st.session_state.input_rows = 1
                st.rerun()
    else:
        st.error("Settingsタブでリーグとプレイヤーを登録してください")

# --- 3. Settings ---
with tab_setting:
    m_tab1, m_tab2, m_tab3 = st.tabs(["👥 Players", "🏟️ Leagues", "🗑️ Trash"])
    
    with m_tab1:
        st.subheader("プレイヤー登録 (リーグ別)")
        if not df_leagues.empty:
            reg_league = st.selectbox("登録先リーグ", df_leagues["リーグ名"].tolist())
            new_p_name = st.text_input("名前")
            img_file = st.file_uploader("アイコン画像(JPG/PNG)", type=['jpg', 'png', 'jpeg'])
            
            icon_data = ""
            if img_file:
                encoded = base64.b64encode(img_file.read()).decode()
                icon_data = f"data:image/png;base64,{encoded}"
            
            if st.button("メンバを登録"):
                if new_p_name:
                    new_p = pd.DataFrame({"名前": [new_p_name], "リーグ": [reg_league], "アイコン": [icon_data]})
                    save_data(pd.concat([df_players, new_p], ignore_index=True), "players")
                    st.success("登録完了！")
                    st.rerun()
        else: st.warning("先にリーグを作成してください")

    with m_tab2:
        st.subheader("リーグ作成")
        new_l = st.text_input("新しいリーグ名")
        if st.button("リーグを新設"):
            if new_l:
                save_data(pd.concat([df_leagues, pd.DataFrame({"リーグ名": [new_l]})], ignore_index=True), "leagues")
                st.success("リーグを作成しました")
                st.rerun()