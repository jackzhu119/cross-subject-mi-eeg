#!/usr/bin/env python3
"""Render publication figures from frozen, already-audited result tables only.

No raw EEG, fitted estimator, checkpoint, training, inference, resampling or new
hypothesis test is performed. Numerical CSV inputs are copied byte-for-byte and
derived plotting columns are deterministic unit conversions/reorderings.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from matplotlib.lines import Line2D
from matplotlib.text import Text
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
FROZEN = REPO / "research_runs/ELIGIBLE_V3_RESULTS_20261018"
AUDIT = FROZEN / "audits/external"
DATA = HERE / "figure_data"
TABLES = HERE / "tables"
FIGURES = HERE / "figures"
TIFF_DPI = 600
PREVIEW_DPI = 300
LEVELS = ["S9", "S29", "S60"]
RULES = ["fixed20", "mean_ce", "mean_rank", "mean_ba", "tail_ce",
         "tail_ba", "mean_min_recall", "tail_min_recall"]
RULE_LABELS = ["Fixed epoch 20", "Mean cross-entropy", "Mean rank",
               "Mean balanced accuracy", "Tail cross-entropy",
               "Tail balanced accuracy", "Mean weaker-class recall",
               "Tail weaker-class recall"]
BLUE, ORANGE, GREY = "#176A9A", "#B76722", "#59616B"
META = []


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def readcsv(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def writecsv(path, rows, fields=None):
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plain_axes(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#8B9198")
    ax.tick_params(length=3, width=.7)
    ax.set_axisbelow(True)


def save(fig, stem):
    # Exactly 6.8 inches wide; no tight bounding-box resize of figure dimensions.
    fig.canvas.draw()
    renderer=fig.canvas.get_renderer()
    width,height=fig.canvas.get_width_height()
    for text in fig.findobj(match=Text):
        if not text.get_visible() or not text.get_text():
            continue
        bounds=text.get_window_extent(renderer)
        if bounds.x0 < -1 or bounds.y0 < -1 or bounds.x1 > width+1 or bounds.y1 > height+1:
            raise ValueError(f"figure_text_outside_canvas:{stem}:{text.get_text()}")
    png = FIGURES / (stem + ".png")
    fig.savefig(png, dpi=PREVIEW_DPI, facecolor="white")
    fig.savefig(FIGURES / (stem + ".svg"), facecolor="white")
    fig.savefig(FIGURES / (stem + ".pdf"), facecolor="white")
    # Render directly at submission resolution, rather than upsampling the PNG.
    raster=io.BytesIO()
    fig.savefig(raster,format="png",dpi=TIFF_DPI,facecolor="white")
    raster.seek(0)
    with Image.open(raster) as image:
        image.convert("RGB").save(FIGURES / (stem + ".tif"),
                                  compression="tiff_lzw", dpi=(TIFF_DPI, TIFF_DPI))
    tiff = FIGURES / (stem + ".tif")
    with Image.open(tiff) as image:
        assert image.width == round(6.8*TIFF_DPI)
        assert image.info["compression"] == "tiff_lzw"
        assert tiff.stat().st_size < 10_000_000
        META.append({"figure": stem, "width_inches": 6.8,
                     "height_inches": fig.get_figheight(),
                     "width_pixels": image.width, "height_pixels": image.height,
                     "dpi": [float(x) for x in image.info["dpi"]],
                     "color_mode": image.mode, "compression": "tiff_lzw",
                     "tiff_bytes": tiff.stat().st_size, "sha256": digest(tiff)})
    plt.close(fig)


def workflow():
    fig, ax = plt.subplots(figsize=(6.8, 6.25))
    fig.subplots_adjust(left=.025, right=.975, bottom=.025, top=.975)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")

    def box(x, y, w, h, title, body, color=BLUE, fs=8.4):
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                     boxstyle="round,pad=0.045,rounding_size=0.08",
                     facecolor="white", edgecolor=color, linewidth=1.0))
        ax.text(x+w/2, y+h-.20, title, ha="center", va="top",
                fontsize=9.0, weight="bold", color=color)
        ax.text(x+w/2, y+h/2-.14, body, ha="center", va="center",
                fontsize=fs, linespacing=1.40)

    def arrow(start, end):
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>",
                     mutation_scale=10, color=GREY, linewidth=.9))

    box(.15, 8.45, 9.70, 1.35, "A   Frozen source configurations",
        "S9: 9 BNCI participants / 2,592 trials\n"
        "S29: BNCI + 20 Yang participants / 14,590 trials\n"
        "S60: BNCI + 51 Yang participants / 33,183 trials")
    box(.15, 6.60, 9.70, 1.35, "B   One dimensionless processing recipe",
        "18 common channels · common-average reference · 160 Hz · 2-s crops\n"
        "BROAD: 8–30 Hz     Shared: μ 8–13 Hz + β 13–30 Hz\n"
        "Per-channel temporal centering; common within-trial broadband RMS")
    arrow((5, 8.42), (5, 8.00))
    box(.15, 4.48, 4.60, 1.62, "C   Source-only selection",
        "5 whole-participant validation folds\n3 validation seeds → 90 trajectories\n"
        "8 frozen rules → 48 selected epochs\nEqual dataset / participant weighting")
    box(5.25, 4.48, 4.60, 1.62, "D   Final source training",
        "3 final seeds → 18 trajectories\n40 epochs × 128 updates per trajectory\n"
        "50:50 BNCI:Yang sampling (S29/S60)\n144 outputs / 99 distinct checkpoints")
    arrow((2.45, 6.56), (2.45, 6.15))
    arrow((7.55, 6.56), (7.55, 6.15))
    arrow((4.82, 5.30), (5.18, 5.30))
    box(.15, 2.12, 9.70, 1.86, "E   Frozen external scoring · exploratory Dreyer evaluation",
        "85 participants × 80 trials = 6,800 unique trials\n"
        "Event/class metadata: eligibility and class mapping\n"
        "Ground-truth labels: scoring only; no target fitting or model selection\n"
        "Per-seed class recalls → within-participant seed averages → paired inference")
    arrow((2.45, 4.44), (2.45, 4.03))
    arrow((7.55, 4.44), (7.55, 4.03))
    box(.15, .12, 9.70, 1.50, "F   Evidence checks with defined scope", 
        "Source identities / contracts / checkpoint and selector bindings\n"
        "Saved predictions → participant metrics → four frozen contrasts\n"
        "1,179 external arithmetic checks passed; no checkpoint-forward replay", GREY)
    arrow((5, 2.08), (5, 1.67))
    save(fig, "Fig1_workflow")


def contrasts(rows):
    order = ["primary_source_expansion_min_recall", "secondary_selector_min_recall",
             "secondary_larger_source_min_recall", "secondary_source_expansion_ba"]
    rows = sorted(rows, key=lambda r: order.index(r["name"]))
    fig = plt.figure(figsize=(6.8, 4.20))
    gs = fig.add_gridspec(1, 3, width_ratios=[2.40, 2.45, 2.05], wspace=.06,
                         left=.02, right=.99, bottom=.18, top=.83)
    label, ax, values = [fig.add_subplot(gs[0, i]) for i in range(3)]
    labels = ["Primary: S60 − S9\nWeaker-class recall",
              "Secondary: tail − mean-BA rule\nS60 weaker-class recall",
              "Secondary: S60 − S29\nWeaker-class recall",
              "Secondary: S60 − S9\nBalanced accuracy"]
    for i, (r, text) in enumerate(zip(rows, labels)):
        y = 3-i
        mean, lo, hi = [float(r[k])*100 for k in ["mean", "t_ci95_low", "t_ci95_high"]]
        color = BLUE if i == 0 else ORANGE
        ax.errorbar(mean, y, xerr=[[mean-lo], [hi-mean]], fmt="o" if i == 0 else "s",
                    color=color, markerfacecolor=color if i == 0 else "white",
                    markeredgewidth=1.2, markersize=5, capsize=3, elinewidth=1.3)
        label.text(.0, y, text, ha="left", va="center", fontsize=8.2, linespacing=1.45)
        if i==0:
            pv=f"Raw p = {float(r['p_two_sided']):.3g}"
        else:
            p=float(r['p_holm'])
            pv="Holm p = "+(f"{p:.4f}" if p>=.001 else f"{p:.3g}")
        values.text(.0, y, f"{mean:+.2f} [{lo:+.2f}, {hi:+.2f}]\n{pv}",
                    ha="left", va="center", fontsize=8.2, linespacing=1.45)
    for panel in [label, ax, values]:
        panel.set_ylim(-.55, 3.55)
    label.axis("off")
    values.axis("off")
    ax.set_xlim(-5, 28)
    ax.set_xticks([0, 10, 20])
    ax.set_yticks([])
    ax.axvline(0, color=GREY, linestyle="--", linewidth=.8)
    plain_axes(ax)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Difference (percentage points)", fontsize=8.1)
    fig.text(.02, .92, "All four frozen participant-paired contrasts", fontsize=11, weight="bold")
    fig.text(.02, .865, "Contrast and endpoint", fontsize=8.5, weight="bold")
    fig.text(.705, .865, "Estimate [95% t interval]", fontsize=8.5, weight="bold")
    fig.text(.02, .04, "n = 85 participants; intervals are pointwise and unadjusted.\n"
             "Three secondary p values form one Holm family; primary p is unadjusted.",
             fontsize=8.0, linespacing=1.4)
    save(fig, "Fig2_frozen_contrasts")


def paired(rows, comparison):
    rows = sorted(rows, key=lambda r: (float(r["difference"]), r["subject"]))
    vals = np.array([float(r["difference"])*100 for r in rows])
    assert len(rows) == 85
    # Strict signs are the archived signs; preserve the source's exact zeros.
    assert (int((vals>0).sum()), int((vals<0).sum()), int((vals==0).sum())) == (72,10,3)
    fig, ax = plt.subplots(figsize=(6.8, 3.85))
    fig.subplots_adjust(left=.105, right=.985, bottom=.20, top=.82)
    x = np.arange(1, len(rows)+1)
    colors = [BLUE if v>0 else ORANGE if v<0 else GREY for v in vals]
    ax.bar(x, vals, color=colors, width=.83, linewidth=0)
    ax.scatter(x[vals==0], vals[vals==0], s=12, marker="s", color=GREY, zorder=3)
    ax.axhline(0, color="#343A40", linewidth=.8)
    mean = float(comparison["mean"])*100
    ax.axhline(mean, color=GREY, linestyle="--", linewidth=1.0)
    ax.text(2, mean+2.0, f"Paired mean: +{mean:.2f} pp", fontsize=8.3, color=GREY)
    ax.set_xlim(0, 86)
    ax.set_ylim(min(-25, vals.min()-4), max(75, vals.max()+4))
    ax.set_xticks([1, 20, 40, 60, 85])
    ax.set_xlabel("Participants ordered by paired difference (all 85)")
    ax.set_ylabel("S60 − S9 weaker-class recall (pp)")
    ax.yaxis.grid(True, color="#E6E8EB", linewidth=.6)
    plain_axes(ax)
    handles = [Line2D([0],[0],marker="s",lw=0,color=c,label=t,markersize=6)
               for c,t in [(BLUE,"72 improved"),(ORANGE,"10 declined"),(GREY,"3 unchanged")]]
    ax.legend(handles=handles, ncol=3, loc="lower left", bbox_to_anchor=(0, 1.015),
              frameon=False, borderaxespad=0, columnspacing=1.6)
    fig.text(.105, .94, "Participant-level improvement in weaker-class recall", fontsize=10.3, weight="bold")
    save(fig, "Fig3_participant_changes")
    for i,r in enumerate(rows,1):
        r["plot_order"] = i
        r["difference_percentage_points"] = float(r["difference"])*100
    writecsv(DATA/"Fig3_primary_participant_changes.csv", rows)


def descriptives(rows):
    fig, axes = plt.subplots(1, 3, figsize=(6.8, 4.1), sharey=True)
    fig.subplots_adjust(left=.085, right=.985, bottom=.20, top=.75, wspace=.17)
    specs = [("BROAD", "BROAD", BLUE, "o", -.08),
             ("MU_BETA_SHARED", "Shared μ/β", ORANGE, "s", 0),
             ("CSP_LDA", "CSP + shrinkage LDA", GREY, "^", .08)]
    gap_rows=[]
    for ax, metric, title in zip(axes, ["ba","min_recall","absolute_recall_gap"],
                                ["A   Balanced accuracy", "B   Weaker-class recall", "C   Absolute recall gap"]):
        for pipe, label, color, marker, offset in specs:
            if metric=="absolute_recall_gap":
                means=[]
                for lev in LEVELS:
                    ba=next(r for r in rows if r["pipeline"]==pipe and r["source_level"]==lev and r["metric"]=="ba")
                    weaker=next(r for r in rows if r["pipeline"]==pipe and r["source_level"]==lev and r["metric"]=="min_recall")
                    gap=2*(float(ba["mean"])-float(weaker["mean"]))
                    means.append(100*gap)
                    gap_rows.append({"source_level":lev,"pipeline":pipe,"selector":ba["selector"],
                        "n_subjects":ba["n_subjects"],"mean_ba":ba["mean"],"mean_min_recall":weaker["mean"],
                        "mean_absolute_recall_gap":gap,"mean_absolute_recall_gap_percentage_points":100*gap,
                        "formula":"2*(mean_ba-mean_min_recall)","scope":"posthoc descriptive algebraic decomposition; no CI or test"})
                ax.plot(np.arange(3)+offset, means, marker+"-",color=color,label=label,
                        markersize=4.5,markerfacecolor="white" if pipe=="CSP_LDA" else color,linewidth=1.05)
            else:
                selected = [next(r for r in rows if r["pipeline"]==pipe and r["source_level"]==lev
                                 and r["metric"]==metric) for lev in LEVELS]
                means = np.array([float(r["mean"])*100 for r in selected])
                low = np.array([float(r["t_ci95_low"])*100 for r in selected])
                high = np.array([float(r["t_ci95_high"])*100 for r in selected])
                ax.errorbar(np.arange(3)+offset, means, yerr=[means-low, high-means],
                            color=color, fmt=marker+"-", label=label, markersize=4.5,
                            markerfacecolor="white" if pipe=="CSP_LDA" else color,
                            capsize=2.5, linewidth=1.05, elinewidth=.9)
        ax.set_xticks(range(3), ["S9", "S29", "S60"])
        ax.set_xlim(-.3, 2.3)
        ax.set_ylim(0, 100)
        ax.set_title(title, fontsize=8.3, loc="left", pad=8)
        ax.yaxis.grid(True, color="#E6E8EB", linewidth=.6)
        plain_axes(ax)
    axes[0].set_ylabel("Participant mean (%) / recall gap (pp)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(.54,.91),
               ncol=3, frameon=False, columnspacing=1.3, handlelength=1.5)
    fig.text(.085, .965, "External outcomes across source configurations", fontsize=11, weight="bold")
    fig.text(.085, .035, "A/B: stored pointwise 95% t intervals. C: 2 × (A − B), descriptive only; no interval.\n"
             "Neural: source-only tail selection. CSP: fixed fit. n = 85; lines guide the eye.", fontsize=8.0,
             linespacing=1.4)
    writecsv(DATA/"Fig4_posthoc_absolute_recall_gap.csv",gap_rows)
    broad=[r for r in gap_rows if r["pipeline"]=="BROAD"]
    assert abs(broad[0]["mean_absolute_recall_gap_percentage_points"]-62.00980392156862)<1e-10
    assert abs(broad[2]["mean_absolute_recall_gap_percentage_points"]-31.38235294117645)<1e-10
    save(fig, "Fig4_source_configurations")


def epochs(rows):
    matrix = np.zeros((8,6), dtype=int)
    for ri,rule in enumerate(RULES):
        for pi,pipe in enumerate(["BROAD","MU_BETA_SHARED"]):
            for li,lev in enumerate(LEVELS):
                row = next(r for r in rows if r["source_level"]==lev and
                           r["pipeline"]==pipe and r["selector"]==rule)
                assert row["min"] == row["max"]
                matrix[ri, pi*3+li] = row["min"]
    assert tuple(matrix[-1,:3]) == (27,5,5)
    fig, ax = plt.subplots(figsize=(6.8,4.55))
    fig.subplots_adjust(left=.335, right=.86, top=.83, bottom=.20)
    im = ax.imshow(matrix, cmap="Blues", vmin=1, vmax=40, aspect="auto", interpolation="none")
    for r in range(8):
        for c in range(6):
            ax.text(c,r,str(matrix[r,c]),ha="center",va="center",fontsize=9,
                    color="white" if matrix[r,c]>=25 else "#17232D",
                    weight="bold" if r==7 and c<3 else "normal")
    ax.set_xticks(range(6), LEVELS+LEVELS)
    ax.set_yticks(range(8), RULE_LABELS)
    ax.tick_params(length=0, pad=5)
    ax.set_xticks(np.arange(-.5,6,1),minor=True)
    ax.set_yticks(np.arange(-.5,8,1),minor=True)
    ax.grid(which="minor",color="white",linewidth=1.2)
    ax.tick_params(which="minor",length=0)
    ax.add_patch(Rectangle((-.5,6.5),3,1,facecolor="none",edgecolor=GREY,linewidth=1.3))
    ax.axvline(2.5,color="white",linewidth=4)
    ax.text(1,-1.0,"BROAD",ha="center",va="center",fontsize=9.2,weight="bold")
    ax.text(4,-1.0,"Shared μ/β",ha="center",va="center",fontsize=9.2,weight="bold")
    for spine in ax.spines.values():
        spine.set_visible(False)
    cbax=fig.add_axes([.885,.20,.018,.63])
    cb=fig.colorbar(im,cax=cbax,ticks=[1,10,20,30,40])
    cb.set_label("Selected epoch",fontsize=8.4)
    fig.text(.035,.955,"All 48 source-selected checkpoint epochs",fontsize=11,weight="bold")
    fig.text(.035,.055,"Each full neural trajectory ran 40 epochs × 128 updates = 5,120 updates.\n"
             "Evaluation checkpoint durations differ; the outlined primary-rule cells are 27 / 5 / 5.",
             fontsize=8.1,linespacing=1.45)
    save(fig,"Fig5_selected_epochs")


def posthoc_contrasts(rows):
    """Display the separately calculated, fully retained four-test posthoc family."""
    assert len(rows)==4
    labels=["BROAD: S29 − S9\nWeaker-class recall",
            "BROAD: S29 − S9\nBalanced accuracy",
            "CSP + shrinkage LDA: S60 − S9\nWeaker-class recall",
            "CSP + shrinkage LDA: S60 − S9\nBalanced accuracy"]
    fig=plt.figure(figsize=(6.8,4.20))
    gs=fig.add_gridspec(1,3,width_ratios=[2.40,2.45,2.05],wspace=.06,
                        left=.02,right=.99,bottom=.18,top=.80)
    label,ax,values=[fig.add_subplot(gs[0,i]) for i in range(3)]
    for i,(r,text) in enumerate(zip(rows,labels)):
        assert int(r["n_participants"])==85
        assert r["metric"]==("min_recall" if i%2==0 else "ba")
        assert r["pipeline"]==("BROAD" if i<2 else "CSP_LDA")
        assert (r["higher_source_level"],r["lower_source_level"])==(("S29","S9") if i<2 else ("S60","S9"))
        mean,lo,hi=[float(r[k]) for k in ["difference_pp","ci95_pointwise_low_pp","ci95_pointwise_high_pp"]]
        y=3-i
        color=BLUE if i<2 else GREY
        ax.errorbar(mean,y,xerr=[[mean-lo],[hi-mean]],fmt="o" if i<2 else "^",
                    color=color,markerfacecolor=color if i<2 else "white",markeredgewidth=1.2,
                    markersize=5,capsize=3,elinewidth=1.3)
        label.text(0,y,text,ha="left",va="center",fontsize=8.0,linespacing=1.45)
        values.text(0,y,f"{mean:+.2f} [{lo:+.2f}, {hi:+.2f}]\n"
                    f"Holm p = {float(r['p_holm_four_posthoc']):.3g}",
                    ha="left",va="center",fontsize=8.2,linespacing=1.45)
    for panel in [label,ax,values]:panel.set_ylim(-.55,3.55)
    label.axis("off"); values.axis("off")
    ax.set_xlim(-1,28); ax.set_xticks([0,10,20]); ax.set_yticks([])
    ax.axvline(0,color=GREY,linestyle="--",linewidth=.8)
    plain_axes(ax); ax.spines["left"].set_visible(False)
    ax.set_xlabel("Difference (percentage points)",fontsize=8.1)
    fig.text(.02,.94,"Source-expansion gains in the additional paired analyses",fontsize=10.2,weight="bold")
    fig.text(.02,.885,"Post hoc: separate four-comparison family",fontsize=8.4,color=GREY)
    fig.text(.02,.835,"Contrast and endpoint",fontsize=8.5,weight="bold")
    fig.text(.705,.835,"Estimate [95% t interval]",fontsize=8.5,weight="bold")
    fig.text(.02,.04,"n = 85 participants; pointwise, unadjusted 95% t intervals.\n"
             "Holm correction applies to these four post hoc tests only; original frozen tests unchanged.",
             fontsize=8.0,linespacing=1.4)
    save(fig,"Fig6_posthoc_source_expansion")


def fixed_duration_control(inventory,seed_rows):
    """Display every fixed20 condition, using cohort-mean seed contrasts."""
    fixed=[r for r in inventory if r["selector"]=="fixed20"]
    assert len(inventory)==68 and len(fixed)==8 and len(seed_rows)==24
    conditions=[("S29","BROAD"),("S60","BROAD"),
                ("S29","MU_BETA_SHARED"),("S60","MU_BETA_SHARED")]
    seeds=["20261013","20261014","20261015"]
    markers=["o","^","D"]
    fig,axes=plt.subplots(1,2,figsize=(6.8,4.2),sharey=True)
    fig.subplots_adjust(left=.09,right=.985,bottom=.22,top=.71,wspace=.15)
    for ax,metric,title in zip(axes,["ba","min_recall"],
                              ["A   Balanced accuracy","B   Weaker-class recall"]):
        for x,(level,pipeline) in enumerate(conditions):
            row=next(r for r in fixed if r["higher_source_level"]==level and
                     r["pipeline"]==pipeline and r["metric"]==metric)
            assert row["lower_source_level"]=="S9" and int(row["n_participants"])==85
            assert row["higher_selected_epoch"]==row["lower_selected_epoch"]=="20"
            assert row["higher_selected_updates"]==row["lower_selected_updates"]=="2560"
            mean=float(row["difference_pp"])
            color=BLUE if pipeline=="BROAD" else ORANGE
            ax.bar(x,mean,width=.64,color=color,alpha=.22,edgecolor=color,linewidth=1.0,zorder=2)
            vals=[]
            for si,seed in enumerate(seeds):
                item=next(r for r in seed_rows if r["higher_source_level"]==level and
                          r["pipeline"]==pipeline and r["metric"]==metric and r["seed"]==seed)
                assert int(item["n_participants"])==85
                assert item["higher_selected_updates"]==item["lower_selected_updates"]=="2560"
                value=float(item["difference_pp"])
                vals.append(value)
                ax.scatter(x+(si-1)*.135,value,s=24,marker=markers[si],facecolors="white",
                           edgecolors="#28323B",linewidths=.9,zorder=4)
            assert abs(sum(vals)/3-mean)<1e-10
            ax.text(x,.65,f"+{mean:.2f}",ha="center",va="bottom",fontsize=8.1,weight="bold",color="#26313B")
        ax.set_xticks(range(4),["BROAD\nS29 − S9","BROAD\nS60 − S9", "Shared\nS29 − S9","Shared\nS60 − S9"])
        ax.set_xlim(-.55,3.55); ax.set_ylim(0,33)
        ax.set_yticks([0,10,20,30]); ax.yaxis.grid(True,color="#E6E8EB",linewidth=.6)
        ax.set_title(title,loc="left",fontsize=9.0,pad=8)
        plain_axes(ax)
    axes[0].set_ylabel("Source expansion − S9 (percentage points)")
    handles=[Rectangle((0,0),1,1,facecolor="#D4DDE3",edgecolor=GREY,label="Three-seed mean")]
    handles += [Line2D([0],[0],color="#28323B",marker=m,linestyle="none",markerfacecolor="white",
                       markersize=5,label=f"Seed {s}") for s,m in zip(seeds,markers)]
    fig.legend(handles=handles,loc="upper center",bbox_to_anchor=(.54,.85),ncol=4,
               frameon=False,columnspacing=1.05,handlelength=1.1,handletextpad=.45)
    fig.text(.035,.955,"Source-expansion gains at a common 20-epoch checkpoint",fontsize=10.3,weight="bold")
    fig.text(.035,.895,"Identical selected duration: 20 epochs × 128 updates = 2,560 updates",fontsize=8.5,color=GREY)
    fig.text(.035,.035,"Post hoc descriptive control; all eight fixed20 differences and 24 seed points are shown.\n"
             "Seed points use the same 85 participants; they are conditional checks, not independent replications.",
             fontsize=8.0,linespacing=1.4)
    save(fig,"Fig7_fixed_duration_control")


def main():
    for p in [DATA,TABLES,FIGURES]:
        p.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":8.5,
                         "axes.labelsize":8.5,"xtick.labelsize":8.2,"ytick.labelsize":8.2,
                         "legend.fontsize":8.2,"svg.fonttype":"none","pdf.fonttype":42,
                         "text.color":"#20262C","axes.labelcolor":"#20262C"})
    source_names = ["neural_recomputed_comparisons.csv", "neural_recomputed_condition_summaries.csv",
                    "neural_recomputed_paired_differences.csv", "csp_recomputed_condition_summaries.csv"]
    provenance=[]
    for name in source_names:
        path=AUDIT/name
        shutil.copyfile(path, DATA/name)
        assert digest(path)==digest(DATA/name)
        provenance.append({"path":str(path.relative_to(REPO)),"bytes":path.stat().st_size,
                           "sha256":digest(path),"copy":str((DATA/name).relative_to(HERE))})
    comparisons=readcsv(AUDIT/source_names[0])
    neural=readcsv(AUDIT/source_names[1])
    csp=readcsv(AUDIT/source_names[3])
    paired_rows=[r for r in readcsv(AUDIT/source_names[2]) if r["comparison"]=="primary_source_expansion_min_recall"]
    descriptive=[r for r in neural if r["selector"]=="tail_min_recall" and r["metric"] in ["ba","min_recall"]]
    descriptive += [r for r in csp if r["metric"] in ["ba","min_recall"]]
    assert len(descriptive)==18
    audit=json.loads((AUDIT/"audit_results.json").read_text())
    chosen=audit["selected_epochs"]
    freeze=json.loads((FROZEN/"indexed/results/selection_freeze.json").read_text())
    for row in chosen:
        assert row["min"]==freeze["selections"][row["source_level"]][row["pipeline"]]["epochs"][row["selector"]]
    study=json.loads((FROZEN/"indexed/provenance/study.json").read_text())
    assert study["epochs"]*study["updates_per_epoch"]==5120
    assert len(study["channels"])==18 and study["sfreq"]==160 and study["n_times"]==320
    source_config=[{"source_level":k,"bnci_participants":study["source_levels"][k]["bnci"],
                    "yang_participants":study["source_levels"][k]["yang"],
                    "total_participants":sum(study["source_levels"][k].values()),
                    "unique_eligible_trials":study["source_trial_counts_expected"][k]}
                   for k in LEVELS]
    assert [r["unique_eligible_trials"] for r in source_config]==[2592,14590,33183]
    writecsv(DATA/"Fig1_source_configurations.csv",source_config)
    writecsv(DATA/"Fig4_descriptive_endpoints.csv",descriptive)
    writecsv(DATA/"Fig5_selected_epochs.csv",chosen)
    writecsv(TABLES/"Table1_source_configurations.csv",source_config)
    shutil.copyfile(DATA/"neural_recomputed_comparisons.csv",TABLES/"Table2_frozen_comparisons.csv")
    writecsv(TABLES/"Table3_descriptive_endpoints.csv",descriptive)
    shutil.copyfile(DATA/"neural_recomputed_condition_summaries.csv",TABLES/"S1_all_neural_condition_summaries.csv")
    shutil.copyfile(DATA/"csp_recomputed_condition_summaries.csv",TABLES/"S2_all_CSP_condition_summaries.csv")
    writecsv(TABLES/"S3_all_selected_epochs.csv",chosen)
    workflow()
    contrasts(comparisons)
    paired(paired_rows,next(r for r in comparisons if r["name"]=="primary_source_expansion_min_recall"))
    descriptives(descriptive)
    epochs(chosen)
    posthoc_source=TABLES/"review2_posthoc_comparisons.csv"
    shutil.copyfile(posthoc_source,DATA/"Fig6_review2_posthoc_comparisons.csv")
    assert digest(posthoc_source)==digest(DATA/"Fig6_review2_posthoc_comparisons.csv")
    posthoc_rows=readcsv(posthoc_source)
    posthoc_contrasts(posthoc_rows)
    provenance.append({"path":str(posthoc_source.relative_to(REPO)),"bytes":posthoc_source.stat().st_size,
                       "sha256":digest(posthoc_source),"copy":"figure_data/Fig6_review2_posthoc_comparisons.csv",
                       "scope":"Separately calculated review2 posthoc four-test family; not an original frozen comparison"})
    inventory_source=TABLES/"source_expansion_inventory.csv"
    fixed_seed_source=TABLES/"source_expansion_fixed20_seed_differences.csv"
    inventory_rows=readcsv(inventory_source)
    fixed_seed_rows=readcsv(fixed_seed_source)
    fixed_duration_control(inventory_rows,fixed_seed_rows)
    for path,name in [(inventory_source,"Fig7_complete_source_expansion_inventory.csv"),
                      (fixed_seed_source,"Fig7_fixed20_seed_differences.csv")]:
        shutil.copyfile(path,DATA/name)
        assert digest(path)==digest(DATA/name)
        provenance.append({"path":str(path.relative_to(REPO)),"bytes":path.stat().st_size,
                           "sha256":digest(path),"copy":"figure_data/"+name,
                           "scope":"Posthoc descriptive fixed-duration control; complete 68-row inventory retained; no new test"})
    source_extra=[FROZEN/"indexed/provenance/study.json", FROZEN/"indexed/results/selection_freeze.json",
                  AUDIT/"audit_results.json"]
    for path in source_extra:
        provenance.append({"path":str(path.relative_to(REPO)),"bytes":path.stat().st_size,"sha256":digest(path)})
    (DATA/"SOURCE_PROVENANCE.json").write_text(json.dumps({
        "frozen_results_commit":"040956085499ed788948de0d5a09cddd9eabca56",
        "operation":"Read frozen JSON/CSV, copy exact CSV bytes, reorder and convert units for figures; no new inference",
        "new_tests":0,"new_fits":0,"raw_eeg_read":False,"checkpoint_deserialization":False,
        "sources":provenance},indent=2)+"\n")
    (FIGURES/"FIGURE_METADATA.json").write_text(json.dumps({
        "renderer":"Matplotlib "+matplotlib.__version__,
        "min_authored_font_points":8.0,"tiff_limit_bytes":10000000,
        "scientific_data_source":"Frozen audited CSV/JSON plus separately identified review2 posthoc paired summaries; original frozen results unchanged",
        "figures":META},indent=2)+"\n")
    (FIGURES/"FIGURE_VALIDATION.json").write_text(json.dumps({
        "scope":"Figure/source-table consistency and render checks only; no rerun of scientific audits",
        "source_csv_copies_byte_identical":True,
        "frozen_contrasts_displayed":len(comparisons),
        "primary_participant_changes_displayed":len(paired_rows),
        "positive_negative_zero_counts":[72,10,3],
        "selected_epochs_displayed":len(chosen),
        "selected_epochs_match_frozen_selection_json":True,
        "neural_and_CSP_descriptive_endpoint_rows":len(descriptive),
        "review2_posthoc_contrasts_rendered":len(posthoc_rows),
        "review2_posthoc_family":"Four tests, Holm-adjusted separately from original frozen comparisons",
        "fixed_duration_control_mean_bars":8,"fixed_duration_control_seed_points":24,
        "fixed_duration_control_selected_epochs":20,"fixed_duration_control_selected_updates":2560,
        "complete_descriptive_inventory_rows_retained":len(inventory_rows),
        "full_precision_CSV":True,"all_visible_text_inside_canvas":True,
        "all_tiff_width_pixels":round(6.8*TIFF_DPI),"all_tiff_dpi":TIFF_DPI,
        "preview_png_width_pixels":round(6.8*PREVIEW_DPI),"preview_png_dpi":PREVIEW_DPI,
        "all_tiff_RGB_LZW":True,"all_tiff_under_10MB":True,
        "posthoc_gap":"Exactly 2*(frozen mean BA - frozen mean weaker recall); no new CI or test",
        "new_fits":0,"new_hypothesis_tests":0,"raw_eeg_read":False,
        "author_figure_approval":"Required for this revised set; not inferred from old manuscript approval"},indent=2)+"\n")
    print(json.dumps({"status":"SEVEN_FIGURES_RENDERED_FROM_FROZEN_AND_POSTHOC_TABLES",
                      "figures":7,"new_hypothesis_tests_in_renderer":0,"source_rows_primary":len(paired_rows),
                      "selected_epochs":len(chosen),"descriptive_rows":len(descriptive)},sort_keys=True))


if __name__ == "__main__":
    main()
