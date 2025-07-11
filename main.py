import sqlite3
import datetime
import os
import argparse
import re
import hashlib
import random
from typing import List, Tuple, Dict, Optional

# ===== 常量定义 =====
# 添加一个常量，用于生成随机名称
CHINESE_SURNAMES = ['李', '王', '张', '刘', '陈', '杨', '赵', '黄', '周', '吴', 
                   '徐', '孙', '胡', '朱', '高', '林', '何', '郭', '马', '罗', 
                   '梁', '宋', '郑', '谢', '韩', '唐', '冯', '于', '董', '萧', 
                   '程', '曹', '袁', '邓', '许', '傅', '沈', '曾', '彭', '吕']

# ===== 数据库操作函数 =====
def connect_to_database(db_path: str) -> Tuple[sqlite3.Connection, sqlite3.Cursor]:
    """连接到SQLite数据库并返回连接和游标对象"""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"数据库文件不存在: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        return conn, cursor
    except sqlite3.Error as e:
        raise sqlite3.Error(f"连接数据库失败: {e}")

def fetch_messages(cursor: sqlite3.Cursor, is_group_chat: bool = False, limit: Optional[int] = None, 
                  date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[Tuple]:
    """
    获取聊天记录，支持限制条数和时间范围
    
    参数:
    cursor: 数据库游标
    is_group_chat: 是否为群聊消息
    limit: 限制返回的消息数量
    date_from: 开始日期，格式为YYYY-MM-DD
    date_to: 结束日期，格式为YYYY-MM-DD
    
    返回:
    消息列表，每条消息包含时间戳、是否发送者、内容等信息
    """
    # 无论群聊还是私聊，都需要获取StrTalker来识别发送者
    if is_group_chat:
        query = """
        SELECT CreateTime, IsSender, StrContent, StrTalker, Type, BytesExtra, CompressContent
        FROM MSG WHERE 1=1
        """
    else:
        query = """
        SELECT CreateTime, IsSender, StrContent, StrTalker, CompressContent
        FROM MSG WHERE 1=1
        """
    
    params = []
    
    # 添加时间范围过滤
    if date_from:
        try:
            timestamp_from = int(datetime.datetime.strptime(date_from, '%Y-%m-%d').timestamp())
            query += " AND CreateTime >= ?"
            params.append(timestamp_from)
        except ValueError:
            print(f"警告: 忽略无效的开始日期格式 {date_from}，应为YYYY-MM-DD")
    
    if date_to:
        try:
            # 设置结束日期为当天的23:59:59
            date_obj = datetime.datetime.strptime(date_to, '%Y-%m-%d')
            date_obj = date_obj.replace(hour=23, minute=59, second=59)
            timestamp_to = int(date_obj.timestamp())
            query += " AND CreateTime <= ?"
            params.append(timestamp_to)
        except ValueError:
            print(f"警告: 忽略无效的结束日期格式 {date_to}，应为YYYY-MM-DD")
    
    query += " ORDER BY CreateTime ASC"
    
    # 添加结果限制
    if limit and limit > 0:
        query += f" LIMIT {limit}"
    
    cursor.execute(query, params)
    return cursor.fetchall()

# ===== 发送者ID提取函数 =====
def extract_sender_id(bytes_extra, is_sender=0):
    """
    从BytesExtra字段中提取消息发送者ID
    
    参数:
    bytes_extra (bytes): 消息的BytesExtra字段数据
    is_sender (int): 消息的IsSender字段值，默认为0(他人发送的消息)
    
    返回:
    str or None: 提取到的发送者ID，如果无法提取则返回None
    """
    # 如果是自己发送的消息，不需要从BytesExtra中提取ID
    if is_sender == 1:
        return None 
        
    if not bytes_extra:
        return None
    
    try:
        # 标准消息发送者ID模式: 0x1A(长度)(0x08 0x01 0x12)(长度)(用户ID)
        sender_pattern = re.compile(b'\x1a.{1,2}\x08\x01\x12(.{1,30})', re.DOTALL)
        sender_matches = sender_pattern.findall(bytes_extra)
        
        # 特殊消息模式(某些群聊消息)
        special_pattern = re.compile(b'\x0a\x04\x08\x05\x10\x01\x1a\x0e\x08\x01\x12(.{1,30})', re.DOTALL)
        special_matches = special_pattern.findall(bytes_extra)
        
        # 合并匹配结果
        all_matches = sender_matches + special_matches
        
        for match in all_matches:
            if len(match) > 1:
                id_length = match[0]  # 第一个字节是长度
                if id_length > 0 and id_length < len(match):
                    try:
                        user_id = match[1:1+id_length].decode('utf-8', errors='ignore')
                        if user_id:
                            return user_id
                    except:
                        pass
        
        return None
    except Exception as e:
        # 出错时返回None
        return None

def parse_compress_content(compress_content):
    """
    解析CompressContent字段中的引用回复消息
    
    参数:
    compress_content (bytes): 消息的CompressContent字段数据
    
    返回:
    dict: 包含引用消息的信息，如果不是引用消息则返回None
    {
        'quoted_content': 被引用的消息内容,
        'quoted_sender_id': 被引用消息的发送者ID (可能为None)
    }
    """
    if not compress_content:
        return None
        
    try:
        # 尝试从CompressContent中提取引用的消息内容
        quoted_content = None
        quoted_sender_id = None
        
        # 微信引用消息通常采用XML格式
        # 1. 首先尝试完整解析XML
        try:
            # 查找XML格式的内容
            xml_pattern = re.compile(b'<msg.*?</msg>', re.DOTALL)
            xml_matches = xml_pattern.findall(compress_content)
            
            if xml_matches:
                for xml_data in xml_matches:
                    try:
                        xml_text = xml_data.decode('utf-8', errors='ignore')
                        
                        # 尝试提取<title>标签中的内容（通常是引用的原始消息）
                        title_match = re.search(r'<title>(.*?)</title>', xml_text)
                        if title_match:
                            quoted_content = title_match.group(1).strip()
                            
                        # 尝试提取<content>标签中的内容（可能包含更多信息）
                        if not quoted_content:
                            content_match = re.search(r'<content>(.*?)</content>', xml_text)
                            if content_match:
                                content_text = content_match.group(1).strip()
                                # 从content中可能需要进一步解析
                                if content_text:
                                    quoted_content = content_text
                        
                        # 尝试提取发送者ID
                        sourceid_match = re.search(r'sourceid="([^"]+)"', xml_text)
                        if sourceid_match:
                            quoted_sender_id = sourceid_match.group(1)
                        
                        # 如果找到了引用内容，可以结束循环
                        if quoted_content:
                            break
                    except:
                        continue
        except:
            pass
        
        # 2. 如果XML解析失败，尝试二进制匹配特定模式
        if not quoted_content:
            # 在压缩数据中查找可能包含文本的部分
            # 微信的引用消息通常在某些固定位置存储引用文本
            
            # 尝试直接解码整个数据
            try:
                decoded = compress_content.decode('utf-8', errors='ignore')
                
                # 寻找可能的消息片段，如有意义的连续汉字或字母
                words = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]{3,}', decoded)
                if words:
                    # 只取最长的片段作为可能的引用内容
                    longest_word = max(words, key=len)
                    if len(longest_word) >= 3:  # 确保是有意义的内容
                        quoted_content = longest_word
            except:
                pass
                
            # 如果直接解码还是没找到，尝试在二进制数据中查找可能的文本块
            if not quoted_content:
                # 微信引用消息中的文本可能是UTF-16LE编码的
                try:
                    utf16_text = compress_content.decode('utf-16-le', errors='ignore')
                    words = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]{3,}', utf16_text)
                    if words:
                        longest_word = max(words, key=len)
                        if len(longest_word) >= 3:
                            quoted_content = longest_word
                except:
                    pass
        
            # 查找特定的引用消息二进制模式（根据微信的数据格式可能需要调整）
            if not quoted_content:
                # 一些常见的二进制数据模式
                patterns = [
                    # 可能需要根据实际情况调整这些模式
                    (b'\x12.\x0a([\x00-\xff]{5,100})', 0),  # 模式1
                    (b'\x0a.\x12([\x00-\xff]{5,100})', 0),  # 模式2
                    (b'\x1a.([\x00-\xff]{5,100})', 0)       # 模式3
                ]
                
                for pattern, group_index in patterns:
                    try:
                        matches = re.finditer(pattern, compress_content, re.DOTALL)
                        for match in matches:
                            data_chunk = match.group(group_index + 1)
                            
                            # 尝试不同的编码解码文本
                            for encoding in ['utf-8', 'utf-16-le', 'gbk', 'gb18030']:
                                try:
                                    text = data_chunk.decode(encoding, errors='ignore')
                                    # 检查是否包含有意义的文本
                                    if re.search(r'[\u4e00-\u9fa5a-zA-Z0-9]{3,}', text):
                                        quoted_content = text.strip()
                                        break
                                except:
                                    continue
                            
                            if quoted_content:
                                break
                    except:
                        continue
                    
                    if quoted_content:
                        break
        
        # 清理提取的文本
        if quoted_content:
            # 移除多余的控制字符和非打印字符
            quoted_content = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', quoted_content)
            # 限制长度
            if len(quoted_content) > 100:
                quoted_content = quoted_content[:97] + "..."
        
        # 只有当找到了引用内容时才返回结果
        if quoted_content:
            return {
                'quoted_content': quoted_content,
                'quoted_sender_id': quoted_sender_id
            }
        
        return None
    except Exception as e:
        # 解析错误时返回None
        return None

