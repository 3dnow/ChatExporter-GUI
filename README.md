ChatExporter-GUI 💬 / 聊天记录全能导出工具

中文 | English

中文文档

ChatExporter-GUI 是一款专为 Windows PC 端设计的聊天记录导出与备份工具。在通过其他工具（如 pywxdump）获取到解密后的 SQLite 数据库后，本工具能以最优雅、最完整的方式，将您的青春记忆提取为交互式 HTML 网页和纯文本 CSV 文件。

✨ 核心特色 (Why choose us?)

与市面上简陋的导出脚本不同，本工具针对聊天软件极其复杂的底层数据结构进行了深度逆向解析与优化：

🎨 现代化 GUI 界面: 告别黑框框！可视化勾选您想导出的联系人，独家支持按会话粒度控制媒体导出（例如：A群只导文字，B好友导出所有图文视频）。

📑 完美解析“合并转发”: 独家实现合并转发聊天记录的无限嵌套解析！不仅能以折叠面板完美还原交互，还能提取转发记录内的图片和视频。

🎵 语音秒转 MP3: 内置集成 pilk 与 ffmpeg，将聊天软件难搞的加密 .silk 语音自动转码为 .mp3，并在网页中直接提供 HTML5 <audio> 播放器（带时长显示）。

⚡ 海量记录防崩溃: HTML 按每 1000 条自动分卷。针对大型视频，采用首帧封面+点击懒加载机制，打破 Chrome 同屏加载多个 Video 标签导致崩溃的限制。

🔍 双格式双管齐下:

HTML: 还原聊天气泡 UI，内置全局图片放大查看器。

CSV: 自动剔除多余媒体标签的纯净版 CSV，方便丢进 Excel 秒搜关键词。

🧩 全量消息类型支持: 完美还原聊天默认 Emoji (Unicode无缝映射)、图片、视频、文件（保留中文名）、撤回/系统消息、名片、定位（直连 OpenStreetMap）、小程序卡片、转账及红包记录。

🚀 快速开始

1. 准备工作

请先使用 pywxdump 等工具将聊天软件的 .db 数据库解密。

确保您的电脑上安装了 Python 3.8+。

安装必要的依赖库：

pip install lz4 blackboxprotobuf pilk


下载 FFmpeg (Windows 常用 ffmpeg.exe)，并记住其存放路径，用于语音转码。

2. 运行工具

python chat_exporter_gui.py


3. 界面操作指南

配置目录：填入您的解密数据库目录、原数据目录（自动识别，含 FileStorage）以及导出的目标文件夹。系统会自动尝试帮您填入用户目录。

加载会话：点击“加载并扫描”，工具会在后台极速整合您的数据库，不卡顿界面。

精准勾选：在列表中勾选需要导出的会话，您可以为每个会话单独开关 [图片] [视频] [语音]。

一键导出：点击开始，享受双进度条的实时反馈！

English Documentation

ChatExporter-GUI is a powerful Windows desktop application designed to archive and beautifully export your *Chat PC chat histories. Once you have decrypted your *Chat SQLite databases (using tools like pywxdump), this tool perfectly extracts your memories into Interactive HTML pages and Searchable CSV files.

✨ Key Features

🎨 Modern GUI User Interface: Say goodbye to the command line. Visually select which contacts to export. Unique Feature: Granular control over media export per chat (e.g., text-only for group A, full media for friend B).

📑 Perfect Nested Forwarding parsing: Uniquely handles *Chat's complex "Merged and Forwarded chat history" format. Supports infinite nesting with foldable UI and restores images/videos within forwarded messages!

🎵 Auto SILK to MP3: Seamlessly integrates pilk and ffmpeg to automatically convert *Chat's encrypted .silk audio files into standard .mp3. Play audio directly in the exported HTML!

⚡ High Performance & Lazy-loading: Automatically paginates HTML every 1000 messages. Videos are rendered with a thumbnail and a "lazy-load on click" mechanism to prevent browser crashes on massive histories.

🔍 Dual Output Formats:

HTML: Beautiful chat bubbles with a built-in fullscreen image viewer.

CSV: A clean, text-only timeline optimized for lightning-fast keyword searching in Excel.

🧩 Rich Message Support: Fully supports native Unicode Emojis, Images, Videos, Files (with Chinese path handling), System messages, Business Cards, Locations (via OpenStreetMap), Mini-programs, Transfers, and Red Packets.

🚀 Quick Start

1. Prerequisites

Decrypt your *Chat .db files using tools like pywxdump first.

Ensure Python 3.8+ is installed.

Install dependencies:

pip install lz4 blackboxprotobuf pilk


Download FFmpeg (specifically ffmpeg.exe for Windows) for voice message conversion.

2. Run

python chat_exporter_gui.py


3. Usage

Set Paths: Provide your decrypted DB folder, *Chat Data folder (containing FileStorage), Export destination, and FFmpeg path.

Load Chats: Click "Load and Scan". An in-memory SQLite engine will compile your history without freezing the UI.

Select & Configure: Check the chats you wish to export. You can toggle image/video/audio export for each chat individually.

Export: Click export and monitor the dual-layer progress bar!

🤝 Acknowledgements / 致谢

PyWxDump - For providing excellent references on *Chat database structures.

blackboxprotobuf - For decoding raw Protobuf buffers.

pilk - For SILK audio decoding.

📄 License

This project is licensed under the MIT License.
