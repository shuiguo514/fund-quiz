import streamlit as st
import json
import random
from datetime import datetime
import database as db

st.set_page_config(page_title="基金刷题神器", page_icon="📚", layout="wide")

db.init_db()

def init_state():
    defaults = {
        'current_qs': [],
        'q_index': 0,
        'answered': False,
        'selected': None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

def render_question(q_row):
    opts = json.loads(q_row['options']) if isinstance(q_row['options'], str) else q_row['options']
    st.markdown(f"#### {q_row['question_text'][:500]}")
    
    opt_list = [f"**{k}.** {v}" for k, v in opts.items()]
    sel = st.radio("请选择答案：", opt_list, index=None, key=f"q_{q_row['id']}")
    
    if st.button("确认答案", key=f"confirm_{q_row['id']}"):
        if sel:
            # choice = sel[0] 会取到 '*'，需要找字母
            import re
            match = re.search(r'([A-D])', sel)
            choice = match.group(1) if match else sel[3] if len(sel) > 3 else sel[0]
            st.session_state.selected = choice
            st.session_state.answered = True
            if choice == q_row['answer']:
                st.success("✅ 正确！")
            else:
                st.error(f"❌ 错误！正确答案是：{q_row['answer']}")
                db.add_wrong_question(q_row['id'])
            # 显示独立存储的解析
            if q_row.get('explanation'):
                with st.expander("📖 答案解析"):
                    st.write(q_row['explanation'])
    if st.session_state.answered:
        st.markdown(f"**你的答案：{st.session_state.selected}** | **正确答案：{q_row['answer']}**")

def nav_buttons(qs_len):
    c1, c2, c3 = st.columns(3)
    idx = st.session_state.q_index
    with c1:
        if idx > 0 and st.button("⬅️ 上一题"):
            st.session_state.q_index -= 1
            st.session_state.answered = False
            st.rerun()
    with c2:
        if idx < qs_len - 1 and st.button("下一题 ➡️"):
            st.session_state.q_index += 1
            st.session_state.answered = False
            st.rerun()
    with c3:
        if st.button("⏭️ 跳过"):
            st.session_state.q_index = min(idx + 1, qs_len - 1)
            st.session_state.answered = False
            st.rerun()

# ===== SIDEBAR =====
with st.sidebar:
    st.title("📚 基金刷题")
    menu = st.radio("功能", [
        "📖 按章节刷题",
        "📋 错题本",
        "📅 复习计划",
        "⚙️ 导入数据",
        "📊 学习统计"
    ], index=0)

# ===== PAGE: 按章节刷题 =====
if menu == "📖 按章节刷题":
    st.title("📖 按章节刷题")
    chapters = db.get_chapters()
    
    if not chapters:
        st.warning("⚠️ 题库为空，请先在「导入数据」页面导入题库！")
        st.stop()
    
    sel_ch = st.selectbox("选择章节", ["全部"] + chapters)
    qs = db.get_all_questions() if sel_ch == "全部" else db.get_questions_by_chapter(sel_ch)
    st.write(f"共 **{len(qs)}** 道题目")
    
    c1, c2 = st.columns([1, 1])
    with c1:
        count = st.number_input("本次刷题数量", 1, min(len(qs), 200), 10)
    with c2:
        if st.button("🎲 开始刷题", type="primary"):
            selected = random.sample(qs, min(count, len(qs)))
            st.session_state.current_qs = selected
            st.session_state.q_index = 0
            st.session_state.answered = False
            st.rerun()
    
    if st.session_state.current_qs:
        idx = st.session_state.q_index
        qs_len = len(st.session_state.current_qs)
        st.progress(idx / qs_len)
        st.markdown(f"**进度：{idx + 1} / {qs_len}**")
        render_question(st.session_state.current_qs[idx])
        nav_buttons(qs_len)
        
        if idx >= qs_len - 1 and st.session_state.answered:
            st.success("🎉 刷题完成！")
            if st.button("🔄 再刷一轮"):
                st.session_state.current_qs = []
                st.rerun()

# ===== PAGE: 按知识点刷题 =====
elif menu == "🎯 按知识点刷题":
    st.title("🎯 按知识点刷题")
    st.info("该功能已移除，请使用「按章节刷题」")

# ===== PAGE: 错题本 =====
elif menu == "📋 错题本":
    st.title("📋 错题本")
    wqs = db.get_wrong_questions()
    
    if not wqs:
        st.info("🎉 太棒了，暂无错题！")
        st.stop()
    
    st.warning(f"当前错题数：{len(wqs)} 道")
    
    for wq in wqs:
        opts = json.loads(wq['options']) if isinstance(wq['options'], str) else wq['options']
        with st.container():
            col1, col2 = st.columns([1, 4])
            with col1:
                st.markdown(f"❌ 错误 {wq['times_wrong']} 次")
            with col2:
                if st.button(f"移除", key=f"rem_{wq['id']}"):
                    db.remove_wrong_question(wq['id'])
                    st.rerun()
            st.markdown(wq['question_text'][:300])
            for k in ['A', 'B', 'C', 'D']:
                if k in opts:
                    mark = "✅" if k == wq['answer'] else ""
                    st.write(f"{k}. {opts[k]} {mark}")
            if wq.get('explanation'):
                with st.expander("📖 解析"):
                    st.write(wq['explanation'])
            st.divider()
    
    if st.button("🗑️ 清空错题本", type="danger"):
        if st.button("⚠️ 确认清空", type="danger"):
            conn = db.get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM wrong_questions")
            conn.commit()
            conn.close()
            st.rerun()

# ===== PAGE: 复习计划 =====
elif menu == "📅 复习计划":
    st.title("📅 复习计划")
    plan = db.get_active_plan()
    
    if plan:
        st.success(f"📆 当前计划：{plan['days']} 天，每天 {plan['daily_count']} 题")
        st.write(f"开始日期：{plan['start_date']}")
        
        records = db.get_records(plan['id'])
        
        if records:
            total_done = sum(r['questions_done'] for r in records)
            total_correct = sum(r['correct_count'] for r in records)
            
            c1, c2, c3 = st.columns(3)
            c1.metric("已完成天数", len(records))
            c2.metric("完成题目数", total_done)
            c3.metric("正确率", f"{total_correct / total_done * 100:.1f}%" if total_done > 0 else "0%")
            
            st.progress(min(len(records) / plan['days'], 1.0))
            st.markdown(f"**进度：{len(records)}/{plan['days']} 天**")
            
            import pandas as pd
            if records:
                df = pd.DataFrame(records)
                st.bar_chart(df.set_index('date')['questions_done'])
        
        if st.button("🛑 暂停计划"):
            conn = db.get_db()
            cur = conn.cursor()
            cur.execute("UPDATE study_plan SET status='paused' WHERE id=?", (plan['id'],))
            conn.commit()
            conn.close()
            st.rerun()
    else:
        st.subheader("📆 设置复习计划")
        days = st.number_input("复习天数", 1, 90, 30)
        total_qs = st.number_input("题库总题数", 10, 5000, 500)
        daily = st.slider("每天刷题数量", 5, 100, min(20, total_qs // days))
        
        st.write(f"计划：{days} 天 × {daily} 题 = {days * daily} 题")
        
        if st.button("🚀 启动计划", type="primary"):
            db.set_study_plan(days, daily)
            st.success("计划已启动！")
            st.rerun()

# ===== PAGE: 导入数据 =====
elif menu == "⚙️ 导入数据":
    st.title("⚙️ 导入数据")
    
    st.subheader("📝 手动添加题目")
    
    q_text = st.text_area("题目文本（支持粘贴多道题，格式不限）", height=150, placeholder="请粘贴题目文本，LLM将自动解析并添加到题库")
    chapter_input = st.text_input("所属章节", value="基金法律法规")
    
    if st.button("🧠 LLM 智能解析并添加", type="primary"):
        if q_text.strip():
            with st.spinner("🧠 LLM 正在智能解析题目，请稍候..."):
                try:
                    import openai
                    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY", "your-api-key"), base_url="https://api.openai.com/v1")
                    
                    prompt = f"""你是一个基金题库专家。请从以下文本中解析出所有题目，输出JSON数组格式。
每道题包含：question_text（题干）、options（选项，字典A-D）、answer（答案字母）、explanation（解析）

文本：
{q_text}

要求：
1. 如果文本中没有明确给出答案，跳过该题
2. 选项如果有多行，合并为一个选项
3. 解析尽量完整
4. 只输出JSON数组，不要其他文字"""
                    
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1
                    )
                    
                    import json as json_mod
                    result_text = response.choices[0].message.content.strip()
                    # 尝试提取JSON
                    if "```json" in result_text:
                        result_text = result_text.split("```json")[1].split("```")[0]
                    elif "```" in result_text:
                        result_text = result_text.split("```")[1].split("```")[0]
                    
                    questions_data = json_mod.loads(result_text)
                    
                    added = 0
                    for q in questions_data:
                        if q.get('options') and len(q['options']) >= 2 and q.get('answer'):
                            db.insert_question(
                                q['question_text'],
                                q['options'],
                                q['answer'],
                                q.get('explanation', ''),
                                chapter_input,
                                '',
                                'LLM导入'
                            )
                            added += 1
                    
                    st.success(f"✅ 成功添加 {added} 道题目！")
                    if added < len(questions_data):
                        st.warning(f"⚠️ 有 {len(questions_data) - added} 道题因格式不完整被跳过")
                        
                except Exception as e:
                    st.error(f"❌ LLM 解析失败：{str(e)}")
                    st.info("💡 备选方案：请使用PDF导入功能")
        else:
            st.warning("请先输入题目文本")
    
    st.divider()
    st.subheader("📄 PDF 导入（备选）")
    pdf_dir = st.text_input("PDF 目录路径", r"D:\Desktop\基金从业\法规")
    
    if st.button("🔍 扫描并导入 PDF", type="secondary"):
        with st.spinner("正在导入，请稍候..."):
            import pdf_parser as pp
            
            results = pp.process_all_pdfs(pdf_dir, db)
            
            for r in results:
                if 'error' in r:
                    st.error(f"❌ {r['file']}: {r['error']}")
                else:
                    icon = "📚" if r['type'] == 'knowledge' else "📝"
                    st.success(f"{icon} {r['file']}：导入 {r['count']} 条")
        
        total, wrong = db.get_stats()
        kps = db.get_knowledge_points()
        st.success(f"✅ 导入完成！题库：{total} 道，知识点：{len(kps)} 个，错题：{wrong} 道")
    
    st.divider()
    st.subheader("🗑️ 数据管理")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🗑️ 清空题目"):
            db.delete_all_questions()
            st.success("题目已清空")
    with c2:
        if st.button("🗑️ 清空知识点"):
            db.delete_all_knowledge_points()
            st.success("知识点已清空")
    
    total, wrong = db.get_stats()
    kps = db.get_knowledge_points()
    st.info(f"当前：{total} 道题目，{len(kps)} 个知识点，{wrong} 道错题")

# ===== PAGE: 学习统计 =====
elif menu == "📊 学习统计":
    st.title("📊 学习统计")
    
    total, wrong = db.get_stats()
    kps = db.get_knowledge_points()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("题库总量", total)
    c2.metric("错题数", wrong)
    c3.metric("正确率", f"{(total - wrong) / total * 100:.1f}%" if total > 0 else "0%")
    
    chapters = db.get_chapters()
    if chapters:
        import pandas as pd
        st.subheader("📖 各章节题目分布")
        data = [{'chapter': ch[:25], 'count': len(db.get_questions_by_chapter(ch))} for ch in chapters]
        st.bar_chart(pd.DataFrame(data).set_index('chapter'))
    
    kp_levels = {}
    for kp in kps:
        kp_levels[kp['level']] = kp_levels.get(kp['level'], 0) + 1
    if kp_levels:
        st.subheader("📚 知识点分布")
        st.write(kp_levels)