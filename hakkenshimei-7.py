import streamlit as st
import pandas as pd
import os
import random
from collections import Counter
from datetime import timedelta, timezone

# タイムゾーン設定
JST = timezone(timedelta(hours=9))

os.makedirs("history", exist_ok=True)

# 乱数生成法（簡易版）
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
    st.title("🎲 指名アプリ")

    if "class_list" not in st.session_state:
        st.session_state.class_list = ["クラスA", "クラスB", "クラスC"]
    if "auto_save" not in st.session_state:
        st.session_state.auto_save = True
    if "sound_on" not in st.session_state:
        st.session_state.sound_on = False
    if "loading" not in st.session_state:
        st.session_state.loading = False

    with st.sidebar.expander("🔧 設定"):
        st.session_state.sound_on = st.checkbox("🔊 指名時に音を鳴らす", value=st.session_state.sound_on)
        st.session_state.auto_save = st.checkbox("💾 自動で履歴を保存する", value=st.session_state.auto_save)
        uploaded_audio = st.file_uploader("🎵 mp3ファイルをアップロード（任意）", type=["mp3"])
        if uploaded_audio:
            st.session_state["mp3_data"] = uploaded_audio.read()

    with st.sidebar.expander("⚙️ クラス設定"):
        selected = st.selectbox("📝 クラス名を変更または削除", st.session_state.class_list, key="class_edit")
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

    tab = st.sidebar.selectbox("📚 クラス選択", st.session_state.class_list)

    st.header(f"📋 {tab} の設定")

    k = st.number_input("年間授業回数", value=st.session_state.get(tab + "k", 30), min_value=1, key=tab + "k")
    l = st.number_input("授業1回あたりの平均指名人数", value=st.session_state.get(tab + "l", 5), min_value=1, key=tab + "l")
    n = st.number_input("クラス人数", value=st.session_state.get(tab + "n", 40), min_value=1, key=tab + "n")

    # 名前一覧は必ず表示されるように修正
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

    if f"{tab}_absent_input" not in st.session_state:
        st.session_state[tab + "_absent_input"] = ""

    # 欠席者入力欄
    absent_input = st.text_area("欠席者（名前を改行区切りで入力）", key=tab + "_absent_input",
                               value=st.session_state.get(tab + "_absent_input", ""))

    absents = [x.strip() for x in absent_input.split("\n") if x.strip()]

    # 利用可能なメンバーインデックスを計算（欠席者除く）
    available = [i for i, name in enumerate(names) if name not in absents and i not in st.session_state.get(tab + "_used", [])]
    st.session_state[tab + "_available"] = available

    st.write(f"✅ 指名可能人数: {len(available)}")

    # 履歴CSVからの復元機能（手動アップロード）
    with st.sidebar.expander("📤 履歴CSVから復元"):
        uploaded_history = st.file_uploader("📄 履歴CSVをアップロード", type=["csv"], key=tab + "_upload")
        if uploaded_history:
            try:
                df = pd.read_csv(uploaded_history)
                # 名前一覧を復元
                names = df["名前"].tolist()
                st.session_state[tab + "_names"] = names
                st.session_state[tab + "_name_input"] = "\n".join(names)
                # k, l, n を復元
                st.session_state[tab + "k"] = int(df["k"].iloc[0])
                st.session_state[tab + "l"] = int(df["l"].iloc[0])
                st.session_state[tab + "n"] = int(df["n"].iloc[0])
                # used（指名済みインデックス）を復元
                used = df.index[df["指名済"] == True].tolist()
                st.session_state[tab + "_used"] = used
                # 欠席者欄はそのまま
                absents_restore = [x.strip() for x in st.session_state.get(tab + "_absent_input", "").split("\n") if x.strip()]
                # availableも再計算（欠席者とused除外）
                available = [i for i, name in enumerate(names) if name not in absents_restore and i not in used]
                st.session_state[tab + "_available"] = available
                st.success("✅ 履歴CSVから復元しました！")
            except Exception as e:
                st.error(f"❌ 履歴の読み込みに失敗しました: {e}")

    # 指名準備ボタン
    if st.button("📊 指名する準備を整える！", key=tab + "_gen"):
        st.session_state.loading = True
        st.session_state[tab + "k"] = k
        st.session_state[tab + "l"] = l
        st.session_state[tab + "n"] = n

        # 指名用乱数生成
        method, seed, variance, mod_list = find_best_seed_and_method(k, l, n)
        st.session_state[tab + "_method"] = method
        st.session_state[tab + "_seed"] = seed
        st.session_state[tab + "_variance"] = variance
        st.session_state[tab + "_mod_list"] = mod_list

        # usedとavailableの初期化（usedは初期化しない、すでにある場合は残す）
        if tab + "_used" not in st.session_state:
            st.session_state[tab + "_used"] = []
        st.session_state[tab + "_available"] = [i for i in range(n) if i not in st.session_state[tab + "_used"] and names[i] not in absents]

        st.success("準備完了！指名可能です。")

    # 指名ボタン
    if st.button("🎯 指名する！", key=tab + "_draw"):
        if not st.session_state.get(tab + "_available"):
            st.warning("⚠️ 指名可能な人がいません。")
        else:
            idx = random.choice(st.session_state[tab + "_available"])
            st.session_state[tab + "_used"].append(idx)
            st.session_state[tab + "_available"].remove(idx)
            st.success(f"🎉 指名されたのは {names[idx]} さん！")

            # 音鳴らすなら再生（ここはmp3アップロード対応用の簡易表示）
            if st.session_state.sound_on and "mp3_data" in st.session_state:
                st.audio(st.session_state["mp3_data"])

            # 自動保存履歴
            if st.session_state.auto_save:
                # 履歴CSVを保存
                rows = []
                for i, name in enumerate(names):
                    rows.append({
                        "名前": name,
                        "指名済": i in st.session_state[tab + "_used"],
                        "k": k,
                        "l": l,
                        "n": n
                    })
                df_save = pd.DataFrame(rows)
                save_path = f"history/{tab}_history.csv"
                df_save.to_csv(save_path, index=False)

    # 指名履歴表示
    st.subheader("📜 指名履歴")
    if tab + "_used" in st.session_state and st.session_state[tab + "_used"]:
        for i, idx in enumerate(st.session_state[tab + "_used"]):
            st.write(f"{i+1}. {names[idx]}")
    else:
        st.write("まだ指名履歴はありません。")

if __name__ == "__main__":
    run_app()