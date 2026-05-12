import fitz, re, os, json

# ============================================================
# MiniMax LLM 解析模式
# ============================================================

def extract_all_text(pdf_path):
    """提取 PDF 所有页面的文本"""
    doc = fitz.open(pdf_path)
    all_text = []
    for page in doc:
        t = page.get_text('text')
        if t:
            all_text.append(t)
    doc.close()
    return all_text


def parse_exam_questions(texts):
    """正则模式解析题目（保留原有逻辑）"""
    Q_SEP_SET = {0x3001, 0xFF0B}
    O_SEP = 0xFF0E

    def is_question_line(s):
        if not s or len(s) < 3:
            return False
        j = 0
        while j < len(s) and s[j].isdigit():
            j += 1
        if j == 0:
            return False
        if j < len(s) and ord(s[j]) in Q_SEP_SET:
            return True
        return False

    def get_q_num_and_text(s):
        j = 0
        while j < len(s) and s[j].isdigit():
            j += 1
        return s[:j], s[j+1:].strip()

    results = []
    lines = []
    for t in texts:
        lines.extend(t.split('\n'))

    i = 0
    while i < len(lines):
        s = lines[i].strip()

        if not s or len(s) < 3:
            i += 1
            continue

        if is_question_line(s):
            q_num, q_text = get_q_num_and_text(s)
            opts = {}
            answer = explanation = None
            found_answer = False

            j = i + 1
            while j < len(lines) and j < i + 50:
                s2 = lines[j].strip()

                if not s2:
                    j += 1
                    continue

                if len(s2) > 2 and s2[0] in 'ABCD' and ord(s2[1]) in (O_SEP, 0x3001, 0xFF1A):
                    opts[s2[0]] = s2[2:].strip()
                    j += 1
                    continue

                opt_match_multi = re.match(r'^([A-D])[．:：]\s*[(（]?[\u2460-⑨\u0030-9①②③④\d]+[)）]?\s*(.+)', s2)
                if opt_match_multi:
                    opts[opt_match_multi.group(1)] = opt_match_multi.group(2).strip()
                    j += 1
                    continue

                if not found_answer and '答案' in s2:
                    ans_match = re.search(r'答案[^\u4e00-\u9fa5]*([A-D])', s2)
                    if ans_match:
                        answer = ans_match.group(1)
                        found_answer = True
                        j += 1
                        if j < len(lines) and '解析' in lines[j].strip():
                            explanation = lines[j].strip().replace('答案解析', '').replace('解析', '').strip()
                            j += 1
                        continue

                if is_question_line(s2):
                    break

                q_text += ' ' + s2
                j += 1

            if q_text and answer and opts and len(opts) >= 2:
                results.append({
                    'num': q_num,
                    'text': q_text.strip(),
                    'options': opts,
                    'answer': answer,
                    'explanation': explanation or ''
                })

            i = j
            continue

        i += 1

    return results


def parse_with_llm(texts, api_key=None, base_url="https://api.minimax.chat/v1", model="MiniMax-Text-01"):
    """
    使用 LLM 智能解析题目文本
    texts: PDF 提取的页面文本列表
    返回结构化题目列表
    """
    import os

    api_key = api_key or os.getenv("MINIMAX_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("未设置 MINIMAX_API_KEY 或 OPENAI_API_KEY 环境变量")

    # 合并所有页面文本
    full_text = "\n".join(texts)

    # 截断避免超出 token 限制（保留前 1.5 万字）
    if len(full_text) > 15000:
        full_text = full_text[:15000] + "\n...（内容已截断）"

    prompt = f"""你是一个专业的基金从业资格考试题库解析专家。请从以下PDF文本中解析出所有题目，输出标准JSON数组格式。

## 输出格式要求
每道题必须包含以下字段：
- question_text: string - 题干文本（保留完整题意）
- options: object - 选项，键为A/B/C/D，值为选项文本
- answer: string - 正确答案字母（如 "A"）
- explanation: string - 答案解析（如果没有则为空字符串）
- chapter: string - 章节名称（根据内容判断，如"基金法律法规"）

## 解析规则
1. 只有明确标注了答案的题目才收录
2. 多选题必须标注所有正确选项（如 "AB"）
3. 选项跨多行时要合并
4. 题目和选项中的序号（如1.2.3.）要去掉，保留实际内容
5. 如果文本中找不到选项内容，尝试根据常见考点补充合理选项
6. 每道题都必须有ABCD四个选项

## 待解析文本：
{full_text}

## 输出要求
- 只输出JSON数组，不要任何其他文字说明
- JSON必须能被json.loads()直接解析
- 选项内容要完整，不能截断"""

    # MiniMax / OpenAI 兼容格式
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        response_format={"type": "json_object"}
    )

    result_text = response.choices[0].message.content.strip()

    # 提取 JSON（防止有 markdown 包裹）
    if "```json" in result_text:
        result_text = result_text.split("```json")[1].split("```")[0]
    elif "```" in result_text:
        result_text = result_text.split("```")[1].split("```")[0]

    data = json.loads(result_text)

    # 如果返回的是 {{"questions": [...]}} 格式
    if isinstance(data, dict) and "questions" in data:
        questions = data["questions"]
    elif isinstance(data, dict) and "data" in data:
        questions = data["data"]
    elif isinstance(data, list):
        questions = data
    else:
        # 尝试找数组
        questions = list(data.values())[0] if len(data) == 1 else []

    # 标准化格式
    normalized = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        opts = q.get('options', {})
        if isinstance(opts, str):
            # 尝试解析选项字符串
            opts = {}
        # 确保有ABCD四个选项
        for key in ['A', 'B', 'C', 'D']:
            if key not in opts:
                opts[key] = opts.get(key.lower(), opts.get(f"option_{key}", ""))

        normalized.append({
            'text': q.get('question_text', q.get('question', '')),
            'options': opts,
            'answer': q.get('answer', q.get('correct_answer', '')),
            'explanation': q.get('explanation', q.get('解析', '')),
            'chapter': q.get('chapter', q.get('category', ''))
        })

    return normalized


