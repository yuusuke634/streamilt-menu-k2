import streamlit as st
import sqlite3
import pandas as pd
from PIL import Image
from google.cloud import vision
from google.oauth2 import service_account
import re
import os
import json
from datetime import datetime, timedelta

# --- データベース関連 (recipe_proposer.pyから流用) ---
DATABASE_NAME = "food_items.db"

def init_db():
    """データベースを初期化し、テーブルがなければ作成します。"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS food_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            purchase_date TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            quantity TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_ingredient_to_db(name, purchase_date, expiry_date, quantity):
    """食材をデータベースに追加します。"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        # 日付オブジェクトをISO 8601形式の文字列に変換して保存
        cursor.execute(
            "INSERT INTO food_items (name, purchase_date, expiry_date, quantity) VALUES (?, ?, ?, ?)",
            (name, str(purchase_date), str(expiry_date), quantity)
        )
        conn.commit()
    except sqlite3.Error as e:
        # エラーが発生した場合はUIにエラーメッセージを表示
        st.error(f"食材 '{name}' のデータベース追加中にエラーが発生しました: {e}")
    finally:
        conn.close()

def analyze_receipt_with_vision_api(image_content: bytes):
    """Google Cloud Vision APIを使用してレシート画像からテキストを抽出します。"""
    try:
        # JSONキーファイルへのパスを指定
        key_path = r"C:\Users\harad\myproject19461\original-nomad-429501-m0-5fe35d81803f.json" 

        # 認証情報を作成
        credentials = service_account.Credentials.from_service_account_file(key_path)

        # 認証情報を使ってクライアントを初期化
        client = vision.ImageAnnotatorClient(credentials=credentials)
        image = vision.Image(content=image_content)
        
        # Vision APIのtext_detectionを呼び出し
        response = client.text_detection(image=image)
        
        if response.error.message:
            raise Exception(response.error.message)
            
        return response.text_annotations
    except Exception as e:
        st.error(f"Google Cloud Vision APIの呼び出し中にエラーが発生しました: {e}")
        return None

def parse_ingredients_from_text(full_text: str):
    """
    Vision APIが抽出したテキスト全体から食材名と量を簡易的に解析します。
    このロジックは単純なため、レシートの形式によっては調整が必要です。
    """
    ingredients = []
    # レシートによく含まれる、食材以外のキーワード
    ignore_keywords = ["合計", "小計", "税", "お預り", "お釣り", "クレジット", "ポイント", "レジ", "No.", "担当", "領収書", "店", "電話", "様"]

    lines = full_text.split('\n')
    for line in lines:
        line = line.strip()

        # 空の行や、無視するキーワードが含まれる行はスキップ
        if not line or any(keyword in line for keyword in ignore_keywords):
            continue

        # 数字や特定記号のみの行はスキップ (価格や数量のみの行を想定)
        if line.replace('¥', '').replace(',', '').replace('.', '').strip().isdigit():
            continue

        # ヒューリスティック: 価格や数量と思われる末尾の数字部分を除去して品名とする
        # 例: 「キャベツ ¥198」 -> 「キャベツ」
        name = re.sub(r'[\s,]*[¥@]?[\d,.]+$', '', line).strip()
        # アスタリスクなどの記号を削除
        name = name.replace('*', '').replace('※', '').strip()

        # 抽出した品名が1文字以上であればリストに追加
        if len(name) > 1:
            # 数量はOCRだけでは正確な判別が難しいため、デフォルトで「1」とし、ユーザーに編集を促す
            ingredients.append({"name": name, "quantity": "1"})

    if not ingredients:
        return pd.DataFrame()
    return pd.DataFrame(ingredients)

