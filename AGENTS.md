# Star Burger — шпаргалка по настройке и деплою

Документ для воспроизведения окружения на любой машине. Пароли/токены здесь не дублируются — они лежат в `.env` (в корне проекта локально и в `/opt/star-burger/.env` на сервере).

## Стек

- **Backend**: Django 5.2, Python (dev: 3.10 Windows, prod: 3.12 Ubuntu)
- **БД**: PostgreSQL 16 (переехали со SQLite командами `dumpdata`/`loaddata`)
- **Фронтенд**: Node.js + Parcel 2 (`npm ci`, сборка в `bundles/`)
- **Мониторинг**: Rollbar (middleware подключается автоматически, если задан `ROLLBAR_TOKEN`)
- **Прод**: nginx (80/443) → gunicorn `127.0.0.1:8002` под systemd

---

## Локальная разработка (Windows)

### 1. Python-зависимости

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Грабли: в `requirements.txt` только двойное `==` (`dj-database-url=3*` — невалидно, нужно `dj-database-url==3.*`).

### 2. PostgreSQL через Docker

Docker Desktop должен быть **запущен** (иначе `failed to connect to the docker API ... dockerDesktopLinuxEngine`). Версия 16 — та же мажорная, что на сервере:

```powershell
docker run -d --name starburger-pg `
  -e POSTGRES_USER=starburger `
  -e POSTGRES_PASSWORD=<пароль_локальной_бд> `
  -e POSTGRES_DB=starburger `
  -p 5432:5432 postgres:16
```

Проверка: `docker ps` → контейнер `starburger-pg` в статусе `Up`.

### 3. Файл `.env` в корне проекта

```ini
SECRET_KEY=<ключ Django>
YANDEX_GEOCODER_API_KEY=<ключ геокодера>
ALLOWED_HOSTS=127.0.0.1,localhost
DEBUG=True
DATABASE_URL=postgres://starburger:<пароль>@127.0.0.1:5432/starburger
ROLLBAR_TOKEN=<токен Rollbar>
ROLLBAR_ENVIRONMENT=development
```

Важно: пока `DATABASE_URL` нет, Django работает со старым `db.sqlite3` (дефолт в `settings.py`). Это используется при переносе данных.

### 4. Перенос данных SQLite → Postgres (порядок критичен!)

```powershell
# 1) Выгрузка ИЗ sqlite — строго ДО добавления DATABASE_URL в .env.
#    Флаг -X utf8 обязателен на Windows: иначе файл пишется в cp1251,
#    и loaddata потом падает с UnicodeDecodeError.
python -X utf8 manage.py dumpdata --natural-foreign --natural-primary `
  -e contenttypes -e auth.permission --indent 2 -o data.json

# 2) Добавить DATABASE_URL в .env (шаг 3)

# 3) Схема в пустом Postgres, затем данные:
python manage.py migrate
python manage.py loaddata data.json

# 4) Убрать sqlite (сайт должен жить без него):
Rename-Item db.sqlite3 db.sqlite3.bak
```

Эталонные счётчики после переноса: users=1, products=6, orders=15, orderitem=15, restaurants=3, restaurantmenuitem=18, productcategory=2, places=11.

`data.json` содержит хэши паролей — **не коммитить** (добавлен в `.gitignore`).

### 5. Запуск dev-версии

```powershell
python manage.py runserver          # терминал 1
.\node_modules\.bin\parcel watch bundles-src/index.js --dist-dir bundles --public-url="./"   # терминал 2 (если меняешь фронт)
```

---

## Фронтенд (prod-сборка)

```sh
npm ci
./node_modules/.bin/parcel build bundles-src/index.js --dist-dir bundles --public-url="./"
```

Каталог `bundles/` в git не входит — собирать на каждой машине. Результат нужен `collectstatic`.

---

## Сервер (Ubuntu 24.04, alias `ssh vds`, IP 132.243.121.192)

Код: `/opt/star-burger/`. Домен: `star-burger.kislyakov.pro` (A-запись → IP, HTTPS через certbot).

На VDS живут ещё два сайта: `kislyakov.pro`→:8000 (dossier), `beauty.kislyakov.pro`→:8001 (beauty). Порт 80 занят nginx — **его не останавливать**, новый сайт вешается отдельным vhost'ом на порт 8002.

### 1. Разовое обновление кода на сервере

```sh
cd /opt/star-burger
git pull
.venv/bin/pip install -r requirements.txt      # venv называется .venv (с точкой)!
npm ci
./node_modules/.bin/parcel build bundles-src/index.js --dist-dir bundles --public-url="./"
.venv/bin/python manage.py collectstatic --noinput   # STATIC_ROOT = staticfiles/
.venv/bin/python manage.py migrate
systemctl restart star-burger
```

### 2. systemd-юнит `/etc/systemd/system/star-burger.service`

```ini
[Unit]
Description=Star Burger Gunicorn Service
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/star-burger
EnvironmentFile=/opt/star-burger/.env
ExecStart=/opt/star-burger/.venv/bin/gunicorn star_burger.wsgi:application \
    --bind 127.0.0.1:8002 \
    --workers 3 \
    --timeout 120 \
    --access-logfile /var/log/star-burger/access.log \
    --error-logfile /var/log/star-burger/error.log
