import re,hashlib
import numpy as np
from scipy import sparse

LABELS = ["high", "medium", "low"]

INTENT_NAMES = [
    # 请求目标（6）
    "ask_direct_answer", "ask_full_solution", "ask_method", "ask_hint",
    "ask_verification", "explicit_dont_give_answer",
    # 自主学习证据（5）
    "has_attempt", "has_reasoning", "has_specific_stuck_point", "has_guess", "knows_method",
    # 不确定性与上下文（2）
    "explicit_uncertainty", "context_dependent",
]

def normalize_prompt(text):
    if not text:
        return ""
    t = text
    t = unicodedata_normalize(t)
    # 全角 -> 半角（NFKC 已覆盖，再补几个常见全角标点）
    t = t.replace("？", "?").replace("！", "!").replace("，", ",").replace("。", ".")
    t = t.replace("：", ":").replace("（", "(").replace("）", ")").replace("＝", "=")
    # x² / x^2 / x的平方 统一为 x²
    t = re.sub(r"x\s*的\s*平方", "x²", t)
    t = re.sub(r"x\s*\^\s*2", "x²", t)
    t = re.sub(r"x\s*²", "x²", t)
    # 图片相关措辞统一
    t = re.sub(r"图片|图中|图上|照片|截图|附图|图里|这张图|这道图", "图片", t)
    # 重复标点折叠
    t = re.sub(r"([!?.,。])\1+", r"\1", t)
    # 空白归一
    t = re.sub(r"\s+", " ", t).strip()
    return t

def unicodedata_normalize(t):
    import unicodedata
    return unicodedata.normalize("NFKC", t)

def mask_math_content(text):
    if not text:
        return ""
    t = text
    # 图片 -> <IMAGE>
    t = re.sub(r"图片", "<IMAGE>", t)
    # 方程（含等号的数学陈述）-> <EQUATION>
    t = re.sub(r"[^\s,，。.!?？:：]{0,20}[=＝][^\s,，。.!?？:：]{0,20}", "<EQUATION>", t)
    # 公式/算式：数字 + 运算符（× ÷ + - 乘 除 加 减 括号 ²）-> <FORMULA>
    t = re.sub(r"[\d(（].{0,20}[×÷+\-x²()（）].{0,20}[\d)）]", "<FORMULA>", t)
    # 分数/小数/科学计数等带运算符或 ² 的纯数字结构 -> <FORMULA>
    t = re.sub(r"\d+\s*[×÷]\s*\d+", "<FORMULA>", t)
    t = re.sub(r"\d+\s*/\s*\d+", "<FORMULA>", t)
    t = re.sub(r"\d+\s*²", "<FORMULA>", t)
    # 选项字母 A/B/C/D（独立成词时）-> <OPTION>
    t = re.sub(r"(?<![A-Za-z])[ABCD](?![A-Za-z])", "<OPTION>", t)
    # 剩余数字 -> <NUM>
    t = re.sub(r"\d+(?:\.\d+)?", "<NUM>", t)
    return t

_INTENT_PATTERNS = {
    "ask_direct_answer": ["答案是", "答案是多少", "等于多少", "等于几", "得多少", "得数",
                          "结果是多少", "直接给我答案", "直接给答案", "把答案告诉我",
                          "A还是", "B还是", "C还是", "D还是", "选哪个", "是多少",
                          "给我答案", "要答案", "直接答案"],
    "ask_full_solution": ["完整过程", "全过程", "详细过程", "步骤", "过程", "帮我做",
                          "帮我解", "帮我算", "帮我写", "代写", "全部过程", "一步步",
                          "具体过程", "怎么做完", "从头"],
    "ask_method": ["怎么做", "怎么求", "怎么算", "怎么解", "怎么判断", "怎么理解",
                   "用什么方法", "什么方法", "方法", "如何", "怎么得", "怎么想",
                   "如何解", "如何算", "怎么证明"],
    "ask_hint": ["提示", "提示一下", "给点提示", "给个提示", "思路", "启发", "暗示",
                 "指点", "引导"],
    "ask_verification": ["对吗", "对不对", "是不是", "正确吗", "正常吗", "是这样吗",
                         "对吗？", "是不是对", "对不对", "check", "验算", "验证"],
    "explicit_dont_give_answer": ["不要答案", "不用给答案", "只要提示", "只要思路",
                                   "别说答案", "别直接给", "不要直接给", "不要过程",
                                   "要方法不要答案", "没说怎么做", "不要告诉答案"],
    "has_attempt": ["我试了", "我试过", "我做了", "我算到", "我写到", "我列了",
                    "我列方程", "我做到", "我完成了", "我做了这", "我先"],
    "has_reasoning": ["我想到", "我觉得", "我认为", "我是这样", "我的思路", "我猜",
                      "我推测", "我分析", "我判断", "我理解"],
    "has_specific_stuck_point": ["卡在", "卡住", "卡了", "到这一步", "这一步", "就卡",
                                 "卡到这里", "不会了", "算不下去", "做不下去"],
    "has_guess": ["可能", "也许", "大概", "我猜", "估计", "不一定", "是不是可以"],
    "knows_method": ["我知道", "我会", "我记得", "这个要用", "公式是", "定理",
                     "应该用", "可以先用", "用公式"],
    "explicit_uncertainty": ["不会", "不懂", "不确定", "不知道", "没学过", "没听懂",
                             "不理解", "没弄懂", "不会做", "搞不懂"],
    "context_dependent": ["这题", "这个", "这道", "图中", "上面", "这里", "这个图",
                          "这道题", "这题", "如图", "此题"],
}

def extract_intent_features(text):
    if not text:
        return np.zeros(len(INTENT_NAMES), dtype=int)
    feat = np.zeros(len(INTENT_NAMES), dtype=int)
    for i, name in enumerate(INTENT_NAMES):
        if any(p in text for p in _INTENT_PATTERNS[name]):
            feat[i] = 1
    return feat

def build_features(texts, tfidf=None, fit=False):
    """返回稀疏 [intent(13) | masked-tfidf]。fit=True 时拟合 tfidf。"""
    intent = sparse.csr_matrix(np.vstack([extract_intent_features(t) for t in texts]))
    if fit:
        tfidf.fit([mask_math_content(normalize_prompt(t)) for t in texts])
    masked = tfidf.transform([mask_math_content(normalize_prompt(t)) for t in texts])
    return sparse.hstack([intent, masked], format="csr")

def sha256_group(text):
    return hashlib.sha256(normalize_prompt(text).encode("utf-8")).hexdigest()