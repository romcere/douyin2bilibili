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
python bilibili_upload.py upload --file 视频.mp4 --title "标题" --tid 138 --tags 标签1 标签2 --desc "视频简介" --copyright 2 --source "xxx" 
```

参数说明：

| 参数          | 类型      | 默认值       | 说明                                                         |
| ------------- | --------- | ------------ | ------------------------------------------------------------ |
| `--file`      | str       | 必填         | 本地视频文件路径                                             |
| `--title`     | str       | 必填         | 视频标题                                                     |
| `--tid`       | int       | 21           | 分区 ID（默认 21＝日常）。完整分区对照可参考：https://bilitool.timerring.com/tid.html。注意：此参数仅支持子分区 ID，主分区 ID（如 1）不可直接使用。 |
| `--tags`      | list[str] | []           | 标签列表（可多个）                                           |
| `--desc`      | str       | ""           | 视频简介                                                     |
| `--copyright` | int       | 1            | 版权类型：1=自制，2=转载                                     |
| `--source`    | str       | ""           | 转载来源（仅 copyright=2 时有效，且必填）                    |
| `--cover`     | str       | None         | 封面图片路径                                                 |
| `--lines`     | str       | AUTO         | 上传线路（AUTO/bda/bda2/ws/qn/tx/txa）                       |
| `--threads`   | int       | 3            | 并发上传线程数                                               |
| `--cookie`    | str       | cookies.json | Cookie 文件路径                                              |

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

  
