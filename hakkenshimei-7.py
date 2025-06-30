import streamlit as st
import random
import pandas as pd
from datetime import datetime, timedelta
import io

# タイムゾーン設定（日本時間）
JST = datetime.utcnow() + timedelta(hours=9)

# アプリ設定
st.set_page_config(page_title="乱数指名アプリ", layout="wide")

# アプリタイトル
st.title("🎲 指名アプリ")

# --- 乱数生成メソッド ---
def xor128(seed, k, l, n):
    x, y, z, w = seed, seed << 13, (seed >> 17) ^ seed, seed ^ 0x12345678
    res = []
    seen = set()
    while len(res) < n:
        t = x ^ (x << k) & 0xFFFFFFFF
        x, y, z = y, z, w
        w = (w ^ (w >> l)) ^ (t ^ (t >> l)) & 0xFFFFFFFF
        i = w % n
        if i not in seen:
            seen.add(i)
            res.append(i)
    return res

def lcg(seed, k, l, n):
    a, c, m = 1103515245, 12345, 2**31
    res = []
    seen = set()
    while len(res) < n:
        seed = (a * seed + c) % m
        i = seed % n
        if i not in seen:
            seen.add(i)
            res.append(i)
    return res

def mid_square(seed, k, l, n):
    res = []
    seen = set()
    while len(res) < n:
        seed = (seed * seed) // 10**k % 10**l
        i = seed % n
        if i not in seen:
            seen.add(i)
            res.append(i)
        seed += 1
    return res

def mt(seed, k, l, n):
    random.seed(seed)
    res = []
    seen = set()
    while len(res) < n:
        i = random.randint(0, n - 1)
        if i not in seen:
            seen.add(i)
            res.append(i)
    return res

def find_best_seed_and_method(k, l, n, iterations=20):
    methods = {
        "Xorshift": xor128,
        "LCG": lcg,
        "MidSquare": mid_square,
        "MersenneTwister": mt,
    }
    best_method, best_seed, best_var, best_order = None, None, float("inf"), []

    for method_name, func in methods.items():
        for seed in range(1, iterations + 1):
            order = func(seed, k, l, n)
            diffs = [order[i + 1] - order[i] for i in range(len(order) - 1)]
            variance = pd.Series(diffs).var()
            if variance < best_var:
                best_var = variance
                best_method = method_name
                best_seed = seed
                best_order = order
    return best_method, best_seed, best_var, best_order

# --- 音声再生 ---
def play_audio_if_needed(mp3_file):
    if mp3_file:
        audio_bytes = mp3_file.read()
        st.audio(audio_bytes, format="audio/mp3")

# --- クラス設定と履歴保存 ---
if "クラス一覧" not in st.session_state:
    st.session_state["クラス一覧"] = ["A組", "B組"]

st.sidebar.header("⚙️ 設定")
st.session_state.sound_on = st.sidebar.checkbox("🔊 音を再生する", value=True)
st.session_state.auto_save = st.sidebar.checkbox("💾 履歴を自動保存する", value=True)

# クラス編集
with st.sidebar.expander("🏫 クラスを編集する"):
    new_class = st.text_input("➕ クラス追加", "")
    if st.button("追加", key="add_class") and new_class and new_class not in st.session_state["クラス一覧"]:
        st.session_state["クラス一覧"].append(new_class)
    remove_class = st.selectbox("➖ 削除するクラス", st.session_state["クラス一覧"], key="remove_select")
    if st.button("削除", key="remove_class") and remove_class:
        st.session_state["クラス一覧"].remove(remove_class)

# タブ切り替え
tabs = st.session_state["クラス一覧"]
tab_objects = st.tabs(tabs)

# 保存先
latest_path = "最新指名履歴.csv"

