# -*- coding: utf-8 -*-
import sqlite3
import os
import re
import shutil
import datetime
import xml.etree.ElementTree as ET
import sys
import csv
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import lz4.block
    import blackboxprotobuf
    import pilk
except ImportError:
    print("[-] 缺少必要的依赖库。请先运行以下命令安装：")
    print("    pip install lz4 blackboxprotobuf pilk")
    sys.exit(1)

# ==========================================
# 核心导出逻辑类
# ==========================================
class WeChatExporter:
    # 净化后的 Emoji 字典：仅映射到真实的 Unicode Emoji，若无合适表情则不在此列（将保留原状）
    WECHAT_EMOJIS = {
        "[微笑]": "🙂", "[色]": "😍", "[发呆]": "😶", "[得意]": "😎",
        "[流泪]": "😭", "[害羞]": "😳", "[闭嘴]": "🤐", "[睡]": "😴", "[大哭]": "😭",
        "[尴尬]": "😅", "[发怒]": "😡", "[调皮]": "😜", "[呲牙]": "😁", "[惊讶]": "😲",
        "[难过]": "😔", "[酷]": "😎", "[冷汗]": "😰", "[抓狂]": "😫", "[吐]": "🤮",
        "[偷笑]": "🤭", "[愉快]": "😄", "[白眼]": "🙄", "[傲慢]": "😤", "[饥饿]": "🤤",
        "[困]": "😪", "[惊恐]": "😱", "[流汗]": "😓", "[憨笑]": "😆", 
        "[奋斗]": "💪", "[咒骂]": "🤬", "[疑问]": "❓", "[嘘]": "🤫", "[晕]": "😵",
        "[疯了]": "🤪", "[衰]": "📉", "[骷髅]": "💀", "[敲打]": "🔨", "[再见]": "👋",
        "[擦汗]": "😅", "[抠鼻]": "👃", "[鼓掌]": "👏", "[坏笑]": "😈",
        "[左哼哼]": "😒", "[右哼哼]": "😒", "[哈欠]": "🥱", "[鄙视]": "😒", "[委屈]": "🥺",
        "[快哭了]": "😢", "[阴险]": "😏", "[亲亲]": "😘", "[吓]": "😱", "[可怜]": "🥺",
        "[菜刀]": "🔪", "[西瓜]": "🍉", "[啤酒]": "🍺", "[篮球]": "🏀", "[乒乓]": "🏓",
        "[咖啡]": "☕", "[饭]": "🍚", "[猪头]": "🐷", "[玫瑰]": "🌹", "[凋谢]": "🥀",
        "[嘴唇]": "💋", "[爱心]": "❤️", "[心碎]": "💔", "[蛋糕]": "🎂", "[闪电]": "⚡",
        "[炸弹]": "💣", "[刀]": "🔪", "[足球]": "⚽", "[瓢虫]": "🐞", "[便便]": "💩",
        "[月亮]": "🌙", "[太阳]": "☀️", "[礼物]": "🎁", "[拥抱]": "🫂", "[强]": "👍",
        "[弱]": "👎", "[握手]": "🤝", "[胜利]": "✌️", "[抱拳]": "🙏", "[勾引]": "👈",
        "[拳头]": "👊", "[差劲]": "👎", "[爱你]": "🤟", "[NO]": "🙅‍♂️", "[OK]": "👌",
        "[爱情]": "💑", "[飞吻]": "💏", "[跳跳]": "🦘", "[发抖]": "🥶", "[怄火]": "🔥",
        "[转圈]": "💃", "[磕头]": "🙇‍♂️", "[回头]": "🔙", "[跳绳]": "🏃‍♂️", "[投降]": "🏳️",
        "[捂脸]": "🤦‍♂️", "[嘿哈]": "🤣", "[机智]": "💡", "[耶]": "✌️",
        "[红包]": "🧧", "[鸡]": "🐔", "[旺柴]": "🐶", "[打脸]": "🤦‍♂️", "[哇]": "🤩",
        "[翻白眼]": "🙄", "[666]": "🤙", "[让我看看]": "🙈", "[叹气]": "😮‍💨", "[苦涩]": "😖",
        "[裂开]": "💔", "[吃瓜]": "🍉", "[加油]": "💪", "[汗]": "😅", "[天啊]": "🙀",
        "[Emm]": "🤔", "[社会社会]": "😎", "[好的]": "👌",
    }

    def __init__(self, db_folder, wechat_data_folder, output_folder, ffmpeg_path, log_cb, progress_overall_cb, progress_current_cb):
        self.db_folder = db_folder
        self.wechat_data_folder = wechat_data_folder
        self.output_folder = output_folder
        self.ffmpeg_path = ffmpeg_path
        self.log = log_cb
        self.progress_overall = progress_overall_cb
        self.progress_current = progress_current_cb
        
        self.contacts = {}
        self.media_index = {} 
        self.mem_conn = None
        self.mem_cursor = None
        
        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)

    def sanitize_filename(self, name):
        if not name: return "Unknown"
        return re.sub(r'[\\/:*?"<>|\r\n]', '_', str(name))

    def load_contacts(self):
        self.log("[*] 正在加载联系人信息...")
        micromsg_path = os.path.join(self.db_folder, "MicroMsg.db")
        if not os.path.exists(micromsg_path):
            self.log(f"[-] 警告: 找不到联系人数据库 {micromsg_path}")
            return

        try:
            conn = sqlite3.connect(micromsg_path)
            cursor = conn.cursor()
            cursor.execute("SELECT UserName, Remark, NickName FROM Contact")
            for row in cursor.fetchall():
                username, remark, nickname = row
                display_name = remark if remark else (nickname if nickname else username)
                self.contacts[username] = self.sanitize_filename(display_name)
            conn.close()
            self.log(f"[+] 成功加载 {len(self.contacts)} 个联系人。")
        except Exception as e:
            self.log(f"[-] 读取联系人出错: {e}")

    def load_media_index(self):
        media_dbs = [f for f in os.listdir(self.db_folder) if f.startswith('MediaMsg') and f.endswith('.db')]
        self.log(f"[*] 找到 {len(media_dbs)} 个 MediaMSG 数据库，建立语音索引...")
        for db_name in media_dbs:
            db_path = os.path.join(self.db_folder, db_name)
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT Reserved0 FROM Media")
                for row in cursor.fetchall():
                    self.media_index[str(row[0])] = db_path
                conn.close()
            except Exception: pass
        self.log(f"[+] 共索引了 {len(self.media_index)} 条语音数据记录。")

    def get_voice_buf(self, msg_svr_id):
        db_path = self.media_index.get(str(msg_svr_id))
        if not db_path: return None
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT Buf FROM Media WHERE Reserved0=?", (msg_svr_id,))
            row = cursor.fetchone()
            conn.close()
            if row and row[0]: return row[0]
        except: pass
        return None

    def decode_dat_image(self, dat_path, out_path):
        if not os.path.exists(dat_path): return False
        try:
            with open(dat_path, 'rb') as f: data = f.read()
            if len(data) < 2: return False
            hex_headers = [(0xFF, 0xD8), (0x89, 0x50), (0x47, 0x49)]
            xor_key = 0
            for h1, h2 in hex_headers:
                k1, k2 = data[0] ^ h1, data[1] ^ h2
                if k1 == k2:
                    xor_key = k1
                    break
            if xor_key == 0: xor_key = data[0] ^ 0xFF 
            with open(out_path, 'wb') as f:
                f.write(bytearray([b ^ xor_key for b in data]))
            return True
        except: return False

    def get_BytesExtra(self, BytesExtra):
        if BytesExtra is None or not isinstance(BytesExtra, bytes): return None
        try:
            deserialize_data, _ = blackboxprotobuf.decode_message(BytesExtra)
            return deserialize_data
        except: return None

    def decompress_CompressContent(self, data):
        if data is None or not isinstance(data, bytes): return None
        try:
            dst = lz4.block.decompress(data, uncompressed_size=len(data) << 8)
            dst = dst.replace(b'\x00', b'') 
            return dst.decode('utf-8', errors='ignore')
        except:
            return data.decode('utf-8', errors='ignore')

    def _find_filestorage_paths(self, data, paths=None):
        if paths is None: paths = []
        if isinstance(data, dict):
            for v in data.values(): self._find_filestorage_paths(v, paths)
        elif isinstance(data, list):
            for item in data: self._find_filestorage_paths(item, paths)
        elif isinstance(data, bytes):
            text = data.decode('utf-8', errors='ignore')
            match = re.search(r'(FileStorage[^\x00-\x1F\'\"\?\*\<\>\|]+)', text)
            if match: paths.append(match.group(1).strip())
        elif isinstance(data, str):
            match = re.search(r'(FileStorage[^\x00-\x1F\'\"\?\*\<\>\|]+)', data)
            if match: paths.append(match.group(1).strip())
        return paths

    def convert_silk_to_mp3(self, silk_path, mp3_path):
        pcm_path = silk_path + ".temp.pcm"
        try:
            pilk.decode(silk_path, pcm_path)
            command = [
                self.ffmpeg_path, "-y", "-f", "s16le", "-ar", "24000", "-ac", "1",
                "-i", pcm_path, "-vn", "-b:a", "64k", mp3_path
            ]
            subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return True
        except Exception as e:
            return False
        finally:
            if os.path.exists(pcm_path):
                try: os.remove(pcm_path)
                except: pass

    def prepare_database(self):
        self.load_contacts()
        self.load_media_index()
        
        msg_dbs = [f for f in os.listdir(self.db_folder) if f.startswith('MSG') and f.endswith('.db') and 'MediaMsg' not in f]
        if not msg_dbs:
            self.log("[-] 错误: 未找到任何 MSG 数据库文件。")
            return False

        self.log(f"[*] 找到 {len(msg_dbs)} 个消息数据库文件，正在整合入内存(可能需要几十秒)...")
        self.mem_conn = sqlite3.connect(':memory:', check_same_thread=False)
        self.mem_cursor = self.mem_conn.cursor()
        self.mem_cursor.execute('''
            CREATE TABLE AllMsg (
                MsgSvrID TEXT, StrTalker TEXT, Type INTEGER, SubType INTEGER,
                IsSender INTEGER, CreateTime INTEGER, StrContent TEXT,
                CompressContent BLOB, BytesExtra BLOB
            )
        ''')

        for db_name in msg_dbs:
            db_path = os.path.join(self.db_folder, db_name)
            try:
                conn = sqlite3.connect(db_path)
                conn.text_factory = lambda b: b.decode(errors='ignore')
                cursor = conn.cursor()
                cursor.execute("SELECT MsgSvrID, StrTalker, Type, SubType, IsSender, CreateTime, StrContent, CompressContent, BytesExtra FROM MSG")
                rows = cursor.fetchall()
                self.mem_cursor.executemany("INSERT INTO AllMsg VALUES (?,?,?,?,?,?,?,?,?)", rows)
                conn.close()
            except Exception as e:
                self.log(f"[-] 读取 {db_name} 失败: {e}")
                
        self.mem_conn.commit()
        self.log("[+] 数据库整合完成！可以开始选择会话。")
        return True

    def scan_chats(self):
        if not self.mem_cursor: return []
        self.mem_cursor.execute("SELECT StrTalker, COUNT(*) FROM AllMsg GROUP BY StrTalker ORDER BY COUNT(*) DESC")
        talkers = self.mem_cursor.fetchall()
        
        chat_list = []
        for talker, count in talkers:
            if talker.endswith("@chatroom"):
                name = f"群聊_{talker}"
            else:
                name = self.contacts.get(talker, talker)
            chat_list.append({
                'id': talker,
                'name': name,
                'count': count
            })
        return chat_list

    def export_selected_chats(self, selected_chats):
        total_chats = len(selected_chats)
        for idx, chat_info in enumerate(selected_chats):
            self.log(f"[{idx+1}/{total_chats}] 正在导出: {chat_info['name']} ({chat_info['count']}条)...")
            self._export_single_chat(chat_info)
            if self.progress_overall:
                self.progress_overall(((idx + 1) / total_chats) * 100)
            
        self.log("[+] 所有选中记录导出完毕！")

    def _get_csv_text(self, msg_type, msg_subtype, str_content, comp_content):
        if msg_type == 1:
            return str(str_content).replace('\n', ' ') if str_content else ""
        elif msg_type == 3: return "[图片]"
        elif msg_type == 34: return "[语音]"
        elif msg_type in [43, 62]: return "[视频]"
        elif msg_type == 42: return "[名片]"
        elif msg_type == 48: return "[位置]"
        elif msg_type == 47: return "[动画表情]"
        elif msg_type == 50: return "[音视频通话]"
        elif msg_type == 11000: return "[视频号动态]"
        elif msg_type == 49:
            content = self.decompress_CompressContent(comp_content) or str_content
            if content:
                try:
                    root = ET.fromstring(content)
                    appmsg = root.find('appmsg')
                    if appmsg is not None:
                        title = appmsg.find('title').text if appmsg.find('title') is not None else "未知"
                        return f"[文件/链接/应用]: {title}"
                except: pass
            return "[AppMsg结构化消息]"
        elif msg_type == 10000:
            cleaned = re.sub(r'<_wc_custom_link_[^>]*>(.*?)(?:</_wc_custom_link_>|$)', r'\1', str(str_content))
            return f"[系统消息] {cleaned}"
        return f"[未知类型 {msg_type}_{msg_subtype}]"

    def _export_single_chat(self, chat_info):
        talker = chat_info['id']
        msg_count = chat_info['count']
        display_name = self.contacts.get(talker, talker) if not talker.endswith("@chatroom") else f"群聊_{talker}"
        chat_dir_name = f"{self.sanitize_filename(display_name)}_{self.sanitize_filename(talker)}"
        chat_dir = os.path.join(self.output_folder, chat_dir_name)
        
        media_dir = os.path.join(chat_dir, 'media')
        file_dir = os.path.join(chat_dir, 'files')
        
        os.makedirs(media_dir, exist_ok=True)
        os.makedirs(file_dir, exist_ok=True)

        self.mem_cursor.execute("SELECT MsgSvrID, Type, SubType, IsSender, CreateTime, StrContent, CompressContent, BytesExtra FROM AllMsg WHERE StrTalker=? ORDER BY CreateTime ASC", (talker,))
        messages = self.mem_cursor.fetchall()
        if not messages: return

        # 1. 导出 CSV
        csv_path = os.path.join(chat_dir, 'chat_history.csv')
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['时间', '发件人', '消息类型(ID)', '内容概要'])
            for msg in messages:
                MsgSvrID, msg_type, msg_subtype, is_sender, create_time, str_content, comp_content, bytes_extra = msg
                dt = datetime.datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S')
                sender_name = "我" if is_sender else display_name
                csv_text = self._get_csv_text(msg_type, msg_subtype, str_content, comp_content)
                writer.writerow([dt, sender_name, str(msg_type), csv_text])

        # 2. 导出 HTML 记录（1000条一卷）
        chunk_size = 1000
        chunk_info_list = []
        processed_msg = 0

        for i in range(0, len(messages), chunk_size):
            chunk = messages[i:i + chunk_size]
            start_date = datetime.datetime.fromtimestamp(chunk[0][4]).strftime('%Y%m%d')
            end_date = datetime.datetime.fromtimestamp(chunk[-1][4]).strftime('%Y%m%d')
            part_name = f"chat_{start_date}_{end_date}_{i//chunk_size + 1}.html"
            part_path = os.path.join(chat_dir, part_name)
            
            chunk_info_list.append({
                'filename': part_name, 'start_date': start_date, 
                'end_date': end_date, 'count': len(chunk)
            })

            with open(part_path, 'w', encoding='utf-8') as f:
                header_title = f"{display_name} (第{i//chunk_size + 1}卷: {start_date}~{end_date})"
                f.write(self._get_html_header(header_title))
                
                for msg in chunk:
                    MsgSvrID, msg_type, msg_subtype, is_sender, create_time, str_content, comp_content, bytes_extra = msg
                    dt = datetime.datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S')
                    html_content = self._parse_message(
                        MsgSvrID, msg_type, msg_subtype, str_content, comp_content, bytes_extra, media_dir, file_dir, chat_info
                    )
                    f.write(self._get_message_html(is_sender, dt, html_content))
                    
                    processed_msg += 1
                    if processed_msg % 100 == 0 and self.progress_current:
                        self.progress_current((processed_msg / len(messages)) * 100)
                    
                f.write(self._get_html_footer())
        
        if self.progress_current:
            self.progress_current(100)
        
        # 3. 导出索引主页
        index_path = os.path.join(chat_dir, 'index.html')
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(self._get_main_index_html(display_name, chunk_info_list, msg_count))

    def parse_emoji(self, text):
        if not text: return text
        def repl(match):
            m = match.group(0)
            # 如果字典里找不到，或者本来就不包含（如[撇嘴]），原样返回 m，防止出现奇怪的汉字歧义
            return self.WECHAT_EMOJIS.get(m, m)
        return re.sub(r'\[.*?\]', repl, str(text))

    def _parse_recorditem_html(self, xml_str):
        """递归解析合并转发的聊天记录 (修正: 移除本地匹配，只做文本降级或识别可用直链)"""
        if not xml_str: return ""
        try:
            root = ET.fromstring(xml_str)
            html = '<div style="margin-top: 8px; border-top: 1px solid #ddd; padding-top: 8px;">'
            
            datalist = root.find('datalist')
            if datalist is None and root.tag == 'datalist':
                datalist = root
            if datalist is None: return ""
            
            for item in datalist.findall('dataitem'):
                datatype = item.get('datatype', '1')
                sourcename = item.find('sourcename').text if item.find('sourcename') is not None else "未知"
                sourcetime = item.find('sourcetime').text if item.find('sourcetime') is not None else ""
                datadesc = item.find('datadesc').text if item.find('datadesc') is not None else ""
                
                cdnurl = item.find('cdndataurl').text if item.find('cdndataurl') is not None else ""
                thumburl = item.find('cdnthumburl').text if item.find('cdnthumburl') is not None else ""

                time_str = ""
                if sourcetime and sourcetime.isdigit():
                    time_str = datetime.datetime.fromtimestamp(int(sourcetime)).strftime('%m-%d %H:%M')
                
                media_html = ""
                
                # 2: 图片
                if datatype == "2":
                    # 只有当提取出来的确实是 http 链接时才加载，否则降级文本（因为合并转发里的常是无效HEX序列化值）
                    if cdnurl and cdnurl.startswith('http'):
                        media_html = f'<br><img src="{cdnurl}" style="max-width: 120px; border-radius: 4px; margin-top: 4px; cursor: zoom-in;" onclick="showImg(this.src)" title="点击放大">'
                    elif thumburl and thumburl.startswith('http'):
                        media_html = f'<br><img src="{thumburl}" style="max-width: 120px; border-radius: 4px; margin-top: 4px; cursor: zoom-in;" onclick="showImg(this.src)" title="点击放大">'
                    if not datadesc: datadesc = "[图片]"
                        
                # 4: 视频
                elif datatype == "4":
                    url = thumburl or cdnurl
                    if url and url.startswith('http'):
                        media_html = f'<br><div style="position:relative; display:inline-block;"><img src="{url}" style="max-width: 120px; border-radius: 4px; margin-top: 4px; opacity: 0.8;"><div style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%); background:rgba(0,0,0,0.5); color:#fff; border-radius:50%; width:24px; height:24px; text-align:center; line-height:24px; font-size:12px;">▶</div></div>'
                    if not datadesc: datadesc = "[视频]"
                        
                # 8: 文件
                elif datatype == "8":
                    if not datadesc: datadesc = "[文件]"
                    
                # 17: 嵌套的合并聊天记录
                elif datatype == "17":
                    if datadesc and "<recordinfo" in datadesc:
                        datadesc = self._parse_recorditem_html(datadesc)
                    else:
                        datadesc = "[嵌套的合并聊天记录]"
                
                # 处理普通文本 (套用最新的安全 Emoji 转换)
                if datatype != "17":
                    datadesc = self.parse_emoji(datadesc).replace('\n', '<br>')
                    
                html += f'''
                <div style="margin-bottom: 8px; font-size: 12px; line-height: 1.4;">
                    <span style="color: #999; margin-right: 5px;">[{time_str}]</span>
                    <span style="color: #576b95; font-weight: bold; margin-right: 5px;">{sourcename}:</span>
                    <span style="color: #333;">{datadesc}</span>
                    {media_html}
                </div>
                '''
            html += '</div>'
            return html
        except Exception as e:
            return f"<div style='font-size:12px; color:#999;'>[聊天记录详情解析失败]</div>"

    def _parse_message(self, MsgSvrID, msg_type, msg_subtype, str_content, comp_content, bytes_extra, media_dir, file_dir, chat_info):
        dict_extra = self.get_BytesExtra(bytes_extra)
        decompressed_content = self.decompress_CompressContent(comp_content)
        type_id = (msg_type, msg_subtype)

        # 纯文本
        if type_id == (1, 0):
            parsed_text = self.parse_emoji(str_content)
            return str(parsed_text).replace('\n', '<br>') if parsed_text else ""

        # 图片
        elif type_id == (3, 0):
            if not chat_info.get('img', True): return "[图片 (本会话未开启导出)]"
            img_paths = self._find_filestorage_paths(dict_extra)
            img_paths = sorted(img_paths, key=lambda p: "Image" in p, reverse=True)
            if img_paths:
                rel_path = img_paths[0].replace("\\\\", "\\").replace("/", "\\")
                abs_path = os.path.join(self.wechat_data_folder, rel_path)
                if os.path.exists(abs_path):
                    filename = os.path.basename(abs_path)
                    img_name = filename.replace('.dat', '.jpg')
                    out_img_path = os.path.join(media_dir, img_name)
                    
                    if not os.path.exists(out_img_path):
                        try:
                            if filename.endswith('.dat'): self.decode_dat_image(abs_path, out_img_path)
                            else: shutil.copy2(abs_path, out_img_path)
                        except: pass
                        
                    return f'<img src="media/{img_name}" class="chat-img" onclick="showImg(this.src)" title="点击放大图片">'
            return "[图片 (未找到源文件)]"
            
        # 语音
        elif type_id == (34, 0):
            if not chat_info.get('audio', True): return "[语音 (本会话未开启导出)]"
            voice_buf = self.get_voice_buf(MsgSvrID)
            if voice_buf:
                silk_filename = f"{MsgSvrID}.silk"
                silk_path = os.path.join(media_dir, silk_filename)
                mp3_filename = f"{MsgSvrID}.mp3"
                mp3_path = os.path.join(media_dir, mp3_filename)
                
                if not os.path.exists(mp3_path):
                    if not os.path.exists(silk_path):
                        try:
                            with open(silk_path, 'wb') as f: f.write(voice_buf)
                        except: pass
                    if os.path.exists(silk_path):
                        success = self.convert_silk_to_mp3(silk_path, mp3_path)
                        if success and os.path.exists(silk_path):
                            try: os.remove(silk_path)
                            except: pass
                
                if os.path.exists(mp3_path):
                    return f'<audio controls src="media/{mp3_filename}" style="max-width: 250px; outline: none;" title="语音消息"></audio>'
                else:
                    duration = ""
                    if str_content:
                        try:
                            root = ET.fromstring(str_content)
                            voicelength = root.attrib.get("voicelength", "")
                            if voicelength.isdigit(): duration = f"时长: {int(voicelength)/1000:.1f}秒 "
                        except: pass
                    return f'🎵 语音消息: {duration}<br><a href="media/{silk_filename}" target="_blank">点击下载 (.silk文件)</a>'
            return "[🎵 语音 (未找到音频数据)]"

        # 视频 & 小视频 (43_0 和 62_0 共用解析逻辑)
        elif type_id[0] in [43, 62]:
            if not chat_info.get('video', True): return "[视频 (本会话未开启导出)]"
            file_paths = self._find_filestorage_paths(dict_extra)
            mp4_cands = [p.replace("\\\\", "\\").replace("/", "\\") for p in file_paths if p.lower().endswith('.mp4')]
            jpg_cands = [p.replace("\\\\", "\\").replace("/", "\\") for p in file_paths if p.lower().endswith('.jpg') or p.lower().endswith('.jpeg') or p.lower().endswith('.thumb')]
            
            mp4_abs = os.path.join(self.wechat_data_folder, mp4_cands[0]) if mp4_cands else None
            jpg_abs = os.path.join(self.wechat_data_folder, jpg_cands[0]) if jpg_cands else None
            
            has_mp4 = mp4_abs and os.path.exists(mp4_abs)
            has_jpg = jpg_abs and os.path.exists(jpg_abs)

            thumb_filename = ""
            if has_jpg:
                thumb_filename = f"thumb_{MsgSvrID}.jpg"
                thumb_dst = os.path.join(media_dir, thumb_filename)
                if not os.path.exists(thumb_dst):
                    try: shutil.copy2(jpg_abs, thumb_dst)
                    except: pass

            if has_mp4:
                vid_filename = os.path.basename(mp4_abs)
                vid_dst = os.path.join(media_dir, vid_filename)
                if not os.path.exists(vid_dst):
                    try: shutil.copy2(mp4_abs, vid_dst)
                    except: pass
                
                thumb_html = f'<img src="media/{thumb_filename}">' if has_jpg else '<div style="width:200px; height:150px; background:#000;"></div>'
                return f'''
                <div class="video-wrapper" onclick="loadVideo(this, 'media/{vid_filename}')" title="点击播放">
                    {thumb_html}
                    <div class="play-btn">▶</div>
                </div>
                '''
            else:
                if has_jpg:
                    return f'''
                    <div style="position:relative; display:inline-block;">
                        <img src="media/{thumb_filename}" class="chat-img" onclick="showImg(this.src)" title="点击放大封面" style="opacity: 0.6;">
                        <div style="position:absolute; bottom:5px; right:5px; background:rgba(0,0,0,0.6); color:#fff; font-size:12px; padding:3px 6px; border-radius:3px; pointer-events: none;">未缓存/已过期视频</div>
                    </div>
                    '''
                else:
                    return "<div style='padding:10px; background:#f0f0f0; border-radius:5px; color:#999; font-size:12px;'>[视频已被清理或未缓存]</div>"

        # 42_0 名片
        elif type_id == (42, 0):
            try:
                root = ET.fromstring(str_content)
                nickname = root.get('nickname', '未知')
                username = root.get('username', '')
                return f'''<div style="border: 1px solid #e2e2e2; padding: 12px; border-radius: 8px; background: #fff; width: 220px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                    <p style="margin:0; font-weight:bold; font-size:15px; display:flex; align-items:center;">👤 {nickname}</p>
                    <p style="margin:8px 0 0 0; font-size:12px; color:#888; border-top:1px solid #eee; padding-top:6px;">个人名片</p>
                </div>'''
            except:
                return "[个人名片]"

        # 48_0 位置
        elif type_id == (48, 0):
            try:
                root = ET.fromstring(str_content)
                loc = root.find('location')
                if loc is not None:
                    x = loc.get('x', '')
                    y = loc.get('y', '')
                    label = loc.get('label', '')
                    poiname = loc.get('poiname', '')
                    osm_url = f"https://www.openstreetmap.org/?mlat={x}&mlon={y}#map=16/{x}/{y}"
                    return f'''<div style="border: 1px solid #eee; padding: 10px; border-radius: 8px; background: #fafafa;">
                        <p style="margin:0; font-weight:bold; font-size: 14px;">📍 [位置] {poiname}</p>
                        <p style="margin:5px 0 8px 0; font-size:12px; color:#666;">{label}</p>
                        <a href="{osm_url}" target="_blank" style="font-size:12px; color:#07c160; text-decoration:none; display:inline-block; border-top: 1px solid #eee; padding-top:5px; width:100%;">查看地图 (OpenStreetMap)</a>
                    </div>'''
            except: pass
            return "[位置信息]"
            
        # 47_0 动画表情 (修正: 优先取无鉴权的直链，并兼顾有鉴权的图片提取)
        elif type_id == (47, 0):
            cdn_match = re.search(r'cdnurl\s*=\s*"(.*?)"', str(str_content))
            thumb_match = re.search(r'thumburl\s*=\s*"(.*?)"', str(str_content))
            
            cdnurl = cdn_match.group(1) if cdn_match else ""
            thumburl = thumb_match.group(1) if thumb_match else ""
            
            target_url = ""
            
            # 优先级判断策略：
            # 1. 优先采用 cdnurl (假设它是 http 且不包含 emoji.qpic.cn 鉴权域名)
            if cdnurl and cdnurl.startswith('http') and 'emoji.qpic.cn' not in cdnurl:
                target_url = cdnurl
            # 2. 如果第一步失败，说明 cdnurl 带鉴权或不存在。此时如果存在 mmbiz 的 thumburl，用它。
            elif thumburl and thumburl.startswith('http'):
                target_url = thumburl
            # 3. 实在不行，如果有 cdnurl (尽管带鉴权可能会裂图)，死马当活马医放上去
            elif cdnurl and cdnurl.startswith('http'):
                target_url = cdnurl
                
            if target_url: 
                return f'<img src="{target_url}" style="max-width: 100px;">'
            
            # 方案 B: XML被截断时，尝试从底层字节流提取
            urls = re.findall(r'http[s]?://[^\s\'\"\<\>]+', str(dict_extra))
            for u in urls:
                if 'qpic.cn' in u or 'weixin.qq.com' in u:
                    return f'<img src="{u}" style="max-width: 100px;">'
                    
            return "[动画表情 (加密或已清理)]"

        # 50_0 音视频通话
        elif type_id == (50, 0):
            return f'<div style="color: #576b95; font-weight: bold; padding: 5px;">📞 音视频通话: {str_content}</div>'

        # 11000_0 视频号动态
        elif type_id == (11000, 0):
            try:
                # 尝试简单解析部分数据
                nickname = re.search(r'<nickname>(.*?)</nickname>', str_content)
                desc = re.search(r'<desc>(.*?)</desc>', str_content)
                title_text = nickname.group(1) if nickname else "视频号"
                desc_text = desc.group(1) if desc else "分享内容"
                return f'''<div style="border: 1px solid #fa9d3b; padding: 10px; border-radius: 5px; background: #fff9f0;">
                    <p style="margin:0; font-weight:bold; color: #fa9d3b;">🎬 视频号: {title_text}</p>
                    <p style="margin:5px 0 0 0; font-size:13px; color:#666;">{desc_text}</p>
                </div>'''
            except:
                return f'<div style="border: 1px solid #fa9d3b; padding: 10px; border-radius: 5px; background: #fff9f0;"><p style="margin:0; font-weight:bold; color: #fa9d3b;">🎬 视频号动态</p></div>'

        # 49_? AppMsg 结构化消息扩展
        elif type_id[0] == 49:
            content_to_parse = decompressed_content if decompressed_content else str_content
            if content_to_parse:
                try:
                    root = ET.fromstring(content_to_parse)
                    appmsg = root.find('appmsg')
                    if appmsg is not None:
                        title = appmsg.find('title').text if appmsg.find('title') is not None else "未知对象"
                        app_type = appmsg.find('type').text if appmsg.find('type') is not None else "0"
                        
                        # 6: 文件
                        if app_type == "6":
                            file_paths = self._find_filestorage_paths(dict_extra)
                            if file_paths:
                                rel_path = file_paths[0].replace("\\\\", "\\").replace("/", "\\")
                                abs_path = os.path.join(self.wechat_data_folder, rel_path)
                                if os.path.exists(abs_path):
                                    filename = os.path.basename(abs_path)
                                    out_file_path = os.path.join(file_dir, filename)
                                    if not os.path.exists(out_file_path):
                                        try: shutil.copy2(abs_path, out_file_path)
                                        except: pass
                                    return f'''<div style="border: 1px solid #ccc; padding: 10px; border-radius: 5px; background: #fff;">
                                        <p style="margin:0; font-weight:bold;">📄 文件: {title}</p><a href="files/{filename}" target="_blank" style="font-size:12px;">点击打开文件</a></div>'''
                            return f"[文件]: {title} (源文件未找到)"
                        # 5/33: 卡片链接
                        elif app_type == "5":
                            url = appmsg.find('url').text if appmsg.find('url') is not None else "#"
                            des = appmsg.find('des').text if appmsg.find('des') is not None else ""
                            return f'''<div style="border: 1px solid #eee; padding: 10px; border-radius: 5px; background: #fafafa;">
                                <p style="margin:0; font-weight:bold;">🔗 {title}</p><p style="margin:5px 0; font-size:12px; color:#666;">{des}</p><a href="{url}" target="_blank" style="font-size:12px;">查看详情</a></div>'''
                        # 33/36: 小程序
                        elif app_type in ["33", "36"]:
                            sourcedisplayname = appmsg.find('sourcedisplayname').text if appmsg.find('sourcedisplayname') is not None else ""
                            return f'''<div style="border: 1px solid #e0e0e0; padding: 10px; border-radius: 8px; background: #fdfdfd;">
                                <p style="margin:0; font-weight:bold; font-size:14px;">◰ 小程序: {title}</p>
                                <p style="margin:5px 0 0 0; font-size:12px; color:#888;">来源: {sourcedisplayname}</p></div>'''
                        # 57: 引用回复
                        elif app_type == "57":
                            title = self.parse_emoji(title).replace('\n', '<br>')
                            refermsg = appmsg.find('refermsg')
                            if refermsg is not None:
                                displayname = refermsg.find('displayname').text
                                refer_content = self.parse_emoji(refermsg.find('content').text)
                                return f"{title}<br><br><div style='border-left: 3px solid #ccc; padding-left: 10px; color: #666; font-size: 13px;'>引用 {displayname}: {refer_content}</div>"
                            return title
                        # 2000: 转账
                        elif app_type == "2000":
                            wcpayinfo = appmsg.find('wcpayinfo')
                            feedesc = wcpayinfo.find('feedesc').text if wcpayinfo is not None and wcpayinfo.find('feedesc') is not None else "转账"
                            pay_memo = wcpayinfo.find('pay_memo').text if wcpayinfo is not None and wcpayinfo.find('pay_memo') is not None else ""
                            return f'''<div style="background: #fdf0e5; border: 1px solid #f8d8b9; padding: 12px; border-radius: 5px;">
                                <p style="margin:0; font-weight:bold; color:#d17c30; font-size: 15px;">💰 微信转账: {feedesc}</p>
                                <p style="margin:5px 0 0 0; font-size:12px; color:#d17c30;">{pay_memo}</p></div>'''
                        # 2001: 红包
                        elif app_type == "2001":
                            wcpayinfo = appmsg.find('wcpayinfo')
                            sendertitle = wcpayinfo.find('sendertitle').text if wcpayinfo is not None and wcpayinfo.find('sendertitle') is not None else "微信红包"
                            return f'''<div style="background: #f7e4e4; border: 1px solid #f1c9c9; padding: 12px; border-radius: 5px;">
                                <p style="margin:0; font-weight:bold; color:#d13d4b; font-size: 15px;">🧧 {sendertitle}</p></div>'''
                        # 19: 聊天记录(合并转发)
                        elif app_type == "19":
                            des = appmsg.find('des').text if appmsg.find('des') is not None else ""
                            recorditem = appmsg.find('recorditem').text if appmsg.find('recorditem') is not None else ""
                            
                            details_html = self._parse_recorditem_html(recorditem)
                            
                            return f'''<div style="background: #f5f5f5; border: 1px solid #e0e0e0; padding: 10px; border-radius: 8px;">
                                <details>
                                    <summary style="cursor: pointer; font-weight:bold; font-size:13px; color:#333; outline: none; user-select: none;">💬 {title} <span style="font-weight:normal; color:#888; font-size:11px;">(点击展开)</span></summary>
                                    <p style="margin:5px 0 0 0; font-size:12px; color:#888;">{des}</p>
                                    {details_html}
                                </details>
                            </div>'''

                        return f"[{title}]"
                except Exception: pass
            return "[复杂/未知 AppMsg 消息]"
            
        # 10000: 系统消息
        elif type_id[0] == 10000:
            content_str = str(str_content)
            cleaned = re.sub(r'<_wc_custom_link_[^>]*>(.*?)(?:</_wc_custom_link_>|$)', r'<span style="color: #d13d4b;">\1</span>', content_str)
            
            if "红包" in cleaned:
                return f"<div style='background: #fff0f0; padding: 5px 10px; border-radius: 5px; color: #a8a8a8; font-size: 12px; text-align: center; display: inline-block;'>🧧 {cleaned}</div>"
            return f"<div style='color: #a8a8a8; font-size: 12px; text-align: center; margin: 10px 0;'>— {cleaned} —</div>"

        return f"[未知类型消息: {msg_type}_{msg_subtype}]"

    def _get_main_index_html(self, title, chunk_info, total_count):
        links = ""
        for idx, info in enumerate(chunk_info):
            links += f'''<a href="{info['filename']}" class="chunk-link"><div class="chunk-title">第 {idx + 1} 卷 ({info['start_date']} ~ {info['end_date']})</div><div class="chunk-meta">包含 {info['count']} 条消息</div></a>'''
        return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{title} - 聊天记录卷宗</title>
            <style>body{{font-family:"Microsoft YaHei",-apple-system,sans-serif;background:#f5f5f5;margin:0;padding:20px;}}.container{{max-width:600px;margin:0 auto;background:#fff;padding:30px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1);}}
            h1{{text-align:center;color:#333;}}.meta{{text-align:center;color:#666;margin-bottom:30px;font-size:14px;}}.chunk-list{{display:flex;flex-direction:column;gap:12px;}}
            .chunk-link{{display:block;padding:15px;border:1px solid #eee;border-radius:8px;text-decoration:none;color:#333;transition:all 0.2s;background:#fafafa;}}
            .chunk-link:hover{{background:#fff;border-color:#07c160;transform:translateY(-1px);box-shadow:0 4px 8px rgba(0,0,0,0.05);}}.chunk-title{{font-size:16px;font-weight:bold;margin-bottom:5px;color:#07c160;}}
            .chunk-meta{{font-size:13px;color:#888;}}.csv-btn{{display:block;text-align:center;margin-top:30px;padding:15px;background:#f2f2f2;border:1px solid #ddd;border-radius:8px;text-decoration:none;color:#333;font-weight:bold;transition:all 0.2s;}}
            .csv-btn:hover{{background:#e6e6e6;}}</style></head><body><div class="container"><h1>{title}</h1><div class="meta">总计 {total_count} 条记录，已自动按日分卷</div>
            <div class="chunk-list">{links}</div><a href="chat_history.csv" class="csv-btn">📥 下载全文 CSV 检索版 (纯文字)</a></div></body></html>"""

    def _get_html_header(self, title):
        return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{title}</title>
            <style>body{{font-family:"Microsoft YaHei",-apple-system,sans-serif;background-color:#f5f5f5;margin:0;padding:20px;}}.chat-container{{max-width:800px;margin:0 auto;background:#fff;padding:20px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1);}}
            .message{{display:flex;margin-bottom:20px;flex-direction:column;}}.message.sender{{align-items:flex-end;}}.message.receiver{{align-items:flex-start;}}.bubble{{max-width:70%;padding:10px 15px;border-radius:8px;line-height:1.5;word-wrap:break-word;font-size:15px;}}
            .sender .bubble{{background-color:#95ec69;color:#000;border-top-right-radius:0;}}.receiver .bubble{{background-color:#ffffff;color:#000;border:1px solid #e0e0e0;border-top-left-radius:0;}}.time{{font-size:12px;color:#b0b0b0;margin-bottom:5px;}}
            .header{{text-align:center;border-bottom:1px solid #eee;padding-bottom:10px;margin-bottom:20px;}}.chat-img{{max-width:200px;border-radius:5px;cursor:zoom-in;transition:opacity 0.2s;}}.chat-img:hover{{opacity:0.8;}}
            #img-modal{{display:none;position:fixed;z-index:9999;left:0;top:0;width:100%;height:100%;background-color:rgba(0,0,0,0.85);cursor:zoom-out;}}#img-modal-content{{display:block;max-width:90%;max-height:90%;margin:0 auto;position:relative;top:50%;transform:translateY(-50%);box-shadow:0 4px 15px rgba(0,0,0,0.5);border-radius:5px;}}
            #img-modal-close{{position:absolute;top:15px;right:35px;color:#f1f1f1;font-size:40px;font-weight:bold;cursor:pointer;user-select:none;}}.video-wrapper{{position:relative;display:inline-block;cursor:pointer;border-radius:5px;overflow:hidden;background:#000;}}
            .video-wrapper img{{display:block;max-width:250px;opacity:0.8;transition:opacity 0.3s;}}.video-wrapper:hover img{{opacity:0.6;}}.play-btn{{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:50px;height:50px;background:rgba(0,0,0,0.6);color:white;border-radius:50%;display:flex;justify-content:center;align-items:center;font-size:20px;padding-left:5px;box-sizing:border-box;pointer-events:none;}}
            </style><script>function loadVideo(el,vidSrc){{const w=el.offsetWidth;const h=el.offsetHeight;el.style.width=w+'px';el.style.height=h+'px';el.innerHTML='<video controls autoplay src="'+vidSrc+'" style="width:100%; height:100%; outline:none;" onloadeddata="this.style.width=\\'auto\\'; this.style.height=\\'auto\\'; this.parentElement.style.width=\\'auto\\'; this.parentElement.style.height=\\'auto\\';"></video>';el.onclick=null;el.style.cursor='default';}}
            function showImg(src){{const modal=document.getElementById('img-modal');const modalImg=document.getElementById('img-modal-content');modal.style.display="block";modalImg.src=src;}}function closeImg(){{document.getElementById('img-modal').style.display="none";}}
            document.addEventListener('keydown',function(event){{if(event.key==="Escape"){{closeImg();}}}});</script></head><body><div id="img-modal" onclick="closeImg()"><span id="img-modal-close" onclick="closeImg()">&times;</span><img id="img-modal-content"></div>
            <div class="chat-container"><div class="header"><h2>{title}</h2><a href="index.html" style="font-size:14px; color:#576b95; text-decoration:none;">返回主目录</a></div>"""

    def _get_message_html(self, is_sender, time_str, content):
        msg_class = "sender" if is_sender else "receiver"
        if isinstance(content, str) and ("text-align: center" in content or "— " in content):
            return f"""<div style="width: 100%; text-align: center; margin-bottom: 20px;"><div class="time" style="text-align: center;">{time_str}</div>{content}</div>"""
        
        return f"""<div class="message {msg_class}"><div class="time">{time_str}</div><div class="bubble">{content}</div></div>"""

    def _get_html_footer(self):
        return """</div></body></html>"""


# ==========================================
# 图形界面 (GUI) 类
# ==========================================
class WeChatExportGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("微信聊天记录导出工具 - 全能 GUI 版")
        self.root.geometry("880x650")
        
        self.root.option_add("*Font", "微软雅黑 10")
        style = ttk.Style()
        style.configure(".", font=("微软雅黑", 10))
        style.configure("Treeview.Heading", font=("微软雅黑", 10, "bold"))
        
        self.db_dir = tk.StringVar(value=r"D:\wx_decrypted_dbs")
        self.wx_data_dir = tk.StringVar()
        self.out_dir = tk.StringVar(value=r"D:\WeChat_Export")
        self.ffmpeg_path = tk.StringVar(value=r"ffmpeg")
        
        detected_dirs = self.detect_wechat_dirs()
        if detected_dirs:
            self.wx_data_dir.set(detected_dirs[0])
            
        self.exporter = None
        self.chat_list = []
        
        self.setup_ui(detected_dirs)

    def detect_wechat_dirs(self):
        dirs = []
        try:
            doc_path = os.path.join(os.path.expanduser("~"), "Documents", "WeChat Files")
            if os.path.exists(doc_path):
                for d in os.listdir(doc_path):
                    if d.lower() not in ['all users', 'applet', 'wmpf'] and os.path.isdir(os.path.join(doc_path, d)):
                        dirs.append(os.path.join(doc_path, d))
        except: pass
        return dirs

    def setup_ui(self, detected_dirs):
        frame_config = ttk.LabelFrame(self.root, text="目录与路径配置", padding=10)
        frame_config.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        
        ttk.Label(frame_config, text="解密数据库目录 (含 MSG0.db 等):").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(frame_config, textvariable=self.db_dir, width=65).grid(row=0, column=1, padx=5)
        ttk.Button(frame_config, text="浏览...", command=lambda: self.db_dir.set(filedialog.askdirectory())).grid(row=0, column=2)

        ttk.Label(frame_config, text="微信数据目录 (自动获取/选择):").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.combo_wx_data = ttk.Combobox(frame_config, textvariable=self.wx_data_dir, width=63, values=detected_dirs)
        self.combo_wx_data.grid(row=1, column=1, padx=5)
        ttk.Button(frame_config, text="手动浏览...", command=lambda: self.wx_data_dir.set(filedialog.askdirectory())).grid(row=1, column=2)

        ttk.Label(frame_config, text="导出保存目录:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(frame_config, textvariable=self.out_dir, width=65).grid(row=2, column=1, padx=5)
        ttk.Button(frame_config, text="浏览...", command=lambda: self.out_dir.set(filedialog.askdirectory())).grid(row=2, column=2)
        
        ttk.Label(frame_config, text="FFmpeg 路径 (用于语音转码):").grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Entry(frame_config, textvariable=self.ffmpeg_path, width=65).grid(row=3, column=1, padx=5)
        ttk.Button(frame_config, text="浏览...", command=lambda: self.ffmpeg_path.set(filedialog.askopenfilename(filetypes=[("Executable", "*.exe")]))).grid(row=3, column=2)

        self.btn_load = ttk.Button(frame_config, text="1. 加载并扫描所有会话", command=self.thread_load_chats)
        self.btn_load.grid(row=4, column=0, columnspan=3, pady=10)

        frame_log = ttk.LabelFrame(self.root, text="运行日志", padding=5)
        frame_log.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        
        self.log_text = tk.Text(frame_log, height=5, state=tk.DISABLED, bg="#f5f5f5", font=("微软雅黑", 9))
        self.log_text.pack(fill=tk.X, pady=(0, 5))
        
        frame_prog = ttk.Frame(frame_log)
        frame_prog.pack(fill=tk.X)
        
        ttk.Label(frame_prog, text="总 进 度:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5), pady=2)
        self.progress_var_total = tk.DoubleVar()
        self.progress_bar_total = ttk.Progressbar(frame_prog, variable=self.progress_var_total, maximum=100)
        self.progress_bar_total.grid(row=0, column=1, sticky=tk.EW, pady=2)
        
        ttk.Label(frame_prog, text="当前会话:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=2)
        self.progress_var_current = tk.DoubleVar()
        self.progress_bar_current = ttk.Progressbar(frame_prog, variable=self.progress_var_current, maximum=100)
        self.progress_bar_current.grid(row=1, column=1, sticky=tk.EW, pady=2)
        
        frame_prog.columnconfigure(1, weight=1)

        frame_action = ttk.Frame(self.root)
        frame_action.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        
        ttk.Button(frame_action, text="全选/反选 (会话)", command=lambda: self.toggle_all_column('Select')).pack(side=tk.LEFT, padx=3)
        ttk.Button(frame_action, text="批量切换[图片]", command=lambda: self.toggle_all_column('ExpImg')).pack(side=tk.LEFT, padx=3)
        ttk.Button(frame_action, text="批量切换[视频]", command=lambda: self.toggle_all_column('ExpVid')).pack(side=tk.LEFT, padx=3)
        ttk.Button(frame_action, text="批量切换[语音]", command=lambda: self.toggle_all_column('ExpAud')).pack(side=tk.LEFT, padx=3)
        
        self.btn_export = ttk.Button(frame_action, text="3. 开始导出选中项", command=self.thread_start_export, state=tk.DISABLED)
        self.btn_export.pack(side=tk.RIGHT, padx=5)

        frame_list = ttk.LabelFrame(self.root, text="2. 勾选需要导出的会话及多媒体偏好 (点击复选框切换)", padding=10)
        frame_list.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        columns = ("Select", "Name", "WeChatID", "Count", "ExpImg", "ExpVid", "ExpAud")
        self.tree = ttk.Treeview(frame_list, columns=columns, show="headings", selectmode="none")
        self.tree.heading("Select", text="导出?")
        self.tree.heading("Name", text="会话名称 / 备注")
        self.tree.heading("WeChatID", text="微信号 / 群ID")
        self.tree.heading("Count", text="消息数")
        self.tree.heading("ExpImg", text="图片")
        self.tree.heading("ExpVid", text="视频")
        self.tree.heading("ExpAud", text="语音")
        
        self.tree.column("Select", width=50, anchor=tk.CENTER)
        self.tree.column("Name", width=250)
        self.tree.column("WeChatID", width=200)
        self.tree.column("Count", width=70, anchor=tk.E)
        self.tree.column("ExpImg", width=50, anchor=tk.CENTER)
        self.tree.column("ExpVid", width=50, anchor=tk.CENTER)
        self.tree.column("ExpAud", width=50, anchor=tk.CENTER)
        
        scrollbar = ttk.Scrollbar(frame_list, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)

    def log(self, msg):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def set_progress_total(self, val):
        self.progress_var_total.set(val)
        self.root.update_idletasks()

    def set_progress_current(self, val):
        self.progress_var_current.set(val)
        self.root.update_idletasks()

    def on_tree_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            col_map = {'#1': 'Select', '#5': 'ExpImg', '#6': 'ExpVid', '#7': 'ExpAud'}
            
            if column in col_map:
                item = self.tree.identify_row(event.y)
                col_name = col_map[column]
                current_val = self.tree.set(item, col_name)
                new_val = "[ ]" if current_val == "[x]" else "[x]"
                self.tree.set(item, col_name, new_val)

    def toggle_all_column(self, col_name):
        items = self.tree.get_children()
        if not items: return
        first_val = self.tree.set(items[0], col_name)
        new_val = "[ ]" if first_val == "[x]" else "[x]"
        for item in items:
            self.tree.set(item, col_name, new_val)

    def thread_load_chats(self):
        self.btn_load.config(state=tk.DISABLED)
        self.tree.delete(*self.tree.get_children())
        threading.Thread(target=self._load_chats_task, daemon=True).start()

    def _load_chats_task(self):
        self.exporter = WeChatExporter(
            self.db_dir.get(), self.wx_data_dir.get(), self.out_dir.get(), self.ffmpeg_path.get(),
            self.log, self.set_progress_total, self.set_progress_current
        )
        if self.exporter.prepare_database():
            self.chat_list = self.exporter.scan_chats()
            for chat in self.chat_list:
                self.tree.insert("", tk.END, values=("[ ]", chat['name'], chat['id'], chat['count'], "[x]", "[x]", "[x]"))
            self.btn_export.config(state=tk.NORMAL)
        self.btn_load.config(state=tk.NORMAL)

    def thread_start_export(self):
        selected_chats = []
        for item in self.tree.get_children():
            if self.tree.set(item, "Select") == "[x]":
                selected_chats.append({
                    'id': self.tree.set(item, "WeChatID"),
                    'name': self.tree.set(item, "Name"),
                    'count': int(self.tree.set(item, "Count")),
                    'img': self.tree.set(item, "ExpImg") == "[x]",
                    'video': self.tree.set(item, "ExpVid") == "[x]",
                    'audio': self.tree.set(item, "ExpAud") == "[x]"
                })
                
        if not selected_chats:
            messagebox.showwarning("提示", "请先在列表中勾选要导出的会话！")
            return
            
        self.btn_export.config(state=tk.DISABLED)
        self.btn_load.config(state=tk.DISABLED)
        threading.Thread(target=self._export_task, args=(selected_chats,), daemon=True).start()

    def _export_task(self, selected_chats):
        self.progress_var_total.set(0)
        self.progress_var_current.set(0)
        try:
            self.exporter.export_selected_chats(selected_chats)
            messagebox.showinfo("完成", "所选聊天记录已全部导出完毕！")
        except Exception as e:
            self.log(f"[-] 导出过程中发生严重错误: {e}")
        finally:
            self.btn_export.config(state=tk.NORMAL)
            self.btn_load.config(state=tk.NORMAL)

if __name__ == "__main__":
    root = tk.Tk()
    app = WeChatExportGUI(root)
    root.mainloop()