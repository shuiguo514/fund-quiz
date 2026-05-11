# 📚 基金刷题神器

基于 Streamlit 的基金从业资格考试刷题应用，支持电脑、手机、平板多端使用。

## 功能

- 📖 **按章节刷题** - 随机抽题，实时判断对错
- 📋 **错题本** - 自动收集错题，方便复习
- 📅 **复习计划** - 设定每日目标，追踪进度
- ⚙️ **导入数据** - 支持 LLM 智能解析添加题目
- 📊 **学习统计** - 可视化学习数据

## 部署

本项目可一键部署到 [Streamlit Cloud](https://share.streamlit.io)：

1. 将代码推送到 GitHub 仓库
2. 登录 [share.streamlit.io](https://share.streamlit.io)
3. 点击 **New app** → 选择你的仓库 → 部署

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 使用说明

- 题库数据存储在云端，所有设备同步
- 建议使用 Chrome/Safari 访问以获得最佳体验
