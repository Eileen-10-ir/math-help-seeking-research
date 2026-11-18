"""Versioned midterm support layer without changing frozen recognition/state code."""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
import json
import math
import re
from typing import Any, Iterable


SUPPORT_VERSION = "edutrace-midterm-support-v1-20261105"
B4_SUPPORT_VERSION = "edutrace-midterm-support-b4-quality-guard-v1-20261105"
CONSTRAINED_SUFFIX = (
    "不要直接给出最终答案或完整代做解答。请根据学生当前卡点给出一个具体、"
    "可执行的下一步；优先用提问或必要的中间步骤引导，并邀请学生继续作答。"
)

HISTORY_REFERENCE_PATTERNS = (
    "前面那道题",
    "沿用前面的题目",
    "上一条提示",
    "刚才的题目",
    "继续前面的题",
)


def _normalize_math(text: str) -> str:
    table = str.maketrans(
        {
            "−": "-",
            "－": "-",
            "＋": "+",
            "＝": "=",
            "×": "*",
            "✕": "*",
            "÷": "/",
            "（": "(",
            "）": ")",
            "²": "^2",
            "ˆ": "^",
        }
    )
    normalized = text.translate(table).lower()
    normalized = re.sub(r"x\s*(?:的)?\s*(?:2次方|二次方|平方)", "x^2", normalized)
    normalized = normalized.replace("加", "+").replace("减", "-")
    normalized = normalized.replace("等于", "=")
    return re.sub(r"\s+", "", normalized)


def _signed_coefficient(raw: str | None, default: int) -> int:
    if raw in (None, ""):
        return default
    if raw == "+":
        return 1
    if raw == "-":
        return -1
    return int(raw)


