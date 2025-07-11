# 微信聊天记录分析工具

本项目用于分析从WeChat备份中提取的聊天数据库文件，可以导出私聊和群聊消息记录，支持引用回复识别、按时间范围筛选等功能。主要用于处理[wechatDataBackup](https://github.com/git-jiadong/wechatDataBackup)工具备份的微信聊天记录，将其导出为易读的文本格式。

## 使用方法

### 准备工作

1. 首先使用[wechatDataBackup](https://github.com/git-jiadong/wechatDataBackup)工具导出微信聊天数据
   - 下载并运行wechatDataBackup.exe
   - 按照工具提示进行全量导出
   - 随后在工具中选择一个聊天框，选择右上角最左边的图标（一个箭头，显示文本：“将此聊天框单独导出”），得到一个新的文件夹

2. 将导出的数据文件夹放置到正确位置
   - 将wechatDataBackup导出的整个文件夹（包含User目录和config.json）复制到本项目的下
   - 确保文件夹结构如下所示：
   ```
   chat-evol/           # 本项目目录
     |- main.py
     |- README.md
     |- ...
     |- weixin-backup/       # wechatDataBackup导出的数据文件夹(可以自定义名称)
            |- User/
                |- wxid_xxx/
                |- Msg/
                    |- MicroMsg.db
                    |- Multi/
                        |- MSG.db
                |- FileStorage/
                    |- ...
            |- config.json
            |- wechatDataBackup.exe
   ```

3. 确认微信数据库路径
   - 数据库文件通常位于导出文件夹的`User/wxid_xxx/Msg/Multi/MSG.db`
   - 联系人信息通常位于`User/wxid_xxx/Msg/MicroMsg.db`

### 使用示例

使用下面的命令格式运行工具，根据需要替换相应的参数：

```bash
python main.py --db 导出文件夹路径/User/wxid_xxx/Msg/Multi/MSG.db --output 输出文件名.txt [其他参数]
```

例如，如果您将wechatDataBackup导出的文件夹命名为`weixin-alice`并放在本项目同级目录下，可以使用如下命令：

**导出群聊消息：**
```bash
python main.py --db ../weixin-alice/User/wxid_xxx/Msg/Multi/MSG.db --output alice_group_chat.txt --group --self-id wxid_xxx
```

**导出私聊消息：**
```bash
python main.py --db ../weixin-alice/User/wxid_xxx/Msg/Multi/MSG.db --output alice_private_chat.txt --self-id wxid_xxx
```

> **注意：** 请将上述命令中的`wxid_xxx`替换为实际的微信ID，可以在导出文件夹的User目录下找到。

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

## 常见问题

**Q: 如何找到自己的微信ID?**  
A: 微信ID通常在wechatDataBackup导出文件夹的User目录下，是以"wxid_"开头的文件夹名。

**Q: 为什么有些消息显示的发送者名称不正确?**  
A: 确保使用正确的`--self-id`参数，并确保MicroMsg.db文件完好，以便程序能正确获取联系人信息。

**Q: 导出的消息数据不完整怎么办?**  
A: 尝试使用wechatDataBackup导出前先退出并重新登录微信，确保所有数据都写入数据库。

## 隐私保护

本项目已配置`.gitignore`文件以排除敏感信息：
- 所有以`weixin`开头的文件夹
- 所有`.txt`文件

在将代码提交到GitHub之前，请确保不要提交含有个人信息的数据库文件或其他敏感信息。