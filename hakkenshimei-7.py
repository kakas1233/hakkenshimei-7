import streamlit as st
import pandas as pd
import os
import random
import math
from collections import Counter
from datetime import timedelta, timezone
import io
import base64
import uuid  # 追加

JST = timezone(timedelta(hours=9))
os.makedirs("history", exist_ok=True)

class Xorshift:
    def __init__(self, seed): self.state = seed if seed != 0 else 1
    def next(self):
        x = self.state
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= (x >> 17)
        x ^= (x << 5) & 0xFFFFFFFF
        self.state = x & 0xFFFFFFFF
        return self.state
    def generate(self, count): return [self.next() for _ in range(count)]

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
    m = 2**32
    a = 1664525
    c = 1013904223
    result = []
    x = seed
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

def run_app():
    st.title("🎲 指名アプリ")

    if "class_list" not in st.session_state:
        st.session_state.class_list = ["クラスA"]
    if "sound_on" not in st.session_state:
        st.session_state.sound_on = False

    with st.sidebar.expander("🔧 設定"):
        st.session_state.sound_on = st.checkbox("🔊 指名時に音を鳴らす", value=st.session_state.sound_on)
        uploaded_audio = st.file_uploader("🎵 mp3ファイルをアップロード（任意）", type=["mp3"])
        if uploaded_audio:
            st.session_state["mp3_data"] = uploaded_audio.read()

    with st.sidebar.expander("📝 クラス管理"):
        updated_list = []
        st.markdown("**現在のクラス一覧**")
        for i, cname in enumerate(st.session_state.class_list):
            col1, col2 = st.columns([4, 1])
            with col1:
                new_name = st.text_input(f"{i+1}. クラス名", value=cname, key=f"class_{i}")
                updated_list.append(new_name)
            with col2:
                if st.button("❌", key=f"delete_{i}"):
                    updated_list.pop()
        st.session_state.class_list = updated_list

        st.markdown("---")
        new_class = st.text_input("➕ 新しいクラス名を入力")
        if st.button("追加"):
            if new_class and new_class not in st.session_state.class_list:
                st.session_state.class_list.append(new_class)
                st.success("✅ 新しいクラスが追加されました")

    tab = st.sidebar.selectbox("📚 クラス選択", st.session_state.class_list)
    st.header(f"📋 {tab} の設定")

    uploaded_history = st.file_uploader("📂 履歴CSVをアップロード", type=["csv"], key=tab+"_upload_csv")
    if uploaded_history:
        try:
            df = pd.read_csv(uploaded_history)
            names = df["名前"].tolist()
            used = [i for i, row in df.iterrows() if row["指名済"]]
            k = int(df["k"].iloc[0])
            l = int(df["l"].iloc[0])
            n = int(df["n"].iloc[0])
            st.session_state[tab + "_names"] = names
            st.session_state[tab + "_used"] = used
            st.session_state[tab + "k"] = k
            st.session_state[tab + "l"] = l
            st.session_state[tab + "n"] = n
            st.session_state[tab + "_name_input"] = "\n".join(names)

            method, seed, var, pool = find_best_seed_and_method(k, l, len(names))
            random.shuffle(pool)
            st.session_state[tab + "_pool"] = pool
            st.session_state[tab + "_method"] = method
            st.session_state[tab + "_seed"] = seed
            st.session_state[tab + "_var"] = var

            st.success("📥 履歴CSVから復元しました")
        except Exception as e:
            st.error(f"読み込み失敗: {e}")

    k = st.number_input("年間授業回数", value=st.session_state.get(tab + "k", 30), min_value=1, key=tab + "k")
    l = st.number_input("授業1回あたりの平均指名人数", value=st.session_state.get(tab + "l", 5), min_value=1, key=tab + "l")
    n = st.number_input("クラス人数", value=st.session_state.get(tab + "n", 40), min_value=1, key=tab + "n")

    name_input = st.text_area("名前を改行区切りで入力（足りない分は自動補完）",
                              height=120,
                              key=tab + "_name_input",
                              value=st.session_state.get(tab + "_name_input", ""))
    raw = [x.strip() for x in name_input.split("\n") if x.strip()]
    if len(raw) < n:
        raw += [f"名前{i+1}" for i in range(len(raw), n)]
    elif len(raw) > n:
        raw = raw[:n]
    names = raw
    st.session_state[tab + "_names"] = names

    st.markdown("### 👥 名前一覧")
    st.write([f"{i+1} : {name}" for i, name in enumerate(names)])

    if f"{tab}_used" not in st.session_state:
        st.session_state[tab + "_used"] = []

    if st.button("📊 指名する準備を整える！", key=tab + "_gen"):
        with st.spinner("準備中です。少々お待ちください。"):
            method, seed, var, pool = find_best_seed_and_method(k, l, len(names))
            random.shuffle(pool)
            std = math.sqrt(var)
            exp = (k * l) / len(names)
            st.session_state[tab + "_pool"] = pool
            st.session_state[tab + "_used"] = []
            st.session_state[tab + "_method"] = method
            st.session_state[tab + "_seed"] = seed
            st.session_state[tab + "_var"] = var
            st.success(f"✅ 使用した式: {method}（seed={seed}、標準偏差={std:.2f}）")
            st.markdown(
                f"<div style='font-size:20px;color:#1e90ff'>1人あたりの指名回数の範囲: 約 {exp - std:.2f} ～ {exp + std:.2f} 回</div>",
                unsafe_allow_html=True
            )

    st.subheader("🚫 欠席者（指名除外）")
    absent_input = st.text_area("欠席者の名前（改行区切り）", height=80, key=tab + "_absent_input")
    absents = [x.strip() for x in absent_input.split("\n") if x.strip()]
    available = [i for i, name in enumerate(names) if name not in absents]

    st.subheader("🎯 指名！")
    if st.button("👆 指名する", key=tab + "_pick"):
        pool = st.session_state.get(tab + "_pool", [])
        used = st.session_state.get(tab + "_used", [])
        counts = Counter(pool)
        remaining = [i for i in pool if i in available and used.count(i) < counts[i]]
        if not remaining:
            st.warning("⚠️ 指名できる人がいません")
        else:
            sel = random.choice(remaining)
            st.session_state[tab + "_used"].append(sel)

            if st.session_state.sound_on and st.session_state.get("mp3_data"):
                b64_mp3 = base64.b64encode(st.session_state["mp3_data"]).decode()
                unique_id = uuid.uuid4()  # ランダムIDで毎回違うタグに
                audio_html = f"""
                    <audio autoplay key="{unique_id}">
                        <source src="data:audio/mp3;base64,{b64_mp3}" type="audio/mp3">
                        あなたのブラウザは audio タグに対応していません。
                    </audio>
                """
                st.markdown(audio_html, unsafe_allow_html=True)

            st.markdown(
                f"<div style='font-size:40px; text-align:center; color:green; font-weight:bold;'>🎉 {sel + 1}番: {names[sel]} 🎉</div>",
                unsafe_allow_html=True
            )

    pool = st.session_state.get(tab + "_pool", [])
    used = st.session_state.get(tab + "_used", [])
    counts = Counter(pool)
    absent_indexes = [i for i, name in enumerate(names) if name in absents]
    absent_count_in_pool = sum(counts.get(i, 0) for i in absent_indexes)
    used_count = len(used)
    remaining_count = len(pool) - absent_count_in_pool - used_count
    st.markdown(f"🔢 **残り指名可能人数: {remaining_count} 人**")

    df = pd.DataFrame([
        {
            "番号": i + 1,
            "名前": names[i],
            "指名済": i in used,
            "音ON": st.session_state.sound_on,
            "クラス名": tab,
            "k": k,
            "l": l,
            "n": n
        }
        for i in range(len(names))
    ])

    if len(df) > 0:
        st.subheader("📋 指名履歴（指名された順）")
        ordered_df = pd.DataFrame([
            {"番号": i + 1, "名前": names[i]} for i in used
        ])
        st.dataframe(ordered_df)

        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue().encode("utf-8")

        st.download_button(
            label="⬇️ 履歴ダウンロード",
            data=csv_data,
            file_name=f"{tab}_履歴.csv",
            mime="text/csv"
        )

    if tab + "_pool" in st.session_state and st.session_state[tab + "_pool"]:
        st.subheader("📈 年間指名回数の統計")
        counts = Counter(st.session_state[tab + "_pool"])
        count_list = [counts.get(i, 0) for i in range(len(names))]
        show_stats = st.selectbox("表示する統計を選択してください",
                                  ["全員の指名回数を一覧表示", "特定の番号の指名回数を見る"],
                                  key=tab + "_stat_select")

        if show_stats == "全員の指名回数を一覧表示":
            stat_df = pd.DataFrame({
                "番号": list(range(1, len(names)+1)),
                "名前": names,
                "指名回数": count_list
            })
            st.dataframe(stat_df)
        else:
            target_num = st.number_input("調べたい番号（1から）", min_value=1, max_value=len(names), step=1)
            count = count_list[target_num - 1]
            st.info(f"📌 {target_num}番「{names[target_num - 1]}」の年間指名回数は **{count}回** です")

if __name__ == "__main__":
    run_app()