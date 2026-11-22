# ⚡ AgentBar — Cross-Platform AI Coding Engine Usage Bar (Linux / Windows / macOS)

**AgentBar** là ứng dụng chạy ngầm đa nền tảng (**Linux**, **Windows**, **macOS**) và công cụ **Terminal CLI/TUI** giúp tự động nhận diện các AI Coding Engine được cài trên máy (**Claude Code**, **OpenAI Codex CLI**, **Google Antigravity**, **Qoder**, **Cursor**, **Aider**) và hiển thị trực tiếp phần trăm Quota / Usage thực tế (100% Live OAuth API / RPC) ngay trên **Thanh Bar hệ thống**.

👉 Xem tài liệu mô tả chi tiết toàn bộ kiến trúc và tính năng tại: **[`PROJECT_OVERVIEW.md`](./PROJECT_OVERVIEW.md)**.

---

## 🚀 Các Lệnh Sử Dụng Nhanh

```bash
# Bật chạy ngầm (hoặc ẩn/hiện bảng chi tiết nếu đã chạy)
agentbar start

# Ẩn / Hiện (Hide / Show) thanh Bar nổi ở góc phải bên dưới màn hình
agentbar toggle-bar

# Mở thẳng bảng Cài đặt (⚙ Settings)
agentbar settings

# Tắt hoàn toàn ứng dụng chạy ngầm
agentbar stop

# Xem trực tiếp trong Terminal hoặc mở bảng Live TUI
agentbar
agentbar watch

# Đóng gói & cập nhật biểu tượng ngoài màn hình Desktop
python3 /home/toan/Toan/agentbar/build_desktop_app.py --autostart

# Chạy bộ kiểm thử tự động (Unit & Integration Tests)
python3 -m unittest discover -s /home/toan/Toan/agentbar/tests -v
```
