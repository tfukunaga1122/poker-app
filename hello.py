import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- 【設定】あなたのスプレッドシートURL ---
url = "https://docs.google.com/spreadsheets/d/1YLXZWQ6XZz04mi0dx9_6WFbm2-yZQGGIXd3yVEh9kTQ/edit?usp=sharing"

# ページのデザイン設定
st.set_page_config(page_title="Poker Score Pro", page_icon="🃏", layout="centered")

# 見た目をオシャレにするための設定（CSS）
# ※ここを unsafe_allow_html=True に修正しました
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; font-weight: bold; background-color: #0e1117; color: white; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { background-color: #f0f2f6; border-radius: 5px 5px 0 0; padding: 10px 20px; }
    .stTabs [aria-selected="true"] { background-color: #0e1117 !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🃏 Poker Score Pro")

# スプレッドシートへの接続
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(sheet_name):
    try:
        return conn.read(spreadsheet=url, worksheet=sheet_name, ttl=0)
    except Exception:
        return pd.DataFrame()

def save_data(df, sheet_name):
    conn.update(spreadsheet=url, worksheet=sheet_name, data=df)

# 各シートからデータを取得
df_scores = load_data("scores")
df_players = load_data("players")
df_trash = load_data("trash")

# --- メイン画面：タブ切り替え ---
tab_input, tab_rank, tab_member, tab_trash = st.tabs([
    "📝 スコア入力", "🏆 ランキング", "👥 メンバ管理", "🗑️ ごみ箱"
])

# --- 1. スコア入力タブ ---
with tab_input:
    st.subheader("今日の戦績を記録")
    if not df_players.empty and "名前" in df_players.columns:
        p_list = df_players["名前"].dropna().tolist()
        with st.container(border=True):
            col1, col2 = st.columns(2)
            with col1:
                selected_name = st.selectbox("プレイヤーを選択", p_list)
            with col2:
                score_val = st.number_input("収支 (±)", step=100, value=0)
            
            if st.button("🚀 スコアを保存する"):
                new_row = pd.DataFrame({
                    "名前": [selected_name],
                    "スコア": [score_val],
                    "日付": [datetime.now().strftime("%Y/%m/%d %H:%M")]
                })
                updated_scores = pd.concat([df_scores, new_row], ignore_index=True)
                save_data(updated_scores, "scores")
                st.success(f"{selected_name}さんのスコアを保存しました！")
                st.balloons()
                st.rerun()
    else:
        st.info("👈 まずは「メンバ管理」タブでプレイヤーを登録してください。")

    st.divider()
    st.subheader("最近の履歴")
    if not df_scores.empty:
        for i, row in df_scores.iloc[::-1].iterrows():
            with st.expander(f"{row['日付']} | {row['名前']} ({row['スコア']})"):
                c1, c2 = st.columns([3, 1])
                c1.write(f"**{row['名前']}** さんのスコア: **{row['スコア']}**")
                if c2.button("🗑️ 削除", key=f"del_{i}"):
                    trash_row = row.to_frame().T
                    trash_row["削除日時"] = datetime.now().strftime("%Y/%m/%d %H:%M")
                    updated_trash = pd.concat([df_trash, trash_row], ignore_index=True)
                    save_data(updated_trash, "trash")
                    new_scores = df_scores.drop(i)
                    save_data(new_scores, "scores")
                    st.warning("ごみ箱へ移動しました。")
                    st.rerun()

# --- 2. ランキングタブ ---
with tab_rank:
    st.subheader("🏆 合計収支ランキング")
    if not df_scores.empty:
        # スコアを数値に変換
        df_scores["スコア"] = pd.to_numeric(df_scores["スコア"], errors='coerce').fillna(0)
        # ※ここを「スコア」に修正しました
        ranking = df_scores.groupby("名前")["スコア"].sum().reset_index()
        ranking = ranking.sort_values("スコア", ascending=False).reset_index(drop=True)
        ranking.index = ranking.index + 1

        def color_score(val):
            color = 'blue' if val >= 0 else 'red'
            return f'color: {color}; font-weight: bold'

        st.table(ranking.style.map(color_score, subset=['スコア']))
    else:
        st.write("データがまだありません。")

# --- 3. メンバ管理タブ ---
with tab_member:
    st.subheader("参加メンバの事前登録")
    new_player = st.text_input("新しいプレイヤーの名前を入力")
    if st.button("👥 メンバを追加"):
        if new_player:
            if df_players.empty or new_player not in df_players["名前"].values:
                add_df = pd.DataFrame({"名前": [new_player]})
                updated_p = pd.concat([df_players, add_df], ignore_index=True)
                save_data(updated_p, "players")
                st.success(f"{new_player} さんを登録しました！")
                st.rerun()
    st.divider()
    st.write("現在の登録メンバ:")
    st.dataframe(df_players, use_container_width=True, hide_index=True)

# --- 4. ごみ箱タブ ---
with tab_trash:
    st.subheader("🗑️ ごみ箱")
    if not df_trash.empty:
        for i, row in df_trash.iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 2, 1])
                col1.write(f"**{row['名前']}** ({row['スコア']})")
                col2.write(f"消去日: {row['削除日時']}")
                if col3.button("🔄 復元", key=f"res_{i}"):
                    restore_row = row.drop("削除日時").to_frame().T
                    updated_scores = pd.concat([df_scores, restore_row], ignore_index=True)
                    save_data(updated_scores, "scores")
                    new_trash = df_trash.drop(i)
                    save_data(new_trash, "trash")
                    st.success("復元しました！")
                    st.rerun()
    else:
        st.write("ごみ箱は空です。")