def _history_items(history: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    return tuple(json.loads(json.dumps(item, ensure_ascii=False)) for item in history)


@dataclass(frozen=True)
class TaskContext:
    """Single source of truth for the actual task and actually supplied history."""

    task_id: str
    question: str
    source: str
    history: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    math_kind: str = "unknown"
    parameters: dict[str, Any] = field(default_factory=dict)
    parse_status: str = "unsupported"

    @property
    def has_history(self) -> bool:
        return bool(self.history)

    @property
    def local_capability(self) -> bool:
        return self.parse_status == "parsed" and self.math_kind in {
            "quadratic",
            "linear",
            "same_denominator_fraction",
            "arithmetic",
            "triangle_area",
            "rectangle_area",
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "question": self.question,
            "source": self.source,
            "history": list(self.history),
            "math_kind": self.math_kind,
            "parameters": self.parameters,
            "parse_status": self.parse_status,
            "has_history": self.has_history,
            "local_capability": self.local_capability,
        }


def build_task_context(
    task_id: str,
    question: str,
    history: Iterable[dict[str, Any]] | None = None,
    source: str = "runtime_actual_question",
) -> TaskContext:
    """Parse only the supplied question; never reload a task by ``task_id``."""
    question = str(question or "").strip()
    actual_history = _history_items(history or [])
    normalized = _normalize_math(question)

    quadratic = re.search(
        r"(?P<a>[+-]?\d*)x\^2(?P<b>[+-]\d*)x(?P<c>[+-]\d+)=0(?:$|[^\d])",
        normalized,
    )
    if quadratic:
        a = _signed_coefficient(quadratic.group("a"), 1)
        b = _signed_coefficient(quadratic.group("b"), 1)
        c = int(quadratic.group("c"))
        if a == 1:
            return TaskContext(
                task_id,
                question,
                source,
                actual_history,
                "quadratic",
                {"a": a, "b": b, "c": c},
                "parsed",
            )

    linear = re.search(
        r"(?P<a>[+-]?\d*)x(?P<b>[+-]\d+)=(?P<c>[+-]?\d+)(?:$|[^\d])",
        normalized,
    )
    if linear:
        return TaskContext(
            task_id,
            question,
            source,
            actual_history,
            "linear",
            {
                "a": _signed_coefficient(linear.group("a"), 1),
                "b": int(linear.group("b")),
                "c": int(linear.group("c")),
            },
            "parsed",
        )

    fraction = re.search(
        r"(?P<a>\d+)/(?P<d>\d+)\+(?P<b>\d+)/(?P=d)(?:$|[^\d])", normalized
    )
    if fraction:
        return TaskContext(
            task_id,
            question,
            source,
            actual_history,
            "same_denominator_fraction",
            {key: int(fraction.group(key)) for key in ("a", "b", "d")},
            "parsed",
        )

    arithmetic = re.search(
        r"(?P<a>-?\d+)(?P<op>[+\-*/])(?P<b>-?\d+)(?:=\?|是多少|等于多少)?(?:$|[^\d])",
        normalized,
    )
    if arithmetic:
        return TaskContext(
            task_id,
            question,
            source,
            actual_history,
            "arithmetic",
            {
                "a": int(arithmetic.group("a")),
                "b": int(arithmetic.group("b")),
                "op": arithmetic.group("op"),
            },
            "parsed",
        )

    triangle = re.search(
        r"(?:底|底边)(?P<base>\d+)(?:厘米|cm)?[,，、]?高(?P<height>\d+)", normalized
    )
    if triangle and "三角形" in normalized:
        return TaskContext(
            task_id,
            question,
            source,
            actual_history,
            "triangle_area",
            {"base": int(triangle.group("base")), "height": int(triangle.group("height"))},
            "parsed",
        )

    rectangle = re.search(
        r"(?:长方形)?.*?长(?P<length>\d+)(?:厘米|cm)?[,，、]?宽(?P<width>\d+)", normalized
    )
    if rectangle and "面积" in normalized:
        return TaskContext(
            task_id,
            question,
            source,
            actual_history,
            "rectangle_area",
            {"length": int(rectangle.group("length")), "width": int(rectangle.group("width"))},
            "parsed",
        )

    return TaskContext(
        task_id,
        question,
        source,
        actual_history,
        "unknown",
        {},
        "unsupported",
    )


def detect_help_intent(text: str) -> str:
    text = str(text or "")
    if re.search(r"直接.{0,8}(?:答案|结果)|只要.{0,6}(?:答案|结果)|帮我(?:写完|做完)|替我完成", text):
        return "direct_answer"
    if re.search(r"完整.{0,6}(?:过程|步骤|解答|推导)|详细.{0,6}(?:过程|步骤)", text):
        return "full_solution"
    if re.search(r"对吗|是否(?:正确|合理)|检查|核验|验算|哪里错", text):
        return "verification"
    if re.search(r"为什么|原理|概念|什么意思|是什么|依据", text):
        return "concept_explanation"
    if re.search(r"提示|一点点|小提示|别告诉.{0,4}答案|不要直接", text):
        return "hint"
    if re.search(r"方法|思路|怎么(?:做|算|解|开始|找)|如何", text):
        return "method"
    if re.search(r"是不是|确认|可以吗", text):
        return "confirmation"
    return "unspecified"


def _actual_supports(history: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    supports = []
    for item in history:
        support = item.get("support") or {}
        if support.get("status") in {"local_success", "success"} and support.get("text"):
            supports.append(support)
    return supports


def next_hint_level(context: TaskContext) -> int:
    """Advance only from hints that were actually returned to the student."""
    levels = [
        int(item["hint_level"])
        for item in _actual_supports(context.history)
        if str(item.get("hint_level", "")).isdigit()
    ]
    return min(3, max(levels, default=0) + 1)


def _divisor_pairs(value: int) -> list[tuple[int, int]]:
    value = abs(value)
    if value == 0:
        return [(0, 0)]
    return [(i, value // i) for i in range(1, math.isqrt(value) + 1) if value % i == 0]


def _operation_name(op: str) -> str:
    return {"+": "加法", "-": "减法", "*": "乘法", "/": "除法"}.get(op, "运算")


def progressive_hint(
    context: TaskContext,
    level: int,
    student_text: str,
    quality_guard: bool = False,
) -> tuple[str, str]:
    """Return a task-grounded hint without completing the full problem."""
    level = max(1, min(3, int(level)))
    p = context.parameters
    kind = context.math_kind

    if kind == "quadratic":
        b, c = p["b"], p["c"]
        if level == 1:
            text = (
                f"先把它看成 `(x+p)(x+q)`：需要满足 `p+q={b}`、`pq={c}`。"
                f"先列出 {abs(c)} 的因数对，再判断符号；你先写出一组候选可以吗？"
            )
        elif level == 2:
            pairs = "、".join(f"{a}和{b_}" for a, b_ in _divisor_pairs(c))
            sign = "同号" if c > 0 else "异号"
            text = (
                f"常数项是 {c}，候选绝对值因数对有：{pairs}；积为 {c}，所以两个数应{sign}。"
                f"再用和为 {b} 排除不合适的组合。你选哪一对？"
            )
        else:
            text = (
                f"把中间结构写完整：`x²+({b})x+({c})=(x+p)(x+q)`，"
                f"右边展开后是 `x²+(p+q)x+pq`。现在只需填写满足 `p+q={b}`、`pq={c}` 的 p、q，"
                "再由你继续写零乘积这一步。"
            )
        return text, f"quadratic_progressive_L{level}"

    if kind == "same_denominator_fraction":
        a, b, d = p["a"], p["b"], p["d"]
        if level == 1:
            text = (
                f"两个分数的分母都是 {d}，表示每一份大小相同；相加时先合并份数。"
                f"你先算一共有 `{a}+{b}` 份，分母是否需要改变？"
            )
        elif level == 2:
            text = (
                f"同分母规则是 `a/{d}+b/{d}=(a+b)/{d}`。"
                f"把本题的 {a} 和 {b} 代入分子位置，先写出未化简的分数。"
            )
        else:
            text = (
                f"先写到中间步骤 `({a}+{b})/{d}`。接下来由你计算分子，并检查结果还能否约分；"
                "请同时用一句话说明分母保持不变的原因。"
            )
        return text, f"fraction_progressive_L{level}"

    if kind == "linear":
        a, b, c = p["a"], p["b"], p["c"]
        inverse = -b
        sign = "+" if inverse >= 0 else "-"
        magnitude = abs(inverse)
        if level == 1:
            text = (
                f"先消去左边的常数项 {b:+d}：等式两边要同时 `{sign}{magnitude}`。"
                "你先写出操作后的等式，暂时不要急着求 x。"
            )
        elif level == 2:
            rhs = c - b
            text = (
                f"两边同时 `{sign}{magnitude}` 后，左边只剩 `{a}x`，右边应计算 `{c}{sign}{magnitude}`。"
                f"请你核对是否得到 `{a}x={rhs}`。"
            )
        else:
            rhs = c - b
            text = (
                f"现在已有 `{a}x={rhs}`。为了让 x 单独留下，等式两边应同时除以 {a}；"
                "请你完成这一步并把结果代回原式检查。"
            )
        return text, f"linear_progressive_L{level}"

    if kind == "triangle_area":
        base, height = p["base"], p["height"]
        if level == 1:
            if quality_guard:
                text = (
                    "两个全等三角形可以拼成同底同高的平行四边形，所以三角形面积要取一半。"
                    f"本题先写出 `{base}×{height}`，算出乘积后再除以 2；你先完成乘法这一步。"
                )
            else:
                text = (
                    f"本题对应的底是 {base}、高是 {height}。先回忆三角形面积与同底同高平行四边形的关系："
                    "面积公式最后为什么要除以 2？"
                )
        elif level == 2:
            text = (
                f"使用 `三角形面积=底×高÷2`，把本题数据代入为 `{base}×{height}÷2`。"
                "请你先算乘法，再处理除以 2。"
            )
        else:
            product = base * height
            text = (
                f"中间乘积是 `{base}×{height}={product}`，还要除以 2。"
                "请你完成最后一步，并检查面积单位是否写成平方单位。"
            )
        return text, f"triangle_progressive_L{level}"

    if kind == "rectangle_area":
        length, width = p["length"], p["width"]
        if level == 1:
            text = (
                f"长方形的长是 {length}、宽是 {width}。面积表示有多少个单位小方格，"
                "应该用加法还是 `长×宽`？"
            )
        elif level == 2:
            text = f"把公式写成 `面积={length}×{width}`，请你计算并说明为什么单位要写平方单位。"
        else:
            text = (
                f"可以把它看作 {length} 行、每行 {width} 个单位小方格。"
                "请你用乘法完成总数，并写出面积单位。"
            )
        return text, f"rectangle_progressive_L{level}"

    if kind == "arithmetic":
        a, b, op = p["a"], p["b"], p["op"]
        if op == "*" and re.search(r"为什么|相同加数|几个几|乘法.*(?:意思|意义)", student_text):
            if level == 1:
                text = (
                    f"`{a}×{b}`可以看成 {b} 个 {a} 相加，也可以交换角度看成 {a} 个 {b} 相加。"
                    f"你先选一种，把它写成重复加法，不必先报结果。"
                )
            elif level == 2:
                text = (
                    f"先画出 {b} 组、每组 {a} 个小点，或写成 `{a}+{a}+…` 共 {b} 个加数。"
                    "请说明这里的两个数分别表示“每组几个”和“有几组”。"
                )
            else:
                text = (
                    f"从 `{a}×{b}` 到重复加法时，加数是 {a}，加数个数是 {b}。"
                    "请你把重复加法写完整，再用乘法算一次并比较。"
                )
            return text, f"multiplication_concept_L{level}"
        if level == 1:
            text = f"这一步是{_operation_name(op)}。先说说你准备从 {a} 和 {b} 中怎样拆数或凑整？"
        elif level == 2:
            text = (
                f"先保持原运算 `{a}{op}{b}`，可以把其中一个数拆成更容易计算的部分。"
                "请你先写出拆分，不要只报结果。"
            )
        else:
            text = (
                f"把 `{a}{op}{b}` 分成一个容易心算的中间步骤和剩余部分；"
                "请你完成中间步骤，再说明怎样合并。"
            )
        return text, f"arithmetic_progressive_L{level}"

    if quality_guard:
        return (
            "我目前不能可靠解析题目，因此不会猜测条件。请把完整算式或题干发来，并标出你已经做到哪一步；"
            "收到后我会先核对这一步，再给出对应方法的下一步。",
            f"unsupported_quality_guard_L{level}",
        )
    return (
        "我目前不能可靠解析这道题的具体数字，因此不猜测条件。请补充当前题目中的一个关键条件，"
        "或贴出你卡住的那一步；我可以先解释相应方法，但不会虚构题目参数。",
        f"unsupported_safe_L{level}",
    )


def verify_student_step(
    context: TaskContext,
    student_text: str,
    quality_guard: bool = False,
) -> dict[str, Any] | None:
    """Finite checks for supported structures; never evaluate arbitrary expressions."""
    text = _normalize_math(student_text)
    p = context.parameters
    if context.math_kind == "quadratic":
        match = re.search(r"\(x(?P<p>[+-]\d+)\)\*?\(x(?P<q>[+-]\d+)\)", text)
        if match:
            left, right = int(match.group("p")), int(match.group("q"))
            correct = left + right == p["b"] and left * right == p["c"]
            return {
                "kind": "factorization",
                "correct": correct,
                "message": (
                    f"展开后一次项系数是 {left + right}，常数项是 {left * right}。"
                    + ("这与当前题目一致；请继续说明零乘积下一步。" if correct else f"当前题目要求分别是 {p['b']} 和 {p['c']}，请先核对符号或因数对。")
                ),
            }
        semantic_text = student_text.translate(str.maketrans({"−": "-", "－": "-"}))
        relation = (
            re.search(
                r"(?:和|相加)(?:为|是|等于)?(?P<sum>-?\d+).{0,12}?"
                r"(?:积|相乘)(?:为|是|等于)?(?P<product>-?\d+)",
                semantic_text,
            )
            if quality_guard
            else None
        )
        if relation:
            observed_sum = int(relation.group("sum"))
            observed_product = int(relation.group("product"))
            correct = observed_sum == p["b"] and observed_product == p["c"]
            return {
                "kind": "quadratic_sum_product",
                "correct": correct,
                "message": (
                    f"你写的“和为 {observed_sum}、积为 {observed_product}”与当前方程一致。"
                    f"下一步请列出 {abs(p['c'])} 的因数对，再选出和为 {p['b']} 的一对。"
                    if correct
                    else f"当前方程要求和为 {p['b']}、积为 {p['c']}；请先核对一次项系数和常数项。"
                ),
            }
    elif context.math_kind == "same_denominator_fraction":
        fraction_rule_pattern = (
            r"(?:分母.{0,5}(?:不变|保持)|先(?:把)?(?:两个)?分子(?:相)?加|"
            r"先(?:把)?(?:相)?加(?:两个)?分子|分子相加)"
            if quality_guard
            else r"(?:分母.{0,5}(?:不变|保持)|先把?分子相加|分子相加)"
        )
        if re.search(fraction_rule_pattern, student_text):
            return {
                "kind": "fraction_rule",
                "correct": True,
                "message": f"这个方向正确：当前两个分数都以 {p['d']} 分之一为单位，所以先合并分子表示的份数。请你写出中间式，并说明分母为何保持不变。",
            }
        match = re.search(
            r"(?:得到|等于|算成|写成)\s*(?P<n>\d+)/(?P<d>\d+)", text
        )
        if match:
            expected = Fraction(p["a"] + p["b"], p["d"])
            observed = Fraction(int(match.group("n")), int(match.group("d")))
            correct = observed == expected
            return {
                "kind": "fraction_result",
                "correct": correct,
                "message": (
                    "这个分数与当前加法结果等值；请再解释同分母时为什么只合并分子。"
                    if correct
                    else f"请先保留当前分母 {p['d']}，只合并两个分子，再检查是否需要约分。"
                ),
            }
    elif context.math_kind == "linear":
        match = re.search(r"(?P<a>-?\d*)x=(?P<c>-?\d+)", text)
        if match:
            left = _signed_coefficient(match.group("a"), 1)
            right = int(match.group("c"))
            expected = p["c"] - p["b"]
            correct = left == p["a"] and right == expected
            inverse = -p["b"]
            operation = f"{p['c']}{inverse:+d}"
            return {
                "kind": "linear_step",
                "correct": correct,
                "message": (
                    "移项后的等式与当前题目一致；下一步请让 x 的系数变成 1。"
                    if correct
                    else f"消去常数项后应保留 {p['a']}x，并把右边计算为 {operation}；请重新核对。"
                ),
            }
    elif context.math_kind == "triangle_area":
        expression = f"{p['base']}*{p['height']}/2"
        if expression in text:
            return {
                "kind": "triangle_formula",
                "correct": True,
                "message": "底、高与面积公式匹配；请完成计算并写平方单位。",
            }
        expected = p["base"] * p["height"] // 2
        claimed = re.search(
            r"(?:我(?:算出|得到|认为)|结果(?:是|为|等于)|面积(?:是|为|等于)|"
            r"算成|得到)\s*(?P<value>-?\d+)",
            text,
        ) if quality_guard else None
        numbers = [int(value) for value in re.findall(r"(?<!\d)-?\d+(?!\d)", text)]
        if claimed or (not quality_guard and numbers and re.search(r"(?:面积|结果|平方)", student_text)):
            observed = int(claimed.group("value")) if claimed else numbers[-1]
            return {
                "kind": "triangle_result",
                "correct": observed == expected,
                "message": (
                    "这个面积结果与当前底、高匹配；请再说明为什么要除以2。"
                    if observed == expected
                    else f"请先按 `底×高÷2` 核对；当前题目的底是 {p['base']}、高是 {p['height']}，不要把两者直接相加。"
                ),
            }
    elif context.math_kind == "rectangle_area":
        claimed = re.search(
            r"(?:我(?:算出|得到|认为)|结果(?:是|为|等于)|面积(?:是|为|等于)|"
            r"算成|得到)\s*(?P<value>-?\d+)",
            text,
        ) if quality_guard else None
        numbers = [int(value) for value in re.findall(r"(?<!\d)-?\d+(?!\d)", text)]
        if claimed or (not quality_guard and numbers and re.search(r"(?:面积|结果|平方)", student_text)):
            observed = int(claimed.group("value")) if claimed else numbers[-1]
            expected = p["length"] * p["width"]
            return {
                "kind": "rectangle_result",
                "correct": observed == expected,
                "message": (
                    "这个面积结果与当前长、宽匹配；请补充平方单位并解释乘法表示什么。"
                    if observed == expected
                    else f"长方形面积应按 `长×宽` 检查，而不是把 {p['length']} 和 {p['width']} 相加。请先写出乘法算式。"
                ),
            }
    elif context.math_kind == "arithmetic":
        matches = re.findall(r"(?:结果(?:是|为)|得到|等于)\s*(-?\d+)", text)
        if matches:
            observed = int(matches[-1])
            a, b, op = p["a"], p["b"], p["op"]
            expected = {
                "+": lambda: a + b,
                "-": lambda: a - b,
                "*": lambda: a * b,
                "/": lambda: a / b,
            }[op]()
            correct = observed == expected
            return {
                "kind": "arithmetic_result",
                "correct": correct,
                "message": (
                    "结果核验正确；请再写出一个拆分、逆运算或乘法口诀依据。"
                    if correct
                    else f"这个结果与当前{_operation_name(op)}不一致。请先把 {a} 和 {b} 按原运算重新列式，再写一个中间步骤。"
                ),
            }
    return None


def _is_complex_request(text: str, context: TaskContext) -> bool:
    if not context.local_capability:
        return True
    return bool(re.search(r"详细|系统|多种方法|举一反三|完整解释|为什么.*为什么", text))


def choose_route(
    analysis: dict[str, Any], context: TaskContext, student_text: str, version: str
) -> dict[str, Any]:
    """Route with risk as a constraint, not the sole cloud eligibility signal."""
    level = analysis.get("decision_level", "medium")
    eligible = bool(analysis.get("eligible", True))
    intent = detect_help_intent(student_text)
    hint_level = next_hint_level(context)
    repeated_stuck = hint_level >= 3 or len(_actual_supports(context.history)) >= 3
    simple_verification = intent in {"verification", "confirmation"} and context.local_capability
    complex_request = _is_complex_request(student_text, context)

    if version in {"B1", "B2"}:
        if not eligible:
            route, reason = "edge_verify", "legacy_three_path_ineligible"
        elif level == "high":
            route, reason = "edge_fixed", "legacy_three_path_high"
        elif level == "medium":
            route, reason = "cloud_constrained", "legacy_three_path_medium"
        else:
            route, reason = "cloud_direct", "legacy_three_path_low"
    elif version in {"B3", "B4"}:
        step_check = (
            verify_student_step(context, student_text, quality_guard=True)
            if version == "B4"
            else None
        )
        if step_check is not None:
            route, reason = "edge_verify", "quality_guard_deterministic_verification"
        elif version == "B4" and intent in {"verification", "confirmation"}:
            route, reason = "cloud_constrained", "quality_guard_unverifiable_step"
        elif simple_verification:
            route, reason = "edge_verify", "deterministic_local_verification"
        elif level == "high" and intent in {"direct_answer", "full_solution"}:
            route, reason = "edge_fixed", "high_direct_answer_control"
        elif repeated_stuck:
            route, reason = "cloud_constrained", "local_scaffold_exhausted"
        elif level == "high" and context.local_capability and intent in {
            "method",
            "concept_explanation",
            "hint",
            "unspecified",
        }:
            route, reason = "edge_fixed", "high_help_locally_supported"
        elif level == "high":
            route, reason = "cloud_constrained", "high_help_local_capability_insufficient"
        elif level == "medium" and not complex_request and context.local_capability:
            route, reason = "edge_fixed", "medium_simple_local_scaffold"
        elif level == "medium":
            route, reason = "cloud_constrained", "medium_complex_or_unsupported"
        elif not complex_request and context.local_capability and intent in {
            "verification",
            "confirmation",
            "hint",
        }:
            route, reason = "edge_verify", "low_simple_local_support"
        else:
            route, reason = "cloud_constrained", "low_complex_teaching"
    else:
        raise ValueError(f"Unknown optimized version: {version}")

    return {
        "route": route,
        "route_reason": reason,
        "dependency_risk": level,
        "help_intent": intent,
        "local_capability": context.local_capability,
        "next_hint_level": hint_level,
        "repeated_stuck": repeated_stuck,
        "complex_request": complex_request,
    }


def build_cloud_messages(
    context: TaskContext,
    student_text: str,
    constrained: bool,
    hint_level: int,
    quality_guard: bool = False,
) -> list[dict[str, str]]:
    system = (
        "你是一位小学数学学习辅导老师。必须只依据下面的当前实际题目和真实对话历史回答，"
        "不得替换题目数字，不得声称存在未提供的历史。\n"
        f"当前实际题目：{context.question or '题目信息尚不完整'}\n"
        f"已使用的本地提示等级：L{max(0, hint_level - 1)}。"
    )
    if constrained:
        system += "\n教学约束：" + CONSTRAINED_SUFFIX
    if quality_guard:
        system += (
            "\n质量保护：先回应学生当前卡点。若学生给出了答案或步骤，可以核验该内容；"
            "不得把学生未给出的最终答案、完整推导或后续全部步骤主动披露。"
            "只有能指出具体算式依据时才纠错；无法可靠判断时应明确说明并请求必要信息。"
        )
    messages = [{"role": "system", "content": system}]
    for item in context.history[-8:]:
        user_text = str(item.get("text", "")).strip()
        support = item.get("support") or {}
        if user_text:
            messages.append({"role": "user", "content": user_text})
        if support.get("status") in {"local_success", "success"} and support.get("text"):
            messages.append({"role": "assistant", "content": str(support["text"])})
    current = student_text + ("\n\n" + CONSTRAINED_SUFFIX if constrained else "")
    messages.append({"role": "user", "content": current})
    return messages


def execute_optimized_support(
    student_text: str,
    analysis: dict[str, Any],
    context: TaskContext,
    gateway: Any,
    version: str,
    forced_route: str | None = None,
) -> dict[str, Any]:
    decision = choose_route(analysis, context, student_text, version)
    if forced_route:
        decision = {**decision, "route": forced_route, "route_reason": "external_reference_arm"}
    route = decision["route"]
    hint_level = decision["next_hint_level"] if version in {"B2", "B3", "B4"} else 1

    base = {
        "routing_version": B4_SUPPORT_VERSION if version == "B4" else SUPPORT_VERSION,
        "optimization_version": version,
        "task_context": context.as_dict(),
        "help_intent": decision["help_intent"],
        "local_capability": decision["local_capability"],
        "route_reason": decision["route_reason"],
        "route_requested": route,
        "messages_sent": [],
        "external_cloud_attempts": 0,
        "external_cloud_successes": 0,
        "cloud_calls": 0,
        "hint_level": hint_level if route.startswith("edge") else None,
        "mathematical_check": None,
    }

    if route in {"edge_fixed", "edge_verify"}:
        check = verify_student_step(
            context, student_text, quality_guard=version == "B4"
        )
        if check and route == "edge_verify":
            text, template = check["message"], f"verified_{check['kind']}_v1"
        else:
            text, template = progressive_hint(
                context,
                hint_level,
                student_text,
                quality_guard=version == "B4",
            )
        return {
            **base,
            "text": text,
            "fixed_template_id": template,
            "provider": "edutrace_parameterized_edge",
            "tier": f"本地渐进提示L{hint_level}",
            "route_executed": route,
            "status": "local_success",
            "mathematical_check": check,
        }

    constrained = route == "cloud_constrained"
    messages = build_cloud_messages(
        context,
        student_text,
        constrained,
        hint_level,
        quality_guard=version == "B4",
    )
    cloud = gateway.request(messages)
    executed = route if cloud.get("status") == "success" else "cloud_unavailable"
    return {
        **base,
        **cloud,
        "messages_sent": messages,
        "provider": "existing_cloud_model",
        "tier": "受限云端教学" if constrained else "直接云端支持",
        "route_executed": executed,
        "cloud_calls": cloud.get("external_cloud_attempts", 0),
        "planned_external_call": int(route in {"cloud_direct", "cloud_constrained"}),
    }


def validate_support_record(
    context: TaskContext, support: dict[str, Any]
) -> dict[str, Any]:
    """Deterministic guards; these are not human teaching-quality scores."""
    messages = support.get("messages_sent") or []
    combined_messages = "\n".join(str(item.get("content", "")) for item in messages)
    generated_messages = "\n".join(
        str(item.get("content", ""))
        for item in messages
        if item.get("role") in {"system", "assistant"}
    )
    text = str(support.get("text", ""))
    route = str(support.get("route_requested", ""))

    context_ok = True
    if route.startswith("cloud"):
        context_ok = (
            context.question in combined_messages
            if context.question
            else "题目信息尚不完整" in combined_messages
        )

    history_ok = context.has_history or not any(
        phrase in text or phrase in generated_messages for phrase in HISTORY_REFERENCE_PATTERNS
    )

    structure_ok = True
    if context.math_kind == "same_denominator_fraction":
        denominators = {int(value) for value in re.findall(r"/(\d+)", text)}
        structure_ok = not denominators or denominators == {context.parameters["d"]}
    elif context.math_kind == "quadratic":
        frozen_constraints = "a+b=-5" in _normalize_math(text) or "ab=6" in _normalize_math(text)
        current_is_frozen = context.parameters["b"] == -5 and context.parameters["c"] == 6
        structure_ok = current_is_frozen or not frozen_constraints

    return {
        "context_consistency_pass": context_ok,
        "math_structure_pass": structure_ok,
        "history_reference_pass": history_ok,
        "automatic_pass": context_ok and structure_ok and history_ok,
        "scope": "automatic consistency only; not C/T/A/H/U/S or learning effect",
    }
