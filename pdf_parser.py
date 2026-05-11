import fitz, re, os

def extract_all_text(pdf_path):
    doc = fitz.open(pdf_path)
    all_text = []
    for page in doc:
        t = page.get_text('text')
        if t:
            all_text.append(t)
    doc.close()
    return all_text

def parse_exam_questions(texts):
    Q_SEP_SET = {0x3001, 0xFF0B}   # 、for 1-9, ＋for 10+
    O_SEP = 0xFF0E   #．
    # Additional option patterns:
    # 1) Options like A. ①xxx B. ②xxx C. ③xxx D. ④xxx (with circled numbers inside)
    # 2) Options like A．xxx where A is followed by U+FF0E separator
    # 3) Options like A:xxx

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
                
                # Multi-choice option format: A．①xxx or A．(1)xxx
                # where after the letter+sep, the option contains circled numbers
                # Check if it's an option by seeing if after A./B./C./D. there's an option-like structure
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

def parse_knowledge_points(texts):
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

def process_pdf_file(pdf_path, db_module):
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
        questions = parse_exam_questions(texts)
        chapter = filename.replace('.pdf', '')[:100]
        for q in questions:
            if q['options'] and len(q['options']) >= 2:
                db_module.insert_question(q['text'], q['options'], q['answer'], q['explanation'], chapter, '', filename)
        return {'file': filename, 'type': 'questions', 'count': len(questions)}

def process_all_pdfs(pdf_dir, db_module):
    results = []
    if not os.path.isdir(pdf_dir):
        return [{'error': f'Directory not found: {pdf_dir}'}]
    for fname in sorted(os.listdir(pdf_dir)):
        if not fname.lower().endswith('.pdf'):
            continue
        fpath = os.path.join(pdf_dir, fname)
        try:
            result = process_pdf_file(fpath, db_module)
            results.append(result)
        except Exception as e:
            results.append({'file': fname, 'error': str(e)})
    return results