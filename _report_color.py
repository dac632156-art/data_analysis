p = r"d:/数据分析项目/frontend/src/utils/exportEChartsDashboard.ts"
s = open(p, encoding="utf-8").read()

repl = [
    # 旧蓝辉光 rgba（96,165,250 = #60A5FA）→ 新蓝 rgba（56,189,248 = #38BDF8）
    ("96,165,250", "56,189,248"),
    # 旧浅蓝辉光 rgba（147,197,253 = #93C5FD）→ 新浅蓝 rgba（125,211,252 = #7DD3FC）
    ("147,197,253", "125,211,252"),
    # 旧品牌蓝 HEX → 新品牌蓝 HEX
    ("#60A5FA", "#38BDF8"),
    ("#93C5FD", "#7DD3FC"),
    ("#3B82F6", "#0ea5e9"),
    ("#BFDBFE", "#67E8F9"),
    ("#2563EB", "#0369a1"),
    ("#1E40AF", "#0c4a6e"),
]

for a, b in repl:
    s = s.replace(a, b)

open(p, "w", encoding="utf-8").write(s)
print("remaining old-brand tokens:")
for tok in ["#60A5FA", "#93C5FD", "#3B82F6", "#BFDBFE", "#2563EB", "#1E40AF",
            "96,165,250", "147,197,253"]:
    print(" ", tok, s.count(tok))
