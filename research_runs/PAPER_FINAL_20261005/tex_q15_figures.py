"""Self-contained PGFPlots counterparts of both publication Q15 figures.

Figures embed every numerical point, including participant-level seed sample
SDs. Required TeX packages: tikz, pgfplots, and the groupplots library.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from build_q15_figures import DATASETS, MODELS, load_data, swarm_offsets


def _coordinates(xs, ys):
    return " ".join(f"({float(x):.8f},{float(y):.8f})" for x, y in zip(xs, ys))


def _plot(xs, ys, options):
    return r"\addplot[" + options + "] coordinates {" + _coordinates(xs, ys) + "};\n"


def _node(x, y, text, options="anchor=west,font=\\scriptsize"):
    return r"\node[" + options + f"] at (axis cs:{x},{y})" + " {" + text + "};\n"


def _start(size="2 by 1", height="5.2cm", hsep="1.25cm", width=r".44\linewidth", vgap="1.05cm"):
    return (r"\definecolor{qfBroad}{HTML}{1B7C88}" + "\n" +
            r"\definecolor{qfShared}{HTML}{C76D2D}" + "\n" +
            r"\definecolor{qfCsp}{HTML}{70777D}" + "\n" +
            r"\begin{tikzpicture}[font=\scriptsize]" + "\n" + r"\begin{groupplot}[group style={group size=" + size +
            ",horizontal sep=" + hsep + ",vertical sep=" + vgap + "},width=" + width + ",height=" + height +
            r",tick label style={font=\scriptsize},label style={font=\scriptsize},title style={font=\small},axis lines=left,tick align=outside," +
            r"legend style={font=\tiny,draw=none,fill=none},grid style={gray!20},clip=false]" + "\n")


def _finish():
    return "\\end{groupplot}\n\\end{tikzpicture}\n"


def tex_inline_figure(name: str, out: Path, numbers=None) -> str:
    """Return a single-file figure; `numbers` is accepted for the old API."""
    del numbers
    people, summaries = load_data(Path(out))
    colors = ["qfBroad", "qfShared", "qfCsp"]
    markers = ["*", "triangle", "square"]
    if name == "figure4_q15_external_transfer":
        text = _start(width=r".43\linewidth", height="5.4cm", hsep="1.55cm")
        text += (r"\nextgroupplot[title={A: External participant performance},ylabel={Balanced accuracy (\%)}," +
                 r"xmin=-.57,xmax=1.82,ymin=35,ymax=100,ytick={40,50,60,70,80,90,100},ymajorgrids," +
                 r"xtick={0,1.25},xticklabels={{Cho2017 ($n=52$)},{Lee2019 MI ($n=54$)}}," +
                 r"legend columns=3,legend style={at={(.5,-.16)},anchor=north,font=\tiny,draw=none,fill=none}]" + "\n")
        for center, (dataset, _, _) in zip((0, 1.25), DATASETS):
            for pos, (model, label, _, _, _), color, marker in zip((-.29, 0, .29), MODELS, colors, markers):
                values = np.array([float(r[model]) * 100 for r in people[dataset]])
                x = center + pos + swarm_offsets(values)
                text += _plot(x, values, f"only marks,color={color},mark={marker},mark size=1.05pt,opacity=.75")
                if center == 0:
                    text += r"\addlegendentry{" + label + "}\n"
                row = summaries[dataset][model]
                mean, sd = [float(row[k]) * 100 for k in ("mean_balanced_accuracy", "person_sample_sd")]
                text += (r"\addplot[black,mark=diamond*,mark size=1.8pt,forget plot," +
                         r"error bars/.cd,y dir=both,y explicit] coordinates {" +
                         f"({center + pos:.8f},{mean:.8f}) +- (0,{sd:.8f})" + "};\n")
        text += _plot([-.57, 1.82], [50, 50], "gray,densely dotted,no marks,forget plot")
        text += r"\node[anchor=north west,font=\tiny] at (axis description cs:0,-.29) {Diamonds/bars: mean $\pm$ participant SD};" + "\n"
        text += (r"\nextgroupplot[title={B: Prespecified paired contrast},xlabel={Shared minus broad BA (pp)}," +
                 r"xmin=-3.05,xmax=1.6,ymin=-.65,ymax=1.65,xtick={-3,-2,-1,0,1},xmajorgrids," +
                 r"ytick={1,0},yticklabels={Cho2017,Lee2019 MI}]" + "\n")
        for y, (dataset, _, _) in zip((1, 0), DATASETS):
            row = summaries[dataset]["BROAD_EEGNET"]
            mean, low, high = [float(row[k]) * 100 for k in ("primary_delta_mean", "primary_ci_low", "primary_ci_high")]
            text += _plot([low, high], [y, y], "black,thick,no marks,forget plot")
            text += _plot([low, low], [y - .045, y + .045], "black,thick,no marks,forget plot")
            text += _plot([high, high], [y - .045, y + .045], "black,thick,no marks,forget plot")
            text += _plot([mean], [y], "black,only marks,mark=*,mark size=2pt,forget plot")
            text += _node(-2.8, y + .23, f"{mean:+.2f} pp [{low:+.2f}, {high:+.2f}]")
            p = float(row["primary_holm_p"])
            text += _node(-2.8, y - .23, r"Holm $p<0.001$" if p < .001 else f"Holm $p={p:.3f}$")
        text += _plot([0, 0], [-.65, 1.65], "gray,no marks,forget plot")
        text += r"\node[anchor=north west,font=\tiny,align=left] at (axis description cs:0,-.29) {Paired-person bootstrap 95\% CI\\Holm: two prespecified cohorts};" + "\n"
        return text + _finish()
    if name != "figureS2_q15_participant_heterogeneity":
        raise ValueError(f"Unknown Q15 figure: {name}")
    delta = [float(r["primary_delta"]) * 100 for dataset, _, _ in DATASETS for r in people[dataset]]
    lim = max(10, math.ceil(max(abs(v) for v in delta) / 5) * 5)
    seeds = [float(r[model + "_seed_sd"]) * 100 for dataset, _, _ in DATASETS for model, *_ in MODELS[:2] for r in people[dataset]]
    seed_lim = max(10, math.ceil(max(seeds) / 5) * 5)
    text = _start(size="2 by 2", height="4.4cm", hsep=".6cm", vgap="1.15cm", width=r".46\linewidth")
    for letter, (dataset, label, n) in zip(("A", "B"), DATASETS):
        text += (r"\nextgroupplot[title={" + letter + ": " + label + " ($n=" + str(n) + "$)}," +
                 (r"ylabel={Shared minus broad BA (pp)}," if letter == "A" else "") +
                 r"xmin=.1,xmax=" + str(n + .9) +
                 ",ymin=" + str(-lim) + ",ymax=" + str(lim) + r",xtick={1,10,20,30,40,50},ymajorgrids]" + "\n")
        persons = [int(r["subject"]) for r in people[dataset]]
        values = [float(r["primary_delta"]) * 100 for r in people[dataset]]
        text += _plot([.1, n + .9], [0, 0], "gray,no marks,forget plot")
        mean = float(summaries[dataset]["BROAD_EEGNET"]["primary_delta_mean"]) * 100
        text += _plot([.1, n + .9], [mean, mean], "qfShared,dashed,no marks,forget plot")
        for person, value in zip(persons, values):
            text += _plot([person, person], [0, value], "gray!65,no marks,forget plot")
        text += _plot(persons, values, "black,only marks,mark=*,mark size=1.2pt,forget plot")
        text += r"\node[anchor=north west,font=\tiny] at (axis description cs:.02,.97) {Participant mean: " + f"{mean:+.2f}" + " pp};\n"
    for letter, (dataset, _, n) in zip(("C", "D"), DATASETS):
        text += (r"\nextgroupplot[title={" + letter + ": Within-participant seed variation}," +
                 r"xlabel={Participant ID}," +
                 (r"ylabel={BA sample SD across\\three seeds (pp)},ylabel style={align=center}," if letter == "C" else "") +
                 r"xmin=.1,xmax=" +
                 str(n + .9) + ",ymin=0,ymax=" + str(seed_lim) + r",xtick={1,10,20,30,40,50},ymajorgrids," +
                 r"legend columns=2,legend style={at={(.5,-.3)},anchor=north,font=\tiny,draw=none,fill=none}]" + "\n")
        for offset, (model, label, _, _, _), color, marker in zip((-.14, .14), MODELS[:2], colors[:2], markers[:2]):
            persons = [int(r["subject"]) + offset for r in people[dataset]]
            values = [float(r[model + "_seed_sd"]) * 100 for r in people[dataset]]
            text += _plot(persons, values, f"only marks,color={color},mark={marker},mark size=1.2pt")
            text += r"\addlegendentry{" + label + "}\n"
    return text + _finish()
