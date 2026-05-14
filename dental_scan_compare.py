"""
dental_scan_compare.py
小児矯正 歯列スキャン変化可視化ツール
使い方: python dental_scan_compare.py before.stl after.stl [患者名] [初回日付] [経過日付]
"""

import sys
import os

# Windowsでリアルタイム出力を保証
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import builtins as _builtins
_orig_print = _builtins.print
def print(*args, **kwargs):
    kwargs.setdefault("flush", True)
    _orig_print(*args, **kwargs)

import numpy as np
import trimesh
import trimesh.registration
import matplotlib
matplotlib.use('Agg')
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import matplotlib.cm as cm

# 日本語フォント設定（リポジトリ内フォント → Windowsフォント の順で試みる）
_FONT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "NotoSansJP.ttf")
if os.path.exists(_FONT_FILE):
    fm.fontManager.addfont(_FONT_FILE)
    matplotlib.rcParams['font.family'] = fm.FontProperties(fname=_FONT_FILE).get_name()
else:
    _JP_FONTS = ["Meiryo", "Yu Gothic", "MS Gothic", "MS Mincho"]
    for _f in _JP_FONTS:
        if any(_f.lower() in p.name.lower() for p in fm.fontManager.ttflist):
            matplotlib.rcParams['font.family'] = _f
            break
from matplotlib.colors import Normalize, LinearSegmentedColormap
from scipy.spatial import KDTree


ACCENT = "#3b82f6"

# ── カラーマップ（青→緑→黄→赤）─────────────────────────────
DENTAL_CMAP = LinearSegmentedColormap.from_list(
    "dental",
    ["#2563eb", "#22c55e", "#facc15", "#ef4444"],
    N=256
)


def load_stl(path):
    mesh = trimesh.load(path, force="mesh")
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(list(mesh.geometry.values()))
    mesh.fix_normals()
    return mesh


def center_mesh(mesh):
    mesh.vertices -= mesh.centroid
    return mesh


def icp_register(source_mesh, target_mesh):
    """trimesh内蔵ICPでsourceをtargetに位置合わせし、変換行列を返す"""
    print("  位置合わせ（ICP）実行中...")
    src_pts = source_mesh.sample(20000)
    tgt_pts = target_mesh.sample(20000)
    matrix, _, cost = trimesh.registration.icp(
        src_pts, tgt_pts,
        max_iterations=100,
        threshold=1e-5
    )
    print(f"  ICP cost: {cost:.4f}")
    return matrix


def compute_vertex_distances(source_mesh, target_mesh):
    """source各頂点からtargetメッシュ面への最近傍距離を計算"""
    print("  距離計算中...")
    tree = KDTree(target_mesh.vertices)
    distances, _ = tree.query(source_mesh.vertices, workers=-1)
    return distances.astype(np.float32)


def sample_surface_with_distances(mesh, distances, n_points=80000):
    """メッシュ面上に均一に点をサンプリングし、距離を補間する"""
    pts, face_idx = trimesh.sample.sample_surface(mesh, n_points)
    # 各サンプル点の距離 = その面の頂点距離の平均
    sampled_dist = distances[mesh.faces[face_idx]].mean(axis=1)
    return pts, sampled_dist


def render_view(ax, pts, dist_colors_rgba, verts, elev, azim, title):
    ax.set_facecolor("#0f172a")
    ax.scatter(
        pts[:, 0], pts[:, 1], pts[:, 2],
        c=dist_colors_rgba,
        s=0.4,
        alpha=0.85,
        linewidths=0,
        depthshade=True,
        rasterized=True
    )
    ax.set_xlim(verts[:, 0].min(), verts[:, 0].max())
    ax.set_ylim(verts[:, 1].min(), verts[:, 1].max())
    ax.set_zlim(verts[:, 2].min(), verts[:, 2].max())
    ax.set_box_aspect([
        np.ptp(verts[:, 0]),
        np.ptp(verts[:, 1]),
        np.ptp(verts[:, 2])
    ])
    ax.view_init(elev=elev, azim=azim)
    ax.axis("off")
    ax.set_title(title, color="white", fontsize=11, pad=4)


