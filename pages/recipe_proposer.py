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



#     # データベースの初期化（初回実行時のみ）
#     if 'db_initialized' not in st.session_state:
#         init_db()
#     st.session_state.db_initialized = True
#     # --- 食材追加セクション ---
#     st.header("食材の追加")
#     with st.form("add_ingredient_form", clear_on_submit=True): # clear_on_submit を使用
#         col1, col2 = st.columns(2)
#         submitted = st.form_submit_button("食材を追加")
#         with col1:
#             name = st.text_input("食材名:", key="ingredient_name_input")
#             purchase_date_str = st.text_input("購入日 (YYYY-MM-DD):", value=datetime.now().strftime("%Y-%m-%d"), key="purchase_date_input")
#         with col2:
#             expiry_date_str = st.text_input("期限 (YYYY-MM-DD):", value=(datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"), key="expiry_date_input")
#             quantity = st.number_input("数量:", min_value=0.01, value=1.0, step=0.1, key="quantity_input")


#     if submitted:
#         if not all([name, purchase_date_str, expiry_date_str, quantity]):
#             st.warning("すべてのフィールドを入力してください。")
#         else:
#             try:
#                 datetime.strptime(purchase_date_str, "%Y-%m-%d")
#                 datetime.strptime(expiry_date_str, "%Y-%m-%d")
#                 add_ingredient_to_db(name, purchase_date_str, expiry_date_str, quantity)
#                 # clear_on_submit=True を使用しているため、以下の手動リセットは不要になるはずです。
#                 # st.session_state.ingredient_name_input = ""
#                 # st.session_state.purchase_date_input = datetime.now().strftime("%Y-%m-%d")
#                 # st.session_state.expiry_date_input = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
#                 # st.session_state.quantity_input = 1.0
#             except ValueError:
#                 st.error("日付はYYYY-MM-DD形式、数量は数値で入力してください。")
#     # --- 食材リスト表示セクション ---
#     st.header("現在の食材リスト")
#     ingredients_data = get_all_ingredients()
#     if ingredients_data:
#     # Pandas DataFrameの作成
#     # get_all_ingredientsがsqlite3.Rowオブジェクトを返す場合、
#     # df = pd.DataFrame(ingredients_data) で直接列名が設定される場合があります。
#     # しかし、明示的にリストのリストとして渡す方が確実です。
#         data_for_df = []
#         for row in ingredients_data:
#             data_for_df.append(list(row)) # sqlite3.Rowオブジェクトをリストに変換
#     else:
#         st.info("データベースに食材がありません。")
#     df_ingredients = pd.DataFrame(data_for_df, columns=["ID", "食材名", "購入日", "期限", "数量"])
#  # ----------------------------------------------------
#     # st.data_editor を使用して編集可能なテーブルを表示
#     # ----------------------------------------------------
#     edited_df = st.data_editor(df_ingredients,
#         column_config={
#             # "ID" 列は表示するが編集不可にする
#             "ID": st.column_config.NumberColumn(
#                 "ID",
#                 help="食材のID",
#                 disabled=True # 編集不可
#             ),
#             # "食材名" 列は表示するが編集不可にする
#             "食材名": st.column_config.TextColumn(
#                 "食材名",
#                 help="食材の名前",
#                 disabled=True # 編集不可
#             ),
#             # "購入日" 列は表示するが編集不可にする
#             "購入日": st.column_config.DateColumn(
#                 "購入日",
#                 help="購入した日付",
#                 format="YYYY/MM/DD",
#                 disabled=True # 編集不可
#             ),
#             # "期限" 列は表示するが編集不可にする
#             "期限": st.column_config.DateColumn(
#                 "期限",
#                 help="食材の賞味期限または消費期限",
#                 format="YYYY/MM/DD",
#                 disabled=True # 編集不可
#             ),
#             # "数量" 列だけを編集可能にする
#             "数量": st.column_config.NumberColumn(
#                 "数量",
#                 help="食材の数量",
#                 min_value=0, # 最小値を設定（必要であれば）
#                 step=1,     # 編集時の増減ステップ
#                 format="%d", # 整数のフォーマット
#                 # editable=True はデフォルトなので明示的に書く必要はないが、
#                 # disabledでない列はeditableになる
#             )
#         },
#         hide_index=True, # DataFrameのインデックス列を非表示にする
#         use_container_width=True, # コンテナの幅に合わせて表示
#         num_rows="fixed", # 行の追加・削除を無効にする
#         key="ingredient_editor" # セッションステートで参照するためのユニークなキー
#     )

