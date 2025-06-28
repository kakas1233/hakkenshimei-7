import streamlit as st
import pandas as pd
import random
import io
import os
import math
from collections import Counter
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=+9), 'JST')

def play_audio_if_needed(mp3_file):
    if mp3_file is not None:
        st.audio(mp3_file, format='audio/mp3')

def find_best_seed_and_method(k, l, n):
    total = k * l
    best_var = float('inf')
    best_seed = None
    best_method = ""
    best_pool = []
    for seed in range(1000):
        random.seed(seed)
        pool = []
        while len(pool) < total:
            pool.extend(random.sample(range(n), n))
        pool = pool[:total]
        count = Counter(pool)
        freq = [count[i] for i in range(n)]
        mean = sum(freq) / n
        var = sum((x - mean) ** 2 for x in freq) / n
        if var < best_var:
            best_var = var
            best_seed = seed
            best_method = "random.sample + extend"
            best_pool = pool
    return best_method, best_seed, best_var, best_pool

def run_app():
    st.title("\U0001F3B2 指名アプリ")

    if "class_list" not in st.session_state:
        st.session_state.class_list = ["クラスA", "クラスB", "クラスC"]
    if "auto_save" not in st.session_state:
        st.session_state.auto_save = True
    if "sound_on" not in st.session_state:
        st.session_state.sound_on = False

    with st.sidebar.expander("\U0001F527 設定"):
        st.session_state.sound_on = st.checkbox("\U0001F50A 指名時に音を鳴らす", value=st.session_state.sound_on)
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

    tab = st.sidebar.selectbox("📚 クラス選択", st.session_state.class_list)
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
                st.toast("\U0001F4E5 自動で前回の履歴を読み込みました！")
        except Exception as e:
            st.warning(f"履歴の読み込み中にエラーが発生しました: {e}")

    st.header(f"📋 {tab} の設定")
    k = st.number_input("年間授業回数", value=st.session_state.get(tab + "k", 30), min_value=1, key=tab + "k")
    l = st.number_input("授業1回あたりの平均指名人数", value=st.session_state.get(tab + "l", 5), min_value=1, key=tab + "l")
    n = st.number_input("クラス人数", value=st.session_state.get(tab + "n", 40), min_value=1, key=tab + "n")

    name_input = st.text_area("名前を改行区切りで入力（足りない分は自動補完します）", height=120, key=tab + "names")
    raw = [x.strip() for x in name_input.split("\n") if x.strip()]
    if len(raw) < n:
        raw += [f"名前{i+1}" for i in range(len(raw), n)]
    elif len(raw) > n:
        raw = raw[:n]
    names = raw
    st.write("\U0001F465 メンバー:", [f"{i+1} : {name}" for i, name in enumerate(names)])

    if f"{tab}_used" not in st.session_state:
        st.session_state[tab + "_used"] = []

    if st.button("\U0001F4CA 指名する準備を整える！", key=tab + "gen"):
        with st.spinner("⚙️ 指名する準備を整えています…"):
            method, seed, var, pool = find_best_seed_and_method(k, l, len(names))
            std = math.sqrt(var)
            exp = (k * l) / len(names)
            lb, ub = exp - std, exp + std
            st.session_state[tab + "_pool"] = pool
            st.session_state[tab + "_used"] = []
            st.session_state[tab + "_names"] = names
        st.success(f"✅ 使用した式: {method}（seed={seed}, 指名回数の偏り具合={std:.2f}）")
        st.markdown(
            f"""<div style=\"font-size: 28px; font-weight: bold; text-align: center; color: #2196F3; margin-top: 20px;\">
                1人あたりの指名回数は 約 {lb:.2f} ～ {ub:.2f} 回です。
            </div>""",
            unsafe_allow_html=True
        )

    if st.button("\U0001F501 全リセット", key=tab + "reset"):
        for key in [tab + "_pool", tab + "_used", tab + "_names", tab + "_mp3"]:
            st.session_state.pop(key, None)
        st.experimental_rerun()

    mp3 = st.file_uploader("\U0001F3B5 指名時に再生したいMP3ファイルをアップロード", type="mp3", key=tab + "_mp3_uploader")
    if mp3:
        st.session_state[tab + "_mp3"] = mp3

    available = []

    if (tab + "_pool" in st.session_state) and (tab + "_names" in st.session_state):
        pool = st.session_state[tab + "_pool"]
        used = st.session_state[tab + "_used"]
        names = st.session_state[tab + "_names"]
        pc = Counter(pool)
        uc = Counter(used)

        absent_input = st.text_area("⛔ 欠席者（1回の指名ごとに設定）", height=80, key=tab + "absent")
        absents = [x.strip() for x in absent_input.split("\n") if x.strip()]
        absents_normalized = set(x.strip() for x in absents)
        available = [i for i, name in enumerate(names) if name.strip() not in absents_normalized]

        debug = st.checkbox("\U0001F50D デバッグ表示", key=tab + "_debug", value=False)
        if debug:
            st.write("\U0001F4E6 Pool（各番号の出現回数）:", pc)
            st.write("\U0001F4C9 Used（各番号の指名回数）:", uc)
            st.write("✅ Available（出席している人の番号）:", available)
            st.write("\U0001F9CD 出席者の名前:", [names[i] for i in available])

        if st.button("\U0001F3AF 指名！", key=tab + "pick"):
            rem = []
            for i in available:
                remaining = pc[i] - uc[i]
                rem.extend([i] * remaining)

            if rem:
                sel = random.choice(rem)
                st.session_state[tab + "_used"].append(sel)
                st.markdown(
                    f"<div style='font-size:64px;text-align:center;color:#4CAF50;margin:30px;'>\U0001F389 {sel+1} : {names[sel]} \U0001F389</div>",
                    unsafe_allow_html=True
                )
                if tab + "_mp3" in st.session_state and st.session_state.sound_on:
                    play_audio_if_needed(st.session_state[tab + "_mp3"])
            else:
                st.warning("✅ 出席者の中で指名可能な人がいません。欠席設定や指名回数を確認してください。")

    used = st.session_state[tab + "_used"]
    df = pd.DataFrame([
        (i+1, names[i], st.session_state.sound_on, st.session_state.auto_save, tab, k, l, n)
        for i in used
    ], columns=["番号", "名前", "音ON", "自動保存ON", "クラス名", "k", "l", "n"])

    csv = io.StringIO(); df.to_csv(csv, index=False)
    timestamp = datetime.now(JST).strftime("%Y-%m-%d_%H-%M")
    filename = f"{tab}_{timestamp}_history.csv"
    st.download_button("⬇️ 指名履歴のダウンロード", csv.getvalue(), file_name=filename)

    if st.session_state.auto_save:
        latest_path = f"history/{tab}_最新.csv"
        with open(latest_path, "w", encoding="utf-8") as f:
            f.write(csv.getvalue())

    remaining = 0
    for i in available:
        remaining += max(pc[i] - uc[i], 0)
    st.write(f"📌 残り指名可能人数: {remaining} / {len(pool)}")

    if used:
        st.write("📋 指名済み:")
        st.write(df)

if __name__ == "__main__":
    run_app()
