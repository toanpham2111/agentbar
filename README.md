<p align="center">
  <img src="assets/kio-mark.svg" alt="Logo KIO" width="96" />
</p>

<div align="center">

# Kio Usage Monitoring

[![Quality](https://github.com/toanpham2111/agentbar/actions/workflows/quality.yml/badge.svg?branch=main)](https://github.com/toanpham2111/agentbar/actions/workflows/quality.yml)
[![Release](https://img.shields.io/github/v/release/toanpham2111/agentbar?label=release)](https://github.com/toanpham2111/agentbar/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Ubuntu%20%7C%20Debian-5E2750?logo=ubuntu&logoColor=white)](#-cài-đặt)

**Theo dõi quota Claude Code, OpenAI Codex và Google Antigravity ngay trên thanh menu Linux.**<br>
*Nhẹ, local-first, không cần mở dashboard và không bịa số liệu khi nhà cung cấp không trả dữ liệu.*

[🌱 Vì sao](#-vì-sao-dự-án-ra-đời) • [🚀 Cài đặt](#-cài-đặt) • [✨ Tính năng](#-tính-năng) • [🔌 Nhà cung cấp](#-nhà-cung-cấp-được-hỗ-trợ) • [🧪 Phát triển](#-phát-triển) • [🔒 Quyền riêng tư](#-quyền-riêng-tư)

</div>

---

## 🌱 Vì sao dự án ra đời?

Kio Usage Monitoring ra đời từ một vấn đề rất thực tế: lập trình viên thường sử dụng nhiều công cụ AI cùng lúc, nhưng quota của mỗi công cụ lại nằm ở một nơi khác nhau. Muốn biết phiên làm việc còn bao nhiêu, khi nào quota được đặt lại hoặc công cụ nào sắp chạm giới hạn, người dùng phải mở từng ứng dụng hay trang quản lý để kiểm tra.

Dự án gom các tín hiệu sử dụng đã được xác minh vào một menu nhỏ trên desktop. Mục tiêu không phải tạo thêm một dashboard nặng nề, mà là giúp người dùng trả lời nhanh ba câu hỏi ngay trong lúc làm việc:

1. Công cụ AI nào đang hoạt động trên máy?
2. Phiên hiện tại và quota tuần đã dùng bao nhiêu?
3. Khi nào giới hạn được đặt lại, hoặc vì sao dữ liệu chưa khả dụng?

Kio ưu tiên tính trung thực của dữ liệu. Nếu nhà cung cấp không trả quota hoặc local service chưa chạy, ứng dụng nói rõ điều đó thay vì hiển thị `0%` hay tự ước đoán một con số.

## 💡 Kio Usage Monitoring là gì?

Kio Usage Monitoring là ứng dụng menu-bar dành cho Linux, giúp bạn xem nhanh mức sử dụng của các công cụ AI coding đang dùng trên máy. Ứng dụng chạy nền, tự làm mới dữ liệu và hiển thị chi tiết theo từng nhà cung cấp mà không cần tài khoản Kio hay backend đám mây.

Khi dữ liệu không khả dụng, Kio hiển thị `--` cùng nguyên nhân rõ ràng thay vì thay thế bằng `0%` hoặc một con số ước đoán.

Ứng dụng đọc dữ liệu từ phiên đăng nhập hoặc local service của từng công cụ, chuẩn hóa thành trạng thái thống nhất rồi hiển thị trên system tray. Người dùng có thể mở popover để xem chi tiết, dùng CLI trong terminal hoặc để Kio tự chạy khi đăng nhập.

<p align="center">
  <img src="docs/screenshots/kio-menu-bar-live.png" alt="Kio Usage Monitoring đang chạy với quota Claude Code, OpenAI Codex và Antigravity" width="588" />
</p>

<p align="center"><sub>Ảnh chụp thực tế từ Kio Usage Monitoring v1.0.0 trên Linux. Số liệu quota thay đổi theo tài khoản và thời điểm sử dụng.</sub></p>

## ✨ Tính năng

- **Theo dõi ngay trên system tray** với giao diện GTK gọn nhẹ.
- **Quota theo phiên và theo tuần** cho Claude Code và OpenAI Codex.
- **Đọc quota Antigravity trực tiếp** khi language server của Antigravity đang chạy.
- **Tự nhận diện công cụ** đã cài trên máy và báo rõ trạng thái chưa hỗ trợ.
- **Tùy chỉnh chu kỳ làm mới, cảnh báo và nhà cung cấp** trong phần Settings.
- **Tự khởi động khi đăng nhập** nếu người dùng bật autostart.
- **CLI đi kèm** cho terminal, TUI live watch, Waybar, tmux và JSON output.
- **Local-first**: credential và dữ liệu sử dụng không rời khỏi thiết bị.

## 🔌 Nhà cung cấp được hỗ trợ

| Nhà cung cấp | Menu-bar | Chi tiết quota | Nguồn dữ liệu |
|---|:---:|:---:|---|
| Claude Code | ✅ | Phiên hiện tại và giới hạn tuần | Phiên OAuth cục bộ + Anthropic usage API |
| OpenAI Codex | ✅ | Cửa sổ 5 giờ và giới hạn tuần | Phiên OAuth cục bộ + OpenAI usage API |
| Google Antigravity | ✅ | Các nhóm quota do Antigravity trả về | Local Antigravity RPC |
| Qoder | 🟡 | Chưa có live quota | Nhận diện cài đặt |

> Antigravity cần được mở vì local RPC dừng khi ứng dụng đóng hoàn toàn. Qoder hiện chỉ hỗ trợ nhận diện cài đặt do chưa có nguồn live quota đã được xác minh.

## 🚀 Cài đặt

### Ubuntu / Debian

1. Tải `Kio-Usage-Monitoring_1.0.0_amd64.deb` tại [GitHub Releases](https://github.com/toanpham2111/agentbar/releases/tag/v1.0.0).
2. Mở file và chọn **Install**, hoặc cài bằng terminal:

```bash
sudo apt install ./Kio-Usage-Monitoring_1.0.0_amd64.deb
```

3. Mở **Kio Usage Monitoring** từ menu ứng dụng.
4. Chọn có tự khởi động Kio khi đăng nhập hay không trong lần chạy đầu tiên.

Gói cài đặt tự khai báo các dependency cần thiết: Python 3, GTK 3, Ayatana AppIndicator và Pillow.

## ⌨️ Sử dụng CLI

```bash
agentbar status                 # Xem quota hiện tại
agentbar watch                  # Theo dõi live trong terminal
agentbar --json                 # Xuất dữ liệu JSON
agentbar --waybar               # Xuất dữ liệu cho Waybar/Polybar
agentbar settings               # Mở phần cài đặt
agentbar stop                   # Dừng app chạy nền
```

Xem toàn bộ tùy chọn bằng `agentbar --help`.

## 🧪 Phát triển

```bash
git clone https://github.com/toanpham2111/agentbar.git
cd agentbar
python3 -m unittest discover -s tests -q
python3 scripts/build_linux_release.py 1.0.0
```

Quy trình build tạo gói `.deb` và checksum tại thư mục `release/`. Hướng dẫn phát hành đầy đủ nằm trong [`docs/RELEASE.md`](docs/RELEASE.md).

## 🗂️ Cấu trúc dự án

```text
agentbar/
├── agentbar/              # CLI, detector, menu-bar và đóng gói
├── assets/                # Logo, app icon và provider icons
├── scripts/               # Công cụ build bản phát hành Linux
├── tests/                 # Unit tests
├── docs/                  # Kiến trúc, bảo mật và tài liệu provider
└── .github/workflows/     # CI quality gate và release automation
```

## 🔒 Quyền riêng tư

- Credential và RPC token chỉ được sử dụng cục bộ để lấy dữ liệu từ nhà cung cấp hoặc local service tương ứng.
- Kio không tải prompt, mã nguồn dự án hay credential lên máy chủ riêng.
- Giá trị không xác minh được luôn hiển thị là không khả dụng; ứng dụng không tạo quota giả.

Xem thêm [`docs/SECURITY.md`](docs/SECURITY.md) và [`docs/PROVIDER_SPEC.md`](docs/PROVIDER_SPEC.md).

## 🤝 Đóng góp

Pull request được chào đón. Mỗi thay đổi tính năng cần có test bao phủ happy path, edge case và error handling; toàn bộ test phải pass trước khi gửi PR.

## 📄 Giấy phép

[MIT](LICENSE) © 2026 KIO Digital.
