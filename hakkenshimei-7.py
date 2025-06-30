import streamlit as st
from collections import Counter
import random
import math
import io
import pandas as pd
from datetime import datetime, timedelta, timezone
import os
import base64

JST = timezone(timedelta(hours=9))
os.makedirs("history", exist_ok=True)

# --- 乱数生成クラスと関数 ---
class Xorshift:
    def __init__(self, seed):
        self.state = seed if seed != 0 else 1
    def next(self):
        x = self.state
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= (x >> 17)
        x ^= (x << 5) & 0xFFFFFFFF
        self.state = x & 0xFFFFFFFF
        return self.state
    def generate(self, count):
        return [self.next() for _ in range(count)]

def mersenne_twister(seed, count):
    random.seed(seed)
    return [random.randint(0, 100000) for _ in range(count)]

def middle_square(seed, count):
    n_digits = len(str(seed))
    value = seed
    result = []
    for _ in range(count):
        squared = value ** 2
        squared_str = str(squared).zfill(2 * n_digits)
        start = (len(squared_str) - n_digits) // 2
        middle_digits = int(squared_str[start:start + n_digits])
        result.append(middle_digits)
        value = middle_digits if middle_digits != 0 else seed + 1
    return result

def lcg(seed, count):
    m = 2**32; a = 1664525; c = 1013904223
    result = []; x = seed
    for _ in range(count):
        x = (a * x + c) % m
        result.append(x)
    return result

def calculate_variance(numbers, n):
    mod = [x % n for x in numbers]
    counts = Counter(mod)
    all_counts = [counts.get(i, 0) for i in range(n)]
    expected = len(numbers) / n
    variance = sum((c - expected) ** 2 for c in all_counts) / n
    return variance, mod

@st.cache_data(show_spinner=False)
def find_best_seed_and_method(k, l, n):
    seed_range = range(0, 1000001, 100)
    count = k * l
    best = (float('inf'), None, None, None)
    for method in ["Xorshift", "Mersenne Twister", "Middle Square", "LCG"]:
        for seed in seed_range:
            nums = {
                "Xorshift": Xorshift(seed).generate(count),
                "Mersenne Twister": mersenne_twister(seed, count),
                "Middle Square": middle_square(seed, count),
                "LCG": lcg(seed, count)
            }[method]
            var, modded = calculate_variance(nums, n)
            if var < best[0]:
                best = (var, method, seed, modded)
    return best[1], best[2], best[0], best[3]

def play_audio_if_needed(mp3_file):
    if mp3_file:
        audio_bytes = mp3_file.read()
        b64 = base64.b64encode(audio_bytes).decode()
        audio_html = f"""
            <audio autoplay>
                <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
        """
        st.markdown(audio_html, unsafe_allow_html=True)
