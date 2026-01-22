import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import math
import time

# --- 設定 ---
url = "https://docs.google.com/spreadsheets/d/1YLXZWQ6XZz04mi0dx9_6WFbm2-yZQGGIXd3yVEh9kTQ/edit?usp=sharing"

st.set_page_config(page_title="Poker League Master", page_icon="♠️", layout="centered")

# --- デザインCSS（行間を極限まで狭くする設定） ---
st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
    input, select, textarea, div[data-baseweb="select"] {
        color: #ffffff !important;
        background-color: #1c2128 !important;
    }
    .stTabs [data-baseweb="tab-list"] { background-color: #161b22; border-radius: 10px; padding: 5px; }
    .stTabs [data-baseweb="tab"] { color: #8b949e; font-weight: bold; font-size: 14px; }
    
    /* 共通：行をコンパクトにする設定 */
    .compact-row { 
        padding: 5px 0px; 
        border-bottom: 1px solid #30363d;
        display: flex;
        align-items: center;
        font-size: 0.9em;
    }
    .total-sum-area { background-color: #1c2128; padding: 12px; border-radius: 12px; border: 2px solid #30363d; text-align: center; margin-top: 15px; }

    /* ロード中（spinner）を画面中央に固定 */
    div[data-testid="stStatusWidget"] {
        background-color: rgba(0, 0, 0, 0.75) !important;
        position: fixed !important;
        top: 0 !important; left: 0 !important;
        width: 100vw !important; height: 100vh !important;
        z-index: 999999 !important;
        display: flex !important; justify-content: center !important; align-items: center !important;
    }

    /* 履歴用の微調整 */
    .history-meta { font-size: 0.75em; color: #8b949e; margin-bottom: -2px; }
    .history-main { font-weight: bold; }
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

st.title("♠️ Poker League Master")

# --- リーグ選択の自動化 ---
target_league = st.session_state.get("selected_league")
if not df_leagues.empty:
    league_list = df_leagues["リーグ名"].tolist()
    if len(league_list) == 1:
        target_league = league_list[0]
        st.sidebar.info(f"🏟️ リーグ: {target_league}")
    else:
        idx = league_list.index(target_league) if target_league in league_list else 0
        target_league = st.sidebar.selectbox("🏟️ リーグを選択", league_list, index=idx)
    st.session_state.selected_league = target_league
else:
    st.sidebar.warning("「設定」からリーグを作成してください")
    target_league = None

tab_rank, tab_input, tab_setting = st.tabs(["🏆 ランキング", "💰 スコア入力", "⚙️ 設定"])

# --- 1. ランキング（コンパクト表示） ---
with tab_rank:
    if target_league and not df_scores.empty:
        df_l = df_scores[df_scores["リーグ"] == target_league].copy()
        period = st.radio("表示範囲", ["今日", "月間", "全期間"], horizontal=True, label_visibility="collapsed")
        
        if not df_l.empty:
            df_l["日付"] = pd.to_datetime(df_l["日付"], errors='coerce')
            now = datetime.now()
            
            if period == "今日":
                df_f = df_l[df_l["日付"].dt.date == now.date()]
            elif period == "月間":
                df_f = df_l[(df_l["日付"].dt.year == now.year) & (df_l["日付"].dt.month == now.month)]
            else:
                df_f = df_l
            
            if not df_f.empty:
                df_f["スコア"] = pd.to_numeric(df_f["スコア"], errors='coerce').fillna(0)
                ranking = df_f.groupby("名前")["スコア"].sum().reset_index().sort_values("スコア", ascending=False).reset_index(drop=True)
                ranking.index += 1
                
                for i, row in ranking.iterrows():
                    val = int(row['スコア'])
                    color = "#58a6ff" if val >= 0 else "#f85149"
                    st.markdown(f"""
                        <div class="compact-row">
                            <div style="flex: 0.4; color: #8b949e;">#{i}</div>
                            <div style="flex: 3; font-weight: bold;">{row['名前']}</div>
                            <div style="flex: 1.5; text-align: right; color: {color}; font-weight: bold; font-size: 1.1em;">{val:+,}</div>
                        </div>
                        """, unsafe_allow_html=True)

                total = int(df_f["スコア"].sum())
                t_color = "#e6edf3" if total == 0 else ("#58a6ff" if total > 0 else "#f85149")
                st.markdown(f'<div class="total-sum-area"><p style="margin:0; color:#8b949e; font-size:0.8em;">合計差額</p><h2 style="margin:0; color:{t_color}; font-size:1.4em;">{total:+,}</h2></div>', unsafe_allow_html=True)
            else: st.info(f"{period}のデータはありません")
    else: st.info("リーグを選択してください")

# --- 2. スコア入力 ---
with tab_input:
    entries = []
    if target_league and not df_players.empty:
        league_players = df_players[df_players["リーグ"] == target_league]["名前"].tolist()
        if league_players:
            if "input_rows" not in st.session_state: st.session_state.input_rows = 1
            for i in range(st.session_state.input_rows):
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1.5, 1.5])
                    p_name = c1.selectbox("プレイヤー", league_players, key=f"p_name_{i}")
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
                        save_df = pd.concat([df_scores, pd.DataFrame(entries)], ignore_index=True)
                        conn.update(spreadsheet=url, worksheet="scores", data=save_df)
                        st.session_state.input_rows = 1
                        for k in list(st.session_state.keys()):
                            if k.startswith(("p_name_", "raw_pts_", "rate_", "cust_")): del st.session_state[k]
                        st.toast("保存完了！")
                        time.sleep(1)
                        st.rerun()
                except: st.error("通信エラー")

# --- 3. 設定（履歴・削除機能のコンパクト化） ---
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
                except: st.error("通信失敗")
    
    with m2:
        with st.form("l_form", clear_on_submit=True):
            new_l = st.text_input("新リーグ名")
            if st.form_submit_button("作成") and new_l:
                try:
                    conn.update(spreadsheet=url, worksheet="leagues", data=pd.concat([df_leagues, pd.DataFrame([{"リーグ名": new_l}])], ignore_index=True))
                    st.rerun()
                except: st.error("失敗")
    
    with m3:
        if not df_scores.empty:
            st.caption("最新20件を表示（スワイプ/スクロールで確認）")
            # 最新20件を取得
            history_df = df_scores.iloc[::-1].head(20)
            
            for i, row in history_df.iterrows():
                # 履歴もHTMLで極限まで狭める
                p_name = row.get('名前','-')
                p_score = int(row.get('スコア',0))
                p_date = row.get('日付','-')
                p_league = row.get('リーグ','-')
                color = "#58a6ff" if p_score >= 0 else "#f85149"
                
                # 削除ボタンと情報を分けるためのカラム
                c_info, c_btn = st.columns([5, 1])
                
                with c_info:
                    st.markdown(f"""
                        <div style="border-bottom: 1px solid #30363d; padding: 4px 0;">
                            <div class="history-meta">{p_date} | {p_league}</div>
                            <div class="history-main">
                                {p_name}: <span style="color: {color};">{p_score:+,}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                
                with c_btn:
                    # 削除ボタンをコンパクトに（ゴミ箱アイコン）
                    if st.button("🗑️", key=f"d_{i}", help="この記録を削除"):
                        try:
                            with st.spinner('削除中...'):
                                updated_scores = df_scores.drop(i)
                                conn.update(spreadsheet=url, worksheet="scores", data=updated_scores)
                                st.rerun()
                        except: st.error("通信失敗")
        else:
            st.write("履歴はありません")