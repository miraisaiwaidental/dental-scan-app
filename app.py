"""
dental_web_app.py
歯列変化分析 Webアプリ（Streamlit）
"""

import streamlit as st
import tempfile
import os
import sys
from pathlib import Path

# ── ページ設定 ─────────────────────────────────────────
st.set_page_config(
    page_title="歯列変化分析ツール | mirai",
    page_icon="🦷",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── スタイル ───────────────────────────────────────────
st.markdown("""
<style>
  .stApp { background-color: #0f172a; color: #f1f5f9; }
  h1, h2, h3 { color: #f1f5f9; }
  .stButton > button {
    background-color: #3b82f6;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0.5rem 2rem;
    font-size: 1rem;
    font-weight: bold;
    width: 100%;
  }
  .stButton > button:hover { background-color: #2563eb; }
  .upload-box {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 1rem 1.5rem;
    margin-bottom: 0.5rem;
  }
  .stat-box {
    background: #1e293b;
    border-left: 4px solid #3b82f6;
    border-radius: 6px;
    padding: 0.8rem 1rem;
    margin: 0.3rem 0;
  }
  .section-title {
    color: #3b82f6;
    font-size: 0.85rem;
    font-weight: bold;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    border-bottom: 1px solid #334155;
    padding-bottom: 4px;
    margin: 1rem 0 0.6rem 0;
  }
  div[data-testid="stFileUploader"] {
    background: #1e293b;
    border-radius: 8px;
  }
</style>
""", unsafe_allow_html=True)


# ── パスワード認証 ─────────────────────────────────────
# ※ 本番環境では st.secrets["PASSWORD"] を使用
APP_PASSWORD = os.environ.get("APP_PASSWORD", "mirai2025")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("## 🦷 歯列変化分析ツール")
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### ログイン")
        pw = st.text_input("パスワード", type="password", placeholder="パスワードを入力")
        if st.button("ログイン"):
            if pw == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("パスワードが違います")
    st.stop()


# ── メインUI ───────────────────────────────────────────
st.markdown("# 🦷 歯列変化分析レポート")
st.markdown("スキャンデータをアップロードして変化を可視化します")
st.markdown("---")

col_left, col_right = st.columns([1, 2])

with col_left:
    # モード選択
    st.markdown('<div class="section-title">モード</div>', unsafe_allow_html=True)
    mode = st.radio(
        label="",
        options=["上顎 + 下顎（統合レポート）", "上顎のみ"],
        label_visibility="collapsed"
    )
    dual = (mode == "上顎 + 下顎（統合レポート）")

    # 患者情報
    st.markdown('<div class="section-title">患者情報</div>', unsafe_allow_html=True)
    patient_name = st.text_input("患者名", placeholder="例：山田太郎（匿名推奨）")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        date_before = st.text_input("初回日付", value="2024-04", placeholder="2024-04")
    with col_d2:
        date_after = st.text_input("経過後日付", value="2025-01", placeholder="2025-01")

    # ファイルアップロード
    st.markdown('<div class="section-title">スキャンデータ（STL）</div>', unsafe_allow_html=True)

    st.markdown("**上顎**")
    upper_before_file = st.file_uploader("初回スキャン", type=["stl"], key="ub",
                                          label_visibility="visible")
    upper_after_file  = st.file_uploader("経過後スキャン", type=["stl"], key="ua",
                                          label_visibility="visible")

    if dual:
        st.markdown("**下顎**")
        lower_before_file = st.file_uploader("初回スキャン", type=["stl"], key="lb",
                                              label_visibility="visible")
        lower_after_file  = st.file_uploader("経過後スキャン", type=["stl"], key="la",
                                              label_visibility="visible")
    else:
        lower_before_file = lower_after_file = None

    # 実行ボタン
    st.markdown("")
    run_btn = st.button("▶  分析を実行する")


with col_right:
    st.markdown('<div class="section-title">分析結果</div>', unsafe_allow_html=True)

    if run_btn:
        # バリデーション
        errors = []
        if not upper_before_file: errors.append("上顎 初回スキャン が未アップロードです")
        if not upper_after_file:  errors.append("上顎 経過後スキャン が未アップロードです")
        if dual:
            if not lower_before_file: errors.append("下顎 初回スキャン が未アップロードです")
            if not lower_after_file:  errors.append("下顎 経過後スキャン が未アップロードです")

        if errors:
            for e in errors:
                st.error(e)
        else:
            # 一時ファイルに保存して処理
            with tempfile.TemporaryDirectory() as tmpdir:
                def save_tmp(f, name):
                    p = os.path.join(tmpdir, name)
                    with open(p, "wb") as fp:
                        fp.write(f.read())
                    return p

                ub_path = save_tmp(upper_before_file, "upper_before.stl")
                ua_path = save_tmp(upper_after_file,  "upper_after.stl")

                if dual:
                    lb_path = save_tmp(lower_before_file, "lower_before.stl")
                    la_path = save_tmp(lower_after_file,  "lower_after.stl")

                pname = patient_name.strip() or "患者"
                db    = date_before.strip() or "初回"
                da    = date_after.strip() or "経過後"

                # 処理実行
                progress = st.progress(0, text="処理中...")
                status   = st.empty()

                try:
                    sys.path.insert(0, str(Path(__file__).parent))
                    from dental_scan_compare import (
                        generate_report, generate_dual_report
                    )

                    status.info("STLデータを読み込み・位置合わせ中...")
                    progress.progress(20)

                    if dual:
                        out = generate_dual_report(
                            ub_path, ua_path, lb_path, la_path,
                            output_dir=tmpdir,
                            patient_name=pname,
                            date_before=db,
                            date_after=da
                        )
                    else:
                        out = generate_report(
                            ub_path, ua_path,
                            output_dir=tmpdir,
                            patient_name=pname,
                            date_before=db,
                            date_after=da
                        )

                    progress.progress(100, text="完了！")
                    status.success("分析が完了しました")

                    # 結果画像表示
                    st.image(out, use_column_width=True)

                    # ダウンロードボタン
                    with open(out, "rb") as f:
                        fname = os.path.basename(out)
                        st.download_button(
                            label="📥  レポート画像をダウンロード",
                            data=f,
                            file_name=fname,
                            mime="image/png"
                        )

                except Exception as e:
                    progress.empty()
                    st.error(f"エラーが発生しました: {e}")
                    st.exception(e)
    else:
        st.markdown("""
        <div style="
            background: #1e293b;
            border-radius: 10px;
            padding: 3rem;
            text-align: center;
            color: #475569;
            margin-top: 2rem;
        ">
            <div style="font-size: 3rem">🦷</div>
            <div style="margin-top: 1rem; font-size: 1rem">
                左のパネルでSTLファイルを<br>アップロードして実行してください
            </div>
        </div>
        """, unsafe_allow_html=True)

# フッター
st.markdown("---")
st.markdown(
    '<div style="text-align:center; color:#475569; font-size:0.8rem">'
    '歯列変化分析ツール　|　医療法人mirai　|　院内専用システム'
    '</div>',
    unsafe_allow_html=True
)