def show_receipt_scanner():
    """メインのStreamlitアプリケーション"""
    st.header("レシートスキャナー")
    st.write("レシートの画像をアップロードして、購入した食材をデータベースに登録します。")

    # APIキーのチェックはVision APIでは不要 (環境変数で認証するため)
    # ただし、環境変数が設定されているかどうかの確認は重要
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        st.error("環境変数 GOOGLE_APPLICATION_CREDENTIALS が設定されていません。")
        st.info("アプリを実行する前に、サービスアカウントキー(JSON)へのパスを設定してください。")
        st.stop()

    # --- UI ---
    uploaded_file = st.file_uploader(
        "レシートの画像ファイル (JPG, PNG) をアップロードしてください",
        type=['jpg', 'jpeg', 'png']
    )

    if uploaded_file is not None:
        # 画像データをバイトとして読み込む
        image_bytes = uploaded_file.getvalue()
        image = Image.open(uploaded_file)
        st.image(image, caption='アップロードされたレシート', width=300)

        if st.button("🖨️ このレシートを読み取る"):
            with st.spinner("Vision APIでレシートを解析中..."):
                # Vision APIに画像データを渡す
                text_annotations = analyze_receipt_with_vision_api(image_bytes)
                
                if text_annotations:
                    # 検出されたテキスト全体を取得
                    full_text = text_annotations[0].description
                    # テキストから食材情報を解析
                    ingredients_df = parse_ingredients_from_text(full_text)
                    
                    if not ingredients_df.empty:
                        # 購入日と賞味期限の列を追加
                        ingredients_df['purchase_date'] = datetime.today().date()
                        # 賞味期限は仮で7日後を設定（編集可能）
                        ingredients_df['expiry_date'] = (datetime.today() + timedelta(days=7)).date()
                        
                        # 編集可能な状態でセッションに保存
                        st.session_state.ingredients_df = ingredients_df
                        st.rerun()
                    else:
                        st.warning("食材と思われる項目を自動で抽出できませんでした。以下に読み取られた全テキストを表示します。")
                        st.text_area("OCR結果", full_text, height=300)
                else:
                    st.error("レシートからテキストを抽出できませんでした。")

# def analyze_receipt_with_gemini(image: Image.Image):
#     """Gemini Pro Visionを使用してレシート画像から食材情報を抽出します。"""
    
#     # Visionモデルの準備 (例: gemini-1.5-pro)
#     model = genai.GenerativeModel('gemini-2.5-Flash')

#     prompt = """
# あなたはレシートを解析する専門家です。
# 添付されたレシートの画像から、購入した「食材」のみを抽出し、その「品名」と「数量」をリストアップしてください。

# 以下のルールに厳密に従ってください:
# 1.  **食材のみを抽出**: "レジ袋"、"消費税"、"合計"、"お釣り"、"ポイント"などの項目は完全に無視してください。
# 2.  **数量の解釈**: 数量が明記されていない品目は、数量を「1」としてください。グラム(g)や個数など、記載されている場合はその数値を採用してください。数値のみを抽出してください（単位は不要）。
# 3.  **出力形式**: 結果は、必ず以下の形式のJSONリストとして出力してください。JSONの前後に説明文や ```json ``` といったマークダウンは一切含めないでください。

# [
#   {
#     "name": "抽出した品名1",
#     "quantity": 抽出した数量1
#   },
#   {
#     "name": "抽出した品名2",
#     "quantity": 抽出した数量2
#   }
# ]
# """
    
#     try:
#         response = model.generate_content([prompt, image])
#         # クリーンなJSONテキストを取得するために不要なマークダウンを削除
#         cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        
#         # JSONとしてパース
#         items = json.loads(cleaned_response)
        
#         # Pandas DataFrameに変換
#         df = pd.DataFrame(items)
        
#         # 必要な列が存在するか確認
#         if 'name' not in df.columns or 'quantity' not in df.columns:
#             st.error("抽出結果に必要な'name'または'quantity'列が含まれていません。")
#             return pd.DataFrame() # 空のDataFrameを返す

#         return df

#     except Exception as e:
#         st.error(f"レシートの解析中にエラーが発生しました: {e}")
#         st.info("プロンプトやモデルが原因である可能性があります。レスポンス内容を確認してください。")
#         st.text_area("Geminiからの生レスポンス:", response.text if 'response' in locals() else "レスポンスなし", height=200)
#         return pd.DataFrame() # 空のDataFrameを返す

