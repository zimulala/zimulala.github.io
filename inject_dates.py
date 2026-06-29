import os
import re
from datetime import datetime

POSTS_DIR = "_posts"

for filename in os.listdir(POSTS_DIR):
    if filename.endswith(".md"):
        # 从文件名提取日期（匹配YYYY-MM-DD格式）
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
        if date_match:
            date_str = date_match.group(1)
            filepath = os.path.join(POSTS_DIR, filename)
            
            # 读取文件内容（强制使用Unix风格换行符）
            with open(filepath, "r+", encoding="utf-8", newline='') as f:
                content = f.read()
                
                # 标准化换行符为\n
                content = content.replace('\r\n', '\n').replace('\r', '\n')
                
                # 检查是否已有Front Matter
                if not content.startswith("---"):
                    content = f"---\n\ndate: {date_str}\n---\n\n{content}"
                elif "date:" not in content.split("---")[1]:
                    # 在现有Front Matter中添加date字段（确保换行符）
                    parts = content.split("---", 2)
                    if len(parts) >= 2:
                        parts[1] = f"{parts[1].rstrip()}\ndate: {date_str}\n"
                        content = "---".join(parts)
                
                # 回写文件（确保末尾有且仅有一个换行符）
                f.seek(0)
                f.write(content.rstrip() + '\n')
                f.truncate()
