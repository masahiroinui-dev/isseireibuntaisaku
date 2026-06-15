import streamlit as st
import pandas as pd
from streamlit_drawable_canvas import st_canvas
import easyocr
import numpy as np
from PIL import Image
import random
import difflib
import cv2

# ページ設定（ゲーム風にダークモード、レイアウトはセンター）
st.set_page_config(page_title="ドラゴン・スペリング RPG", layout="centered")

# OCRモデルの読み込み（英語を指定）
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'], gpu=False)

reader = load_ocr()

# エクセルデータの読み込み (Sheet1を指定)
@st.cache_data
def load_data():
    try:
        # Sheet1から読み込み、空欄補充に必要なカラムを取得
        df = pd.read_excel("questions.xlsx", sheet_name="Sheet1")
        df.columns = df.columns.str.strip()
        # sentence, word, meaning が揃っている行を対象にする
        df = df.dropna(subset=["sentence", "word", "meaning"])
        return df
    except Exception as e:
        st.error(f"データロードエラー: {e}")
        return pd.DataFrame(columns=["sentence", "word", "meaning"])

df = load_data()

# --- ゲーム風グラフィックのためのカスタムCSS ---
st.markdown("""
<style>
    /* 全体を黒基調のレトロゲーム風にする */
    .stApp {
        background-color: #111116 !important;
        color: #ffffff !important;
        font-family: 'Courier New', Courier, monospace; /* ドット絵風フォントの代替 */
    }
    
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 0rem !important;
    }

    /* タイトルロゴ風 */
    .game-title {
        text-align: center;
        font-size: 2.2rem;
        font-weight: bold;
        color: #ffb800;
        text-shadow: 3px 3px #000, -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000;
        margin-bottom: 20px;
        letter-spacing: 2px;
    }

    /* RPGのメッセージウィンドウ風ボックス */
    .rpg-box {
        background-color: #000000;
        padding: 20px;
        border: 4px solid #ffffff;
        border-radius: 8px;
        box-shadow: 0 0 0 4px #000000;
        margin-bottom: 20px;
    }
    
    /* 例文（問題）のスタイル */
    .sentence-text {
        margin: 0 0 10px 0;
        color: #00ffcc;
        font-size: 1.6rem;
        font-weight: bold;
        line-height: 1.5;
    }
    
    /* 日本語訳（ヒント）のスタイル */
    .meaning-text {
        margin: 0;
        color: #aaaaaa;
        font-size: 1.1rem;
    }

    /* ボタンをファミコンのコマンド選択風にする */
    div[data-testid="stButton"] > button {
        background-color: #000000 !important;
        color: #ffffff !important;
        border: 3px solid #ffffff !important;
        border-radius: 4px !important;
        font-weight: bold !important;
        font-family: 'Courier New', monospace !important;
        transition: 0.2s;
    }
    
    /* ボタンホバー時 */
    div[data-testid="stButton"] > button:hover {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 3px solid #ffb800 !important;
    }

    /* 特殊なボタン色設定（採点・次へはゴールド枠） */
    div[data-testid="stButton"] > button:contains("採点"),
    div[data-testid="stButton"] > button:contains("次へ") {
        border-color: #ffb800 !important;
        color: #ffb800 !important;
    }
    
    /* サイドバーのゲーム風調整 */
    section[data-testid="stSidebar"] {
        background-color: #1a1a24 !important;
        border-right: 2px solid #333;
    }
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] p {
        color: #ffffff !important;
    }
</style>
""", unsafe_allow_html=True)

# セッション状態の初期化
if 'question_pool' not in st.session_state:
    if not df.empty:
        indices = list(range(len(df)))
        random.shuffle(indices)
        st.session_state.question_pool = indices
        st.session_state.pool_ptr = 0
        st.session_state.q_index = st.session_state.question_pool[0]
        st.session_state.history = []
        st.session_state.canvas_key = 0
    else:
        st.session_state.question_pool = []
        st.session_state.q_index = 0
        st.session_state.canvas_key = 0

if 'answer_status' not in st.session_state:
    st.session_state.answer_status = None

# ゲームタイトル表示
st.markdown('<div class="game-title">⚔️ WORD QUEST: 空欄を埋めよ</div>', unsafe_allow_html=True)

# サイドバー設定
st.sidebar.title("🛠️ COMMAND")
stroke_width = st.sidebar.slider("ペンの太さ", 1, 15, 7)
st.sidebar.caption("※ 丁寧に書くと魔法（OCR）が成功しやすいぞ！")

