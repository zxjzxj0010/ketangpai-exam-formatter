#!/usr/bin/env python3
"""试题排版格式验证脚本

检查项：
1. 题目之间是否恰好三个空行（答案解析行不计入，不视为新题）
2. 选项字母是否为半角 A. B. C. D.
3. 判断题答案是否使用半角括号 (对)/(错)
4. 选择题答案是否使用全角括号（　X　）
5. 题型标识是否正确
6. 题干行是否存在异常换行（通过行结构推断）
7. 题干/选项正文中的注释圆括号是否已改为六角括号〔〕（答案解析行豁免）
8. 填空题答案花括号检查
9. 答案解析位置：应紧跟上一行（最后一个选项或题干行），不空行

用法: python3 validate.py <文件路径>
"""

import re
import sys


def validate(filepath: str) -> list[str]:
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    errors: list[str] = []
    n = len(lines)

    option_line = re.compile(r"^[A-E]\.")
    analysis_line = re.compile(r"^答案解析：")

    # 1. 检测题目分隔：题干行之前的连续空行数（答案解析行不视为新题）
    blank_run = 0
    first_question_seen = False
    for i, line in enumerate(lines, 1):
        stripped = line.rstrip("\n")
        if stripped.strip() == "":
            blank_run += 1
        else:
            is_option = bool(option_line.match(stripped.strip()))
            is_analysis = bool(analysis_line.match(stripped.strip()))
            if not is_option and not is_analysis:
                if first_question_seen:
                    if blank_run != 3:
                        errors.append(
                            f"第{i}行: 题目开始前应有3个空行，实际有{blank_run}个"
                        )
                first_question_seen = True
            blank_run = 0

    # 1b. 答案解析位置：应紧跟上一行（最后一个选项或题干行），前一行不能为空行
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if analysis_line.match(stripped):
            if i >= 2 and lines[i - 2].strip() == "":
                errors.append(
                    f"第{i}行: 答案解析应紧跟上一行（最后一个选项或题干行），不应空行"
                )

    # 2. 选项字母半角检查
    fullwidth_option = re.compile(r"^[Ａ-Ｅ][．.]")
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if fullwidth_option.match(stripped):
            errors.append(f"第{i}行: 选项字母应使用半角，当前为全角: {stripped[:20]}")

    # 3. 判断题检查：答案应为半角括号 (对) 或 (错)
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # 全角括号的判断答案是错误的
        if re.search(r"[（][对错][）]", stripped):
            errors.append(
                f"第{i}行: 判断题答案应使用半角括号 (对)/(错)，当前为全角括号"
            )
        if "[判断题]" in stripped:
            errors.append(f"第{i}行: 判断题不应标注 [判断题] 题型标识")

    # 4. 选择题检查
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if "[单选题]" in stripped or "[多选题]" in stripped:
            # 答案应该用全角括号，不允许半角
            if re.search(r"\([A-E]+\)", stripped):
                errors.append(
                    f"第{i}行: 选择题答案应使用全角括号（　X　），当前为半角括号"
                )
            # 检查全角括号内是否有全角空格
            m = re.search(r"[（]([A-E]+)[）]", stripped)
            if m and not re.search(r"[　][A-D]+[　]", stripped):
                errors.append(
                    f"第{i}行: 选择题答案括号内应使用全角空格包裹，如（　{m.group(1)}　）"
                )

    # 5. 多选题 [多选题] 和分数之间应有空格
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if "[多选题]" in stripped:
            compact = stripped.replace(" ", "")
            if "[多选题][" in compact and "[多选题] [" not in stripped:
                errors.append(f"第{i}行: [多选题] 与分数之间应有一个半角空格")

    # 6. 检查是否有 ↓ 字符
    for i, line in enumerate(lines, 1):
        if "↓" in line:
            errors.append(f"第{i}行: 禁止使用 '↓' 作为换行符，应使用标准换行")

    # 7. 简答题题干末尾句号
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if "[简答题]" in stripped:
            before = stripped.split("[简答题]")[0]
            if before and not before.rstrip().endswith("。"):
                errors.append(f"第{i}行: 简答题题干末尾应加句号")

    # 8. 注释圆括号检查：题干/选项中不应出现注释用圆括号
    #    允许的例外：选择题答案处（　X　）、判断题答案处 (对)/(错)
    choice_answer = re.compile(r"（　[A-E]+　）")
    judge_answer = re.compile(r"[(][对错][)]")
    group_header = re.compile(r"^（\d+[～～]\d+.*(共用题干|共用备选答案)）$")
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # 豁免B1/A3/A4组标题行
        if group_header.match(stripped):
            continue
        # 豁免答案解析行（说明性文本，不强制注释圆括号转换）
        if analysis_line.match(stripped):
            continue
        # 去掉允许的答案括号后，检查是否还有残留圆括号
        cleaned = choice_answer.sub("", stripped)
        cleaned = judge_answer.sub("", cleaned)
        # 半角圆括号残留
        if re.search(r"[(][^)]*[)]", cleaned):
            errors.append(
                f"第{i}行: 题干/选项中注释应使用六角括号〔〕，不应使用圆括号(): {stripped[:30]}"
            )
        # 全角圆括号残留（排除已被替换的选择题答案）
        # 重新检查全角括号
        remaining = cleaned
        if "（" in remaining or "）" in remaining:
            errors.append(
                f"第{i}行: 题干/选项中注释应使用六角括号〔〕，不应使用全角圆括号（）: {stripped[:30]}"
            )

    # 9. 填空题检查
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if "[填空题]" in stripped:
            if "{" not in stripped or "}" not in stripped:
                errors.append(f"第{i}行: 填空题应使用 {{}} 包裹答案")
            if "｛" in stripped or "｝" in stripped:
                errors.append(f"第{i}行: 填空题答案应使用半角花括号 {{}}")

    return errors


def main():
    if len(sys.argv) != 2:
        print("用法: python3 validate.py <文件路径>")
        sys.exit(1)

    filepath = sys.argv[1]
    try:
        errors = validate(filepath)
    except FileNotFoundError:
        print(f"错误: 文件不存在: {filepath}")
        sys.exit(1)

    if errors:
        print(f"发现 {len(errors)} 个格式问题：")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("格式校验通过，未发现问题。")


if __name__ == "__main__":
    main()
