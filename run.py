import streamlit as st
import sqlite3
from datetime import datetime, timedelta
import google.generativeai as genai
import json # For parsing potential structured responses from Gemini, though not strictly used for current dummy.
import os
import pandas as pd
import streamlit as st
import sqlite3 # データベースの初期化のため
from sidebar import show_sidebar # sidebar.pyからサイドバー関数をインポート
from pages.ingredient_manager import show_ingredient_manager # 食材管理ページをインポート
from pages.recipe_proposer import show_recipe_proposer     # 献立提案ページをインポート
from pages.receipt_scanner import show_receipt_scanner


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






# --- Streamlitアプリのメイン部分 ---
st.set_page_config(layout="wide") # ページレイアウトをワイドに設定

# サイドバーのUIを表示し、選択されたオプションを取得
selected_option = show_sidebar()

# 選択されたオプションに基づいてメインコンテンツを切り替え
if selected_option == "食材リスト管理":
    show_ingredient_manager() # 食材管理ページの関数を呼び出す
elif selected_option == "献立提案":
    show_recipe_proposer()    # 献立提案ページの関数を呼び出す
elif selected_option == "レシート読取":
    show_receipt_scanner()    # 献立提案ページの関数を呼び出す