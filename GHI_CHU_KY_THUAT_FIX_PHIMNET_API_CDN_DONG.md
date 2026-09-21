# GHI CHÚ KỸ THUẬT: FIX PHIM NÉT / PHIM4K API-CDN ĐỘNG

Ngày hoàn tất: 22/09/2026  
Phạm vi: Kodi `plugin.video.phimnet` và CloudStream `PhimNetProvider.cs3`  
Không sửa giao diện hoặc hành vi của APK Phim4K TV trong đợt này.

## 1. Hiện tượng ban đầu

- Plugin Kodi Phim Nét mở danh mục bị xoay lâu hoặc báo lỗi.
- CloudStream `PhimNetProvider.cs3` cũng không vào được nội dung/phát phim.
- Phim4K TV vẫn xem bình thường, chứng tỏ nguồn phim chưa chết hoàn toàn.
- Endpoint cũ `apip4k.dpdns.org` trả HTTP 403.
- Resolver cũ `sv1.p4k.dpdns.org` không còn phân giải DNS.

## 2. Nguyên nhân

Plugin Kodi và CloudStream đang ghi cứng API/CDN cũ. Phim4K TV không dùng cố định
hai địa chỉ này mà tải cấu hình mã hóa từ máy chủ cấu hình động, nên app TV vẫn
hoạt động khi nhà cung cấp đổi tên miền.

Ngoài ra, CloudStream có một lỗi trong cách tạo `signingSecret`: phần tiền tố bị
ghép bằng ngày UTC thay vì bí mật HMAC gốc. API danh sách có thể chạy nhưng bước
ký resolver để phát video sẽ sai.

## 3. Cấu hình động hiện tại

Thứ tự ưu tiên:

1. Máy chủ cấu hình của Phim4K:
   `https://ltv.cryboiz.workers.dev/api/add`
2. Cấu hình dự phòng công khai:
   `https://raw.githubusercontent.com/TNB88/phimnet.kodi/main/config.json`
3. Kodi dùng bản cấu hình tốt gần nhất trong profile addon.
4. Nếu cả ba không có, dùng giá trị mặc định được đóng trong plugin.

Giá trị tại thời điểm kiểm tra:

- API host: `aa.maclife.dpdns.org`
- Resolver/CDN host: `sv1.maclife.dpdns.org`
- API base: `https://aa.maclife.dpdns.org/rest-api/v130/`

Lưu ý quan trọng: worker cấu hình có thể trả HTTP 403 với User-Agent Python mặc
định. Plugin phải gửi User-Agent dạng Android/Dalvik. Payload của worker dùng
AES-256-GCM; mã nguồn tự giải mã tương thích Phim4K TV. Không ghi API key/token
thật vào file ghi chú hay `config.json` công khai.

## 4. Cách ký link phát

Giữ đúng thuật toán của APK:

1. Lấy ngày UTC dạng `yyyyMMdd`.
2. Băm SHA-256 bí mật HMAC để tạo khóa AES.
3. Nonce là 12 byte đầu của SHA-256 chuỗi `iv:<bí mật HMAC>`.
4. AES-GCM mã hóa chuỗi `<bí mật HMAC>:<ngày UTC>`.
5. `signingSecret` đúng là `<bí mật HMAC>:<ciphertext+tag dạng hex>`.
6. Tạo timestamp Unix, che timestamp bằng HMAC `otp-ts-mask`.
7. Token resolver là HMAC-SHA256 của `<file-id>:<timestamp>`.
8. Gọi resolver động và lấy URL HTTPS cuối cùng để phát.

Điểm sửa quan trọng của CloudStream: không được dùng ngày UTC làm tiền tố ở bước
5. Tiền tố phải là bí mật HMAC gốc giống APK và plugin Kodi.

## 5. Thay đổi trong Kodi 1.0.14

Mã nguồn làm việc:

- `C:\fix plugin phim net\plugin.video.phimnet`
- Bản quản lý Git: `C:\Users\Admin\Documents\GitHub\phimnet.kodi`

Các thay đổi:

- Thêm AES-GCM decrypt thuần Python, không cần cài `cryptography`/PyCryptodome.
- Tự tải và kiểm tra cấu hình API/CDN động.
- Chỉ nhận hostname hợp lệ; bỏ qua dữ liệu cấu hình sai.
- Lưu cấu hình tốt gần nhất ở `special://profile/addon_data/plugin.video.phimnet/dynamic_config.json`.
- API key động chỉ được nhận khi đúng định dạng; nếu thiếu thì dùng fallback sẵn có.
- Giữ nguyên thuật toán ký resolver, lựa chọn bản phim, tải xuống và cách phát.
- Nâng addon từ `1.0.13` lên `1.0.14`.
- Đăng ký kho cập nhật online `TNB88/phimnet.kodi`.

