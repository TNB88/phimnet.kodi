# Phim Nét cho Kodi

Kho cập nhật chính thức của addon `plugin.video.phimnet`.

## Cài đặt lần đầu

1. Tải `repository.phimnet-1.0.0.zip` từ thư mục `repository.phimnet`.
2. Trong Kodi chọn **Add-ons → Install from zip file** và mở file ZIP đó.
3. Chọn **Install from repository → Phim Nét Online Repository → Video add-ons → Phim Nét**.
4. Bật **Install updates automatically** trong Kodi để các phiên bản sau tự cập nhật.

Có thể cài thẳng `plugin.video.phimnet-1.0.14.zip`; bản 1.0.14 cũng đăng ký cùng
kho online để tiếp tục nhận các bản mới.

## Cấu trúc kho

- `addons.xml`, `addons.xml.md5`: chỉ mục cập nhật Kodi.
- `repository.phimnet/`: addon kho online và file ZIP cài đặt.
- `plugin.video.phimnet/`: mã nguồn và file ZIP của addon Phim Nét.
- `config.json`: cấu hình API/CDN dự phòng; cấu hình động của app vẫn được ưu tiên.