def generate_report(
    stl_before, stl_after,
    output_dir=".",
    patient_name="患者名",
    date_before="初回",
    date_after="経過後"
):
    print(f"\n{'='*50}")
    print(f"  {patient_name}  {date_before} → {date_after}")
    print(f"{'='*50}")

    print("\n[1/4] STLデータ読み込み中...")
    mesh_before = load_stl(stl_before)
    mesh_after  = load_stl(stl_after)
    print(f"  初回: {len(mesh_before.vertices):,}頂点 / {len(mesh_before.faces):,}面")
    print(f"  経過: {len(mesh_after.vertices):,}頂点 / {len(mesh_after.faces):,}面")

    center_mesh(mesh_before)
    center_mesh(mesh_after)

    print("\n[2/4] 位置合わせ中...")
    transform = icp_register(mesh_before, mesh_after)
    mesh_before.apply_transform(transform)

    print("\n[3/4] 変化量を計算中...")
    distances = compute_vertex_distances(mesh_before, mesh_after)
    max_dist   = float(np.percentile(distances, 95))
    mean_dist  = float(distances.mean())
    print(f"  平均変化: {mean_dist:.2f} mm")
    print(f"  最大変化 (95th): {max_dist:.2f} mm")

    # 表面を均一サンプリングして点群を生成
    norm = Normalize(vmin=0, vmax=max(max_dist, 0.01))
    pts, pt_dist = sample_surface_with_distances(mesh_before, distances, n_points=80000)
    pt_rgba = DENTAL_CMAP(norm(pt_dist))

    print("\n[4/4] レポート画像を生成中...")
    fig = plt.figure(figsize=(22, 13), facecolor="#0f172a")
    fig.patch.set_facecolor("#0f172a")

    title_str = (
        f"歯列変化分析レポート　　"
        f"{patient_name}　　"
        f"{date_before}  →  {date_after}"
    )
    fig.suptitle(title_str, color="white", fontsize=15, y=0.99, fontproperties=None)

    views = [
        (10,  180, "正面"),
        (10,    0, "後面"),
        (10,   90, "右側面"),
        (10,  -90, "左側面"),
        (85,    0, "咬合面（上）"),
        (-85,   0, "舌側面（下）"),
    ]

    for i, (elev, azim, label) in enumerate(views):
        ax = fig.add_subplot(2, 3, i + 1, projection="3d")
        render_view(ax, pts, pt_rgba, mesh_before.vertices, elev, azim, label)

    # カラーバー
    ax_cb = fig.add_axes([0.91, 0.12, 0.012, 0.72])
    sm = cm.ScalarMappable(cmap=DENTAL_CMAP, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, cax=ax_cb)
    cbar.set_label("変化量 (mm)", color="white", fontsize=11, labelpad=8)
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")
    ax_cb.set_facecolor("#0f172a")

    # 統計テキスト
    stats_text = (
        f"平均変化: {mean_dist:.2f} mm\n"
        f"最大変化: {max_dist:.2f} mm\n"
        f"─────────────\n"
        f"青  = 変化小\n"
        f"緑  = 中程度\n"
        f"黄  = やや大\n"
        f"赤  = 変化大"
    )
    fig.text(
        0.91, 0.07, stats_text,
        color="white", fontsize=9,
        verticalalignment="bottom",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#1e293b", edgecolor="#334155")
    )

    plt.subplots_adjust(
        left=0.01, right=0.90, top=0.96, bottom=0.01,
        wspace=0.02, hspace=0.05
    )

    # 出力ファイル名
    safe_name = patient_name.replace(" ", "_").replace("/", "-")
    out_file = os.path.join(
        output_dir,
        f"dental_compare_{safe_name}_{date_before}_{date_after}.png"
    )
    plt.savefig(out_file, dpi=150, bbox_inches="tight",
                facecolor="#0f172a", pad_inches=0.1)
    plt.close()

    print(f"\n  完了: {out_file}")
    print(f"{'='*50}\n")
    return out_file


def _process_arch(stl_before, stl_after, label):
    """1つのアーチを処理してサンプル点・距離・統計を返す"""
    print(f"\n  [{label}] 読み込み中...")
    mb = load_stl(stl_before)
    ma = load_stl(stl_after)
    print(f"    初回: {len(mb.vertices):,}頂点  経過: {len(ma.vertices):,}頂点")
    center_mesh(mb)
    center_mesh(ma)
    print(f"  [{label}] 位置合わせ中...")
    mb.apply_transform(icp_register(mb, ma))
    print(f"  [{label}] 距離計算中...")
    dist = compute_vertex_distances(mb, ma)
    mean_d = float(dist.mean())
    max_d  = float(np.percentile(dist, 95))
    print(f"    平均変化: {mean_d:.2f} mm  最大変化: {max_d:.2f} mm")
    pts, pt_dist = sample_surface_with_distances(mb, dist, n_points=80000)
    return pts, pt_dist, mb.vertices, mean_d, max_d


