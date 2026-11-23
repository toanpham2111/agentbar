# AgentBar Legacy — Tài liệu tham chiếu

> **Trạng thái:** Tài liệu bên dưới mô tả ứng dụng Python cũ và chỉ được giữ lại để
> tham chiếu trong quá trình chuyển đổi. Sản phẩm đang phát triển hiện tại là
> **KIO Usage Monitor** (Tauri 2 + Rust + React). Xem `README.md` và thư mục `docs/`
> để biết kiến trúc, nguồn dữ liệu và chính sách bảo mật đang áp dụng. Các cơ chế
> OAuth/RPC riêng tư được mô tả bên dưới không thuộc bản KIO mới.

**AgentBar** là ứng dụng chạy ngầm đa nền tảng (**Linux**, **Windows**, **macOS**) và công cụ **Terminal CLI/TUI** giúp tự động nhận diện các AI Coding Engine được cài trên máy (**Claude Code**, **OpenAI Codex CLI**, **Google Antigravity**, **Qoder**, **Cursor**, **Aider**) và hiển thị trực tiếp phần trăm Quota / Usage thực tế theo thời gian thực ngay trên **Thanh Bar hệ thống** mà không cần mở từng ứng dụng hay trình duyệt web.

- **Thư mục dự án**: `/home/toan/Toan/agentbar`
- **File thực thi độc lập**: `/home/toan/Toan/agentbar/dist/agentbar` (đã cài toàn cục tại `/home/toan/.local/bin/agentbar`)
- **Biểu tượng Desktop**: `/home/toan/Desktop/AgentBar.desktop`
- **Cấu hình người dùng**: `~/.config/agentbar/settings.json`

---

## 1. Tự Động Nhận Diện & Lấy Dữ Liệu Thật 100% Theo Thời Gian Thực (`agentbar/detectors.py`)

Ứng dụng tự động quét cả file thực thi (`PATH`, `nvm`, `~/.local/bin`, `cargo`, `%APPDATA%\npm`, `/opt/homebrew/bin`) lẫn thư mục cấu hình cục bộ và kết nối trực tiếp tới API OAuth / RPC gốc của từng Engine đang đăng nhập trên máy:

### 🟠 Claude Code (`detect_claude_code`, `_fetch_claude_live_oauth_usage`)
- **Nguồn dữ liệu thật**:
  - Đọc thông tin xác thực OAuth từ `~/.claude/.credentials.json`.
  - Tự động làm mới (refresh) `accessToken` qua `https://platform.claude.com/v1/oauth/token` khi token hết hạn.
  - Truy vấn trực tiếp `https://api.anthropic.com/api/oauth/usage` (kèm fallback đọc log `~/.claude/projects/*/*.jsonl`).
- **Thông số lấy được**:
  - **`Current session`**: Phần trăm đã sử dụng trong khung 5 giờ (`five_hour.utilization`) và thời điểm reset chính xác (`Resets at 11:50 PM`).
  - **`This week`**: Phần trăm đã sử dụng trong khung 7 ngày (`seven_day.utilization`) và ngày giờ reset (`Resets Saturday 3:00 PM`).
  - **`Limit resets (Full reset)`**: Thời hạn hiệu lực và nút hành động `Reset for free`.
  - **`Usage credits` & `Monthly spend limit`**: Số dư credit (`$0`), trạng thái bật/tắt (`ON/OFF`), số tiền đã dùng trong tháng (`$0.00 this month`), giới hạn chi tiêu (`No spend limit`) và trạng thái `Auto-reload`.
  - **`This week's usage by product`**: Phân bổ tỷ lệ sử dụng trong tuần theo từng sản phẩm từ `seven_day_breakdown.rows` (`Claude Code`, `Chats`, `Cowork`, `Other`).

### 🟢 OpenAI Codex CLI (`detect_codex`, `_fetch_codex_live_oauth_usage`)
- **Nguồn dữ liệu thật**:
  - Đọc token từ `~/.codex/auth.json` và truy vấn trực tiếp `https://chatgpt.com/backend-api/wham/usage` (kèm fallback đọc `~/.codex/state_5.sqlite` và `~/.codex/sessions/**/*.jsonl`).
- **Thông số lấy được**:
  - **`5-hour limit`**: Phần trăm hạn mức còn lại (`100% left`) và thời gian đếm ngược reset (`Resets in 4h 35m`).
  - **`Weekly limit`**: Phần trăm hạn mức tuần còn lại (`100% left`) và thời gian đếm ngược reset (`Resets in 6d 23h`).
  - **`Recent plan usage`**: Hiển thị phần trăm hạn mức khả dụng theo bộ chọn `5-hour` hoặc `Weekly` và nút nâng cấp gói cước (`upgrade your plan`).

