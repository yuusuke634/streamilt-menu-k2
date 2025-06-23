import streamlit as st
import sqlite3
import pandas as pd
from PIL import Image
import os
from datetime import datetime, timedelta
import time
import re
import io
import boto3
import uuid

# Azure Computer Vision関連のライブラリをインポート
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from msrest.authentication import CognitiveServicesCredentials

# --- DynamoDB関連の関数 ---
@st.cache_resource # このデコレータを追加
def get_dynamodb_table():
    """DynamoDBへの接続とテーブルオブジェクトを取得します。"""
    try:
        # Streamlitのsecretsから認証情報と設定を読み込む
        aws_access_key_id = st.secrets["aws"]["AWS_ACCESS_KEY_ID"]
        aws_secret_access_key = st.secrets["aws"]["AWS_SECRET_ACCESS_KEY"]
        region_name = st.secrets["aws"]["AWS_DEFAULT_REGION"]
        table_name = st.secrets["aws"]["DYNAMODB_TABLE_NAME"]
        # aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
        # aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
        # region_name = os.environ.get("AWS_DEFAULT_REGION")
        # table_name = os.environ.get("DYNAMODB_TABLE_NAME")


        # DynamoDBリソースを取得
        dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name
        )
        return dynamodb.Table(table_name)
    except Exception as e:
        st.error(f"DynamoDBへの接続に失敗しました: {e}")
        return None

# DynamoDBではテーブルは事前にコンソールで作成するため、init_dbは不要です。

def add_ingredient_to_db(name, purchase_date, expiry_date, quantity):
    """食材をDynamoDBに追加します。"""
    table = get_dynamodb_table()
    if table:
        try:
            # DynamoDBの項目（アイテム）を一意に識別するためのIDを生成
            item_id = str(uuid.uuid4())
            # date型をテキストに編集
            if not isinstance(purchase_date, str):
                purchase_date_str = purchase_date.strftime('%Y-%m-%d')
            else:
                purchase_date_str = purchase_date

            if not isinstance(expiry_date, str):
                expiry_date_str = expiry_date.strftime('%Y-%m-%d')
            else:
                expiry_date_str = expiry_date
           
            table.put_item(
                Item={
                    'id': item_id,
                    'name': name,
                    'purchase_date': purchase_date_str, # 文字列に変換した値を渡す
                    'expiry_date': expiry_date_str,     # 文字列に変換した値を渡す
                    'quantity': quantity
                }
            
            )
            st.success("食材が追加されました。")
        except Exception as e:
            st.error(f"食材の追加中にエラーが発生しました: {e}")

def get_all_ingredients():
    """DynamoDBからすべての食材を取得します。"""
    table = get_dynamodb_table()
    if table:
        try:
            # Scanオペレーションはテーブル全体を読み取るため、大規模なテーブルでは注意が必要
            response = table.scan()
            # 期限でソート
            items = sorted(response.get('Items', []), key=lambda x: x.get('expiry_date', ''))
            # 元のUIと互換性のある形式（タプルのリスト）に変換
            return [(item['id'], item['name'], item['purchase_date'], item['expiry_date'], item['quantity']) for item in items]
        except Exception as e:
            st.error(f"食材の取得中にエラーが発生しました: {e}")
    return []

def update_ingredient_quantity(ingredient_id, new_quantity):
    """DynamoDBの食材の数量を更新します。"""
    table = get_dynamodb_table()
    if table:
        try:
            table.update_item(
                Key={'id': ingredient_id},
                UpdateExpression='SET quantity = :val',
                ExpressionAttributeValues={':val': new_quantity}
            )
            st.success(f"ID: {ingredient_id} の数量を更新しました。")
        except Exception as e:
            st.error(f"数量の更新中にエラーが発生しました: {e}")

def delete_ingredient_from_db(ingredient_id):
    """DynamoDBから指定されたIDの食材を削除します。"""
    table = get_dynamodb_table()
    if table:
        try:
            table.delete_item(
                Key={'id': ingredient_id}
            )
            return 1 # 成功した場合は1を返す
        except Exception as e:
            st.error(f"食材の削除中にエラーが発生しました: {e}")
    return 0

def clear_database():
    """DynamoDBのテーブルからすべてのアイテムを削除します。"""
    table = get_dynamodb_table()
    if table:
        try:
            with table.batch_writer() as batch:
                # Scanで全アイテムのキーを取得してバッチ削除
                response = table.scan(ProjectionExpression="id")
                for item in response['Items']:
                    batch.delete_item(Key={'id': item['id']})
            st.success("データベースの食材データを初期化しました。")
        except Exception as e:
            st.error(f"データベースの初期化中にエラーが発生しました: {e}")
    return 0


# # --- データベース関連 (recipe_proposer.pyから流用) ---
# DATABASE_NAME = "food_items.db"

# def init_db():
#     """データベースを初期化し、テーブルがなければ作成します。"""
#     conn = sqlite3.connect(DATABASE_NAME)
#     cursor = conn.cursor()
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS food_items (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             name TEXT NOT NULL,
#             purchase_date TEXT NOT NULL,
#             expiry_date TEXT NOT NULL,
#             quantity TEXT NOT NULL
#         )
#     """)
#     conn.commit()
#     conn.close()

# def add_ingredient_to_db(name, purchase_date, expiry_date, quantity):
#     """食材をデータベースに追加します。"""
#     conn = sqlite3.connect(DATABASE_NAME)
#     cursor = conn.cursor()
#     try:
#         # 日付オブジェクトをISO 8601形式の文字列に変換して保存
#         cursor.execute(
#             "INSERT INTO food_items (name, purchase_date, expiry_date, quantity) VALUES (?, ?, ?, ?)",
#             (name, str(purchase_date), str(expiry_date), quantity)
#         )
#         conn.commit()
#     except sqlite3.Error as e:
#         # エラーが発生した場合はUIにエラーメッセージを表示
#         st.error(f"食材 '{name}' のデータベース追加中にエラーが発生しました: {e}")
#     finally:
#         conn.close()

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
    # subscription_key = st.secrets["AZURE_VISION_KEY"]
    # endpoint = st.secrets["AZURE_VISION_ENDPOINT"]
    subscription_key = os.environ.get("AZURE_VISION_KEY")
    endpoint = os.environ.get("AZURE_VISION_ENDPOINT")

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
                # st.rerun()
        with col2:
            if st.button("🗑️ キャンセルしてやり直す", use_container_width=True):
                del st.session_state.ingredients_df
                # st.rerun()
    return 0


if __name__ == "__main__":
    # init_db()  # アプリ起動時にデータベースとテーブルの存在を確認・作成
    show_receipt_scanner()