def parse_knowledge_points(texts):
    """解析知识点（保留原有逻辑）"""
    kps = []
    current_chapter = ""
    current_section = ""

    chapter_pat = re.compile(r'^第[一二三四五六七八九十\d]+[章节部篇]\s*(.+)')
    section_pat = re.compile(r'^(第[一二三四五六七八九十]+节|\d+\.\d+)\s*(.+)')

    for t in texts:
        lines = t.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue

            cm = chapter_pat.match(line)
            if cm:
                current_chapter = cm.group(1).strip()
                current_section = ""
                kps.append({'chapter': current_chapter, 'section': '', 'title': f'【章节】{current_chapter}', 'level': 'chapter', 'content': line})
                continue

            sm = section_pat.match(line)
            if sm:
                current_section = sm.group(1) + " " + sm.group(2).strip()
                kps.append({'chapter': current_chapter, 'section': current_section, 'title': current_section, 'level': 'section', 'content': line})
                continue

            if current_chapter or current_section:
                level = '一般'
                if '★' in line or '重点' in line or '必背' in line:
                    level = '重要'
                kps.append({'chapter': current_chapter, 'section': current_section, 'title': line[:80], 'level': level, 'content': line})

    return kps


def process_pdf_file(pdf_path, db_module, use_llm=False, llm_api_key=None):
    """
    处理单个 PDF 文件
    use_llm=True 时使用 LLM 智能解析
    """
    filename = os.path.basename(pdf_path)
    is_knowledge = any(k in filename for k in ['笔记', '知识点', '三色', '考点', '教材', '目录'])

    texts = extract_all_text(pdf_path)
    if not texts:
        return {'file': filename, 'type': 'unknown', 'count': 0, 'error': 'No text extracted'}

    if is_knowledge:
        kps = parse_knowledge_points(texts)
        for kp in kps:
            db_module.insert_knowledge_point(kp['chapter'], kp['section'], kp['title'], kp['level'], kp['content'], filename)
        return {'file': filename, 'type': 'knowledge', 'count': len(kps)}
    else:
        if use_llm:
            questions = parse_with_llm(texts, api_key=llm_api_key)
            chapter = filename.replace('.pdf', '')[:100]
            for q in questions:
                opts = q.get('options', {})
                if opts and len(opts) >= 2 and q.get('answer'):
                    db_module.insert_question(
                        q['text'], opts, q['answer'],
                        q.get('explanation', ''), chapter, '', filename
                    )
            return {'file': filename, 'type': 'questions', 'count': len(questions), 'mode': 'llm'}
        else:
            questions = parse_exam_questions(texts)
            chapter = filename.replace('.pdf', '')[:100]
            for q in questions:
                if q['options'] and len(q['options']) >= 2:
                    db_module.insert_question(q['text'], q['options'], q['answer'], q['explanation'], chapter, '', filename)
            return {'file': filename, 'type': 'questions', 'count': len(questions), 'mode': 'regex'}


def process_all_pdfs(pdf_dir, db_module, use_llm=False, llm_api_key=None):
    """批量处理 PDF 目录"""
    results = []
    if not os.path.isdir(pdf_dir):
        return [{'error': f'Directory not found: {pdf_dir}'}]
    for fname in sorted(os.listdir(pdf_dir)):
        if not fname.lower().endswith('.pdf'):
            continue
        fpath = os.path.join(pdf_dir, fname)
        try:
            result = process_pdf_file(fpath, db_module, use_llm=use_llm, llm_api_key=llm_api_key)
            results.append(result)
        except Exception as e:
            results.append({'file': fname, 'error': str(e)})
    return results
