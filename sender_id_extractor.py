import re

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

def get_display_name(user_id, contact_info):
    """
    根据用户ID获取显示名称
    
    参数:
    user_id (str): 用户ID
    contact_info (dict): 联系人信息字典，格式为 {user_id: (nickname, remark)}
    
    返回:
    str: 用户的显示名称，优先使用备注名
    """
    if not user_id or not contact_info or user_id not in contact_info:
        return user_id  # 如果找不到映射，则返回原始ID
    
    nickname, remark = contact_info.get(user_id, (user_id, None))
    return remark if remark else nickname

def load_contact_info(db_cursor):
    """
    从数据库加载联系人信息
    
    参数:
    db_cursor: MicroMsg.db数据库的游标
    
    返回:
    dict: 联系人信息字典，格式为 {user_id: (nickname, remark)}
    """
    contact_info = {}
    
    try:
        db_cursor.execute("SELECT UserName, NickName, Remark FROM Contact")
        contacts = db_cursor.fetchall()
        
        for contact in contacts:
            username, nickname, remark = contact
            contact_info[username] = (nickname, remark)
    except Exception as e:
        print(f"加载联系人信息失败: {e}")
    
    return contact_info

# 示例用法
if __name__ == "__main__":
    # 这是一个示例的BytesExtra数据(十六进制表示)
    sample_hex = "0a0408101000111608011212777869645f7878787878787878787878"
    sample_bytes = bytes.fromhex(sample_hex)
    
    # 提取发送者ID
    sender_id = extract_sender_id(sample_bytes)
    print(f"提取的发送者ID: {sender_id}")
    
    # 模拟联系人信息 - 使用匿名示例数据
    mock_contacts = {
        'wxid_example1': ('username1', '用户1'),
        'wxid_example2': ('username2', '用户2')
    }
    
    # 获取显示名称
    if sender_id:
        display_name = get_display_name(sender_id, mock_contacts)
        print(f"显示名称: {display_name}") 