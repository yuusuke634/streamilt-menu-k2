import streamlit as st
import sqlite3
import pandas as pd
from PIL import Image
import os
from datetime import datetime, timedelta
import time
import re
import io

# Azure Computer Vision関連のライブラリをインポート
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from msrest.authentication import CognitiveServicesCredentials


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

def analyze_receipt_with_azure_cv(image_bytes, client):
    """Azure Computer Vision APIを使用してレシート画像からテキストを抽出します。"""
    try:
        # バイトデータをインメモリストリームに変換します
        image_stream = io.BytesIO(image_bytes)
        # Read APIを呼び出し、非同期で読み取りを開始
        read_response = client.read_in_stream(image_stream, raw=True)

        # レスポンスヘッダーから結果取得用のURLを取得
        operation_location = read_response.headers["Operation-Location"]
        operation_id = operation_location.split("/")[-1]

        # 分析が完了するまで待機（ポーリング）
        while True:
            read_result = client.get_read_result(operation_id)
            if read_result.status.lower() not in ['notstarted', 'running']:
                break
            time.sleep(1) # 1秒待機

        # 成功した場合、テキスト行を連結して返す
        if read_result.status.lower() == 'succeeded':
            full_text = []
            for text_result in read_result.analyze_result.read_results:
                for line in text_result.lines:
                    full_text.append(line.text)
            return "\n".join(full_text)
        else:
            st.error(f"Azureでのテキスト認識に失敗しました。ステータス: {read_result.status}")
            return None

    except Exception as e:
        st.error(f"Azure Computer Vision APIの呼び出し中にエラーが発生しました: {e}")
        return None

def parse_ingredients_from_text(full_text: str):
    """抽出されたテキスト全体から食材名と量を簡易的に解析します。"""
    ingredients = []
    ignore_keywords = ["合計", "小計", "税", "お預り", "お釣り", "クレジット", "ポイント", "レジ", "No.", "担当", "領収書", "店", "電話", "様", "内税", "外税","イオン","※","まとめ","領収証","登録番号","個","責","アプリ","EON","TEL"]

    lines = full_text.split('\n')
    for line in lines:
        line = line.strip()
        # チェック用に、行から半角と全角のスペースをすべて削除した新しい変数を用意
        line_for_check = line.replace(" ", "").replace("　", "")
        # 行が空っぽもしくはigonore_key_wordsが含まれている場合はスキップ
        if not line_for_check or any(keyword in line for keyword in ignore_keywords):
            continue
        # 行から「¥」や「,」「.」を取り除いた結果、残りがすべて数字になる場合
        if line.replace('¥', '').replace(',', '').replace('.', '').strip().isdigit():
            continue

        name = re.sub(r'[\s,]*[¥@]?[\d,.]+$', '', line).strip()
        name = name.replace('*', '').replace('※', '').strip()

        if len(name) > 1:
            ingredients.append({"name": name, "quantity": "1個"})

    if not ingredients:
        return pd.DataFrame()
    return pd.DataFrame(ingredients)

def show_receipt_scanner():
    """メインのStreamlitアプリケーション"""
    st.header("レシートスキャナー (Azure Computer Vision)")
    st.write("レシートの画像をアップロードして、購入した食材をデータベースに登録します。")

    # --- Azure Computer Vision API設定 ---
    subscription_key = st.secrets["AZURE_VISION_KEY"]
    endpoint = st.secrets["AZURE_VISION_ENDPOINT"]
    # subscription_key = os.environ.get("AZURE_VISION_KEY")
    # endpoint = os.environ.get("AZURE_VISION_ENDPOINT")

    if not subscription_key or not endpoint:
        st.error("環境変数 AZURE_VISION_KEY と AZURE_VISION_ENDPOINT が設定されていません。")
        st.info("アプリを実行する前に、Azureのキーとエンドポイントを設定してください。")
        st.stop()
    
    # Computer Visionクライアントを認証
    computervision_client = ComputerVisionClient(endpoint, CognitiveServicesCredentials(subscription_key))

    # --- UI ---
    uploaded_file = st.file_uploader(
        "レシートの画像ファイル (JPG, PNG) をアップロードしてください",
        type=['jpg', 'jpeg', 'png']
    )

    if uploaded_file is not None:
        image_bytes = uploaded_file.getvalue()
        image = Image.open(uploaded_file)
        st.image(image, caption='アップロードされたレシート', width=300)

        if st.button("🖨️ このレシートを読み取る"):
            with st.spinner("Azure Computer Visionでレシートを解析中..."):
                full_text = analyze_receipt_with_azure_cv(image_bytes, computervision_client)
                
                if full_text:
                    ingredients_df = parse_ingredients_from_text(full_text)
                    
                    if not ingredients_df.empty:
                        ingredients_df['purchase_date'] = datetime.today().date()
                        ingredients_df['expiry_date'] = (datetime.today() + timedelta(days=7)).date()
                        st.session_state.ingredients_df = ingredients_df
                        st.rerun()
                    else:
                        st.warning("食材と思われる項目を自動抽出できませんでした。以下に読み取られた全テキストを表示します。")
                        st.text_area("OCR結果", full_text, height=300)
                else:
                    st.error("レシートからテキストを抽出できませんでした。")