ExecReload=/bin/kill -s HUP $MAINPID
ExecStop=/bin/kill -s TERM $MAINPID
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Грабли, на которых уже горели:
- путь именно **`.venv`** (с точкой), а не `venv`;
- каталог `/var/log/star-burger/` должен существовать **до** первого старта (`mkdir -p /var/log/star-burger`), иначе gunicorn падает с `error.log isn't writable` и сервис крутится в рестарт-цикле;
- после правки юнита всегда `systemctl daemon-reload`.

Запуск: `systemctl enable --now star-burger`.

### 3. nginx-vhost `/etc/nginx/sites-available/star-burger.kislyakov.pro`

После certbot выглядит так (443-блок и редирект дописывает certbot сам):

```nginx
server {
    server_name star-burger.kislyakov.pro;

    client_max_body_size 20M;

    location /static/ {
        alias /opt/star-burger/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /opt/star-burger/media/;
        expires 30d;
    }

    location / {
        proxy_pass http://127.0.0.1:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_read_timeout 120s;
    }

    listen 443 ssl; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/star-burger.kislyakov.pro/fullchain.pem; # managed by Certbot
    ssl_certificate_key /etc/letsencrypt/live/star-burger.kislyakov.pro/privkey.pem; # managed by Certbot
    include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot
}

server {
    if ($host = star-burger.kislyakov.pro) {
        return 301 https://$host$request_uri;
    } # managed by Certbot

    listen 80;
    listen [::]:80;
    server_name star-burger.kislyakov.pro;
}
```

Активация нового vhost:

```sh
ln -s /etc/nginx/sites-available/star-burger.kislyakov.pro /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d star-burger.kislyakov.pro   # выпуск сертификата (нужен рабочий DNS)
```

### 4. PostgreSQL на сервере

```sh
apt install -y postgresql
sudo -u postgres psql -c "CREATE USER starburger WITH PASSWORD '<СЛУЧАЙНЫЙ_НЕ_ДЕФОЛТНЫЙ_ПАРОЛЬ>';"
sudo -u postgres psql -c "CREATE DATABASE starburger OWNER starburger;"
```

Требование задания: пароль ≠ дефолтному из репозитория. Генерация: `openssl rand -base64 24`. Живёт только в `/opt/star-burger/.env`:

```ini
DEBUG=False
ALLOWED_HOSTS=star-burger.kislyakov.pro,127.0.0.1,localhost
DATABASE_URL=postgres://starburger:<пароль>@127.0.0.1:5432/starburger
ROLLBAR_ENVIRONMENT=production
```

Перенос данных на сервере (данные брать из **серверного** sqlite — там живые заказы):

```sh
systemctl stop star-burger                                  # заморозить запись
.venv/bin/python manage.py dumpdata --natural-foreign --natural-primary \
  -e contenttypes -e auth.permission -o data.json           # Linux уже в UTF-8, флаг не нужен
# добавить DATABASE_URL в .env
.venv/bin/python manage.py migrate
.venv/bin/python manage.py loaddata data.json
mv db.sqlite3 db.sqlite3.backup                             # сайт обязан работать без него
systemctl start star-burger
```

### 5. Диагностика проблем

| Симптом | Причина / проверка |
|---|---|
| 502 Bad Gateway | upstream не слушает: `systemctl status star-burger`, `ss -tlnp \| grep 8002`, `journalctl -u star-burger -n 50` |
| Сервис в рестарт-цикле | смотреть `journalctl`; типовые причины: нет каталога логов, неверный путь к venv |
| `That port is already in use` | порт занят другим сайтом; свободный диапазон уточнить `ss -tlnp` |
| npm `Killed` | не хватило RAM (на VDS 1.8G); добавить swap или собрать бандлы локально и залить |
| Ошибки SSL в браузере | сертификат чужого домена = vhost без своего 443-блока/сертификата; выпустить certbot'ом |

Финальная проверка продакшена:

```sh
curl -sI https://star-burger.kislyakov.pro | head -1     # HTTP/2 200
curl -s https://star-burger.kislyakov.pro | grep -o "<title>[^<]*</title>"   # <title>Star Burger</title>
```
