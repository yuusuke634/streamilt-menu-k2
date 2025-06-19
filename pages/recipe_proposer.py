import streamlit as st
import sqlite3
from datetime import datetime, timedelta
import google.generativeai as genai
import json # For parsing potential structured responses from Gemini, though not strictly used for current dummy.
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
    conn = sqlite3.connect('food_items.db')
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
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE food_items SET quantity = ? WHERE id = ?', (new_quantity, ingredient_id))
    conn.commit()
    conn.close()
    st.success(f"ID: {ingredient_id} の数量を {new_quantity} に更新しました。")


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




    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        gemini_configured_successfully = True
    except Exception as e:
        st.error(f"Gemini APIの設定中にエラーが発生しました: {e}")



# # --- データベースの初期化ボタン ---
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
def show_recipe_proposer():
    st.header("献立生成")
    st.write("現在登録されている食材を使って、献立を提案します。")
   

    # --- 献立提案セクション ---
    # Google Gemini APIの設定
    # api_key = st.secrets["GOOGLE_API_KEY"]
    api_key = os.environ.get("GOOGLE_API_KEY")
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
                    response = model.generate_content(prompt)
                    suggested_menu = response.text
                
                except Exception as e:
                    # ここで詳細なエラーが表示される
                    st.error(f"Gemini API呼び出し中にエラーが発生しました: {e}")
                    suggested_menu = "献立の生成に失敗しました。"

                st.session_state.current_suggested_menu = suggested_menu
                st.rerun()
    # if st.button("献立を提案"):
    #     if not ingredients_data:
    #         st.warning("食材がデータベースにありません。献立を提案できません。")
    #     else:
    #         with st.spinner("献立を生成中..."):
    #             ingredient_list_for_prompt = []
    #             for _, name, _, expiry_date, quantity in ingredients_data:
    #                 ingredient_list_for_prompt.append(f"{name} (期限: {expiry_date}, 数量: {quantity})")

    #             prompt = f"""
    #             以下の食材・分量・好み・その他条件を使用して、{menu_type if menu_type else ''}献立を提案してください。
    #             提案は具体的なレシピ名、使用する食材、簡単な調理手順を含めてください。
    #             食材リストにない食材は使用しないでください。使用する場合は最後に何を買うべきか提案してください。
    #             献立検討時には以下リンクの情報を参考にして、提案する際には具体的なURLを添付してください。
    #             https://panasonic.jp/cooking/recipe/autocooker.html
    #             https://cookpad.com/jp
    #             期限が近い食材を優先的に使用してください。
    #             分量: {serving_size if serving_size else '指定なし'}
    #             好み: {preferences if preferences else '指定なし'}
    #             その他条件: {others_conditions if others_conditions else 'なし'}

    #             食材リスト:
    #             {', '.join(ingredient_list_for_prompt)}

    #             提案例:
    #             レシピ名: 鶏肉と野菜の炒め物
    #             使用食材: 鶏もも肉、玉ねぎ、ピーマン、にんじん
    #             調理手順: 1. 鶏肉と野菜を切る。2. フライパンで炒める。3. 塩コショウで味を調える。
    #             """

    #             if selected_model:
    #                 try:
    #                     # Gemini API呼び出し
    #                     response = selected_model.generate_content(prompt)
    #                     suggested_menu = response.text
    #                 except Exception as e:
    #                     st.error(f"Gemini API呼び出し中にエラーが発生しました: {e}")
    #                     suggested_menu = "献立の生成に失敗しました。"
    #             else:
    #                 # ダミー応答
    #                 suggested_menu = f"""
    #                 レシピ名: 鶏肉と野菜の彩り炒め (ダミー)
    #                 使用食材: 鶏もも肉、玉ねぎ、ピーマン、にんじん、キャベツ
    #                 調理手順: ダミーの調理手順です。

    #                 レシピ名: 大根と豚バラの煮物 (ダミー)
    #                 使用食材: 大根、豚バラ肉、生姜
    #                 調理手順: ダミーの調理手順です。
    #                 """
    #             st.session_state.current_suggested_menu = suggested_menu
    #             st.rerun() # 献立表示を更新するため再実行

    with col_menu_output:
        st.subheader("提案された献立:")
    if 'current_suggested_menu' in st.session_state and st.session_state.current_suggested_menu:
        st.text_area("献立", st.session_state.current_suggested_menu, height=300, key="menu_output_area")
        # if st.button("この献立を選択"):
        #     suggested_menu_text = st.session_state.current_suggested_menu
        #     lines = suggested_menu_text.split('\n')
        #     used_ingredients = set()
        #     for line in lines:
        #         if "使用食材:" in line:
        #             ingredients_str = line.split("使用食材:")[1].strip()
        #             # カンマ、句読点、スペースで分割し、重複を避けるためにセットに追加
        #             for item in ingredients_str.replace("、", ",").replace(" ", "").split(','):
        #                 if item:
        #                     used_ingredients.add(item.strip())

    #         if not used_ingredients:
    #             st.warning("使用された食材を特定できませんでした。")
    #         else:
    #             # Streamlitではmessagebox.askyesnoの代わりに確認UIを構築
    #             st.write(f"以下の食材をデータベースから削除しますか？\n{', '.join(used_ingredients)}")
    #             if st.button("はい、削除します"):
    #                 total_deleted_count = 0
    #                 for ingredient_name in used_ingredients:
    #                     deleted_count = delete_ingredient_from_db(ingredient_name)
    #                     total_deleted_count += deleted_count
    #                 st.success(f"{total_deleted_count}個の食材がデータベースから削除されました。")
    #                 st.session_state.current_suggested_menu = "" # 献立をクリア
    #                 st.rerun() # リストを更新するため再実行
    #             elif st.button("いいえ、削除しません"):
    #                 st.info("食材の削除はキャンセルされました。")
    # else:
    #     st.info("献立を提案してください。")

if __name__ == "__main__":
    show_recipe_proposer()