# --- 各クラスごとの処理 ---
def run_app():
    for i, tab in enumerate(tabs):
        with tab_objects[i]:
            st.header(f"🎯 {tab} の指名ボード")

    st.header(f"🎯 {tab} の指名ボード")

    # 名前入力
    if f"{tab}_names" not in st.session_state:
        st.session_state[f"{tab}_names"] = []
    names = st.session_state[f"{tab}_names"]

    num_names = st.number_input("👥 生徒数", min_value=1, max_value=100, value=len(names) or 30, step=1, key=f"{tab}_num")
    default_names = [f"生徒{i+1}" for i in range(num_names)]
    for i in range(num_names):
        name = st.text_input(f"名前 {i+1}", value=names[i] if i < len(names) else default_names[i], key=f"{tab}_name_{i}")
        if i < len(names):
            names[i] = name
        else:
            names.append(name)
    st.session_state[f"{tab}_names"] = names[:num_names]

    absentees = st.multiselect("❌ 欠席者を選んでください", names, key=f"{tab}_absent")

    # 履歴管理
    if f"{tab}_used" not in st.session_state:
        st.session_state[f"{tab}_used"] = []

    if f"{tab}_pool" not in st.session_state:
        method, seed, var, pool = find_best_seed_and_method(3, 10, num_names)
        st.session_state[f"{tab}k"] = 3
        st.session_state[f"{tab}l"] = 10
        st.session_state[f"{tab}n"] = num_names
        st.session_state[f"{tab}_pool"] = pool

    # MP3ファイルアップロード
    mp3_file = st.file_uploader("🎵 MP3ファイル（任意）", type="mp3", key=f"{tab}_mp3")

    # 指名ボタン
    if st.button("📢 指名！"):
        used = st.session_state[f"{tab}_used"]
        pool = st.session_state[f"{tab}_pool"]
        available = [i for i in range(len(names)) if i not in used and names[i] not in absentees and names[i]]
        if not available:
            st.warning("⚠️ 指名できる人がいません")
        else:
            next_index = None
            for i in pool:
                if i in available:
                    next_index = i
                    break
            if next_index is None:
                st.warning("⚠️ すべての生徒を指名済みです。")
            else:
                st.success(f"🎉 指名: {names[next_index]}")
                st.session_state[f"{tab}_used"].append(next_index)
                if st.session_state.sound_on and mp3_file:
                    play_audio_if_needed(mp3_file)

    # 履歴保存（CSV）
    if st.session_state.auto_save and st.session_state.get(f"{tab}_used"):
        df = pd.DataFrame({
            "番号": [i + 1 for i in st.session_state[f"{tab}_used"]],
            "名前": [names[i] for i in st.session_state[f"{tab}_used"]],
            "日時": [datetime.now(JST).strftime("%Y-%m-%d %H:%M")] * len(st.session_state[f"{tab}_used"]),
            "音ON": [st.session_state.sound_on] * len(st.session_state[f"{tab}_used"]),
            "自動保存ON": [st.session_state.auto_save] * len(st.session_state[f"{tab}_used"]),
            "クラス名": [tab] * len(st.session_state[f"{tab}_used"]),
            "k": [st.session_state[f"{tab}k"]] * len(st.session_state[f"{tab}_used"]),
            "l": [st.session_state[f"{tab}l"]] * len(st.session_state[f"{tab}_used"]),
            "n": [st.session_state[f"{tab}n"]] * len(st.session_state[f"{tab}_used"])
        })
        df.to_csv(latest_path, index=False)

    # 履歴ダウンロード
    if st.session_state.get(f"{tab}_used"):
        if st.download_button(
            label="📥 指名履歴をダウンロード",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name=f"{tab}_指名履歴.csv",
            mime="text/csv"
        ):
            st.toast("✅ ダウンロードしました")

    # 履歴手動読み込み
    uploaded = st.file_uploader("📤 指名履歴CSVを読み込み", type=["csv"], key=f"{tab}_upload_csv")
    if uploaded:
        df_new = pd.read_csv(uploaded)
        try:
            if {"番号", "名前"}.issubset(df_new.columns):
                st.session_state[f"{tab}_used"] = [int(x) - 1 for x in df_new["番号"]]
                st.session_state[f"{tab}_names"] = df_new["名前"].tolist()
                st.success("📖 履歴を読み込みました")
            else:
                st.error("❌ 正しい形式のCSVではありません（番号・名前列が必要）")
        except Exception as e:
            st.error(f"エラー: {e}")

if __name__ == "__main__":
    run_app()