# def analyze_receipt_with_vision_api(image_content: bytes):
#     """Google Cloud Vision APIを使用してレシート画像からテキストを抽出します。"""
#     try:
#         # JSONキーファイルへのパスを指定
#         key_path = r"C:\Users\harad\myproject19461\original-nomad-429501-m0-5fe35d81803f.json" 

#         # 認証情報を作成
#         credentials = service_account.Credentials.from_service_account_file(key_path)

#         # 認証情報を使ってクライアントを初期化
#         client = vision.ImageAnnotatorClient(credentials=credentials)
#         image = vision.Image(content=image_content)
        
#         # Vision APIのtext_detectionを呼び出し
#         response = client.text_detection(image=image)
        
#         if response.error.message:
#             raise Exception(response.error.message)
            
#         return response.text_annotations
#     except Exception as e:
#         st.error(f"Google Cloud Vision APIの呼び出し中にエラーが発生しました: {e}")
#         return None

# def parse_ingredients_from_text(full_text: str):
#     """
#     Vision APIが抽出したテキスト全体から食材名と量を簡易的に解析します。
#     このロジックは単純なため、レシートの形式によっては調整が必要です。
#     """
#     ingredients = []
#     # レシートによく含まれる、食材以外のキーワード
#     ignore_keywords = ["合計", "小計", "税", "お預り", "お釣り", "クレジット", "ポイント", "レジ", "No.", "担当", "領収書", "店", "電話", "様"]

#     lines = full_text.split('\n')
#     for line in lines:
#         line = line.strip()

#         # 空の行や、無視するキーワードが含まれる行はスキップ
#         if not line or any(keyword in line for keyword in ignore_keywords):
#             continue

#         # 数字や特定記号のみの行はスキップ (価格や数量のみの行を想定)
#         if line.replace('¥', '').replace(',', '').replace('.', '').strip().isdigit():
#             continue

#         # ヒューリスティック: 価格や数量と思われる末尾の数字部分を除去して品名とする
#         # 例: 「キャベツ ¥198」 -> 「キャベツ」
#         name = re.sub(r'[\s,]*[¥@]?[\d,.]+$', '', line).strip()
#         # アスタリスクなどの記号を削除
#         name = name.replace('*', '').replace('※', '').strip()

#         # 抽出した品名が1文字以上であればリストに追加
#         if len(name) > 1:
#             # 数量はOCRだけでは正確な判別が難しいため、デフォルトで「1」とし、ユーザーに編集を促す
#             ingredients.append({"name": name, "quantity": "1"})

#     if not ingredients:
#         return pd.DataFrame()
#     return pd.DataFrame(ingredients)

# def show_receipt_scanner():
#     """メインのStreamlitアプリケーション"""
#     st.header("レシートスキャナー")
#     st.write("レシートの画像をアップロードして、購入した食材をデータベースに登録します。")

#     # APIキーのチェックはVision APIでは不要 (環境変数で認証するため)
#     # ただし、環境変数が設定されているかどうかの確認は重要
#     if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
#         st.error("環境変数 GOOGLE_APPLICATION_CREDENTIALS が設定されていません。")
#         st.info("アプリを実行する前に、サービスアカウントキー(JSON)へのパスを設定してください。")
#         st.stop()

#     # --- UI ---
#     uploaded_file = st.file_uploader(
#         "レシートの画像ファイル (JPG, PNG) をアップロードしてください",
#         type=['jpg', 'jpeg', 'png']
#     )

#     if uploaded_file is not None:
#         # 画像データをバイトとして読み込む
#         image_bytes = uploaded_file.getvalue()
#         image = Image.open(uploaded_file)
#         st.image(image, caption='アップロードされたレシート', width=300)

#         if st.button("🖨️ このレシートを読み取る"):
#             with st.spinner("Vision APIでレシートを解析中..."):
#                 # Vision APIに画像データを渡す
#                 text_annotations = analyze_receipt_with_vision_api(image_bytes)
                
#                 if text_annotations:
#                     # 検出されたテキスト全体を取得
#                     full_text = text_annotations[0].description
#                     # テキストから食材情報を解析
#                     ingredients_df = parse_ingredients_from_text(full_text)
                    
#                     if not ingredients_df.empty:
#                         # 購入日と賞味期限の列を追加
#                         ingredients_df['purchase_date'] = datetime.today().date()
#                         # 賞味期限は仮で7日後を設定（編集可能）
#                         ingredients_df['expiry_date'] = (datetime.today() + timedelta(days=7)).date()
                        
#                         # 編集可能な状態でセッションに保存
#                         st.session_state.ingredients_df = ingredients_df
#                         st.rerun()
#                     else:
#                         st.warning("食材と思われる項目を自動で抽出できませんでした。以下に読み取られた全テキストを表示します。")
#                         st.text_area("OCR結果", full_text, height=300)
#                 else:
#                     st.error("レシートからテキストを抽出できませんでした。")



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