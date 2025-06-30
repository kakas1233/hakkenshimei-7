import streamlit as st
import random
import pandas as pd
from datetime import datetime, timedelta
import io
import os
import re

# --- 基本設定 ---
JST = datetime.utcnow() + timedelta(hours=9)
os.makedirs("history", exist_ok=True)
st.set_page_config(page_title="乱数指名アプリ", layout="wide")
st.title("🎲 乱数指名アプリ")

# --- 乱数メソッド定義 ---
def xor128(seed, k, l, n):
    x, y, z, w = seed, seed << 13, (seed >> 17) ^ seed, seed ^ 0x12345678
    res, seen = [], set()
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
    res, seen = [], set()
    while len(res) < n:
        seed = (a * seed + c) % m
        i = seed % n
        if i not in seen:
            seen.add(i)
            res.append(i)
    return res

def mid_square(seed, k, l, n):
    res, seen = [], set()
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
    res, seen = [], set()
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

def play_audio_if_needed(mp3_file):
    if mp3_file:
        audio_bytes = mp3_file.read()
        st.audio(audio_bytes, format="audio/mp3")

def parse_names(input_text):
    return [x.strip() for x in re.split(r'[,\s\n　]+', input_text) if x.strip()]

# --- セッションとUI設定 ---
if "クラス一覧" not in st.session_state:
    st.session_state["クラス一覧"] = ["A組", "B組"]

st.sidebar.header("⚙️ 設定")
st.session_state.sound_on = st.sidebar.checkbox("🔊 音を再生する", value=True)
st.session_state.auto_save = st.sidebar.checkbox("💾 履歴を自動保存する", value=True)

with st.sidebar.expander("🏫 クラスを編集する"):
    new_class = st.text_input("➕ クラス追加", "")
    if st.button("追加", key="add_class") and new_class and new_class not in st.session_state["クラス一覧"]:
        st.session_state["クラス一覧"].append(new_class)
    remove_class = st.selectbox("➖ 削除するクラス", st.session_state["クラス一覧"], key="remove_select")
    if st.button("削除", key="remove_class") and remove_class:
        st.session_state["クラス一覧"].remove(remove_class)

tabs = st.session_state["クラス一覧"]
tab_objects = st.tabs(tabs)

# --- クラスごとの処理 ---
for i, tab in enumerate(tabs):
    with tab_objects[i]:
        st.header(f"🎯 {tab} の指名ボード")

        k = st.number_input("年間授業回数", min_value=1, value=30, key=tab + "_k")
        l = st.number_input("1回の平均指名人数", min_value=1, value=5, key=tab + "_l")
        n = st.number_input("クラス人数", min_value=1, value=40, key=tab + "_n")

        names_raw = st.text_area("👥 名前（スペース・カンマ・改行区切り）", key=tab + "_names_input")
        names = parse_names(names_raw)
        if len(names) < n:
            names += [f"名前{i+1}" for i in range(len(names), n)]
        else:
            names = names[:n]

        mp3 = st.file_uploader("📢 MP3ファイル", type="mp3", key=tab + "_mp3")
        absent_input = st.text_area("❌ 欠席者（区切り自由）", key=tab + "_absent")
        absents = parse_names(absent_input)
        available = [i for i, name in enumerate(names) if name not in absents]

        if st.button("準備する", key=tab + "_prep"):
            method, seed, var, order = find_best_seed_and_method(k, l, n)
            st.session_state[tab + "_order"] = order
            st.session_state[tab + "_used"] = []
            st.session_state[tab + "_names"] = names
            st.session_state[tab + "_count"] = [0]*n
            st.success(f"使用: {method} (seed={seed}) 偏差={var:.2f}")

        uploaded = st.file_uploader("📂 履歴CSVを読み込み", type="csv", key=tab + "_csv")
        if uploaded:
            df = pd.read_csv(uploaded)
            if "番号" in df.columns and "名前" in df.columns:
                st.session_state[tab + "_used"] = [int(i)-1 for i in df["番号"]]
                st.session_state[tab + "_names"] = df["名前"].tolist()
                st.success("✅ 履歴を読み込みました！")

        if st.button("🎯 指名！", key=tab + "_pick"):
            if tab + "_order" not in st.session_state:
                st.warning("⚠️ まず『準備する』を押してください。")
            else:
                order = st.session_state[tab + "_order"]
                used = st.session_state.get(tab + "_used", [])
                count = st.session_state.get(tab + "_count", [0]*n)
                remaining = [i for i in order if i not in used and i in available]
                if not remaining:
                    st.error("⛔ 指名できる人がいません。")
                else:
                    choice = random.choice(remaining)
                    st.session_state[tab + "_used"].append(choice)
                    count[choice] += 1
                    st.session_state[tab + "_count"] = count
                    st.markdown(f"<h2 style='text-align:center; color:green;'>🎉 {choice+1}番：{names[choice]} 🎉</h2>", unsafe_allow_html=True)
                    if mp3 and st.session_state.sound_on:
                        play_audio_if_needed(mp3)

        used = st.session_state.get(tab + "_used", [])
        count = st.session_state.get(tab + "_count", [0]*n)
        if used:
            df = pd.DataFrame([(i+1, names[i]) for i in used], columns=["番号", "名前"])
            csv = io.StringIO(); df.to_csv(csv, index=False)
            timestamp = datetime.now(JST).strftime("%Y%m%d_%H%M")
            filename = f"{tab}_履歴_{timestamp}.csv"
            st.download_button("⬇️ 履歴ダウンロード", csv.getvalue(), file_name=filename)

            if st.session_state.auto_save:
                with open(f"history/{tab}_最新.csv", "w", encoding="utf-8") as f:
                    f.write(csv.getvalue())

            st.write("📋 指名済み一覧", df)

            # 回数統計表示
            count_df = pd.DataFrame({
                "番号": list(range(1, n+1)),
                "名前": names,
                "指名回数": count
            })
            st.subheader("📊 指名回数の統計")
            st.dataframe(count_df[count_df["指名回数"] > 0])
            st.bar_chart(count_df.set_index("名前")["指名回数"])

