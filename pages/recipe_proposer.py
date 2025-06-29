import streamlit as st
import sqlite3
from datetime import datetime, timedelta
import google.generativeai as genai
import json # For parsing potential structured responses from Gemini, though not strictly used for current dummy.
import os
import pandas as pd
import boto3
import uuid

# --- データベース関連の関数 ---

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




# --- Streamlit UI ---
def show_recipe_proposer():
    st.header("献立生成")
    st.write("現在登録されている食材を使って、献立を提案します。")
   

    # --- 献立提案セクション ---
    # Google Gemini APIの設定
    api_key = st.secrets["GOOGLE_API_KEY"]
    # api_key = os.environ.get("GOOGLE_API_KEY")
    gemini_configured_successfully = False
    if api_key:
        try:
            genai.configure(api_key=api_key)
            # model_options = ["gemini-1.5-flash", "gemini-2.0-flash","gemini-2.5-flash",]
            # select_model = st.selectbox("AIモデル:", model_options)
            # selected_model = genai.GenerativeModel(select_model)
            gemini_configured_successfully = True
        except Exception as e:
            st.error(f"Gemini APIの設定中にエラーが発生しました: {e}")
    else:
        st.error("APIキーが環境変数 GOOGLE_API_KEY に設定されていません。")
        st.info("ローカルで実行する場合: 環境変数に GOOGLE_API_KEY を設定してください。")
        st.info("Streamlit Cloudにデプロイする場合: アプリ設定のSecretsに GOOGLE_API_KEY = \"あなたのAPIキー\" を追加してください。")
        model = None # モデルが利用できないことを示す

    st.header("献立提案")
    col_menu_input, col_menu_output = st.columns(2)

    with col_menu_input:
        # モデルを選択するためのUIを追加 
        model_options = ["gemini-1.5-flash", "gemini-2.0-flash","gemini-2.5-flash"]
        selected_model_name = st.selectbox("AIモデル:", model_options)

        # 提案内容の選択ボタン
        menu_options = ["主菜", "副菜", "汁物", "デザート"]
        size_options = ["1人前" , "2人前", "3人前", "4人前"]
        preferences_opions = ["和食", "洋食", "中華", "イタリアン", "その他"]
        menu_type = st.multiselect("献立の種類:", menu_options)
        serving_size = st.radio("分量： ", size_options)
        preferences = st.radio("好み:", preferences_opions)
        others_conditions = st.text_input("その他の条件:", placeholder="例: アレルギー、特定の食材を避けるなど")

    ingredients_data = get_all_ingredients()

    if st.button("献立を提案"):
        if not gemini_configured_successfully:
            st.error("APIキーが正しく設定されていないため、献立を生成できません。")
        elif not ingredients_data:
            st.warning("食材がデータベースにありません。献立を提案できません。")
        else:
            with st.spinner("献立を生成中..."):
                try:
                    # --- ボタンが押された時にモデルを初期化する ---
                    model = genai.GenerativeModel(selected_model_name)

                    ingredient_list_for_prompt = []
                    for _, name, _, expiry_date, quantity in ingredients_data:
                        ingredient_list_for_prompt.append(f"{name} (期限: {expiry_date}, 数量: {quantity})")

                    prompt = f"""
                    以下の食材・分量・好み・その他条件を使用して、{menu_type if menu_type else ''}献立を提案してください。
                    提案は具体的なレシピ名、使用する食材、簡単な調理手順を含めてください。
                    食材リストにない食材は使用しないでください。使用する場合は最後に何を買うべきか提案してください。
                    献立検討時には以下リンクの情報を参考にして、提案する際には具体的なURLを添付してください。
                    https://panasonic.jp/cooking/recipe/autocooker.html
                    https://cookpad.com/jp
                    期限が近い食材を優先的に使用してください。
                    分量: {serving_size if serving_size else '指定なし'}
                    好み: {preferences if preferences else '指定なし'}
                    その他条件: {others_conditions if others_conditions else 'なし'}

                    食材リスト:
                    {', '.join(ingredient_list_for_prompt)}

                    提案例:
                    レシピ名: 鶏肉と野菜の炒め物
                    使用食材: 鶏もも肉、玉ねぎ、ピーマン、にんじん
                    調理手順: 1. 鶏肉と野菜を切る。2. フライパンで炒める。3. 塩コショウで味を調える。
                    """
                    
                    # Gemini API呼び出し
                    # response_stream = model.generate_content(prompt, stream=True)

                
                    response = model.generate_content(prompt)
                    suggested_menu = response.text
                
                except Exception as e:
                    # ここで詳細なエラーが表示される
                    st.error(f"Gemini API呼び出し中にエラーが発生しました: {e}")
                    suggested_menu = "献立の生成に失敗しました。"

                st.session_state.current_suggested_menu = suggested_menu
                st.rerun()
 
    with col_menu_output:
        st.subheader("提案された献立:")
    if 'current_suggested_menu' in st.session_state and st.session_state.current_suggested_menu:
        st.text_area("献立", st.session_state.current_suggested_menu, height=300, key="menu_output_area")


if __name__ == "__main__":
    show_recipe_proposer()