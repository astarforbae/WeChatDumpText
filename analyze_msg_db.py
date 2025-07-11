import os
import sqlite3
import sys
import re
import argparse
from xml.etree import ElementTree as ET

def extract_sender_info(bytes_extra):
    """从BytesExtra字段中提取发送者信息"""
    sender_info = {}
    
    # 首先尝试从二进制数据中查找XML内容
    try:
        # 寻找XML格式的数据
        xml_match = re.search(b'<msgsource>.*?</msgsource>', bytes_extra, re.DOTALL)
        if xml_match:
            xml_data = xml_match.group(0).decode('utf-8', errors='ignore')
            try:
                # 解析XML
                root = ET.fromstring(xml_data)
                sender_info['xml'] = xml_data
            except Exception as e:
                sender_info['xml_error'] = str(e)
        
        # 这是在Protobuf编码的BytesExtra中找到的模式:
        # 0x0A 0x04 0x08 0x10 0x10 0x00 (固定头部) 0x1A 长度字节 0x08 0x01 0x12 长度字节 (用户名)
        
        # 模式1: 用户ID信息
        # 在BytesExtra中，0x1A后紧跟一个字节表示长度，然后包含0x08 0x01 0x12模式
        sender_pattern = re.compile(b'\x1a.{1,2}\x08\x01\x12(.{1,30})', re.DOTALL)
        sender_matches = sender_pattern.findall(bytes_extra)
        
        if sender_matches:
            for match in sender_matches:
                try:
                    # 第一个字节是长度，之后是实际的用户ID
                    if len(match) > 1:
                        id_length = match[0]  # 第一个字节是长度
                        if id_length > 0 and id_length < len(match):
                            user_id = match[1:1+id_length].decode('utf-8', errors='ignore')
                            if user_id:
                                sender_info['user_id'] = user_id
                                break
                except Exception as e:
                    pass
    except Exception as e:
        sender_info['error'] = str(e)
    
    return sender_info

