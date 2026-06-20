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
- ✅ B站登录后自动获得cookie

## 🛠 使用方法

### 自动将抖音视频上传到B站

1. 手动配置`config/douyin_config.yaml`文件中的抖音`cookie`
2. 运行`python bilibili_upload.py login`，自动生成B站cookie

3. 使用 `auto_pipeline.py` 脚本，将 `DOUYIN_USER_URL` 配置为目标用户主页地址后，即可一键运行完成全流程处理。

### 1. 抖音视频下载

脚本：`douyin_download.py`

#### （1）使用说明

1. 需要自行获取抖音的`cookie`，并将其序列化后放入`config/douyin_config.yaml`中

2. 准备目标视频链接（支持格式详见：[支持的提交格式](https://github.com/Evil0ctal/Douyin_TikTok_Download_API?tab=readme-ov-file#️支持的提交格式)）

#### （2）视频信息获取

```bash
# 获取精简视频信息
python douyin_download.py info <视频链接>

# 获取完整原始数据
python douyin_download.py info <视频链接> --full

# 保存为 JSON 文件
python douyin_download.py info <视频链接> --output data.json
```

#### （3）视频下载

```bash
# 下载无水印视频（默认）
python douyin_download.py download <视频链接>

# 下载带水印视频（暂未实现）
python douyin_download.py download <视频链接> --watermark

# 下载时不添加文件名前缀（暂未实现）
python douyin_download.py download <视频链接> --no-prefix
```

---

### 2. B站自动投稿

脚本：`bilibili_upload.py`

#### （1）登录账号

首次使用需要登录以生成 `cookies.json`（存放于`config/bili_cookies.json`）：

```bash
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
| `--cover`     | str       | None         | 封面图片路径（未实现）                                       |
| `--lines`     | str       | AUTO         | 上传线路（AUTO/bda/bda2/ws/qn/tx/txa）                       |
| `--threads`   | int       | 3            | 并发上传线程数                                               |
| `--cookie`    | str       | cookies.json | Cookie 文件路径                                              |

### 3.抖音获取用户视频链接

脚本：`douyin_user_info.py`

```bash
# 基本用法（位置参数 + 默认值）
python douyin_user_info.py MS4wLjABAAAAsFL91bhVsEDoW39ZsExLDP6vhQ901VeWqx_eANoIMjJM4fKuSnka68tqyBHJs87j

# 指定数量和游标
python douyin_user_info.py <sec_user_id> -c 5 -m 0

# 输出到 stdout（控制台）
python douyin_user_info.py <sec_user_id> -o -

# 保存到自定义文件
python douyin_user_info.py <sec_user_id> -o my_output.json

# 查看帮助
python douyin_user_info.py --help
```

## ⚙ 使用GitHub自动运行

### 1. Fork 本仓库

点击右上角 **Fork**，将本仓库复制到你的账号下。

### 2. 配置 Secrets

进入你 Fork 后的仓库，点击 **Settings → Secrets and variables → Actions → New repository secret**，依次添加以下两个 Secret：

#### `DOUYIN_COOKIE`

你的抖音登录 Cookie，用于访问抖音接口。

获取方式：

1. 浏览器打开 https://www.douyin.com 并登录
2. 按 `F12` 打开开发者工具，切换到 **Network** 标签
3. 刷新页面，随意点击一个请求
4. 在请求头（Request Headers）中找到 `Cookie` 字段，复制其完整值

| 字段   | 值                     |
| ------ | ---------------------- |
| Name   | `DOUYIN_COOKIE`        |
| Secret | 你复制的 Cookie 字符串 |

------

#### `BILIBILI_CREDENTIALS`

你的 B 站登录凭证，JSON 格式。

获取方式：

1. 在本地运行 `python crawler_suite/bilibili_upload.py login` 完成登录
2. 找到生成的 `config/bili_cookies.json` 文件
3. 将文件的完整内容粘贴进来

| 字段   | 值                                   |
| ------ | ------------------------------------ |
| Name   | `BILIBILI_CREDENTIALS`               |
| Secret | `bili_cookies.json` 的完整 JSON 内容 |

### 3. 修改配置

编辑 `auto_pipeline.py`，根据需要调整以下配置项：

```python
# 目标抖音用户主页链接
DOUYIN_USER_URL = "https://www.douyin.com/user/..."

# B 站分区 ID，138=搞笑，自行调整
BILI_TID = 138

# 默认标签
BILI_TAGS = ["抖音", "搬运"]

# 标题关键词过滤（留空列表则不过滤）
TITLE_INCLUDE_KEYWORDS = []       # 标题必须包含其中一个
TITLE_EXCLUDE_KEYWORDS = ["xxx"]  # 标题不能包含其中任何一个
```

### 4. 启用 GitHub Actions

1. 进入你 Fork 后的仓库，点击顶部 **Actions** 标签
2. 点击 **I understand my workflows, go ahead and enable them**（首次使用需要手动开启）
3. 在左侧找到 **auto-dy2bili**，点击右侧 **Enable workflow**

### 5. 运行时机

Workflow 会在以下北京时间自动触发：

| UTC 时间 | 北京时间 |
| -------- | -------- |
| 11:30    | 19:30    |
| 12:30    | 20:30    |
| 13:30    | 21:30    |
| 14:30    | 22:30    |

也可以在 **Actions → auto-dy2bili → Run workflow** 手动触发。

### 其他

- Cookie 有过期时间，失效后需要重新获取并更新对应的 Secret
- B 站凭证同样有效期有限，过期后需重新登录并更新

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

- GitHub每60天会自动关闭闲置工作流，需进行一次提交进行活跃：2026.6.20
  
