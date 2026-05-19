import sqlite3
import json
from datetime import datetime

DB_PATH = "comments.db"
def init_db():
    """初始化数据库，建表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                        comment_id TEXT PRIMARY KEY,
                        user_name TEXT,
                        content TEXT,
                        fetch_time TEXT
            )
    ''')
    conn.commit()
    conn.close()

def save_comment(comment_id, user_name, content):
        """
        保存单条评论，自动去重
        返回值: True=新增, False=已存在
        """
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 检查是否已存在
        cursor.execute("SELECT 1 FROM comments WHERE comment_id = ?", (comment_id,))
        if cursor.fetchone():
            conn.close()
            return False

            # 插入新评论
            cursor.execute('''
                    INSERT INTO comments (comment_id, user_name, content, fetch_time)
                    VALUES (?, ?, ?, ?)
            ''', (comment_id, user_name, content, datetime.now().isoformat()))

            conn.commit()
            conn.close()
            return True

def get_new_comments_as_json():
    """获取本次新增的评论（供学生3输出用）"""
    # 这个函数可以由学生3在抓取过程中自行记录新增列表
    pass

def export_all_to_json(filepath="comments_export.json"):
    """导出全部评论为JSON"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM comments ORDER BY fetch_time")
    rows = cursor.fetchall()
    conn.close()

    data = [dict(row) for row in rows]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"已导出 {len(data)} 条评论到 {filepath}")
# 初始化数据库（程序启动时执行一次）
init_db()
