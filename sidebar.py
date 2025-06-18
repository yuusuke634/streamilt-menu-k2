# sidebar.py
import streamlit as st

def show_sidebar():
    st.sidebar.title("メニュー")
    selected_option = st.sidebar.radio(
        "機能を選択してください:",
        ("レシート読取(開発中)","食材リスト管理", "献立提案"),
        key="main_menu_radio" # サイドバーのラジオボタンにもキーを付ける
    )
    return selected_option