# ===== 联系人信息获取函数 =====
def get_contact_map(db_path: str) -> Dict[str, str]:
    """
    构建联系人ID到名称的映射，优先使用备注。
    
    参数:
    db_path: MSG.db数据库路径，用于找到同目录的MicroMsg.db
    
    返回:
    字典，键为联系人ID，值为联系人名称(优先备注)
    """
    contact_map = {}
    
    # 尝试连接 MicroMsg.db
    try:
        microMsg_db_path = os.path.join(os.path.dirname(os.path.dirname(db_path)), 'MicroMsg.db')
        if not os.path.exists(microMsg_db_path):
            print(f"警告: 联系人数据库 'MicroMsg.db' 未找到于: {microMsg_db_path}")
            return contact_map

        conn_contact = sqlite3.connect(microMsg_db_path)
        cursor_contact = conn_contact.cursor()

        # 从 'Contact' 表中读取备注(Remark)、昵称(NickName)和别名(Alias)
        try:
            cursor_contact.execute("SELECT UserName, Remark, NickName, Alias FROM Contact")
            for user_id, remark, nick_name, alias in cursor_contact.fetchall():
                                # 优先使用备注
                if remark:
                    contact_map[user_id] = remark
                elif nick_name and user_id not in contact_map:
                    contact_map[user_id] = nick_name
                elif alias and user_id not in contact_map:
                    contact_map[user_id] = alias
        except sqlite3.Error as e:
            print(f"警告: 读取 'Contact' 表失败: {e}。将尝试从其他位置获取。")

        # 备用方案：从 ContactHeadImgUrl 表获取
        if not contact_map: # 仅在主要方法失败时尝试
            try:
                cursor_contact.execute("SELECT UserName, NickName FROM ContactHeadImgUrl")
                for user_id, nick_name in cursor_contact.fetchall():
                    if nick_name and user_id not in contact_map:
                        contact_map[user_id] = nick_name
            except sqlite3.Error:
                pass # 静默失败，因为这是备用方案

        conn_contact.close()
    except Exception as e:
        print(f"警告: 访问联系人数据库时发生严重错误: {e}")
    
    return contact_map

