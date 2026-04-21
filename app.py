import streamlit as st
import pandas as pd
from streamlit_drawable_canvas import st_canvas
import easyocr
import numpy as np
from PIL import Image
import random

# ページ設定
st.set_page_config(page_title="英単語手書き採点アプリ", layout="centered")

# OCRモデルの読み込み（英語を指定）
@st.cache_resource
def load_ocr():
    # 初回起動時にモデルをダウンロードするため時間がかかります
    return easyocr.Reader(['en'])

reader = load_ocr()

# エクセルデータの読み込み
@st.cache_data
def load_data():
    try:
        # デスクトップにある questions.xlsx を読み込む
        # 列名: sentence (例文), word (正解単語), meaning (和訳)
        df = pd.read_excel("questions.xlsx")
        # 列名を文字列として確実に扱い、空白行などを削除
        df.columns = df.columns.str.strip()
        df = df.dropna(subset=["sentence", "word", "meaning"])
        return df
    except Exception as e:
        st.error(f"エラー: {e}")
        return pd.DataFrame(columns=["sentence", "word", "meaning"])

df = load_data()

# サイドバーの設定（キャンバスの調整）
st.sidebar.title("🖌️ 書き心地の設定")
stroke_width = st.sidebar.slider("線の太さ (aやdの判別に影響します)", 1, 10, 5)
st.sidebar.caption("※ aとdが混同される場合は、少し細め(3〜4)にすると文字の隙間がはっきりします。")

# セッション状態の初期化
if 'q_index' not in st.session_state:
    if not df.empty:
        st.session_state.q_index = random.randint(0, len(df) - 1)
    else:
        st.session_state.q_index = 0

if 'answer_status' not in st.session_state:
    st.session_state.answer_status = None

st.title("📝 例文穴埋め手書き練習")

# データが空でないかチェック
if not df.empty:
    # インデックスが範囲内にあるか確認
    if st.session_state.q_index >= len(df):
        st.session_state.q_index = 0
        
    # 現在の問題データを取得
    current_question = df.iloc[st.session_state.q_index]
    
    # 明示的にそれぞれの列から値を取得（型の変換も含む）
    q_meaning = str(current_question['meaning'])
    q_sentence = str(current_question['sentence'])
    q_word = str(current_question['word'])
    
    # 問題の表示
    st.subheader("以下の空欄を埋めてください")
    
    # カード形式で意味と例文を表示
    with st.container():
        # 意味を表示
        st.info(f"💡 **意味**: {q_meaning}")
        
        # 例文を表示（[ ] の部分を強調）
        display_sentence = q_sentence.replace("[ ]", " ___ ( ? ) ___ ")
        st.markdown(f"### {display_sentence}")

    st.write("下の枠に英単語を書いてください")

    # 手書きキャンバスの設定
    canvas_result = st_canvas(
        fill_color="rgba(255, 165, 0, 0.3)",
        stroke_width=stroke_width,
        stroke_color="#000000",
        background_color="#ffffff",
        height=200,
        width=600,
        drawing_mode="freedraw",
        key=f"canvas_{st.session_state.q_index}", # 問題ごとにキャンバスをリセット
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("採点する", use_container_width=True):
            if canvas_result.image_data is not None:
                img = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA').convert('RGB')
                img_np = np.array(img)
                
                with st.spinner('AIが文字を読み取っています...'):
                    results = reader.readtext(img_np)
                    # 認識されたテキストを結合して小文字化
                    # aとdの誤読対策として、もし認識が極端に短い場合は再度確認を促すロジックの余地
                    recognized_text = "".join([res[1] for res in results]).replace(" ", "").lower()
                    
                    correct_word = q_word.strip().lower()
                    
                    if recognized_text == correct_word:
                        st.session_state.answer_status = ("success", f"正解です！ (認識: {recognized_text})")
                    else:
                        st.session_state.answer_status = ("error", f"おしい！ 認識結果: {recognized_text} / 正解: {correct_word}")
            else:
                st.warning("何か書いてから採点してください。")

    with col2:
        if st.button("次の問題へ ➡️", use_container_width=True):
            if len(df) > 1:
                new_idx = st.session_state.q_index
                while new_idx == st.session_state.q_index:
                    new_idx = random.randint(0, len(df) - 1)
                st.session_state.q_index = new_idx
            
            st.session_state.answer_status = None
            st.rerun()

    # 採点結果の表示
    if st.session_state.answer_status:
        status, msg = st.session_state.answer_status
        if status == "success":
            st.success(msg)
            st.balloons()
            # 完成した例文を表示
            completed = q_sentence.replace("[ ]", f"**{q_word}**")
            st.markdown(f"✅ **{completed}**")
        else:
            st.error(msg)
            if st.button("答えを見る"):
                st.write(f"正解は **{q_word}** です")

else:
    st.warning("問題データが見つかりません。エクセルファイルを確認してください。")

# サイドバー：学習メニュー
st.sidebar.divider()
st.sidebar.title("学習メニュー")
if not df.empty:
    st.sidebar.write(f"全 {len(df)} 問中、現在 {st.session_state.q_index + 1} 問目を表示中")
    if st.sidebar.button("問題をシャッフルして最初から"):
        st.session_state.q_index = random.randint(0, len(df)-1)
        st.session_state.answer_status = None
        st.rerun()

st.sidebar.divider()
st.sidebar.caption("※文字認識(OCR)は手書きの癖により誤判定される場合があります。")