if not df.empty:
    current_question = df.iloc[st.session_state.q_index]
    q_sentence = str(current_question['sentence'])
    q_meaning = str(current_question['meaning'])
    q_word = str(current_question['word'])
    
    # RPGウィンドウ風に「問題の例文」と「日本語訳」を表示
    st.markdown(f"""
    <div class="rpg-box">
        <p class="sentence-text">{q_sentence}</p>
        <p class="meaning-text">💡 意味: {q_meaning}</p>
    </div>
    """, unsafe_allow_html=True)

    # 手書きキャンバス（白背景に黒文字のまま、枠線でゲーム感を演出）
    st.markdown("<p style='color:#ffb800; font-weight:bold; margin-bottom:5px;'>👇 ここに答えの英単語を書け！</p>", unsafe_allow_html=True)
    
    canvas_result = st_canvas(
        fill_color="rgba(255, 165, 0, 0.3)",
        stroke_width=stroke_width,
        stroke_color="#000000",
        background_color="#ffffff",
        height=180,
        width=600,
        drawing_mode="freedraw",
        key=f"canvas_{st.session_state.q_index}_{st.session_state.canvas_key}",
    )

    # コマンドボタン
    col_clear, col_judge, col_prev, col_next = st.columns([1, 1, 1, 1])

    with col_clear:
        if st.button("逃げる (クリア)", use_container_width=True):
            st.session_state.canvas_key += 1
            st.session_state.answer_status = None
            st.rerun()

    with col_judge:
        if st.button(" ⚔️ 採点する ", use_container_width=True):
            if canvas_result.image_data is not None:
                img_rgba = canvas_result.image_data.astype('uint8')
                img_pil = Image.fromarray(img_rgba)
                bg = Image.new("RGB", img_pil.size, (255, 255, 255))
                bg.paste(img_pil, mask=img_pil.split()[3])
                
                open_cv_image = np.array(bg)
                gray = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2GRAY)
                _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
                
                kernel = np.ones((2,2), np.uint8)
                dilated = cv2.dilate(binary, kernel, iterations=1)
                processed_img = cv2.bitwise_not(dilated)
                
                with st.spinner('呪文を解読中...'):
                    results = reader.readtext(
                        processed_img, 
                        detail=0, 
                        allowlist='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
                        mag_ratio=1.5
                    )
                    recognized_text = "".join(results).replace(" ", "").lower()
                    correct_word = q_word.strip().lower()
                    
                    # --- 判定ロジックの厳格化（完全一致のみ） ---
                    if recognized_text == correct_word:
                        st.session_state.answer_status = ("success", f"✨ クリティカルヒット！ 正解: {correct_word}")
                    else:
                        # 1文字でも違えばすべてここ（間違い扱い）になります
                        st.session_state.answer_status = ("error", f"💥 ミス！ 正解とは異なるようだ。 汝の解答: {recognized_text if recognized_text else '判定不能'} / 正解: {correct_word}")
            else:
                st.warning("キャンバスに文字を刻むのだ。")

    with col_prev:
        if st.button("⬅️ 戻る", use_container_width=True):
            if len(st.session_state.history) > 0:
                st.session_state.q_index = st.session_state.history.pop()
                st.session_state.pool_ptr = max(0, st.session_state.pool_ptr - 1)
                st.session_state.answer_status = None
                st.rerun()

    with col_next:
        if st.button("進む ➡️", use_container_width=True):
            st.session_state.history.append(st.session_state.q_index)
            st.session_state.pool_ptr += 1
            if st.session_state.pool_ptr >= len(st.session_state.question_pool):
                random.shuffle(st.session_state.question_pool)
                st.session_state.pool_ptr = 0
            st.session_state.q_index = st.session_state.question_pool[st.session_state.pool_ptr]
            st.session_state.answer_status = None
            st.rerun()

    # 判定結果の表示（ゲームのメッセージ風）
    if st.session_state.answer_status:
        status, msg = st.session_state.answer_status
        if status == "success":
            st.success(msg)
            st.snow() # 星や雪が降る演出（ゲームのクリアエフェクト風）
        else:
            st.error(msg)
            if st.checkbox("🔮 水晶玉でAIの視界を覗く"):
                st.image(processed_img, caption="AI解析用画像")
else:
    st.warning("冒険の書（問題データ）が存在しないようだ。")

# サイドバー：ステータス
st.sidebar.divider()
if not df.empty:
    st.sidebar.write(f"📈 探索度: {st.session_state.pool_ptr + 1} / {len(df)}")
    if st.sidebar.button("最初から冒険を始める 🔄"):
        indices = list(range(len(df)))
        random.shuffle(indices)
        st.session_state.question_pool = indices
        st.session_state.pool_ptr = 0
        st.session_state.q_index = st.session_state.question_pool[0]
        st.session_state.history = []
        st.session_state.answer_status = None
        st.rerun()