# ===== 消息内容处理函数 =====
def process_message_content(content: str) -> str:
    """
    处理消息内容，过滤特殊格式或标记
    
    参数:
    content: 原始消息内容
    
    返回:
    处理后的消息内容
    """
    if content is None:
        return ""
    
    # 过滤HTML标签
    content = re.sub(r'<[^>]+>', '', content)
    
    # 检测并替换OpenAI API密钥
    # 使用一个统一的正则表达式匹配所有API密钥格式
    # \b表示单词边界，确保匹配完整的密钥
    # 匹配以sk-开头的所有API密钥，包括sk-proj-格式
    content = re.sub(r'\bsk-[a-zA-Z0-9_-]{20,}', 'x', content)
    
    # 可以添加更多的内容处理逻辑
    return content.strip()

def should_skip_message(content: str) -> bool:
    """
    判断是否应该跳过某些消息
    
    参数:
    content: 消息内容
    
    返回:
    如果应该跳过则返回True，否则返回False
    """
    if content is None:
        return True
    
    content = content.strip()
    # 跳过特定格式的消息
    if (content.startswith('<') or 
        content.startswith('sk') or 
        content == '收到一条图片' or
        content == '收到一条视频' or
        content.startswith('[语音]')):
        return True
    
    return False

def format_timestamp(timestamp: int) -> str:
    """
    将Unix时间戳格式化为可读的日期时间字符串
    
    参数:
    timestamp: Unix时间戳
    
    返回:
    格式化的日期时间字符串
    """
    try:
        return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError, OverflowError):
        return "无效时间戳"

