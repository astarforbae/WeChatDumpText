# 微信聊天记录分析工具

本项目用于分析从WeChat备份中提取的聊天数据库文件，可以导出私聊和群聊消息记录，支持引用回复识别、按时间范围筛选等功能。主要用于处理[wechatDataBackup](https://github.com/git-jiadong/wechatDataBackup)工具备份的微信聊天记录，将其导出为易读的文本格式。

## 功能特点

- 导出私聊和群聊消息
- 准确识别群聊中的发送者（使用BytesExtra字段提取发送者ID）
- 支持引用回复消息的显示（解析CompressContent字段中的引用内容）
- 支持按时间范围筛选消息
- 过滤特殊格式的消息（如图片、视频等）
- 根据联系人数据库显示用户备注名或昵称

## 主要工具

### 导出聊天记录 (main.py)

这是主要的聊天记录导出工具，支持多种参数配置。

```bash
python main.py [参数]
```

#### 完整参数列表

| 参数 | 描述 | 默认值 |
|------|------|--------|
| `--db` | 数据库文件路径 | `weixin-gui-agent/User/your_wechat_id/Msg/Multi/MSG.db` |
| `--output` | 输出文件路径 | `chat_records_final.txt` |
| `--limit` | 限制导出的消息数量 | 不限制 |
| `--from-date` | 开始日期 (YYYY-MM-DD) | 不限制 |
| `--to-date` | 结束日期 (YYYY-MM-DD) | 不限制 |
| `--sender` | 发送者名称 | `我` |
| `--receiver` | 接收者名称（当无法获取联系人信息时使用） | `老师` |
| `--group` | 导出群聊消息（不提供此参数则默认导出私聊） | `False` |
| `--group-name` | 群聊名称 | `群聊` |
| `--self-id` | 当前用户的微信ID | `your_wechat_id` |

#### 使用示例

**导出群聊消息**
```bash
python main.py --db weixin-example/User/your_wechat_id/Msg/Multi/MSG.db --output example_group_chat.txt --group
```

**导出私聊消息**
```bash
python main.py --db weixin-example/User/your_wechat_id/Msg/Multi/MSG.db --output example_private_chat.txt
```

**限定日期范围导出消息**
```bash
python main.py --group --from-date 2024-10-01 --to-date 2024-11-30 --output example_oct_nov_chat.txt
```

**限制导出消息数量**
```bash
python main.py --limit 500 --output example_limited.txt
```

### 分析消息数据库 (analyze_msg_db.py)

用于分析MSG.db消息结构的工具。

```bash
python analyze_msg_db.py [数据库路径] [-n 消息数量] [-d] [-t]
```

参数说明:
- 数据库路径: 指定要分析的MSG.db文件路径
- -n, --num: 指定分析的消息数量（默认20条）
- -d, --deep: 启用深度分析模式
- -t, --test: 测试所有可能的提取模式

### 分析用户数据库 (analyze_userdata_db.py)

用于分析UserData.db数据库结构的工具。

```bash
python analyze_userdata_db.py [数据库路径] [-s] [-d] [-t 表名] [-a]
```

参数说明:
- 数据库路径: 可选，指定要分析的数据库文件
- -s, --structure: 显示表结构
- -d, --data: 显示表数据
- -t, --table: 指定要分析的表名
- -a, --all: 分析所有找到的数据库

## 输出格式

导出的聊天记录格式如下：

```
发送者名称  (时间戳)
消息内容

接收者名称  (时间戳)
回复内容
```

## 隐私保护

本项目已配置`.gitignore`文件以排除敏感信息：
- 所有以`weixin`开头的文件夹
- 所有`.txt`文件

在将代码提交到GitHub之前，请确保不要提交含有个人信息的数据库文件或其他敏感信息。