#     # # ユーザーが編集した内容を検出
#     # # edited_cellsには、変更されたセルの情報が辞書として格納されます
#     # if st.session_state.ingredient_editor.edited_cells:
#     #     st.write("変更を検出しました！")
#     #     # どのセルが変更されたかを確認
#     #     # st.session_state.ingredient_editor.edited_cells を直接表示することも可能
#     #     # st.write(st.session_state.ingredient_editor.edited_cells)

#     #     # 変更された行ごとに処理
#     #     for row_index, col_changes in st.session_state.ingredient_editor.edited_cells.items():
#     #         if "数量" in col_changes: # 数量列が変更された場合
#     #             ingredient_id_to_update = edited_df.loc[row_index, "ID"]
#     #             new_quantity_value = col_changes["数量"]

#     #             # データベースの更新関数を呼び出す
#     #             update_ingredient_quantity(ingredient_id_to_update, new_quantity_value)

#     #     # 変更を処理した後、edited_cellsをクリア（これはst.rerun()で自動的にクリアされることが多い）
#     #     # ただし、確実に状態をリセットしたい場合は手動でクリアすることも検討
#     #     # st.session_state.ingredient_editor.edited_cells = {}
#     #     st.rerun() # 変更をデータベースに反映後、UIを最新の状態に更新

#     # 編集前のdf_ingredientsと、編集後のedited_dfを比較して変更箇所を検出
#     if not df_ingredients.equals(edited_df):
#         st.write("変更を検出しました！")
#         for idx in range(len(df_ingredients)):
#             if df_ingredients.loc[idx, "数量"] != edited_df.loc[idx, "数量"]:
#                 ingredient_id_to_update = edited_df.loc[idx, "ID"]
#                 new_quantity_value = edited_df.loc[idx, "数量"]
#                 update_ingredient_quantity(ingredient_id_to_update, new_quantity_value)
#         # st.rerun()
#     else:
#         st.write("変更はありません。")

#     # # --- 現在の食材リスト表示セクション ---
#     # st.header("現在の食材")
#     # ingredients_data = get_all_ingredients()
#     # if ingredients_data:
#     # # Streamlitのdataframeは列名を自動で設定しないため、手動で指定
    
#     #     df_ingredients = pd.DataFrame(ingredients_data, columns=["ID", "食材名", "購入日", "期限", "数量"])
#     #     st.dataframe(df_ingredients, use_container_width=True)
#     # else:
#     #     st.info("データベースに食材がありません。")
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
            model = genai.GenerativeModel('gemini-1.5-flash')
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
        menu_options = ["主菜", "副菜", "汁物", "デザート"]
        size_options = ["1人前" , "2人前", "3人前", "4人前"]
        preferences_opions = ["和食", "洋食", "中華", "イタリアン", "その他"]
        menu_type = st.multiselect("献立の種類:", menu_options)
        serving_size = st.radio("分量： ", size_options)
        preferences = st.radio("好み:", preferences_opions)
        others_conditions = st.text_input("その他の条件:", placeholder="例: アレルギー、特定の食材を避けるなど")

    ingredients_data = get_all_ingredients()

    
    if st.button("献立を提案"):
        if not ingredients_data:
            st.warning("食材がデータベースにありません。献立を提案できません。")
        else:
            with st.spinner("献立を生成中..."):
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

                if model:
                    try:
                        # Gemini API呼び出し
                        response = model.generate_content(prompt)
                        suggested_menu = response.text
                    except Exception as e:
                        st.error(f"Gemini API呼び出し中にエラーが発生しました: {e}")
                        suggested_menu = "献立の生成に失敗しました。"
                else:
                    # ダミー応答
                    suggested_menu = f"""
                    レシピ名: 鶏肉と野菜の彩り炒め (ダミー)
                    使用食材: 鶏もも肉、玉ねぎ、ピーマン、にんじん、キャベツ
                    調理手順: ダミーの調理手順です。

                    レシピ名: 大根と豚バラの煮物 (ダミー)
                    使用食材: 大根、豚バラ肉、生姜
                    調理手順: ダミーの調理手順です。
                    """
                st.session_state.current_suggested_menu = suggested_menu
                st.rerun() # 献立表示を更新するため再実行

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