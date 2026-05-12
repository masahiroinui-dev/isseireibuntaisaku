import streamlit as st
import pandas as pd
from streamlit_drawable_canvas import st_canvas
import easyocr
import numpy as np
from PIL import Image
import random
import difflib
import cv2

# ページ設定
st.set_page_config(page_title="英単語手書き採点アプリ", layout="centered")

# OCRモデルの読み込み（英語を指定）
@st.cache_resource
def load_ocr():
    # アルファベットのみをターゲットにロード
    return easyocr.Reader(['en'], gpu=False)

reader = load_ocr()

# エクセルデータの読み込み
@st.cache_data
def load_data():
    try:
        # デスクトップにある questions.xlsx を読み込む
        df = pd.read_excel("questions.xlsx")
        df.columns = df.columns.str.strip()
        df = df.dropna(subset=["word", "meaning"])
        return df
    except Exception as e:
        st.error(f"エラー: {e}")
        return pd.DataFrame(columns=["word", "meaning"])

df = load_data()

# ボタンの視認性を上げるためのカスタムCSS
st.markdown("""
<style>
    /* 削除/クリアボタンのスタイル */
    div[data-testid="stButton"] > button:contains("書き直す"),
    div[data-testid="stButton"] > button:contains("最初から") {
        border: 2px solid #ff4b4b !important;
        color: #ff4b4b !important;
        background-color: white !important;
    }
    /* 戻るボタンのスタイル */
    div[data-testid="stButton"] > button:contains("前へ") {
        border: 2px solid #0068c9 !important;
        color: #0068c9 !important;
        background-color: white !important;
    }
    /* 次へ/採点ボタンのスタイル */
    div[data-testid="stButton"] > button:contains("採点"),
    div[data-testid="stButton"] > button:contains("次へ") {
        background-color: #0068c9 !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# セッション状態の初期化
if 'question_pool' not in st.session_state:
    if not df.empty:
        # ランダムに並び替えたインデックスのリストを作成
        indices = list(range(len(df)))
        random.shuffle(indices)
        st.session_state.question_pool = indices
        st.session_state.pool_ptr = 0 # 現在のプールの位置
        st.session_state.q_index = st.session_state.question_pool[0]
        st.session_state.history = [] # 戻るための履歴
    else:
        st.session_state.question_pool = []
        st.session_state.q_index = 0

if 'answer_status' not in st.session_state:
    st.session_state.answer_status = None

st.title("📝 英単語手書きテスト")

# サイドバー設定
st.sidebar.title("🖌️ 書き心地と精度の調整")
stroke_width = st.sidebar.slider("ペンの太さ", 1, 15, 7)
st.sidebar.info("【精度向上のコツ】\n・dの縦棒を長めに書く\n・aの丸をしっかり閉じる\n・gの尻尾を明確に下げる")

if not df.empty:
    current_question = df.iloc[st.session_state.q_index]
    q_meaning = str(current_question['meaning'])
    q_word = str(current_question['word'])
    
    st.subheader("この意味になる英単語を書いてください")
    
    st.markdown(f"""
    <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; border-left: 5px solid #ff4b4b; margin-bottom: 20px;">
        <h1 style="margin: 0; color: #31333f; font-size: 2.5rem; text-align: center;">{q_meaning}</h1>
    </div>
    """, unsafe_allow_html=True)

    # 手書きキャンバス
    canvas_result = st_canvas(
        fill_color="rgba(255, 165, 0, 0.3)",
        stroke_width=stroke_width,
        stroke_color="#000000",
        background_color="#ffffff",
        height=250,
        width=600,
        drawing_mode="freedraw",
        key=f"canvas_{st.session_state.q_index}",
    )

    # ボタンレイアウト
    col_clear, col_judge, col_prev, col_next = st.columns([1, 1, 1, 1])

    with col_clear:
        if st.button("書き直す 🗑️", use_container_width=True):
            st.rerun()

    with col_judge:
        if st.button("採点する ✅", use_container_width=True):
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
                
                with st.spinner('確認中...'):
                    results = reader.readtext(
                        processed_img, 
                        detail=0, 
                        allowlist='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
                        mag_ratio=2.0 
                    )
                    recognized_text = "".join(results).replace(" ", "").lower()
                    correct_word = q_word.strip().lower()
                    similarity = difflib.SequenceMatcher(None, recognized_text, correct_word).ratio()
                    
                    if recognized_text == correct_word:
                        st.session_state.answer_status = ("success", f"完璧です！ 正解: {correct_word}")
                    elif similarity >= 0.75:
                        st.session_state.answer_status = ("success", f"正解！ (認識: {recognized_text} → 判定: {correct_word})")
                    else:
                        st.session_state.answer_status = ("error", f"認識結果: {recognized_text} / 正解: {correct_word}")
            else:
                st.warning("何か書いてください。")

    with col_prev:
        if st.button("⬅️ 前へ", use_container_width=True):
            if len(st.session_state.history) > 0:
                # 履歴から戻る
                st.session_state.q_index = st.session_state.history.pop()
                st.session_state.pool_ptr = max(0, st.session_state.pool_ptr - 1)
                st.session_state.answer_status = None
                st.rerun()

    with col_next:
        if st.button("次へ ➡️", use_container_width=True):
            # 現在の問題を履歴に追加
            st.session_state.history.append(st.session_state.q_index)
            
            # プールの次の問題へ
            st.session_state.pool_ptr += 1
            
            # プールを一周したらシャッフルし直す
            if st.session_state.pool_ptr >= len(st.session_state.question_pool):
                random.shuffle(st.session_state.question_pool)
                st.session_state.pool_ptr = 0
            
            st.session_state.q_index = st.session_state.question_pool[st.session_state.pool_ptr]
            st.session_state.answer_status = None
            st.rerun()

    if st.session_state.answer_status:
        status, msg = st.session_state.answer_status
        if status == "success":
            st.success(msg)
            st.balloons()
        else:
            st.error(msg)
            if st.checkbox("AIに渡された画像を確認"):
                st.image(processed_img, caption="解析用画像")
else:
    st.warning("問題データがありません。")

# サイドバー：学習メニュー
st.sidebar.divider()
st.sidebar.title("学習メニュー")
if not df.empty:
    st.sidebar.write(f"進捗: {st.session_state.pool_ptr + 1} / {len(df)}")
    if st.sidebar.button("最初からやり直す 🔄"):
        indices = list(range(len(df)))
        random.shuffle(indices)
        st.session_state.question_pool = indices
        st.session_state.pool_ptr = 0
        st.session_state.q_index = st.session_state.question_pool[0]
        st.session_state.history = []
        st.session_state.answer_status = None
        st.rerun()