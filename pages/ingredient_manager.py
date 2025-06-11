import streamlit as st
import sqlite3
from datetime import datetime, timedelta
# import google.generativeai as genai # このファイルではGeminiは使わないのでコメントアウトか削除推奨
# import json # このファイルでは使わないのでコメントアウトか削除推奨
import os
import pandas as pd

# --- データベース関連の関数 ---
DATABASE_NAME = "food_items.db"

def init_db():
    """データベースを初期化し、テーブルを作成します。"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS food_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            purchase_date TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            quantity REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME) # 'food_items.db' ではなく DATABASE_NAME を使用
    conn.row_factory = sqlite3.Row
    return conn

def add_ingredient_to_db(name, purchase_date, expiry_date, quantity):
    """食材をデータベースに追加します。"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO food_items (name, purchase_date, expiry_date, quantity) VALUES (?, ?, ?, ?)",
            (name, purchase_date, expiry_date, quantity)
        )
        conn.commit()
        st.success("食材が追加されました。")
    except sqlite3.Error as e:
        st.error(f"食材の追加中にエラーが発生しました: {e}")
    finally:
        conn.close()

def get_all_ingredients():
    """データベースからすべての食材を取得し、期限が近い順にソートします。"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, purchase_date, expiry_date, quantity FROM food_items ORDER BY expiry_date ASC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def update_ingredient_quantity(ingredient_id, new_quantity):
    """データベースの食材の数量を更新します。"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE food_items SET quantity = ? WHERE id = ?', (new_quantity, ingredient_id))
        conn.commit()
        st.success(f"ID: {ingredient_id} の数量を {new_quantity} に更新しました。")
    except sqlite3.Error as e:
        st.error(f"数量の更新中にデータベースエラーが発生しました: {e}")
    finally:
        conn.close()

def delete_ingredient_from_db(ingredient_name_like):
    """指定された食材をデータベースから削除します（部分一致）。"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM food_items WHERE name LIKE ?", (f"%{ingredient_name_like}%",))
        deleted_count = cursor.rowcount
        conn.commit()
        return deleted_count
    except sqlite3.Error as e:
        st.error(f"食材の削除中にエラーが発生しました: {e}")
        return 0
    finally:
        conn.close()

def clear_database():
    """food_items テーブルのデータをすべて削除します。"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM food_items")
        conn.commit()
        st.success("データベースの食材データを初期化しました。")
    except sqlite3.Error as e:
        st.error(f"データベースの初期化中にエラーが発生しました: {e}")
    finally:
        conn.close()

