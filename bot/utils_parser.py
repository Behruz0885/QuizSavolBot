import re
from typing import List, Tuple, Dict, Any, Optional


def parse_quiz_text(text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Supported formats (case-insensitive):
      1) Question text
      A. option
      B. option
      C. option
      D. option
      Answer: C   |  Answer: 3  |  C  |  3  |  Answer Option Number: 2
      Explanation: ... (optional)  |  (next line after answer) ...

    - Questions can repeat with "2." "3." etc.
    - Explanation may be multiple lines until next question begins.
    """
    errors: List[str] = []
    questions: List[Dict[str, Any]] = []

    if not text or not text.strip():
        return [], ["Empty file."]

    lines = [ln.rstrip() for ln in text.splitlines()]
    i = 0

    qnum_re = re.compile(r"^\s*(\d+)[\.\)]\s*(.+)\s*$")
    opt_re = re.compile(r"^\s*([ABCD])[\.\)]\s*(.+)\s*$", re.IGNORECASE)

    def norm_answer(ans_raw: str) -> Optional[str]:
        a = (ans_raw or "").strip()
        a = re.sub(r"(?i)^(answer|ans|correct|javob)\s*[:\-]?\s*", "", a).strip()
        a = re.sub(r"(?i)^answer\s+option\s+number\s*[:\-]?\s*", "", a).strip()
        a = a.replace(")", "").replace(".", "").strip()
        if not a:
            return None

        m = re.match(r"^([ABCD])$", a, re.IGNORECASE)
        if m:
            return m.group(1).upper()

        m = re.match(r"^([1-4])$", a)
        if m:
            return {"1": "A", "2": "B", "3": "C", "4": "D"}[m.group(1)]

        # ba'zan "Answer: C" butun qator bo‘ladi, yuqorida kesdik, lekin baribir bo‘lishi mumkin:
        m = re.search(r"([ABCD])", a, re.IGNORECASE)
        if m and a.upper() in ("A", "B", "C", "D"):
            return a.upper()

        return None

    def is_question_start(line: str) -> bool:
        return bool(qnum_re.match(line))

    while i < len(lines):
        line = (lines[i] or "").strip()
        if not line:
            i += 1
            continue

        # question start
        m_q = qnum_re.match(line)
        if not m_q:
            i += 1
            continue

        q_text = m_q.group(2).strip()
        start_line_num = i + 1
        i += 1

        opts = {"A": None, "B": None, "C": None, "D": None}

        # read 4 options
        got = 0
        while i < len(lines) and got < 4:
            l = (lines[i] or "").strip()
            if not l:
                i += 1
                continue

            m_o = opt_re.match(l)
            if not m_o:
                break
            key = m_o.group(1).upper()
            val = m_o.group(2).strip()
            opts[key] = val
            got += 1
            i += 1

        if got < 4 or any(opts[k] is None for k in ("A", "B", "C", "D")):
            errors.append(f"Line {start_line_num}: Missing options A-D.")
            # skip to next question
            while i < len(lines) and not is_question_start((lines[i] or "").strip()):
                i += 1
            continue

        # read answer line
        # skip blanks
        while i < len(lines) and not (lines[i] or "").strip():
            i += 1

        if i >= len(lines):
            errors.append(f"Line {start_line_num}: Missing Answer line.")
            break

        ans_line = (lines[i] or "").strip()
        ans = norm_answer(ans_line)
        if ans is None:
            errors.append(f"Line {i+1}: Answer must be 1-4 or A-D. Got: {ans_line}")
            # skip to next question
            i += 1
            while i < len(lines) and not is_question_start((lines[i] or "").strip()):
                i += 1
            continue
        i += 1

        # explanation: optional (can be "Explanation: ..." or free text lines)
        expl_lines: List[str] = []

        # skip blanks
        while i < len(lines) and not (lines[i] or "").strip():
            i += 1

        # if next line starts a new question -> no explanation
        if i < len(lines) and is_question_start((lines[i] or "").strip()):
            explanation = None
        else:
            # read until next question start
            while i < len(lines):
                lraw = (lines[i] or "").rstrip()
                l = lraw.strip()
                if is_question_start(l):
                    break
                if l:
                    # allow "Explanation: text"
                    if l.lower().startswith("explanation:"):
                        expl_lines.append(l.split(":", 1)[1].strip())
                    else:
                        expl_lines.append(l)
                i += 1

            explanation = "\n".join(expl_lines).strip() or None

        questions.append(
            {
                "q_text": q_text,
                "opt_a": opts["A"],
                "opt_b": opts["B"],
                "opt_c": opts["C"],
                "opt_d": opts["D"],
                "correct": ans,
                "explanation": explanation,
            }
        )

    return questions, errors
