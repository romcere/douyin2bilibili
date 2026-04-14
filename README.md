## 📦 项目说明

本项目基于以下开源项目进行扩展开发：

- [Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API)
- [biliup](https://github.com/biliup/biliup)

核心功能代码来源于上述项目，在此基础上进行了整合与功能增强。
感谢原作者 **Evil0ctal** 与 **biliup** 提供的优秀开源实现。

## 🚀 功能简介

- ✅ 抖音视频下载（无水印）
- ✅ B站自动投稿（支持命令行上传）
- ✅ 可组合为“抖音 → B站”自动搬运流程

## 🛠 使用方法

### 1. 抖音视频下载

脚本：`douyin_download.py`

使用方式：

1. 打开入口函数 `main()`
2. 修改目标参数（支持的链接格式详见：[支持的提交格式](https://github.com/Evil0ctal/Douyin_TikTok_Download_API?tab=readme-ov-file#️支持的提交格式)）：

```python
target_url = "抖音视频链接"
```

3. 运行脚本：

```bash
python douyin_download.py
```

---

### 2. B站自动投稿

脚本：`bilibili_upload.py`

#### （1）登录账号

首次使用需要登录以生成 `cookies.json`：

```
python bilibili_upload.py login
```

#### （2）上传视频

```bash
python bilibili_upload.py upload --file 视频.mp4 --title "标题" --tags 标签1 标签2
```

参数说明：

| 参数      | 说明                                                          |
| --------- |-------------------------------------------------------------|
| `--file`  | 视频文件路径                                                      |
| `--title` | 视频标题                                                        |
| `--tags`  | 视频标签（可多个）                                                   |

## 🧩 扩展工具（可选）

如果你希望将项目转换为 **AI 可读上下文文档**（用于代码分析 / Prompt 构建）：

### 安装工具

```bash
pip install code2prompt
```

### 生成文档

```bash
code2prompt -p ./ -o ./prompt.md --line-number -e "*.json,*.log,*.jsonl,*.csv"
```

------

## ⚠️ 注意事项

- 请确保已正确配置 Python 环境（推荐 3.10+）

- B站接口可能存在风控或变动，请自行处理异常情况

- 本项目仅供学习与研究，请勿用于违规用途

  
