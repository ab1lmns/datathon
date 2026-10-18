# Прямой HTTPS на текущем GPU-сервере

DNS: A `forte.makquiz.site` → `95.3.33.46`, **DNS only**.
Публичный TCP 14901 проброшен Vast в контейнерный TCP 10100.
Отдельный supervisor `forte_direct_tls` запускает Caddy с admin off;
управляющий Caddy Vast не изменяется. TLS завершается на нашем сервере,
затем запрос идёт в gateway 127.0.0.1:7860. X-API-Key проверяется приложением.

URL: `https://forte.makquiz.site:14901`, Swagger: `/docs`.
Не убирать порт из URL. Доступ зависит от сохранения аренды, IP и проброса порта.

Сертификат Let's Encrypt выдан через DNS-01, истекает 2027-01-16.
**Автопродление не настроено.** До этой даты повторить на сервере:

```sh
/workspace/forte-tls-env/bin/certbot certonly --manual --preferred-challenges dns \
  --config-dir /workspace/forte-tls/config \
  --work-dir /workspace/forte-tls/work --logs-dir /workspace/forte-tls/logs \
  -d forte.makquiz.site
```

Добавить предложенную TXT-запись в DNS, проверить её, продолжить certbot.
После успешного продления: `supervisorctl restart forte_direct_tls`.
Ключ сертификата и ACME-аккаунт хранятся только на сервере, не коммитить.

Конфиги рядом фиксируют текущие пути сервера; перед переносом заменить пути
и проверить доступные порты. Это не автоматическая установка на любом хосте.
