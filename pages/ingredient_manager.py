import os
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import boto3  # AWSのライブラリ
import uuid   # DynamoDBのユニークなIDを生成するため

# --- DynamoDB関連の関数 ---
AWS_DEFAULT_REGION = "ap-northeast-1" # あなたが使用するAWSリージョン (例: 東京)
DYNAMODB_TABLE_NAME = "food_items" # あなたが作成したDynamoDBのテーブル名

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
def show_ingredient_manager():
    st.header("食材管理 (DynamoDB版)")
    st.write("このアプリは、食材の管理と献立の提案を行います。")
    st.sidebar.header("設定")

    # (既存のUIコードはここにそのままペースト... フォーム、リスト表示など)
    # --- 食材追加セクション ---
    st.header("食材の追加")
    with st.form("add_ingredient_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("食材名:")
            purchase_date_str = st.text_input("購入日 (YYYY-MM-DD):", value=datetime.now().strftime("%Y-%m-%d"))
        with col2:
            expiry_date_str = st.text_input("期限 (YYYY-MM-DD):", value=(datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"))
            quantity = st.text_input("数量:")
        submitted = st.form_submit_button("食材を追加")

    if submitted:
        if not all([name, purchase_date_str, expiry_date_str, quantity]):
            st.warning("すべてのフィールドを入力してください。")
        else:
            try:
                datetime.strptime(purchase_date_str, "%Y-%m-%d")
                datetime.strptime(expiry_date_str, "%Y-%m-%d")
                add_ingredient_to_db(name, purchase_date_str, expiry_date_str, quantity)
                st.rerun()
            except ValueError:
                st.error("日付はYYYY-MM-DD形式で入力してください。")

    # --- 現在の食材リスト表示セクション ---
    st.header("現在の食材リスト")
    ingredients_data = get_all_ingredients()
    if ingredients_data:
        df_ingredients = pd.DataFrame(ingredients_data, columns=["ID", "食材名", "購入日", "期限", "数量"])

        st.write("数量を直接編集できます。")
        edited_df = st.data_editor(
            df_ingredients,
            column_config={
                "ID": st.column_config.TextColumn("ID", disabled=True),
                "食材名": st.column_config.TextColumn("食材名", disabled=True),
                "購入日": st.column_config.TextColumn("購入日", disabled=True),
                "期限": st.column_config.TextColumn("期限", disabled=True),
                "数量": st.column_config.TextColumn("数量", disabled=False),
            },
            hide_index=True,
            use_container_width=True,
            key="ingredient_editor"
        )

        if st.button("変更を保存"):
            for i in range(len(edited_df)):
                if not df_ingredients.iloc[i].equals(edited_df.iloc[i]):
                    if df_ingredients.iloc[i]['数量'] != edited_df.iloc[i]['数量']:
                        update_ingredient_quantity(edited_df.iloc[i]['ID'], edited_df.iloc[i]['数量'])
            st.success("変更が保存されました。")
            st.rerun()
            
    else:
        st.info("現在、食材は登録されていません。")
    
    # --- 個別の食材削除セクション ---
    st.subheader("リストから削除")
    if ingredients_data:
        df_delete_view = pd.DataFrame(ingredients_data, columns=["ID", "食材名", "購入日", "期限", "数量"])
        for index, row in df_delete_view.iterrows():
            col1, col2, col3, col4, col5, col6 = st.columns([1.5, 2, 1.5, 1.5, 1, 1])
            with col1: st.write(row["ID"])
            with col2: st.write(row["食材名"])
            with col3: st.write(row["購入日"])
            with col4: st.write(row["期限"])
            with col5: st.write(row["数量"])
            with col6:
                if st.button("削除", key=f"delete_row_btn_ing_mgr_{row['ID']}"):
                    delete_ingredient_from_db(row['ID']) # 名前ではなくIDで削除
                    st.success(f"'{row['食材名']}' を削除しました。")
                    st.rerun()
    else:
        st.info("削除する食材がありません。")

    if st.sidebar.button("全食材データをクリア"):
        clear_database()
        st.rerun()