# --- Streamlit UI ---
def show_ingredient_manager():
    st.header("献立生成AIアプリ")
    st.write("このアプリは、食材の管理と献立の提案を行います。")
    st.sidebar.header("設定")   

    # データベースの初期化（初回実行時のみ）
    if 'db_initialized' not in st.session_state:
        init_db()
        st.session_state.db_initialized = True # この行は init_db() の直後に移動

    # --- 食材追加セクション ---
    st.header("食材の追加")
    with st.form("add_ingredient_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("食材名:", key="ingredient_name_input")
            purchase_date_str = st.text_input("購入日 (YYYY-MM-DD):", value=datetime.now().strftime("%Y-%m-%d"), key="purchase_date_input")
        with col2:
            expiry_date_str = st.text_input("期限 (YYYY-MM-DD):", value=(datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"), key="expiry_date_input")
            quantity = st.number_input("数量:", min_value=0.01, value=1.0, step=0.1, key="quantity_input")
        submitted = st.form_submit_button("食材を追加")


    if submitted:
        if not all([name, purchase_date_str, expiry_date_str, quantity]):
            st.warning("すべてのフィールドを入力してください。")
        else:
            try:
                datetime.strptime(purchase_date_str, "%Y-%m-%d")
                datetime.strptime(expiry_date_str, "%Y-%m-%d")
                add_ingredient_to_db(name, purchase_date_str, expiry_date_str, quantity)
            except ValueError:
                st.error("日付はYYYY-MM-DD形式、数量は数値で入力してください。")

    # --- 現在の食材リスト表示セクション ---
    st.header("現在の食材リスト")
    ingredients_data = get_all_ingredients()

    if ingredients_data: # 食材データがある場合のみdata_editorと編集ロジックを表示
        data_for_df = []
        for row in ingredients_data:
            data_for_df.append(list(row))

        df_ingredients = pd.DataFrame(data_for_df, columns=["ID", "食材名", "購入日", "期限", "数量"])
        df_ingredients["購入日"] = pd.to_datetime(df_ingredients["購入日"])
        df_ingredients["期限"] = pd.to_datetime(df_ingredients["期限"])

        st.write("数量を直接編集できます。")

        edited_df = st.data_editor(
            df_ingredients,
            column_config={
                "ID": st.column_config.NumberColumn("ID", help="食材のID", disabled=True),
                "食材名": st.column_config.TextColumn("食材名", help="食材の名前", disabled=True),
                "購入日": st.column_config.DateColumn("購入日", help="購入した日付", format="YYYY/MM/DD", disabled=True),
                "期限": st.column_config.DateColumn("期限", help="食材の賞味期限または消費期限", format="YYYY/MM/DD", disabled=True),
                "数量": st.column_config.NumberColumn("数量", help="食材の数量", min_value=0.1, step=0.1, format="%.2f"), # REAL型に合わせて小数点以下2桁表示
            },
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            key="ingredient_editor" # ユニークなキー
        )
        # print("edited_df:", edited_df) # デバッグ用に編集後のDataFrameを表示
    if not df_ingredients.equals(edited_df):
        st.write("変更を検出しました！")
        for idx in range(len(df_ingredients)):
            if df_ingredients.loc[idx, "数量"] != edited_df.loc[idx, "数量"]:
                ingredient_id_to_update = edited_df.loc[idx, "ID"]
                new_quantity_value = edited_df.loc[idx, "数量"]
                # print(ingredient_id_to_update, new_quantity_value) # デバッグ用に変更されたIDと数量を表示
                update_ingredient_quantity(ingredient_id_to_update, new_quantity_value)
        st.rerun()
   



    # --- 個別の食材削除セクション ---
    st.subheader("個別の食材を削除")
    st.write("削除したい食材のIDを入力して削除ボタンを押すか、以下のリストから直接削除してください。")

    # 現在の食材リストを再度取得して表示（削除ボタン用）
    current_ingredients_for_delete = get_all_ingredients()
    if current_ingredients_for_delete:
        df_delete_view = pd.DataFrame(current_ingredients_for_delete, columns=["ID", "食材名", "購入日", "期限", "数量"])
        
        # # IDで削除するフォーム
        # delete_id_input = st.number_input("削除する食材のID", min_value=1, step=1, key="delete_id_input_ing_mgr")
        # if st.button("IDで削除", key="delete_by_id_btn_ing_mgr"):
        #     # IDによる削除関数は名前ではなくIDを受け取るように修正が必要
        #     # 例: delete_ingredient_by_id(delete_id_input) という関数を作成
        #     # 現在の delete_ingredient_from_db はnameを引数にとるので、IDで削除する関数を別に定義するか、既存を修正
        #     # ここでは仮にIDをname_likeとして渡し、部分一致で意図せず複数削除されるのを避けるために警告を出すか、ID検索用の関数を実装
        #     st.warning("現在、IDによる直接削除関数は実装されていません。食材名での削除か、以下のリストのボタンをご利用ください。")
        #     st.info("IDで削除するには、`delete_ingredient_by_id(ingredient_id)`のような新しい関数を実装する必要があります。")

        st.markdown("---")
        st.subheader("リストから削除")
        # 各行に削除ボタンを配置する
        for index, row in df_delete_view.iterrows():
            col1, col2, col3, col4, col5, col6 = st.columns([0.5, 2, 1.5, 1.5, 1, 1])

            with col1:
                st.write(row["ID"])
            with col2:
                st.write(row["食材名"])
            with col3:
                st.write(row["購入日"])
            with col4:
                st.write(row["期限"])
            with col5:
                st.write(f"{row['数量']:.2f}") # REAL型に合わせて小数点以下2桁表示
            with col6:
                if st.button("削除", key=f"delete_row_btn_ing_mgr_{row['ID']}"):
                    # ここでは食材名を引数にとる delete_ingredient_from_db を使用
                    # 完全一致で削除したい場合は、別途関数を定義することをお勧めします
                    deleted_count = delete_ingredient_from_db(row["食材名"])
                    if deleted_count > 0:
                        st.success(f"'{row['食材名']}' を削除しました。")
                    else:
                        st.error(f"'{row['食材名']}' の削除に失敗しました。")
                    st.rerun() # 削除後にリストを更新

    else:
        st.info("削除する食材がありません。")

    # データベースの初期化ボタン
    st.sidebar.button("全食材データをクリア", on_click=clear_database)

