import streamlit as st
import pandas as pd
from streamlit_drawable_canvas import st_canvas
import easyocr
import numpy as np
from PIL import Image
import random
import difflib

# ページ設定
st.set_page_config(page_title="英単語手書き採点アプリ", layout="centered")

@st.cache_resource
def load_ocr():
    # アルファベットのみを許可するようにモデルをロード（後で認識時にも制限）
    return easyocr.Reader(['en'])

reader = load_ocr()

@st.cache_data
def load_data():
    try:
        df = pd.read_excel("questions.xlsx")
        df.columns = df.columns.str.strip()
        df = df.dropna(subset=["sentence", "word", "meaning"])
        return df
    except Exception as e:
        st.error(f"エラー: {e}")
        return pd.DataFrame(columns=["sentence", "word", "meaning"])

df = load_data()

# サイドバー設定
st.sidebar.title("🖌️ 書き心地の調整")
stroke_width = st.sidebar.slider("ペンの太さ", 1, 10, 5)
st.sidebar.info("【認識のコツ】\n数字は出ない設定にしています。a, d, g などの形をハッキリ書くと正解率が上がります。")

if 'q_index' not in st.session_state:
    st.session_state.q_index = random.randint(0, len(df)-1) if not df.empty else 0
if 'answer_status' not in st.session_state:
    st.session_state.answer_status = None

st.title("📝 例文穴埋め手書き練習")

if not df.empty:
    current_question = df.iloc[st.session_state.q_index]
    
    with st.container():
        st.info(f"💡 **意味**: {current_question['meaning']}")
        raw_sentence = str(current_question['sentence'])
        display_sentence = raw_sentence.replace("[ ]", " ___ ( ? ) ___ ")
        st.markdown(f"### {display_sentence}")

    st.write("下の枠に英単語を書いてください")

    # キャンバス
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

    col1, col2 = st.columns(2)

    with col1:
        if st.button("採点する", use_container_width=True):
            if canvas_result.image_data is not None:
                img_rgba = Image.fromarray(canvas_result.image_data.astype('uint8'))
                img_rgb = Image.new("RGB", img_rgba.size, (255, 255, 255))
                img_rgb.paste(img_rgba, mask=img_rgba.split()[3]) 
                
                with st.spinner('AIがアルファベットを解析中...'):
                    # 画像をリサイズして認識率向上
                    img_resized = img_rgb.resize((img_rgb.width * 2, img_rgb.height * 2), Image.Resampling.LANCZOS)
                    img_np = np.array(img_resized)
                    
                    # 認識! 数字を除外し、アルファベットのみを許可(allowlist)
                    # a-z A-Z のみをターゲットにする
                    results = reader.readtext(
                        img_np, 
                        detail=0, 
                        allowlist='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
                    )
                    recognized_text = "".join(results).replace(" ", "").lower()
                    
                    correct_word = str(current_question['word']).strip().lower()
                    
                    # 判定ロジック: 類似度計算 (80%以上の合致で正解とする)
                    # a/d, g/q などの微細な誤読を許容するための「予測」判断
                    similarity = difflib.SequenceMatcher(None, recognized_text, correct_word).ratio()
                    
                    if recognized_text == correct_word:
                        st.session_state.answer_status = ("success", f"完璧です！ 正解: {correct_word}")
                    elif similarity >= 0.8:
                        st.session_state.answer_status = ("success", f"正解！ (認識結果: {recognized_text} → 判定: {correct_word})")
                    else:
                        st.session_state.answer_status = ("error", f"認識結果: {recognized_text} / 正解: {correct_word}")
            else:
                st.warning("何か書いてください。")

    with col2:
        if st.button("次の問題へ ➡️", use_container_width=True):
            if len(df) > 1:
                new_idx = st.session_state.q_index
                while new_idx == st.session_state.q_index:
                    new_idx = random.randint(0, len(df)-1)
                st.session_state.q_index = new_idx
            st.session_state.answer_status = None
            st.rerun()

    if st.session_state.answer_status:
        status, msg = st.session_state.answer_status
        if status == "success":
            st.success(msg)
            st.balloons()
            st.markdown(f"✅ **{raw_sentence.replace('[ ]', f'**{current_question['word']}**')}**")
        else:
            st.error(msg)
            st.caption("【アドバイス】dやgは縦の棒を長めに書くと認識しやすくなります。数字の誤読はしない設定になっています。")
else:
    st.warning("問題データがありません。")