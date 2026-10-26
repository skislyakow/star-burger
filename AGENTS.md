# Star Burger — шпаргалка по настройке и деплою

Документ для воспроизведения окружения на любой машине. Пароли/токены здесь не дублируются — они лежат в `.env` (в корне проекта локально и в `/opt/star-burger/.env` на сервере).

## Стек

- **Backend**: Django 5.2, Python (dev: 3.13 Windows, prod: 3.12 Ubuntu), зависимости через `uv` (`pyproject.toml` + `uv.lock`)
- **БД**: PostgreSQL 16 (переехали со SQLite командами `dumpdata`/`loaddata`)
- **Фронтенд**: Node.js + Parcel 2 (`npm ci`, сборка в `bundles/`)
- **Мониторинг**: Rollbar (middleware подключается автоматически, если задан `ROLLBAR_TOKEN`)
- **Качество кода**: `ruff` (линт + формат), `djlint` (шаблоны), `mypy` + `django-stubs` — всё прогоняется через `pre-commit`
- **Прод**: nginx (80/443) → gunicorn `127.0.0.1:8002` под systemd

---

## Локальная разработка (Windows)

### 1. Python-зависимости

Ставятся через [uv](https://docs.astral.sh/uv/) — он сам создаёт `.venv` и ставит точные версии из `uv.lock`:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"   # один раз, если uv ещё нет
uv sync
```

Требуется Python >= 3.12 (`requires-python` в `pyproject.toml`); если подходящего интерпретатора нет, uv скачает его сам.

Грабли: `requirements.txt` больше нет — не возвращайте его. Зависимости правим в `pyproject.toml` командой `uv add <пакет>` (она же обновляет `uv.lock`), а не вручную; иначе `uv sync` перезапишет окружение по старому lock-файлу. `uv.lock` коммитится.

Пакеты делятся на два набора: основные (`[project].dependencies` — Django, DRF, psycopg, gunicorn и т.д.) и `dev` (`[dependency-groups]` — `django-debug-toolbar`, `django-stubs`). `uv sync` ставит оба, `uv sync --no-dev` — только прод-набор. Поэтому `debug_toolbar` подключается в `settings.py` условно: `if DEBUG: INSTALLED_APPS.append("debug_toolbar")` — на проде он не установлен.

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
uv run python -X utf8 manage.py dumpdata --natural-foreign --natural-primary `
  -e contenttypes -e auth.permission --indent 2 -o data.json

# 2) Добавить DATABASE_URL в .env (шаг 3)

# 3) Схема в пустом Postgres, затем данные:
uv run python manage.py migrate
uv run python manage.py loaddata data.json

# 4) Убрать sqlite (сайт должен жить без него):
Rename-Item db.sqlite3 db.sqlite3.bak
```

Эталонные счётчики после переноса: users=1, products=6, orders=15, orderitem=15, restaurants=3, restaurantmenuitem=18, productcategory=2, places=11.

`data.json` содержит хэши паролей — **не коммитить** (добавлен в `.gitignore`).

### 5. Линтеры и pre-commit

В dev-группе лежат `ruff`, `djlint`, `mypy` (+ `django-stubs`) и сам `pre-commit`. Настройки — в `pyproject.toml`:

- `[tool.ruff]` — линт и формат Python, `line-length = 79` (стиль исходного курса), миграции исключены через `extend-exclude = ["*/migrations/*"]`;
- `[tool.djlint]` — шаблоны, `profile = "django"`, `indent = 2`, игнорируются `H021/H036/H050` (инлайн-стили SVG, `<br>` для отступов, устаревший `<center>` — унаследованная вёрстка);
- `[tool.mypy]` + `[tool.django-stubs]` — типы с плагином django-stubs. Без `mypy_path = "."` и `explicit_package_bases = true` mypy не понимает `from . import settings` в `star_burger/urls.py`.

Установка git-хука (один раз в каждом клоне — `.git/hooks/` не коммитится):

```powershell
uv run pre-commit install
uv run pre-commit run --all-files   # разовый прогон по всему проекту
```

Грабли, на которых горели:

- в `args` хуков `ruff-check`/`ruff-format` нельзя дублировать `--force-exclude`: ruff-pre-commit передаёт его сам, и ruff падает с `the argument '--force-exclude' cannot be used multiple times`;
- `mypy` подключён как `repo: local` с `entry: uv run mypy`, а не через `mirrors-mypy`: плагину нужен django-stubs из окружения проекта, а изолированное env pre-commit его не видит;
- mypy импортирует `star_burger/settings.py`, поэтому без `.env` в корне он падает так же, как `runserver`;
- корневой `__init__.py` пришлось удалить: из-за него mypy считал корень репозитория пакетом и ругался `star-burger contains __init__.py but is not a valid Python package name`;
- `pre-commit run --all-files` смотрит только на *отслеживаемые* git файлы — новые, ещё не добавленные в индекс, он не проверяет;
- на сервере хуки не нужны: там `uv sync --no-dev`, а `.git/hooks` в `/opt/star-burger` не устанавливаются.

### 6. Запуск dev-версии

```powershell
uv run python manage.py runserver          # терминал 1
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

### 0. uv на сервере

Зависимости Python ставит `uv` — тот же, что локально. Один раз:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh    # бинарник в /root/.local/bin/uv
```

`uv sync --frozen --no-dev` в каталоге `/opt/star-burger` ставит ровно те версии, что записаны в `uv.lock`, создаёт/переиспользует `.venv` и **не трогает lock-файл** (флаг `--frozen`; без него uv попытается перерешать зависимости на сервере). `--no-dev` пропускает `django-debug-toolbar` и `django-stubs` — на проде они не нужны, а `settings.py` подключает панель только при `DEBUG=True`.

Грабли: `gunicorn` не был ни в `requirements.txt`, ни в `pyproject.toml` — он когда-то ставился в серверный `.venv` руками. `uv sync` вычищает из окружения всё, чего нет в lock-файле, поэтому gunicorn **обязан** быть в `[project].dependencies` (сейчас там есть). Если после перехода на uv systemd падает с `No such file or directory` на `.venv/bin/gunicorn` — значит его вычистили: верните в `pyproject.toml` и повторите `uv sync`.

`pip` в окружении от uv не нужен: зависимости ставятся только из lock-файла. В серверном `.venv` старый `pip` остался (uv не трогает «служебные» пакеты унаследованного окружения — `pip`, `setuptools`, `wheel`), но `.venv/bin/pip install …` бессмыслен: ближайший `uv sync` вычистит всё, чего нет в lock-файле. Ставить пакеты нужно через `uv add` локально и деплоить обновлённый `uv.lock`.

### 1. Деплой: `/root/deploy_star_burger.sh`

Рутина обновления автоматизирована bash-скриптом в домашней папке root'а (в репозиторий не входит — сервероспецифичен). Порядок действий при релизе: коммит → push → `ssh vds` → `~/deploy_star_burger.sh`.

Скрипт переведён на uv 26.10.2026: шаг `pip install` заменён на `uv sync --frozen --no-dev`, добавлен `export PATH="$HOME/.local/bin:$PATH"` (иначе `uv: command not found` в неинтерактивном шелле). Бэкап прежней версии — `/root/deploy_star_burger.sh.bak.20261026`.

```bash
#!/bin/bash

set -e

# uv ставится в /root/.local/bin и не попадает в PATH неинтерактивного шелла.
export PATH="$HOME/.local/bin:$PATH"

cd /opt/star-burger

echo "=== git pull ==="
git pull

echo "=== uv sync ==="
uv sync --frozen --no-dev

echo "=== npm ci ==="
npm ci --no-audit --no-fund

echo "=== parcel build ==="
./node_modules/.bin/parcel build bundles-src/index.js --dist-dir bundles --public-url="./"

echo "=== collectstatic ==="
.venv/bin/python manage.py collectstatic --noinput

echo "=== migrate ==="
.venv/bin/python manage.py migrate --noinput

echo "=== restart star-burger ==="
systemctl restart star-burger

echo "=== notify rollbar ==="
ROLLBAR_TOKEN=$(grep '^ROLLBAR_TOKEN=' .env | cut -d= -f2)
ROLLBAR_ENVIRONMENT=$(grep '^ROLLBAR_ENVIRONMENT=' .env | cut -d= -f2)
REVISION=$(git rev-parse HEAD)

curl -sS https://api.rollbar.com/api/1/deploy/ \
  -F access_token=$ROLLBAR_TOKEN \
  -F environment=$ROLLBAR_ENVIRONMENT \
  -F revision=$REVISION \
  -F local_username=root

echo

echo "Deploy OK!"
```

Ключевое: `set -e` роняет скрипт на первой же ошибке (до рестарта сервиса сайт не дойдёт — битая версия не выкатится); nginx при деплое не трогается; все команды линейные и копируются для ручного запуска. Уведомление Rollbar о деплое стоит в самом конце и уходит только после успешного рестарта (`set -e` гарантирует: упавший деплой не будет помечен как выкаченный). Токен берётся из `.env`, хэш коммита скрипт узнаёт сам через `git rev-parse HEAD` уже после `git pull`; ответ API `{"err":0,...}` = успех, запись появляется в Rollbar (лента Items + страница Deploys).

Грабли, на которых горели: путь к parcel — именно `./node_modules/.bin/parcel` (относительный, работает из-за `cd /opt/star-burger` выше). Без `./` bash ищет бинарник от корня ФС (`/node_modules/...`) и падает с `No such file or directory`.

### 2. systemd-юнит `/etc/systemd/system/star-burger.service`

```ini
[Unit]
Description=Star Burger Gunicorn Service
After=network.target postgresql.service
Requires=postgresql.service

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

`After=` + `Requires=` на `postgresql.service` гарантируют: при загрузке сервера база поднимется раньше сайта, а остановка Postgres останавливает и gunicorn (вместо работы с мёртвой БД). Проверка зависимостей: `systemctl list-dependencies star-burger.service`.

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

### 3.1. Автопродление сертификатов

Сертификаты Let's Encrypt живут 3 месяца. Продление автоматизировано своим таймером (штатный `certbot.timer` из пакета отключён, чтобы не было двух планировщиков):

- `/etc/systemd/system/certbot-renewal.timer` — `OnCalendar=weekly`, `Persistent=true`, `enabled`;
- `/etc/systemd/system/certbot-renewal.service` — oneshot: `certbot -q renew --no-random-sleep-on-renew`;
- хук `/etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh` (`systemctl reload nginx`, исполняемый) — срабатывает только при фактическом продлении и заставляет nginx подхватить новые файлы сертификатов.

Проверки: `systemctl list-timers | grep certbot-renewal` (ближайший запуск), `certbot renew --dry-run` (пробное продление через staging), ручной прогон `systemctl start certbot-renewal.service` — в `/var/log/letsencrypt/letsencrypt.log` появится «Certificate not yet due for renewal», а юнит останется в `inactive (dead)` — для oneshot это норма.

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
| `uv: command not found` | uv не в `PATH` у root'а: `ls /root/.local/bin/uv`, затем `source $HOME/.profile` или `/root/.local/bin/uv sync --frozen --no-dev` |
| `uv sync` падает с `Failed to resolve` | на сервере нет Python >= 3.12 или правлен `pyproject.toml` без обновления `uv.lock`; локально `uv lock`, закоммитить и деплоить снова (на сервере `--frozen` намеренно не даёт перерешать зависимости) |
| `No such file or directory` на `.venv/bin/gunicorn` | gunicorn вычищен из окружения, потому что пропал из `pyproject.toml`; вернуть в `[project].dependencies`, `uv lock`, задеплоить |
| Ошибки SSL в браузере | сертификат чужого домена = vhost без своего 443-блока/сертификата; выпустить certbot'ом |

Финальная проверка продакшена:

```sh
curl -sI https://star-burger.kislyakov.pro | head -1     # HTTP/2 200
curl -s https://star-burger.kislyakov.pro | grep -o "<title>[^<]*</title>"   # <title>Star Burger</title>
```
