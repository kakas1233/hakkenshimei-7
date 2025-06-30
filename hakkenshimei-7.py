import streamlit as st
import pandas as pd
import os
import random
import math
from collections import Counter
from datetime import timedelta, timezone

# タイムゾーン設定（必要なら）
JST = timezone(timedelta(hours=9))

# 履歴保存ディレクトリ
os.makedirs("history", exist_ok=True)

# 乱数生成法定義
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

def run_app():
    st.title("\U0001F3B2 指名アプリ")

    if "class_list" not in st.session_state:
        st.session_state.class_list = ["クラスA", "クラスB", "クラスC"]
    if "auto_save" not in st.session_state:
        st.session_state.auto_save = True
    if "sound_on" not in st.session_state:
        st.session_state.sound_on = False
    if "loading" not in st.session_state:
        st.session_state.loading = False

    with st.sidebar.expander("\U0001F527 設定"):
        st.session_state.sound_on = st.checkbox("\U0001F50A 指名時に音を鳴らす", value=st.session_state.sound_on)
        st.session_state.auto_save = st.checkbox("💾 自動で履歴を保存する", value=st.session_state.auto_save)

    with st.sidebar.expander("⚙️ クラス設定"):
        selected = st.selectbox("\U0001F4DD クラス名を変更または削除", st.session_state.class_list, key="class_edit")
        new_name = st.text_input("✏️ 新しいクラス名", key="rename_input")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("名前変更", key="rename"):
                if new_name and new_name not in st.session_state.class_list:
                    idx = st.session_state.class_list.index(selected)
                    st.session_state.class_list[idx] = new_name
                else:
                    st.warning("名前が空か、既に存在しています。")
        with col2:
            if st.button("削除", key="delete_class"):
                if len(st.session_state.class_list) > 1:
                    st.session_state.class_list.remove(selected)
                else:
                    st.warning("最低1クラスは必要です。")

        new_class = st.text_input("➕ 新しいクラス名を追加", key="add_input")
        if st.button("クラス追加") and new_class and new_class not in st.session_state.class_list:
            st.session_state.class_list.append(new_class)

    tab = st.sidebar.selectbox("\U0001F4DA クラス選択", st.session_state.class_list)

    st.header(f"\U0001F4CB {tab} の設定")

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

    st.write("👥 メンバー:", [f"{i+1} : {name}" for i, name in enumerate(names)])

    if f"{tab}_used" not in st.session_state:
        st.session_state[tab + "_used"] = []

    if st.button("\U0001F4CA 指名する準備を整える！", key=tab + "_gen"):
        st.session_state.loading = True
        with st.spinner("準備中です。少しお待ちください。"):
            method, seed, var, pool = find_best_seed_and_method(k, l, len(names))
            random.shuffle(pool)  # 順番だけランダム化！
            std = math.sqrt(var)
            exp = (k * l) / len(names)
            st.session_state[tab + "_pool"] = pool
            st.session_state[tab + "_used"] = []
            st.session_state[tab + "_method"] = method
            st.session_state[tab + "_seed"] = seed
            st.session_state[tab + "_var"] = var
            st.session_state.loading = False
            st.success(f"✅ 使用した式: {method}（seed={seed}、標準偏差={std:.2f}）")
            st.markdown(
                f"<div style='font-size:20px;color:#1e90ff'>1人あたりの指名回数の範囲: 約 {exp - std:.2f} ～ {exp + std:.2f} 回</div>",
                unsafe_allow_html=True
            )

    st.subheader("🚫 欠席者（指名除外）")
    absent_input = st.text_area("欠席者の名前（改行区切り）※上で入力した名前と同じ表記をしてください", height=80, key=tab + "_absent_input")
    absents = [x.strip() for x in absent_input.split("\n") if x.strip()]
    available = [i for i, name in enumerate(names) if name not in absents]

    # 残り指名可能人数（欠席者除く & 指名済み除く）
    pool = st.session_state.get(tab + "_pool", [])
    used = st.session_state.get(tab + "_used", [])
    remaining_set = {i for i in pool if i in available and i not in used}
    st.markdown(f"🔢 **残り指名可能人数：{len(remaining_set)} 人**")

    st.subheader("\U0001F3AF 指名！")
    if st.button("\U0001F446 指名する", key=tab + "_pick"):
        remaining = [i for i in pool if i not in used and i in available]
        if not remaining:
            st.warning("⚠️ 指名できる人がいません（全員指名済 or 欠席）")
        else:
            sel = remaining[0]  # シャッフル済みなので順に出せばOK
            st.session_state[tab + "_used"].append(sel)
            st.markdown(
                f"<div style='font-size:40px; text-align:center; color:green;'>🎉 {sel + 1}番: {names[sel]} 🎉</div>",
                unsafe_allow_html=True
            )

    used = st.session_state.get(tab + "_used", [])
    df = pd.DataFrame([
        {
            "番号": i + 1,
            "名前": names[i],
            "指名済": i in used,
            "音ON": st.session_state.sound_on,
            "自動保存ON": st.session_state.auto_save,
            "クラス名": tab,
            "k": k,
            "l": l,
            "n": n
        }
        for i in range(len(names))
    ])

    if len(df) > 0:
        st.subheader("\U0001F4CB 指名履歴（指名された順）")
        ordered_df = pd.DataFrame([
            {"番号": i + 1, "名前": names[i]} for i in used
        ])
        st.dataframe(ordered_df)

        if st.session_state.auto_save:
            df.to_csv(f"history/{tab}_最新.csv", index=False)

        st.download_button("⬇️ 履歴ダウンロード(必ずダウンロードしてからサイトを離れてください)", df.to_csv(index=False), file_name=f"{tab}_履歴.csv")

    if tab + "_pool" in st.session_state and st.session_state[tab + "_pool"]:
        st.subheader("📈 年間指名回数の統計")
        counts = Counter(st.session_state[tab + "_pool"])
        count_list = [counts.get(i, 0) for i in range(len(names))]
        show_stats = st.selectbox("表示する統計を選択してください",
                                  ["全員の指名回数を一覧表示", "特定の番号の指名回数を見る"],
                                  key=tab + "_stats_select")

        if show_stats == "全員の指名回数を一覧表示":
            stats_df = pd.DataFrame({
                "番号": range(1, len(names) + 1),
                "名前": names,
                "指名回数": count_list
            })
            st.dataframe(stats_df)
        else:
            num = st.number_input("番号を入力", min_value=1, max_value=len(names), step=1, key=tab + "_stats_num")
            st.write(f"番号 {num} の {names[num-1]} さんは {count_list[num-1]} 回指名される見込みです。")

if __name__ == "__main__":
    run_app()