def generate_persistent_name(talker_id: str) -> str:
    """
    为特定的talker_id生成一个持久化的随机名称
    
    参数:
    talker_id: 用户ID
    
    返回:
    生成的随机名称
    """
    # 使用talker_id的哈希值作为随机种子，确保同一ID总是得到相同的名字
    hash_value = int(hashlib.md5(talker_id.encode()).hexdigest(), 16)
    random.seed(hash_value)
    
    # 从中文姓氏列表中选择一个
    surname = CHINESE_SURNAMES[hash_value % len(CHINESE_SURNAMES)]
    
    # 返回格式化的名字
    return f"{surname}{'先生' if hash_value % 2 == 0 else '女士'}"

def extract_names_from_chat_content(content: str) -> List[str]:
    """
    从聊天内容中提取可能的用户名
    
    参数:
    content: 消息内容
    
    返回:
    提取到的用户名列表
    """
    names = []
    
    # 1. 提取引号中的名字，如"张三"邀请...
    quote_matches = re.findall(r'"([^"]+)"(?:邀请|修改|撤回|发起|说)', content)
    names.extend(quote_matches)
    
    # 2. 提取@后的名字
    at_matches = re.findall(r'@([^\s@]+)', content)
    for name in at_matches:
        if name != "所有人" and len(name) < 20:  # 过滤掉"所有人"和太长的名字
            names.append(name)
    
    # 3. 提取冒号前的名字，如"张三: 你好"
    colon_matches = re.findall(r'^([^:：]+)[：:]', content)
    for name in colon_matches:
        if len(name.strip()) < 20:  # 过滤掉太长的名字
            names.append(name.strip())
    
    return names

