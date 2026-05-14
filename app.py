"""
dental_web_app.py
歯列変化分析 Webアプリ（Streamlit）
"""

import streamlit as st
import tempfile
import os
import sys
import zipfile
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
        with st.form("login_form"):
            pw = st.text_input("パスワード", type="password", placeholder="パスワードを入力")
            submitted = st.form_submit_button("ログイン", use_container_width=True)
        if submitted:
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
    # 患者情報
    st.markdown('<div class="section-title">患者情報</div>', unsafe_allow_html=True)
    patient_name = st.text_input("患者名", placeholder="例：山田太郎（匿名推奨）")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        date_before = st.text_input("初回日付", value="2024-04", placeholder="2024-04")
    with col_d2:
        date_after = st.text_input("経過後日付", value="2025-01", placeholder="2025-01")

    # ファイルアップロード（ZIP or STL）
    st.markdown('<div class="section-title">スキャンデータ</div>', unsafe_allow_html=True)

    st.markdown("**初回スキャン**")
    before_zip = st.file_uploader(
        "ZIPファイル（WESCAN書き出し）またはSTLファイル",
        type=["zip", "stl"], key="before",
        label_visibility="visible"
    )

    st.markdown("**経過後スキャン**")
    after_zip = st.file_uploader(
        "ZIPファイル（WESCAN書き出し）またはSTLファイル",
        type=["zip", "stl"], key="after",
        label_visibility="visible"
    )

    # 実行ボタン
    st.markdown("")
    run_btn = st.button("▶  分析を実行する")


with col_right:
    st.markdown('<div class="section-title">分析結果</div>', unsafe_allow_html=True)

    if run_btn:
        if not before_zip or not after_zip:
            st.error("初回・経過後の両方のファイルをアップロードしてください")
        else:
            with tempfile.TemporaryDirectory() as tmpdir:

                def extract_stls(uploaded_file, prefix):
                    """ZIP or STL を受け取り、{upper, lower} のパスdictを返す"""
                    found = {}
                    if uploaded_file.name.lower().endswith(".zip"):
                        zip_path = os.path.join(tmpdir, f"{prefix}.zip")
                        with open(zip_path, "wb") as fp:
                            fp.write(uploaded_file.read())
                        with zipfile.ZipFile(zip_path, "r") as zf:
                            for name in zf.namelist():
                                base = os.path.basename(name).lower()
                                for key in ("upper", "lower", "bite0", "bite1"):
                                    if base == f"{key}.stl":
                                        out_path = os.path.join(tmpdir, f"{prefix}_{key}.stl")
                                        with zf.open(name) as src, open(out_path, "wb") as dst:
                                            dst.write(src.read())
                                        found[key] = out_path
                    else:
                        # 単体STLファイル → upper として扱う
                        out_path = os.path.join(tmpdir, f"{prefix}_upper.stl")
                        with open(out_path, "wb") as fp:
                            fp.write(uploaded_file.read())
                        found["upper"] = out_path
                    return found

                before_stls = extract_stls(before_zip, "before")
                after_stls  = extract_stls(after_zip,  "after")

                # 検出されたファイルを表示
                def stl_badge(d):
                    keys = sorted(d.keys())
                    return "  ".join([f"✅ {k}" for k in keys])
                st.info(f"初回: {stl_badge(before_stls)}　　経過後: {stl_badge(after_stls)}")

                # モード自動判定
                has_upper = "upper" in before_stls and "upper" in after_stls
                has_lower = "lower" in before_stls and "lower" in after_stls
                dual = has_upper and has_lower

                if not has_upper:
                    st.error("upper.stl が見つかりません。ZIPの内容を確認してください。")
                    st.stop()

                pname = patient_name.strip() or "患者"
                db    = date_before.strip() or "初回"
                da    = date_after.strip() or "経過後"

                progress = st.progress(0, text="処理中...")
                status   = st.empty()

                try:
                    sys.path.insert(0, str(Path(__file__).parent))
                    from dental_scan_compare import generate_report, generate_dual_report

                    status.info("STLデータを読み込み・位置合わせ中...")
                    progress.progress(20)

                    if dual:
                        out = generate_dual_report(
                            before_stls["upper"], after_stls["upper"],
                            before_stls["lower"], after_stls["lower"],
                            output_dir=tmpdir,
                            patient_name=pname,
                            date_before=db,
                            date_after=da
                        )
                    else:
                        out = generate_report(
                            before_stls["upper"], after_stls["upper"],
                            output_dir=tmpdir,
                            patient_name=pname,
                            date_before=db,
                            date_after=da
                        )

                    progress.progress(100, text="完了！")
                    status.success(f"分析完了（{'上顎+下顎' if dual else '上顎のみ'}）")

                    st.image(out, use_column_width=True)

                    with open(out, "rb") as f:
                        st.download_button(
                            label="📥  レポート画像をダウンロード",
                            data=f,
                            file_name=os.path.basename(out),
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
