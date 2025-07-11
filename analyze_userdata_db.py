import os
import sqlite3
import sys

def analyze_db(db_path, show_structure=False, show_data=False, specific_table=None):
    """分析SQLite数据库中的表结构和记录数量"""
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在: {db_path}")
        return
        
    print(f"正在分析数据库: {db_path}")
    print("-" * 60)
    
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取所有表名
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        if not tables:
            print("数据库中没有找到任何表。")
            return
            
        print(f"数据库中共有 {len(tables)} 个表:")
        print("-" * 60)
        
        # 计算每个表的记录数
        for table in tables:
            table_name = table[0]
            
            # 如果指定了特定表，只分析该表
            if specific_table and table_name != specific_table:
                continue
                
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"表 {table_name:<30} 包含 {count:>8} 条记录")
                
                # 如果需要显示表结构
                if show_structure or specific_table:
                    try:
                        cursor.execute(f"PRAGMA table_info({table_name})")
                        columns = cursor.fetchall()
                        column_names = [col[1] for col in columns]
                        print(f"  列结构: {', '.join(column_names)}")
                    except sqlite3.Error as e:
                        print(f"  无法获取表结构: {e}")
                
                # 如果需要显示表数据
                if (show_data or specific_table) and count > 0:
                    try:
                        # 限制返回数据量
                        limit = 10 if count > 10 else count
                        cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
                        rows = cursor.fetchall()
                        
                        if not columns:  # 如果上面没获取到列信息，这里重新获取
                            cursor.execute(f"PRAGMA table_info({table_name})")
                            columns = cursor.fetchall()
                            column_names = [col[1] for col in columns]
                        
                        print(f"  数据预览 (前 {limit} 条):")
                        for row in rows:
                            print("  " + "-" * 40)
                            for i, col_value in enumerate(row):
                                col_name = column_names[i] if i < len(column_names) else f"列{i}"
                                # 限制显示长度
                                if isinstance(col_value, str) and len(col_value) > 50:
                                    col_value = col_value[:47] + "..."
                                print(f"    {col_name}: {col_value}")
                    except sqlite3.Error as e:
                        print(f"  无法获取表数据: {e}")
                
                print() # 空行分隔
            except sqlite3.Error as e:
                print(f"表 {table_name:<30} 读取错误: {e}")
                print()
            
    except sqlite3.Error as e:
        print(f"数据库操作失败: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='分析SQLite数据库')
    parser.add_argument('db_path', nargs='?', help='数据库文件路径')
    parser.add_argument('-s', '--structure', action='store_true', help='显示表结构')
    parser.add_argument('-d', '--data', action='store_true', help='显示表数据')
    parser.add_argument('-t', '--table', help='指定要分析的表名')
    parser.add_argument('-a', '--all', action='store_true', help='分析所有找到的数据库')
    
    args = parser.parse_args()
    
    if args.db_path:
        analyze_db(args.db_path, args.structure, args.data, args.table)
    elif args.all or not args.db_path:
        # 尝试查找所有可能的数据库
        default_paths = [
            "weixin-gui-agent/User/wxid_8wn6q6udwtjq22/Msg/UserData.db",
            "weixin-liwenhao/User/wxid_8wn6q6udwtjq22/Msg/UserData.db",
            "weixin-gui-agent/User/wxid_8wn6q6udwtjq22/Msg/MicroMsg.db",
            "weixin-liwenhao/User/wxid_8wn6q6udwtjq22/Msg/MicroMsg.db",
            "weixin-gui-agent/User/wxid_8wn6q6udwtjq22/Msg/Multi/MSG.db",
            "weixin-liwenhao/User/wxid_8wn6q6udwtjq22/Msg/Multi/MSG.db"
        ]
        
        for path in default_paths:
            if os.path.exists(path):
                print(f"找到数据库: {path}")
                analyze_db(path, args.structure, args.data, args.table)
                print("\n" + "=" * 60 + "\n") 