# def show_receipt_scanner():
#     """メインのStreamlitアプリケーション"""
#     st.header("レシートスキャナー")
#     st.write("レシートの画像をアップロードして、購入した食材をデータベースに登録します。")

#     # --- Gemini API設定 ---
#     api_key = os.environ.get("GOOGLE_API_KEY")
#     if not api_key:
#         st.error("APIキーが環境変数 GOOGLE_API_KEY に設定されていません。")
#         st.info("アプリを実行する前に、環境変数にAPIキーを設定してください。")
#         st.stop()
#     else:
#         genai.configure(api_key=api_key)

#     # --- UI ---
#     uploaded_file = st.file_uploader(
#         "レシートの画像ファイル (JPG, PNG) をアップロードしてください",
#         type=['jpg', 'jpeg', 'png']
#     )

#     if uploaded_file is not None:
#         image = Image.open(uploaded_file)
#         st.image(image, caption='アップロードされたレシート', width=300)

#         if st.button("🖨️ このレシートを読み取る"):
#             with st.spinner("Geminiがレシートを解析中..."):
#                 ingredients_df = analyze_receipt_with_gemini(image)
#                 if not ingredients_df.empty:
#                     # 購入日と賞味期限の列を追加
#                     ingredients_df['purchase_date'] = datetime.today().date()
#                     # 賞味期限は仮で7日後を設定（編集可能）
#                     ingredients_df['expiry_date'] = (datetime.today() + timedelta(days=7)).date()
                    
#                     # 編集可能な状態でセッションに保存
#                     st.session_state.ingredients_df = ingredients_df
#                     st.rerun() # 再実行してデータエディタを表示

    # --- 編集画面 ---
    if 'ingredients_df' in st.session_state and not st.session_state.ingredients_df.empty:
        st.divider()
        st.header("🛒 読み取り結果の確認と編集")
        st.info("以下の表は直接編集できます。行の追加や削除も可能です。")

        # st.data_editorを使用して編集可能な表を表示
        edited_df = st.data_editor(
            st.session_state.ingredients_df,
            column_config={
                "name": st.column_config.TextColumn("品名", required=True, help="食材の名前"),
                "quantity": st.column_config.TextColumn("数量",  help="食材の数量" , required = True),
                "purchase_date": st.column_config.DateColumn("購入日", format="YYYY-MM-DD", required=True),
                "expiry_date": st.column_config.DateColumn("賞味期限", format="YYYY-MM-DD", required=True, help="おおよその賞味期限を入力してください"),
            },
            num_rows="dynamic", # 行の追加・削除を有効化
            use_container_width=True
        )

        st.write("") # スペーサー
        
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("💾 データベースに登録", type="primary", use_container_width=True):
                with st.spinner("データベースに登録中..."):
                    added_count = 0
                    error_count = 0
                    
                    # DataFrameの各行をループしてDBに追加
                    for index, row in edited_df.iterrows():
                        if pd.notna(row['name']) and row['name'].strip() != "":
                            try:
                                add_ingredient_to_db(
                                    row['name'],
                                    row['purchase_date'],
                                    row['expiry_date'],
                                    row['quantity']
                                )
                                added_count += 1
                            except Exception:
                                error_count += 1

                if added_count > 0:
                    st.success(f"{added_count}件の食材をデータベースに登録しました！")
                if error_count > 0:
                    st.warning(f"{error_count}件の食材は登録に失敗しました。")
                
                # 処理完了後、セッションステートをクリアして初期状態に戻る
                del st.session_state.ingredients_df
                st.rerun()
        with col2:
            if st.button("🗑️ キャンセルしてやり直す", use_container_width=True):
                del st.session_state.ingredients_df
                st.rerun()


if __name__ == "__main__":
    # init_db()  # アプリ起動時にデータベースとテーブルの存在を確認・作成
    show_receipt_scanner()