def run_app():
    st.title("🎲 指名アプリ（完全版）")

    if "class_list" not in st.session_state:
        st.session_state.class_list = ["クラスA", "クラスB", "クラスC"]
    if "auto_save" not in st.session_state:
        st.session_state.auto_save = True
    if "sound_on" not in st.session_state:
        st.session_state.sound_on = False

    # --- サイドバー設定 ---
    with st.sidebar.expander("🔧 設定"):
        st.session_state.sound_on = st.checkbox("🔊 指名時に音を鳴らす", value=st.session_state.sound_on)
        st.session_state.auto_save = st.checkbox("💾 自動で履歴を保存する", value=st.session_state.auto_save)

    with st.sidebar.expander("⚙️ クラス設定"):
        selected = st.selectbox("📝 クラス名を変更または削除", st.session_state.class_list, key="class_edit")
        new_name = st.text_input("✏️ 新しいクラス名", key="rename_input")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("名前変更", key="rename"):
                idx = st.session_state.class_list.index(selected)
                st.session_state.class_list[idx] = new_name
        with col2:
            if st.button("削除", key="delete_class"):
                st.session_state.class_list.remove(selected)

        new_class = st.text_input("➕ 新しいクラス名を追加", key="add_input")
        if st.button("クラス追加") and new_class and new_class not in st.session_state.class_list:
            st.session_state.class_list.append(new_class)

    # クラス選択
    tab = st.sidebar.selectbox("📚 クラス選択", st.session_state.class_list)

    # --- 履歴手動アップロード ---
    st.sidebar.markdown("### 📂 履歴CSVを手動読み込み")
    uploaded_history = st.sidebar.file_uploader("CSVファイルをアップロード", type="csv")
    if uploaded_history:
        try:
            df = pd.read_csv(uploaded_history)
            st.session_state[tab + "_used"] = [int(row["番号"]) - 1 for _, row in df.iterrows()]
            st.session_state[tab + "_names"] = df["名前"].tolist()
            st.session_state.sound_on = bool(df["音ON"].iloc[0])
            st.session_state.auto_save = bool(df["自動保存ON"].iloc[0])
            st.session_state[tab + "k"] = int(df["k"].iloc[0])
            st.session_state[tab + "l"] = int(df["l"].iloc[0])
            st.session_state[tab + "n"] = int(df["n"].iloc[0])
            method, seed, var, pool = find_best_seed_and_method(
                st.session_state[tab + "k"],
                st.session_state[tab + "l"],
                st.session_state[tab + "n"]
            )
            st.session_state[tab + "_pool"] = pool
            st.success("✅ 履歴を手動で読み込みました！")
        except Exception as e:
            st.warning(f"CSV読み込みエラー: {e}")

    # --- 自動履歴読み込み ---
    latest_path = f"history/{tab}_最新.csv"
    if os.path.exists(latest_path):
        try:
            df = pd.read_csv(latest_path)
            required_cols = {"番号", "名前", "音ON", "自動保存ON", "クラス名", "k", "l", "n"}
            if required_cols.issubset(df.columns):
                st.session_state[tab + "_used"] = [int(row["番号"]) - 1 for _, row in df.iterrows()]
                st.session_state[tab + "_names"] = df["名前"].tolist()
                st.session_state.sound_on = bool(df["音ON"].iloc[0])
                st.session_state.auto_save = bool(df["自動保存ON"].iloc[0])
                st.session_state[tab + "k"] = int(df["k"].iloc[0])
                st.session_state[tab + "l"] = int(df["l"].iloc[0])
                st.session_state[tab + "n"] = int(df["n"].iloc[0])
                method, seed, var, pool = find_best_seed_and_method(
                    st.session_state[tab + "k"],
                    st.session_state[tab + "l"],
                    st.session_state[tab + "n"]
                )
                st.session_state[tab + "_pool"] = pool
                st.toast("📥 自動で前回の履歴を読み込みました！")
        except Exception as e:
            st.warning(f"履歴の読み込み中にエラーが発生しました: {e}")

    # --- パラメータ入力 ---
    st.header(f"📋 {tab} の設定")
    k = st.number_input("年間授業回数", value=st.session_state.get(tab + "k", 30), min_value=1, key=tab + "k")
    l = st.number_input("授業1回あたりの平均指名人数", value=st.session_state.get(tab + "l", 5), min_value=1, key=tab + "l")
    n = st.number_input("クラス人数", value=st.session_state.get(tab + "n", 40), min_value=1, key=tab + "n")

    # 名前入力
    name_input = st.text_area("名前を改行区切りで入力（足りない分は自動補完します）", height=120, key=tab + "names_input")
    raw = [x.strip() for x in name_input.split("\n") if x.strip()]
    if len(raw) < n:
        raw += [f"名前{i+1}" for i in range(len(raw), n)]
    elif len(raw) > n:
        raw = raw[:n]
    names = [x.strip() for x in raw]

    st.session_state[tab + "_names"] = names
    st.write("👥 メンバー:", [f"{i+1} : {name}" for i, name in enumerate(names)])

    # プール生成
    if st.button("📊 指名する準備を整える！", key=tab + "gen"):
        with st.spinner("⚙️ 指名する準備を整えています…"):
            method, seed, var, pool = find_best_seed_and_method(k, l, len(names))
            std = math.sqrt(var)
            exp = (k * l) / len(names)
            lb, ub = exp - std, exp + std
            st.session_state[tab + "_pool"] = pool
            st.session_state[tab + "_used"] = []
        st.success(f"✅ 使用した式: {method}（seed={seed}, 偏り={std:.2f}）")
        st.markdown(
            f"<div style='font-size: 24px; text-align: center; color: #2196F3;'>1人あたりの指名回数は 約 {lb:.2f} ～ {ub:.2f} 回です。</div>",
            unsafe_allow_html=True
        )

    if st.button("🔄 全リセット", key=tab + "reset"):
        for key in [tab + "_pool", tab + "_used", tab + "_names", tab + "_mp3"]:
            st.session_state.pop(key, None)
        st.experimental_rerun()
    # --- 欠席者入力 ---
    st.subheader("🚫 欠席者を入力（指名から除外）")
    absent_input = st.text_area("欠席者の名前（複数可、改行区切り）", height=100, key=tab + "_absent_input")
    absents = [x.strip() for x in absent_input.split("\n") if x.strip()]
    
    # --- 指名処理 ---
    st.subheader("🎯 指名！")
    if st.button("👆 指名する", key=tab + "nominate"):
        pool = st.session_state.get(tab + "_pool", [])
        used = st.session_state.get(tab + "_used", [])
        names = st.session_state.get(tab + "_names", [])

        if not pool or len(pool) == 0:
            st.error("⚠️ 指名用プールが未生成です。「準備を整える」ボタンを先に押してください。")
        else:
            remaining = [i for i in range(len(pool)) if i not in used and names[i] not in absents]
            if not remaining:
                st.warning("💡 指名できる人がいません（全員指名済 or 欠席）")
            else:
                selected_index = random.choice(remaining)
                selected_name = names[selected_index]
                st.session_state[tab + "_used"].append(selected_index)

                st.success(f"🎉 今日の指名は…『{selected_name}』さん！")

                # --- mp3再生処理 ---
                if st.session_state.sound_on and selected_index < len(mp3_files):
                    audio_file = mp3_files[selected_index]
                    if os.path.exists(audio_file):
                        audio_bytes = open(audio_file, 'rb').read()
                        st.audio(audio_bytes, format='audio/mp3')

    # --- 履歴表示 ---
    st.subheader("📜 指名履歴")
    used = st.session_state.get(tab + "_used", [])
    names = st.session_state.get(tab + "_names", [])
    history = []
    for i, idx in enumerate(used):
        if idx < len(names):
            history.append({"回数": i+1, "番号": idx + 1, "名前": names[idx]})
    df = pd.DataFrame(history)
    st.dataframe(df)

    # --- 履歴CSV保存 ---
    if st.session_state.auto_save and len(df) > 0:
        df["クラス名"] = tab
        df["音ON"] = st.session_state.sound_on
        df["自動保存ON"] = st.session_state.auto_save
        df["k"] = st.session_state[tab + "k"]
        df["l"] = st.session_state[tab + "l"]
        df["n"] = st.session_state[tab + "n"]
        os.makedirs("history", exist_ok=True)
        df.to_csv(f"history/{tab}_最新.csv", index=False)

    # --- 履歴CSVダウンロード ---
    if len(df) > 0:
        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 履歴CSVをダウンロード",
            data=csv,
            file_name=f"{tab}_履歴.csv",
            mime="text/csv"
        )