### 🔵 Google Antigravity (`detect_antigravity`, `_fetch_antigravity_live_rpc_usage`)
- **Nguồn dữ liệu thật**:
  - Tự động phát hiện tiến trình `language_server` đang chạy trên máy, lấy `--csrf_token` và cổng kết nối nội bộ để gọi trực tiếp RPC gốc `/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary` (kèm fallback `GetUserStatus` và `conversation_summaries.db`).
- **Thông số lấy được**:
  - **`Gemini Models`**: `Weekly Limit Remaining` (`97%`) và `Five Hour Limit Remaining` (`90%`) kèm thời gian làm mới thực tế.
  - **`Claude and GPT models`**: `Weekly Limit Remaining` (`100%`) và `Five Hour Limit Remaining` (`100%`).
  - **`Gemini 4 Argon`**: `Gemini 4 Argon Weekly Limit` (`49%`) kèm thời gian làm mới chi tiết và tooltip danh sách model thuộc từng nhóm.

### 🟣 Qoder & Mở Rộng (`detect_qoder`, `detect_additional_engines`)
- Nhận diện `qoder` binary và dữ liệu phiên làm việc thực tế trong `~/.qoder`, `~/.config/Qoder`, `%APPDATA%\Qoder` (tự động bỏ qua các thư mục chỉ chứa symlink rỗng), đồng thời hỗ trợ mở rộng cho **Cursor AI** và **Aider CLI**.

---

## 2. Hiển Thị Đa Nền Tảng Trên Thanh Bar Hệ Thống

### 🐧 Trên Linux (`agentbar/sni_indicator.py`, `agentbar/menubar.py`)
- **Tích hợp trực tiếp vào thanh Top Panel gốc của Linux GNOME**:
  - Sử dụng giao thức D-Bus `org.kde.StatusNotifierItem` (thuộc tính `XAyatanaLabel`) kết hợp `com.canonical.dbusmenu`.
  - Hiển thị biểu tượng 4 cột màu động cùng dòng chữ **`Claude 29% · Codex 0% · Agy 71%`** nằm trực tiếp bên trong thanh Top Bar màu đen của Linux (ngay cạnh đồng hồ hệ thống và khay icon).
  - Bấm chuột trái 1 lần trên thanh Top Bar sẽ xổ xuống menu gốc của GNOME cho phép mở nhanh từng tab (`All`, `Claude`, `Codex`, `Agy`, `⚙ Settings`) hoặc ẩn/hiện thanh Bar nổi góc dưới.

### 🪟 Trên Windows & 🍎 MacBook (`agentbar/win_mac_bar.py`)
- **Thanh Bar nổi ở góc phải bên dưới màn hình (Bottom-Right Floating Bar)**:
  - Neo gọn gàng ở góc phải bên dưới màn hình (ngay phía trên Taskbar của Windows hoặc Dock của macOS).
  - Bấm vào thanh Bar để mở bảng Popover chi tiết ngay phía trên.
  - **Ẩn / Hiện (Hide / Show) tùy ý**:
    - Bấm nút `×` ngay trên cạnh phải của thanh Bar để ẩn xuống khay hệ thống.
    - Bấm vào icon AgentBar dưới System Tray (Windows) / Menu Bar (macOS) chọn **`👁 Show / Hide Bottom-Right Bar`** hoặc chạy lệnh `agentbar toggle-bar` để bật/tắt bất cứ lúc nào.

---

## 3. Giao Diện Popover Tối Giản & Chi Tiết Theo Từng Tab (`agentbar/menubar.py`)

Cửa sổ Popover được thiết kế tối giản trên nền tối (`#18181a`) với thanh điều hướng gồm các tab:

1. **Tab `All`**: Hiển thị tóm tắt 2 thanh tiến trình bo tròn mượt (`Current session` và `This week`) cho tất cả các engine đang bật. Thanh tiến trình tự động chuyển từ màu xanh dương (`#3b82f6`) sang màu đỏ (`#e5484d`) khi chạm ngưỡng cảnh báo.
2. **Tab `Claude`**: Hiển thị đầy đủ `Current session`, `This week`, `Limit resets (Full reset)`, `Usage credits`, `Monthly spend limit` và `This week's usage by product` kèm các nút bấm tương tác thật (`Reset for free`, `Learn more`, `ON/OFF`, `Buy usage credits · Up to 30% off`, `Manage`).
3. **Tab `Codex`**: Hiển thị thẻ bo góc `Plan limits` (`5-hour limit`, `Weekly limit` với thanh tiến trình trắng và `% left`), thẻ `Recent plan usage` kèm bộ chuyển đổi trực tiếp `5-hour` / `Weekly` và nút `upgrade your plan`.
4. **Tab `Agy`**: Hiển thị 3 thẻ `Gemini Models`, `Claude and GPT models`, `Gemini 4 Argon` với biểu đồ vòng tròn tiến trình màu xanh lá cây và tooltip `ⓘ` mô tả danh sách model thực tế trong từng nhóm.
5. **Tab `⚙` (Settings)**:
   - **Engines (Show / Hide on Bar)**: Bật / tắt hiển thị từng Engine (`Claude Code`, `OpenAI Codex`, `Antigravity`, `Qoder`).
   - **Background & Startup**:
     - `Show bottom-right floating bar`: Ẩn / hiện thanh Bar nổi ở góc phải bên dưới màn hình.
     - `Run in background on startup`: Tự động chạy ngầm khi mở máy.
     - `Start minimized on menu bar`: Khởi chạy thu gọn trên thanh bar.
     - `Desktop quota warning alert`: Gửi thông báo hệ thống khi có Engine vượt ngưỡng cảnh báo.
   - **Display & Refresh**: Tùy chỉnh chu kỳ cập nhật (`15s / 30s / 60s / 5m`), ngưỡng cảnh báo đỏ (`70% / 80% / 90%`), vị trí thanh bar và định dạng phần trăm hiển thị (`Session % / Max % / Compact`).