def analyze_messages(db_path, limit=20, deep_analysis=False, test_patterns=False):
    """分析MSG表中的消息，重点关注发送方信息"""
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在: {db_path}")
        return
    
    print(f"正在分析数据库: {db_path}")
    print("-" * 60)
    
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取所有列名
        cursor.execute("PRAGMA table_info(MSG)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        # 获取消息数据
        cursor.execute(f"""
            SELECT localId, TalkerId, IsSender, StrTalker, StrContent, BytesExtra 
            FROM MSG 
            ORDER BY CreateTime 
            LIMIT {limit}
        """)
        messages = cursor.fetchall()
        
        print(f"分析 {len(messages)} 条消息的发送方信息:")
        print("-" * 60)
        
        # 存储所有找到的发送者ID
        all_sender_ids = set()
        sender_patterns = [
            (b'\x1a.{1,2}\x08\x01\x12(.{1,30})', "模式1: 标准消息"),
            (b'\x0a\x04\x08\x05\x10\x01\x1a\x0e\x08\x01\x12(.{1,30})', "模式2: 特殊消息")
        ]
        
        for msg in messages:
            localId, talkerId, isSender, strTalker, strContent, bytesExtra = msg
            
            print(f"消息ID: {localId}")
            print(f"会话ID: {talkerId}")
            print(f"是否为自己发送: {'是' if isSender == 1 else '否'}")
            print(f"会话名称: {strTalker}")
            
            # 提取内容的前30个字符
            content_preview = strContent[:30] + "..." if strContent and len(strContent) > 30 else strContent
            print(f"消息内容: {content_preview}")
            
            # 分析BytesExtra字段
            if bytesExtra:
                print(f"BytesExtra长度: {len(bytesExtra)} 字节")
                
                # 十六进制显示前60个字节
                if deep_analysis:
                    hex_data = bytesExtra.hex()
                    print(f"BytesExtra(hex): {hex_data[:60]}..." if len(hex_data) > 60 else hex_data)
                
                # 如果是测试模式，尝试所有模式提取
                if test_patterns:
                    print("测试所有提取模式:")
                    for pattern, desc in sender_patterns:
                        matches = re.finditer(pattern, bytesExtra, re.DOTALL)
                        found = False
                        for i, match in enumerate(matches):
                            found = True
                            try:
                                matched_bytes = match.group(1)
                                print(f"  {desc} 匹配 #{i+1}:", end=" ")
                                
                                # 解析长度字节和内容
                                if len(matched_bytes) > 1:
                                    length = matched_bytes[0]  # 第一个字节是长度
                                    if length > 0 and length < len(matched_bytes):
                                        try:
                                            user_id = matched_bytes[1:1+length].decode('utf-8', errors='ignore')
                                            print(f"ID: {user_id}")
                                        except:
                                            print(f"无法解码: {matched_bytes[1:1+length].hex()}")
                                    else:
                                        print(f"长度无效: {length}, 数据: {matched_bytes.hex()}")
                                else:
                                    print(f"数据太短: {matched_bytes.hex()}")
                            except Exception as e:
                                print(f"解析错误: {e}")
                        
                        if not found:
                            print(f"  {desc}: 未找到匹配")
                
                # 提取发送者信息
                sender_info = extract_sender_info(bytesExtra)
                if sender_info:
                    print("提取的发送者信息:")
                    for key, value in sender_info.items():
                        if key == 'xml':
                            # 只显示XML的前100个字符
                            print(f"  XML数据: {value[:100]}..." if len(value) > 100 else f"  XML数据: {value}")
                        elif key == 'user_id':
                            print(f"  用户ID: {value}")
                            all_sender_ids.add(value)
                        else:
                            print(f"  {key}: {value}")
            
            print("-" * 60)
        
        # 尝试查询Contact表来获取用户名映射
        print("\n尝试查找用户ID映射表...")
        try:
            # 检查MicroMsg.db是否在同一目录
            micro_msg_db = os.path.join(os.path.dirname(os.path.dirname(db_path)), "MicroMsg.db")
            if os.path.exists(micro_msg_db):
                print(f"找到MicroMsg.db: {micro_msg_db}")
                micro_conn = sqlite3.connect(micro_msg_db)
                micro_cursor = micro_conn.cursor()
                
                # 获取联系人信息
                micro_cursor.execute("SELECT UserName, NickName, Remark FROM Contact")
                contacts = micro_cursor.fetchall()
                
                print(f"联系人映射表 (共{len(contacts)}条):")
                for contact in contacts:
                    username, nickname, remark = contact
                    display_name = remark if remark else nickname
                    # 高亮显示在消息中找到的发送者ID
                    is_sender = username in all_sender_ids
                    highlight = "**" if is_sender else ""
                    print(f"  {highlight}UserName: {username:<25} | 昵称: {nickname:<15} | 备注: {remark if remark else '无'}{highlight}")
                
                micro_conn.close()
                
                # 为找到的每个发送者ID尝试找到匹配的联系人
                if all_sender_ids:
                    print("\n发送者ID与联系人匹配结果:")
                    for sender_id in all_sender_ids:
                        # 重新连接数据库查询每个ID
                        micro_conn = sqlite3.connect(micro_msg_db)
                        micro_cursor = micro_conn.cursor()
                        micro_cursor.execute("SELECT UserName, NickName, Remark FROM Contact WHERE UserName = ?", (sender_id,))
                        contact = micro_cursor.fetchone()
                        if contact:
                            username, nickname, remark = contact
                            display_name = remark if remark else nickname
                            print(f"  ID: {sender_id} => 匹配到: {display_name} (昵称: {nickname})")
                        else:
                            print(f"  ID: {sender_id} => 未在联系人表中找到匹配")
                        micro_conn.close()
        except Exception as e:
            print(f"读取联系人映射表失败: {e}")
    
    except sqlite3.Error as e:
        print(f"数据库操作失败: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='分析微信消息数据库中的发送者信息')
    parser.add_argument('db_path', nargs='?', default="weixin-gui-agent/User/wxid_8wn6q6udwtjq22/Msg/Multi/MSG.db", 
                        help='数据库文件路径')
    parser.add_argument('-n', '--num', type=int, default=20, help='分析的消息数量')
    parser.add_argument('-d', '--deep', action='store_true', help='深度分析BytesExtra字段')
    parser.add_argument('-t', '--test', action='store_true', help='测试所有可能的提取模式')
    
    args = parser.parse_args()
    
    analyze_messages(args.db_path, args.num, args.deep, args.test) 