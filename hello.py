import streamlit as st
import pandas as pd
import math
from datetime import datetime
import time

# --- 0. 画面を暗くするためのカスタムCSS ---
st.markdown("""
    <style>
    /* ロード中（st.spinner）が表示されている時に画面を少し暗くする */
    div[data-testid="stStatusWidget"] {
        background-color: rgba(0, 0, 0, 0.5);
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        z-index: 9999;
        display: flex;
        justify-content: center;
        align-items: center;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 1. データ読み込み（仮の関数。既存のものをそのまま使ってください） ---
# ここに load_data() や save_data() の定義があるはずです
def save_data(df, category):
    # 保存処理
    df.to_csv(f"{category}.csv", index=False) # 例

# --- 2. 初期設定（セッション状態） ---
if "input_rows" not in st.session_state:
    st.session_state.input_rows = 1

# --- 3. メイン処理：スコア入力エリア ---
st.header("スコア入力")

# 【修正ポイント】先にリーグがあるかチェックし、なければエラーを出す
if 'df_leagues' not in locals() or df_leagues.empty:
    st.warning("⚠️ 先に設定タブからリーグとプレイヤーを登録してください。")
else:
    # リーグが存在する場合のみ、入力フォームを表示
    entries = []
    for i in range(st.session_state.input_rows):
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            p_name = c1.text_input("名前", key=f"p_name_{i}")
            raw_pts = c2.number_input("ポイント", step=10, key=f"raw_pts_{i}")
            rate = c3.selectbox("レート", ["1/1", "1/5", "1/10", "1/30", "カスタム"], key=f"rate_{i}")
            
            div = 1
            if rate == "1/5": div = 5
            elif rate == "1/10": div = 10
            elif rate == "1/30": div = 30
            elif rate == "カスタム":
                div = st.number_input("割る数", min_value=0.1, value=1.0, key=f"cust_{i}")
            
            final_score = math.floor(raw_pts / div)
            st.caption(f"スコア換算: {final_score:,}")
            
            # リーグのターゲットなどを指定している場合はここに追加
            target_league = st.selectbox("リーグ", df_leagues["リーグ名"].tolist(), key=f"target_{i}")
            
            entries.append({
                "名前": p_name, 
                "スコア": final_score, 
                "日付": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "リーグ": target_league
            })

    col_add, col_save = st.columns(2)

    if col_add.button("➕ プレイヤーを追加"):
        st.session_state.input_rows += 1
        st.rerun()

    # 【修正ポイント】保存ボタンの中に spinner（ぐるぐる）を配置
    if col_save.button("🚀 まとめて保存"):
        if not entries:
            st.error("保存するデータがありません。")
        else:
            with st.spinner('データを保存しています...'):
                # 実際の保存処理（画像にあったロジック）
                new_df = pd.DataFrame(entries)
                save_data(pd.concat([df_scores, new_df], ignore_index=True), "scores")
                
                # 少し待機（ぐるぐるを見せるため。一瞬で終わるなら不要）
                time.sleep(1.5) 
                
                st.success("保存完了しました！リセットします。")
                
                # セッションのリセット処理
                st.session_state.input_rows = 1
                for key in list(st.session_state.keys()):
                    if key.startswith(("p_name_", "raw_pts_", "rate_", "cust_", "target_")):
                        del st.session_state[key]
                
                st.rerun()

# --- 4. 設定エリア ---
st.divider()
tab_input, tab_setting = st.tabs(["入力", "⚙️ 設定"])

with tab_setting:
    m_tab1, m_tab2, m_tab3 = st.tabs(["👥 プレイヤー管理", "🏆 リーグ管理", "🗑️ ごみ箱"])
    # 以降、画像にあったプレイヤー登録などの処理...