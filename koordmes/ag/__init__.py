"""Çok kullanıcılı çalışma: bir bilgisayar veritabanını ağda paylaşır (sunucu), diğerleri ona bağlanır.

Sunucu, programın içinde ayrı bir iş parçacığında çalışan şifreli (TLS) ve parolalı bir HTTP hizmetidir.
İstemciler veritabanı komutlarını sunucuya gönderir; sunucu her istemci için ayrı bir SQLite bağlantısı
tutar, böylece işlem (transaction) mantığı yerel çalışmayla aynıdır. Bir bilgisayarda yapılan değişiklik
diğer bilgisayarlara anında bildirilir ve açık ekranlar yenilenir.
"""
