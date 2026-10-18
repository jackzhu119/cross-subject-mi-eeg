"""Produce readable tables and figures; synthetic checks are visibly labelled."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import numpy as np

from p1_common import atomic_bytes, read_json


def _csv(path, rows):
    if not rows:
        raise ValueError("A report table is empty")
    keys = list(dict.fromkeys(k for r in rows for k in r))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=keys)
    writer.writeheader()
    writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                     for k, v in row.items()} for row in rows)
    atomic_bytes(path, stream.getvalue().encode("utf-8"))


def render_report(results, config):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    results = Path(results)
    report = read_json(results/"report.json")
    if report["study_status"] != "exploratory_external" or not report["diagnostics"]["complete_paired_grid"]:
        raise ValueError("External report is incomplete or has the wrong scientific status")
    synthetic = (config.get("evidence_scope") == "synthetic_only"
                 or report.get("evidence_scope") == "synthetic_only")
    seed_count = report["diagnostics"]["n_seeds"]
    for key in ["condition_summaries", "comparisons", "per_subject_metrics", "paired_subject_differences"]:
        _csv(results/(key+".csv"), report[key])
    primary = next(x for x in report["comparisons"] if x["family"] == "prespecified_primary")
    lines = ["# Paper1：扩大源训练数据后的外部评估", "",
             "**状态：探索性外部验证。** Dreyer 历史使用情况不确定，因此本结果不称为首次使用的独立确认。", "",
             f"协议：`{config['protocol_id']}`。统计单位是 {report['diagnostics']['n_subjects']} 名外部被试；"
             f"每名被试先计算各随机种子的指标，再平均 {report['diagnostics']['n_seeds']} 个种子。", "",
             "## 预设主比较", "",
             "S60 对 S9；BROAD；tail_min_recall 选轮；终点为每名被试较弱类别召回率。", "",
             f"均值差 **{primary['mean_difference_percentage_points']:+.3f} 个百分点**；"
             f"配对 t 的 95% CI [{primary['t_ci95_low_percentage_points']:+.3f}, {primary['t_ci95_high_percentage_points']:+.3f}]；"
             f"双侧 p={primary['p_two_sided']:.6g}。", "",
             f"被试配对 bootstrap 95% CI [{primary['bootstrap_ci95_low_percentage_points']:+.3f}, "
             f"{primary['bootstrap_ci95_high_percentage_points']:+.3f}]。区间均为点态区间，没有做多重性校正。", "",
             "正差表示扩源组指标较高；若区间包含零，应报告证据仍不足，不能写成已经证实改进。", "",
             "## 三组数据规模", "",
             "| 组 | 源被试 | 可用不同试次 | 每条轨迹优化更新数 |", "|---|---:|---:|---:|"]
    if synthetic:
        lines[:4] = ["# Paper1：合成软件测试预览（非科研结果）", "",
                     "**仅验证报告与导出程序。所有分数来自合成 logits，没有读取真实 EEG、拟合模型或评估真实被试；"
                     "以下数值不得用于论文结论。**", ""]
    for level, groups in config["source_levels"].items():
        lines.append(f"| {level} | {sum(groups.values())} | {config['source_trial_counts_expected'][level]} | "
                     f"{config['epochs']*config['updates_per_epoch']} |")
    lines += ["", "## 各组主要指标", "",
              f"同一 tail_min_recall 选轮规则；均先跨 {seed_count} 个种子平均到被试，再跨被试求均值。", "",
              "| Pipeline | 组 | 较弱类召回率 % | Balanced accuracy % |", "|---|---|---:|---:|"]
    summaries = report["condition_summaries"]
    for pipeline in config["pipelines"]:
        for level in config["source_levels"]:
            data = {s["metric"]: s for s in summaries if s["pipeline"] == pipeline and s["source_level"] == level
                    and s["selector"] == "tail_min_recall"}
            lines.append(f"| {pipeline} | {level} | {100*data['min_recall']['mean']:.3f} | {100*data['ba']['mean']:.3f} |")
    if config.get("traditional_baseline", {}).get("enabled", False):
        csp = read_json(results/"csp_report.json")
        if not csp["diagnostics"]["complete_paired_grid"] or csp["study_status"] != "exploratory_external":
            raise ValueError("Conventional baseline report is incomplete")
        for key in ["condition_summaries", "per_subject_metrics"]:
            _csv(results/("csp_"+key+".csv"), csp[key])
        csp_description = (
            "固定 CSP + shrinkage LDA 使用相同的源人员和外部试次。"
            f"每个规模使用 {csp['diagnostics']['n_seeds']} 个种子，共 "
            f"{len(config['source_levels'])*csp['diagnostics']['n_seeds']} 次拟合；"
            "该结果独立汇总，用作描述性基线，不加入神经实验的预设假设检验家族。")
        if synthetic:
            csp_description = ("下表使用 CSP_LDA 条件名称下的合成概率验证描述性汇总格式。"
                               "没有拟合 CSP 或 LDA；这些虚构数值不加入神经实验的预设假设检验家族。")
        lines += ["", "## 传统基线", "",
                  csp_description, "",
                  "| 组 | 较弱类召回率 % | Balanced accuracy % |", "|---|---:|---:|"]
        for level in config["source_levels"]:
            data = {s["metric"]: s for s in csp["condition_summaries"] if s["source_level"] == level}
            lines.append(f"| {level} | {100*data['min_recall']['mean']:.3f} | {100*data['ba']['mean']:.3f} |")
    lines += ["", "![扩源结果](source_expansion.png)", "", "## 次要比较", "",
              "三项预设次要检验一起使用 Holm 校正；没有根据主比较是否显著而改变检验家族。", "",
              "| 比较 | 差值 pp | 双侧 p | Holm p |", "|---|---:|---:|---:|"]
    for c in report["comparisons"]:
        if c["family"] == "secondary_holm_3":
            lines.append(f"| {c['name']} | {c['mean_difference_percentage_points']:+.3f} | {c['p_two_sided']:.6g} | {c['p_holm']:.6g} |")
    lines += ["", "## 被试差异", "", "![外部被试逐人变化](paired_subject_changes.png)", "",
              "所有选择器的完整结果见 condition_summaries.csv；不得把表现最佳的外部选择器重新命名为预设主方法。", "",
              "## 解释边界", ""]
    lines.extend("- "+x for x in config["limitations"])
    lines += ["", "## 复现材料", "",
              "selection_freeze.json 给出在外部评估前冻结的全部选轮结果；source_validation_curves.csv 保存源内曲线；"
              "final_fit_manifest.csv 保存真正训练轨迹与复用检查点的对应关系；external_predictions.csv.gz 保存逐试次 logits。", "",
              f"逐试次结果：{report['prediction_rows']:,} 行。8 个选轮规则复用同一最终轨迹，不能将别名视作独立模型重复。", "",
              "这些结果没有执行外部被试微调、目标标签选轮、目标集合归一化拟合或目标 BatchNorm 更新。", ""]
    if synthetic:
        start = lines.index("## 复现材料")
        lines[start:] = ["## 软件验证材料", "",
                         "本目录仅包含确定性合成 logits、由实际统计函数生成的 JSON/CSV、图片和 PDF。"
                         "不存在真实源训练曲线、训练完成声明或真实被试预测。", "",
                         f"合成神经预测表共 {report['prediction_rows']:,} 行；"
                         "CSP 表也仅为合成概率的描述性汇总。", ""]
    atomic_bytes(results/"REPORT_zh.md", "\n".join(lines).encode("utf-8"))

    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "pdf.fonttype": 42, "ps.fonttype": 42})
    levels = list(config["source_levels"])
    figure, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    for ax, metric, title in zip(axes, ["min_recall", "ba"], ["Weaker-class recall", "Balanced accuracy"]):
        for pipeline, color, offset in [("BROAD", "#225ea8", -0.04), ("MU_BETA_SHARED", "#c46521", 0.04)]:
            rows = [next(s for s in summaries if s["pipeline"] == pipeline and s["source_level"] == level
                         and s["selector"] == "tail_min_recall" and s["metric"] == metric) for level in levels]
            means = np.array([s["mean"] for s in rows])*100
            lower = np.array([s["bootstrap_ci95_low"] for s in rows])*100
            upper = np.array([s["bootstrap_ci95_high"] for s in rows])*100
            ax.errorbar(np.arange(3)+offset, means, yerr=[np.maximum(0, means-lower), np.maximum(0, upper-means)],
                        color=color, marker="o", capsize=3, label=pipeline)
        ax.set(xticks=np.arange(3), xticklabels=["9 people", "29 people", "60 people"],
               ylabel="Mean across external people (%)", xlabel="Available source participants", title=title)
        ax.grid(axis="y", alpha=.2)
    axes[0].legend(frameon=False, fontsize=8)
    figure.suptitle("Source expansion at a fixed optimization budget\nPointwise paired-person bootstrap 95% intervals", fontsize=11)
    if synthetic:
        figure.text(.5, .51, "SYNTHETIC SOFTWARE TEST — NOT RESEARCH RESULTS", ha="center", va="center",
                    fontsize=15, weight="bold", color="#9f2436", alpha=.5, rotation=10)
    for ext in ["png", "pdf"]:
        figure.savefig(results/f"source_expansion.{ext}", dpi=300)
    plt.close(figure)
    differences = sorted(100*r["difference"] for r in report["paired_subject_differences"]
                         if r["comparison"] == primary["name"])
    figure, ax = plt.subplots(figsize=(8, 4), constrained_layout=True)
    ax.scatter(np.arange(1, len(differences)+1), differences, c=["#c46521" if d < 0 else "#225ea8" for d in differences], s=19)
    ax.axhline(0, color="black", linewidth=.8)
    ax.axhline(primary["mean_difference_percentage_points"], color="#444444", linestyle="--", linewidth=1)
    ax.set(xlabel="External participants sorted by their paired change", ylabel="S60 minus S9 (percentage points)",
           title="Weaker-class recall: individual gains and harms\nBROAD, frozen tail_min_recall selector")
    ax.grid(axis="y", alpha=.2)
    if synthetic:
        figure.text(.5, .5, "SYNTHETIC SOFTWARE TEST\nNOT RESEARCH RESULTS", ha="center", va="center",
                    fontsize=15, weight="bold", color="#9f2436", alpha=.5, rotation=10)
    for ext in ["png", "pdf"]:
        figure.savefig(results/f"paired_subject_changes.{ext}", dpi=300)
    plt.close(figure)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("results", type=Path)
    a = p.parse_args()
    render_report(a.results, read_json(Path(__file__).resolve().parent/"config/study.json"))