---

## 4. Cấu Trúc Thư Mục Dự Án (`/home/toan/Toan/agentbar`)

```text
/home/toan/Toan/agentbar/
├── agentbar.py                 # Entry point chạy trực tiếp từ CLI
├── build_desktop_app.py        # Script đóng gói 1-click ra Desktop & App Menu
├── pyproject.toml              # Cấu hình Python package
├── requirements.txt            # Thư viện tùy chọn (Pillow, pystray)
├── README.md                   # Hướng dẫn cài đặt & sử dụng nhanh
├── PROJECT_OVERVIEW.md         # Tài liệu mô tả tổng quan dự án
├── assets/
│   ├── agentbar.png            # Icon ứng dụng 256x256 PNG
│   └── agentbar.ico            # Icon ứng dụng đa kích thước cho Windows
├── dist/
│   ├── agentbar                # File thực thi độc lập (Single-File ZipApp Binary)
│   └── AgentBar.app/           # Gói ứng dụng Menu Bar chuẩn cho macOS
├── agentbar/
│   ├── __init__.py
│   ├── models.py               # Data models & bộ định dạng thời gian / phần trăm
│   ├── detectors.py            # Bộ nhận diện & lấy dữ liệu Live OAuth API / RPC
│   ├── config.py               # Quản lý Settings, Autostart & Background Daemon
│   ├── sni_indicator.py        # Tích hợp trực tiếp vào thanh Top Panel của Linux GNOME
│   ├── menubar.py              # Giao diện Popover đa tab (All, Claude, Codex, Agy, Settings)
│   ├── win_mac_bar.py          # Thanh Bar nổi góc phải bên dưới cho Windows & MacBook
│   ├── tui.py                  # Giao diện bảng Terminal ANSI & Live TUI (curses)
│   ├── packaging.py            # Công cụ đóng gói đa nền tảng (.desktop, .app, .lnk)
│   └── cli.py                  # Bộ điều phối lệnh CLI
└── tests/
    └── test_agentbar.py        # Bộ 7 Unit & Integration Tests tự động
```

---

## 5. Tổng Hợp Các Lệnh Sử Dụng Nhanh

```bash
# 1. Điều khiển ứng dụng chạy ngầm & giao diện
agentbar start              # Bật ứng dụng chạy ngầm (hoặc bật/tắt bảng Popover nếu đang chạy)
agentbar toggle-bar         # Ẩn / Hiện (Hide / Show) thanh Bar nổi ở góc phải bên dưới
agentbar settings           # Mở thẳng bảng Cài đặt (⚙ Settings)
agentbar stop               # Tắt hoàn toàn ứng dụng chạy ngầm

# 2. Mở trực tiếp một Tab cụ thể
agentbar bar --tab all
agentbar bar --tab claude
agentbar bar --tab codex
agentbar bar --tab antigravity

# 3. Dành cho người chỉ dùng Terminal
agentbar                    # Xem bảng thống kê tối giản ngay trong Terminal
agentbar watch              # Chế độ Live TUI tự động làm mới trong Terminal (nhấn 'q' để thoát)
agentbar --short            # Xuất 1 dòng ngắn gọn
agentbar --tmux             # Xuất chuỗi màu cho thanh status-right của tmux
agentbar --waybar           # Xuất JSON cho thanh Waybar / Polybar trên Linux
agentbar --swiftbar         # Xuất plugin cho SwiftBar / xbar trên macOS
agentbar --json             # Xuất toàn bộ dữ liệu dạng JSON

# 4. Đóng gói lại ra Desktop & chạy kiểm thử
python3 /home/toan/Toan/agentbar/build_desktop_app.py --autostart
python3 -m unittest discover -s /home/toan/Toan/agentbar/tests -v
```
