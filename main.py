"""命令行入口：读聊天记录，打印任务报告（可选 AI 增强）。

用法（在项目根目录 deadline-sentinel 下）：
    python main.py                       # 默认读 data/demo_chat.txt
    python main.py data/sample_chat.txt  # 读指定文件
    python main.py a.txt b.txt           # 合并多个文件
    python main.py --ai data/sample_chat.txt   # 启用 AI 增强（需配置环境变量）

导出：
    python main.py --csv out.csv data/sample_chat.txt
    python main.py --json out.json data/sample_chat.txt
    python main.py --xlsx out.xlsx data/sample_chat.txt   # 需要 openpyxl
"""

import os
import sys
from datetime import datetime

from sentinel.read_chat import read_many_files
from sentinel.tasks import build_tasks, summarize
from sentinel.report import build_report
from sentinel import export as exporter
from sentinel import ai_helper


# 尝试加载项目根目录的 .env，使配置生效
ai_helper.load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


def main(argv: list) -> int:
    use_ai = "--ai" in argv
    argv = [a for a in argv if a != "--ai"]

    csv_out = json_out = xlsx_out = None
    if "--csv" in argv:
        i = argv.index("--csv")
        csv_out = argv[i + 1]
        del argv[i:i + 2]
    if "--json" in argv:
        i = argv.index("--json")
        json_out = argv[i + 1]
        del argv[i:i + 2]
    if "--xlsx" in argv:
        i = argv.index("--xlsx")
        xlsx_out = argv[i + 1]
        del argv[i:i + 2]

    paths = argv if argv else ["data/demo_chat.txt"]
    now = datetime.now()

    messages, problems = read_many_files(paths)
    tasks = build_tasks(messages, now=now)

    if use_ai:
        suggestions, meta = ai_helper.suggest_for_tasks(tasks, now)
        if meta.get("used"):
            from webapp import apply_ai_suggestions  # 复用同一套写回逻辑
            apply_ai_suggestions(tasks, suggestions, now)
            print(f"[AI] 已对 {meta['candidates']} 条待确认消息给出建议。{meta.get('sent_scope','')}\n")
        else:
            print(f"[AI] 未产生建议：{meta.get('error')}\n")

    print(build_report(tasks, problems))

    if csv_out:
        # utf-8-sig 写入带 BOM，Excel 双击不乱码
        with open(csv_out, "w", encoding="utf-8-sig", newline="") as f:
            f.write(exporter.to_csv([t for t in tasks]))
        print(f"已导出 CSV：{csv_out}")
    if json_out:
        with open(json_out, "w", encoding="utf-8") as f:
            f.write(exporter.to_json(tasks))
        print(f"已导出 JSON：{json_out}")
    if xlsx_out:
        if not exporter.HAS_OPENPYXL:
            print("未安装 openpyxl，跳过 XLSX 导出。请运行：pip install openpyxl")
        else:
            with open(xlsx_out, "wb") as f:
                f.write(exporter.to_xlsx(tasks))
            print(f"已导出 Excel：{xlsx_out}")

    print("统计：", summarize(tasks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))