# ===== 聊天记录生成函数 =====
def write_chat_records(messages: List[Tuple], output_path: str, contact_map: Dict[str, str] = None,
                      is_group_chat: bool = False, sender_name: str = "我", 
                      receiver_name: str = "老师", group_name: str = "群聊", self_id: str = None) -> int:
    """
    将聊天记录写入文件，并返回写入的消息数量
    
    参数:
    messages: 消息列表
    output_path: 输出文件路径
    contact_map: 联系人映射表
    is_group_chat: 是否为群聊
    sender_name: 发送者名称
    receiver_name: 接收者名称 (仅当无法找到联系人信息时使用)
    group_name: 群聊名称
    self_id: 当前用户的微信ID
    
    返回:
    写入的消息数量
    """
    message_count = 0
    persistent_names = {}
    sender_id_map = {}  # 用于缓存提取的发送者ID
    other_talker_id = None  # 记录私聊中对方的talker_id

    with open(output_path, 'w', encoding='utf-8') as f:
        for message in messages:
            if is_group_chat:
                if len(message) < 7: 
                    continue
                
                timestamp, is_sender, content, talker_id, msg_type, bytes_extra, compress_content = message
                
                # 首先检查是否应该跳过这条消息
                if should_skip_message(content):
                    # 对于空内容的消息，检查是否包含引用消息
                    if not content and compress_content:
                        quoted_msg = parse_compress_content(compress_content)
                        if quoted_msg and quoted_msg['quoted_content']:
                            # 这是一个引用回复消息，我们应该处理它而不是跳过
                            pass
                        else:
                            continue
                    else:
                        continue
                
                # 处理消息内容
                processed_content = process_message_content(content)
                
                # 检查是否包含引用回复内容
                quoted_text = None
                if compress_content:
                    quoted_msg = parse_compress_content(compress_content)
                    if quoted_msg and quoted_msg['quoted_content']:
                        quoted_text = quoted_msg['quoted_content']
                
                # 确定发送者显示名称
                if is_sender == 1:
                    # 自己发送的消息
                    name = sender_name
                else:
                    # 提取发送者ID
                    sender_id = extract_sender_id(bytes_extra, is_sender)
                    
                    # 如果能提取到发送者ID
                    if sender_id:
                        sender_id_map[talker_id] = sender_id  # 缓存提取的ID
                        
                        # 优先使用联系人映射表中的名称
                        if sender_id in contact_map:
                            name = contact_map[sender_id]
                        elif sender_id == self_id:
                            # 如果是当前用户的ID（应该不会出现在这里，但以防万一）
                            name = sender_name
                        else:
                            # 如果没有映射，使用持久化随机名称
                            if sender_id not in persistent_names:
                                persistent_names[sender_id] = generate_persistent_name(sender_id)
                            name = persistent_names[sender_id]
                    else:
                        # 如果无法提取ID，使用备用方法
                        # 1. 尝试从消息内容提取名字
                        extracted_names = extract_names_from_chat_content(processed_content)
                        if extracted_names:
                            name = extracted_names[0]  # 使用第一个提取到的名字
                        else:
                            # 2. 如果无法提取名字，使用持久化随机名称
                            if talker_id not in persistent_names:
                                persistent_names[talker_id] = generate_persistent_name(talker_id)
                            name = persistent_names[talker_id]
            else:
                # 私聊消息处理
                if len(message) < 5:  # 现在私聊消息应该有5个字段
                    continue
                timestamp, is_sender, content, talker_id, compress_content = message
                
                if should_skip_message(content):
                    # 对于空内容的消息，检查是否包含引用消息
                    if not content and compress_content:
                        quoted_msg = parse_compress_content(compress_content)
                        if quoted_msg and quoted_msg['quoted_content']:
                            # 这是一个引用回复消息，我们应该处理它而不是跳过
                            pass
                        else:
                            continue
                    else:
                        continue
                    
                processed_content = process_message_content(content)
                
                # 如果是自己发送的消息
                if is_sender == 1:
                    name = sender_name
                else:
                    # 如果是对方发送的消息，尝试获取对方的备注名
                    # 首先尝试直接在联系人映射中查找talker_id
                    if talker_id and talker_id in contact_map:
                        name = contact_map[talker_id]
                    else:
                        # 如果talker_id不在联系人映射中，可能需要进一步处理
                        # 对于私聊，talker_id通常是对方的wxid
                        name = receiver_name  # 默认使用接收者名称
                        
                        # 遍历联系人映射，查找是否有其他可能的匹配
                        # 这是一种兜底方案，如果直接匹配失败
                        for contact_id, contact_name in contact_map.items():
                            if contact_id in talker_id or talker_id in contact_id:
                                name = contact_name
                                break
                
                # 检查是否包含引用回复内容
                quoted_text = None
                if compress_content:
                    quoted_msg = parse_compress_content(compress_content)
                    if quoted_msg and quoted_msg['quoted_content']:
                        quoted_text = quoted_msg['quoted_content']
            
            # 写入聊天记录
            formatted_time = format_timestamp(timestamp)
            f.write(f"{name}  ({formatted_time})\n")
            
            # 如果存在引用内容，先显示引用内容
            if quoted_text:
                # 美化引用内容的显示格式
                quoted_lines = quoted_text.split('\n')
                f.write("┌─────────────────────────────\n")
                for line in quoted_lines:
                    f.write(f"│ {line}\n")
                f.write("└─────────────────────────────\n")
            
            # 如果原始消息非空，显示消息内容
            if processed_content:
                f.write(f"{processed_content}\n\n")
            elif quoted_text:  # 如果原始消息为空但有引用内容，则添加空行
                f.write("\n")
            else:
                f.write("\n")  # 确保每条消息之后都有空行
            
            message_count += 1
            
    return message_count

