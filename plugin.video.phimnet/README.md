# Phim Nét cho Kodi

Addon riêng cho Server Nét gốc của APK Phim4K 2.6.0. Addon không trộn hai
nguồn phụ Free 1/Free 2.

Chức năng:

- Phim mới, phim lẻ, phim bộ, thể loại, quốc gia và tìm kiếm.
- Đọc đầy đủ `videos[]` của API gốc.
- Hiện nguyên nhãn bản phim gồm 1080p/2160p, HDR/DV/REMUX và dung lượng GB.
- Ký URL CDN ngay lúc phát bằng thuật toán tương thích APK.
- Không phát nội dung có `is_paid=1`; addon không vượt khóa thuê bao.
- Không có màn hình cài đặt và không hiện API/key trong giao diện Kodi.

Thư mục addon: `plugin.video.phimnet`

Phiên bản `1.0.1` dùng bộ nhận diện Siêu Nét mới:

- Icon vuông: `resources/media/icon-phimnet-v2.png`
- Fanart nền ngang: `resources/media/fanart-phimnet-v2.png`
- Tên tệp mới giúp Kodi không lấy nhầm ảnh cũ từ bộ nhớ đệm.

Phiên bản `1.0.2` kiểm tra link cuối bằng GET Range trước khi phát. Nếu resolver
trả `demo.mp4`/`demo-proxy`, addon dừng sạch và báo lỗi máy chủ thay vì mở clip
thông báo như phim thật.

Phiên bản `1.0.6` dùng User-Agent chuẩn của client, lấy thời gian ký từ header
máy chủ thay vì phụ thuộc hoàn toàn vào đồng hồ của Android box, và tự đồng bộ
giờ/ký lại một lần nếu resolver trả clip demo.

Phiên bản `1.0.7` có bộ tải riêng của Phim Nét, giữ nguyên User-Agent và URL ký số khi
tải. File được lưu trong thư mục riêng của addon hoặc đường dẫn do người dùng chọn;
không gọi hay phụ thuộc VietmediaF.

Phiên bản `1.0.8` phát các file phim trực tiếp bằng InputStream FFmpeg Direct. Máy chủ
Phim Nét trả dữ liệu dạng chunked, không có Content-Length nên đầu đọc cURL của Kodi
coi phim là luồng không thể tua dù máy chủ có hỗ trợ byte-range. FFmpeg đọc đúng tổng
dung lượng từ Content-Range, nhờ đó thanh thời gian và thao tác tua hoạt động lại.

Phiên bản `1.0.9` buộc dùng `inputstream.ffmpeg` tích hợp sẵn trong Kodi cho file phim.
Cách này không phụ thuộc addon nhị phân InputStream FFmpeg Direct và tránh trường hợp
Kodi âm thầm quay về đầu đọc cURL khi addon đó chưa được bật hoặc không tương thích.

Phiên bản `1.0.10` cập nhật API/resolver động theo Phim4K ATV 2.6.5. Link đã ký
được chuyển ngay cho Kodi thay vì chờ GET Range trước khi phát; việc này loại bỏ
timeout giả làm Kodi quay về CDN cũ và báo lỗi nguồn phát.

Phiên bản `1.0.11` bỏ ép giá trị `inputstream.ffmpeg` không phải addon trên Kodi 21.
Kodi tự chọn đầu đọc gốc cho URL đã ký, tránh lỗi chờ 30 giây rồi
`OpenDemuxStream - Error creating demuxer`.

Phiên bản `1.0.12` khôi phục tua cho file MP4/MKV bằng đúng addon nhị phân
`inputstream.ffmpegdirect`, buộc chế độ mở FFmpeg cho VOD và khai báo dependency
Kodi 21. Header `Accept-Encoding: identity` giữ byte offset ổn định qua proxy.
Luồng HLS vẫn dùng đầu đọc mặc định. Cách này giữ bản vá phát video 1.0.11 nhưng
không còn ép tên inputstream không tồn tại.

Phiên bản `1.0.13` khắc phục phim tự tắt giữa chừng khi worker Railway đóng kết
nối HTTP sớm. URL phát MP4/MKV truyền thêm các tùy chọn FFmpeg `reconnect`,
`reconnect_at_eof`, `reconnect_streamed`, `reconnect_delay_max=15` và
`seekable=1`. Khi gặp EOF trước cuối phim, FFmpeg Direct nối lại bằng byte-range
từ vị trí hiện tại thay vì để Kodi đóng trình phát. Header `Connection:
keep-alive` được thêm nhưng không thay đổi resolver, giao diện hoặc nguồn phim.

Phiên bản `1.0.14` bỏ các tên miền API/CDN cũ đã hỏng, đồng bộ cấu hình động với
Phim4K TV và lưu cấu hình tốt gần nhất để dùng khi máy chủ cấu hình tạm gián đoạn.
Addon đồng thời đăng ký kho cập nhật `TNB88/phimnet.kodi`; từ bản này trở đi Kodi
có thể kiểm tra và tự cài bản mới trực tiếp trong mục cập nhật addon.