File cài trực tiếp:

`plugin.video.phimnet/plugin.video.phimnet-1.0.14.zip`

## 6. Kho tự cập nhật Kodi

Repository GitHub:

`https://github.com/TNB88/phimnet.kodi`

Các file bắt buộc:

- `addons.xml`: danh sách addon và phiên bản.
- `addons.xml.md5`: MD5 chính xác của `addons.xml`.
- `repository.phimnet/repository.phimnet-1.0.0.zip`: gói cài kho.
- `plugin.video.phimnet/plugin.video.phimnet-<version>.zip`: gói plugin.

Người dùng chỉ cần cài `repository.phimnet-1.0.0.zip` một lần, cài Phim Nét từ
repository và bật `Install updates automatically`. Các bản sau phải tăng version,
tạo ZIP mới, cập nhật `addons.xml`, rồi tạo lại `addons.xml.md5` trước khi push.

Commit phát hành đầu tiên của repository: `70e83c6`.

## 7. Thay đổi trong CloudStream PhimNetProvider v7

Mã nguồn làm việc:

`C:\Users\Admin\CXXX\PhimNetProvider`

File build:

`C:\Users\Admin\CXXX\PhimNetProvider\build\PhimNetProvider.cs3`

File phát hành:

`C:\Users\Admin\Documents\GitHub\FSHARE\PhimNetProvider.cs3`

Các thay đổi:

- Nâng manifest provider từ version `6` lên `7`.
- Dùng cùng cấu hình API/CDN động và cấu hình GitHub dự phòng.
- Sửa tiền tố `signingSecret` cho đúng APK.
- Khi resolver lỗi, tải lại cấu hình động và thử thêm một lần.
- `plugins.json` đã cập nhật version, file size và SHA-256.

Thông tin file đã phát hành:

- Kích thước: `43356` byte.
- SHA-256: `0f5c14ca380f6922a2e45c9d49cfc2e6b08c29335e783ada01c7646fccdcba5b`.
- Commit FSHARE: `1068364`.

## 8. Kiểm thử đã thực hiện

- Python compile toàn bộ mã Kodi: đạt.
- AES-GCM encrypt/decrypt round-trip: đạt.
- Giải mã payload worker cấu hình: đạt.
- API danh sách trả 24 phim ở trang đầu: đạt.
- Lấy chi tiết phim ID `17927`: đạt.
- Lấy được một bản phim và ký resolver: đạt.
- Resolver trả URL HTTPS trên Railway: đạt.
- Kiểm tra cấu trúc ZIP: mọi file nằm đúng thư mục gốc của addon.
- Kiểm tra XML/JSON và MD5 repository: đạt.
- Tải lại toàn bộ file từ GitHub raw: HTTP 200.
- So khớp kích thước/hash của `PhimNetProvider.cs3`: đạt.
- Hai working tree Git sạch và đồng bộ `origin/main` sau khi push.

## 9. Quy trình cập nhật lần sau

### Kodi

1. Sửa trong `C:\fix plugin phim net\plugin.video.phimnet`.
2. Tăng version trong `addon.xml`.
3. Chạy compile/test API, chi tiết phim và resolver.
4. Chép source vào repo `phimnet.kodi`.
5. Tạo ZIP có thư mục gốc `plugin.video.phimnet/`.
6. Cập nhật addon tương ứng trong `addons.xml`.
7. Tính lại `addons.xml.md5` sau cùng.
8. Commit, push và kiểm tra các URL raw trả HTTP 200.

### CloudStream

1. Sửa project `C:\Users\Admin\CXXX\PhimNetProvider`.
2. Tăng `version` trong `build.gradle.kts`.
3. Build bằng `gradlew :PhimNetProvider:make` tại `C:\Users\Admin\CXXX`.
4. Kiểm tra `manifest.json` bên trong `.cs3`.
5. Chép `.cs3` sang repo FSHARE.
6. Cập nhật đúng `version`, `fileSize`, `fileHash` trong `plugins.json`.
7. Commit, push và tải bản raw về kiểm tra hash.

## 10. Không được làm mất khi sửa tiếp

- Không quay lại các domain `p4k.dpdns.org` cũ.
- Không bỏ fallback GitHub và cache cấu hình Kodi.
- Không ghi token/API key thật vào repository công khai hoặc ghi chú.
- Không đổi thuật toán ký nếu chưa đối chiếu lại APK đang chạy.
- Không ghi đè các bản vá phát/tua/reconnect đã có từ Kodi 1.0.11–1.0.13.
- Không phát hành nếu ZIP sai thư mục gốc, `addons.xml.md5` chưa cập nhật hoặc
  `plugins.json` không khớp hash/kích thước file thực tế.