# ===== 命令行参数处理 =====
def parse_arguments():
    """
    解析命令行参数
    
    使用示例:
    - 导出群聊消息:
      python main.py --group --output group_chat.txt
      
    - 导出私聊消息:
      python main.py --db weixin-liwenhao/User/your_wechat_id/Msg/Multi/MSG.db --output private_chat.txt
      
    - 限定日期范围:
      python main.py --group --from-date 2024-10-01 --to-date 2024-11-30 --output oct_nov_chat.txt
    """
    parser = argparse.ArgumentParser(description='导出微信聊天记录到文本文件')
    
    parser.add_argument('--db', type=str, default='weixin-gui-agent/User/your_wechat_id/Msg/Multi/MSG.db',
                        help='数据库文件路径')
    parser.add_argument('--output', type=str, default='chat_records_final.txt',
                        help='输出文件路径')
    parser.add_argument('--limit', type=int, default=None,
                        help='限制导出的消息数量')
    parser.add_argument('--from-date', type=str, default=None,
                        help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--to-date', type=str, default=None,
                        help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--sender', type=str, default='我',
                        help='发送者名称')
    parser.add_argument('--receiver', type=str, default='老师',
                        help='接收者名称（当无法获取联系人信息时使用）')
    parser.add_argument('--group', action='store_true',
                        help='导出群聊消息')
    parser.add_argument('--group-name', type=str, default='群聊',
                        help='群聊名称')
    parser.add_argument('--self-id', type=str, default='your_wechat_id',
                        help='当前用户的微信ID')
    
    return parser.parse_args()

# ===== 主函数 =====
def main():
    """主函数"""
    args = parse_arguments()
    
    print(f"开始导出聊天记录...")
    print(f"- 数据库文件: {args.db}")
    print(f"- 输出文件: {args.output}")
    
    if args.from_date:
        print(f"- 开始日期: {args.from_date}")
    if args.to_date:
        print(f"- 结束日期: {args.to_date}")
    if args.limit:
        print(f"- 限制条数: {args.limit}")
    
    print(f"- 类型: {'群聊' if args.group else '私聊'}")
    
    try:
        # 1. 连接数据库
        conn, cursor = connect_to_database(args.db)
        
        # 2. 获取消息
        print("- 正在读取消息数据...")
        messages = fetch_messages(cursor, args.group, args.limit, args.from_date, args.to_date)
        print(f"  读取了 {len(messages)} 条消息")
        
        # 3. 获取联系人映射（无论是群聊还是私聊）
        print("- 正在分析联系人信息...")
        contact_map = get_contact_map(args.db)
        print(f"  找到了 {len(contact_map)} 位联系人的信息")
        
        # 4. 写入文件
        message_count = write_chat_records(
            messages, args.output, contact_map, args.group, 
            args.sender, args.receiver, args.group_name, args.self_id
        )
        
        print(f"成功导出 {message_count} 条聊天记录到文件: {args.output}")
        
    except (sqlite3.Error, FileNotFoundError) as e:
        print(f"错误: {e}")
    finally:
        # 5. 关闭数据库连接
        if 'conn' in locals() and conn:
            conn.close()
            print("数据库连接已关闭。")

# ===== 程序入口 =====
if __name__ == "__main__":
    main() 