def generate_dual_report(
    upper_before, upper_after,
    lower_before, lower_after,
    output_dir=".",
    patient_name="患者名",
    date_before="初回",
    date_after="経過後"
):
    print(f"\n{'='*55}")
    print(f"  {patient_name}  {date_before} → {date_after}  [上顎+下顎]")
    print(f"{'='*55}")

    u_pts, u_dist, u_verts, u_mean, u_max = _process_arch(upper_before, upper_after, "上顎")
    l_pts, l_dist, l_verts, l_mean, l_max = _process_arch(lower_before, lower_after, "下顎")

    # 上下共通のカラースケール
    shared_max = max(u_max, l_max, 0.01)
    norm = Normalize(vmin=0, vmax=shared_max)
    u_rgba = DENTAL_CMAP(norm(u_dist))
    l_rgba = DENTAL_CMAP(norm(l_dist))

    print("\n  レポート画像を生成中...")

    # 2行×3列レイアウト（行ラベル付き）
    fig = plt.figure(figsize=(22, 14), facecolor="#0f172a")
    fig.patch.set_facecolor("#0f172a")

    title_str = (
        f"歯列変化分析レポート　　{patient_name}　　{date_before}  →  {date_after}"
    )
    fig.suptitle(title_str, color="white", fontsize=15, y=0.99)

    # 上顎のビュー：正面 / 咬合面（上から） / 右側面
    upper_views = [(10, 90, "正面"), (85, 90, "咬合面（上）"), (10, 180, "右側面")]
    # 下顎のビュー：正面 / 咬合面（下から） / 右側面
    lower_views = [(10, 90, "正面"), (-85, 90, "咬合面（下）"), (10, 180, "右側面")]

    row_labels = [("上顎", 0.74), ("下顎", 0.26)]

    for col, (elev, azim, label) in enumerate(upper_views):
        ax = fig.add_subplot(2, 3, col + 1, projection="3d")
        render_view(ax, u_pts, u_rgba, u_verts, elev, azim, label)

    for col, (elev, azim, label) in enumerate(lower_views):
        ax = fig.add_subplot(2, 3, col + 4, projection="3d")
        render_view(ax, l_pts, l_rgba, l_verts, elev, azim, label)

    # 行ラベル（上顎 / 下顎）
    for text, y in row_labels:
        fig.text(0.005, y, text, color=ACCENT, fontsize=13, fontweight="bold",
                 va="center", rotation="vertical")

    # カラーバー
    ax_cb = fig.add_axes([0.915, 0.12, 0.012, 0.72])
    sm = cm.ScalarMappable(cmap=DENTAL_CMAP, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, cax=ax_cb)
    cbar.set_label("変化量 (mm)", color="white", fontsize=11, labelpad=8)
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")
    ax_cb.set_facecolor("#0f172a")

    # 統計テキスト
    stats_text = (
        f"【上顎】\n"
        f"  平均: {u_mean:.2f} mm\n"
        f"  最大: {u_max:.2f} mm\n"
        f"\n"
        f"【下顎】\n"
        f"  平均: {l_mean:.2f} mm\n"
        f"  最大: {l_max:.2f} mm\n"
        f"\n─────────\n"
        f"青 = 変化小\n"
        f"緑 = 中程度\n"
        f"黄 = やや大\n"
        f"赤 = 変化大"
    )
    fig.text(
        0.915, 0.07, stats_text,
        color="white", fontsize=9,
        verticalalignment="bottom",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#1e293b", edgecolor="#334155")
    )

    plt.subplots_adjust(
        left=0.025, right=0.905, top=0.96, bottom=0.01,
        wspace=0.02, hspace=0.05
    )

    safe_name = patient_name.replace(" ", "_").replace("/", "-")
    out_file = os.path.join(
        output_dir,
        f"dental_compare_{safe_name}_{date_before}_{date_after}_dual.png"
    )
    plt.savefig(out_file, dpi=150, bbox_inches="tight",
                facecolor="#0f172a", pad_inches=0.1)
    plt.close()

    print(f"\n  完了: {out_file}")
    print(f"{'='*55}\n")
    return out_file


if __name__ == "__main__":
    args = sys.argv[1:]

    # 上顎+下顎モード: 7引数
    # python dental_scan_compare.py upper_before lower_before upper_after lower_after 患者名 日付1 日付2
    if len(args) >= 4 and all(
        a.lower().endswith(".stl") for a in args[:4]
    ):
        upper_before = args[0]
        upper_after  = args[1]
        lower_before = args[2]
        lower_after  = args[3]
        patient_name = args[4] if len(args) > 4 else "患者名"
        date_before  = args[5] if len(args) > 5 else "初回"
        date_after   = args[6] if len(args) > 6 else "経過後"
        output_dir   = os.path.dirname(os.path.abspath(upper_before))
        generate_dual_report(
            upper_before, upper_after,
            lower_before, lower_after,
            output_dir=output_dir,
            patient_name=patient_name,
            date_before=date_before,
            date_after=date_after
        )
    # 単体モード: 2引数
    elif len(args) >= 2:
        stl_before   = args[0]
        stl_after    = args[1]
        patient_name = args[2] if len(args) > 2 else "患者名"
        date_before  = args[3] if len(args) > 3 else "初回"
        date_after   = args[4] if len(args) > 4 else "経過後"
        output_dir   = os.path.dirname(os.path.abspath(stl_before))
        generate_report(
            stl_before, stl_after,
            output_dir=output_dir,
            patient_name=patient_name,
            date_before=date_before,
            date_after=date_after
        )
    else:
        print("使い方（上顎のみ）:")
        print("  python dental_scan_compare.py upper_before.stl upper_after.stl 患者名 初回日付 経過日付")
        print("\n使い方（上顎+下顎）:")
        print("  python dental_scan_compare.py upper_before.stl upper_after.stl lower_before.stl lower_after.stl 患者名 初回 経過後")
        sys.exit(1)
