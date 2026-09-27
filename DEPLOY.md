# Serverga chiqarish

Ubuntu 22.04+ uchun. Taxminan 40 daqiqa.

## 1. Server tayyorlash

```bash
sudo apt update && sudo apt install -y python3-venv python3-pip postgresql nginx
sudo -u postgres psql -c "CREATE DATABASE bogcha;"
sudo -u postgres psql -c "CREATE USER bogcha WITH PASSWORD 'KUCHLI_PAROL';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE bogcha TO bogcha;"
sudo -u postgres psql -d bogcha -c "GRANT ALL ON SCHEMA public TO bogcha;"
```

## 2. Loyihani joylash

```bash
sudo mkdir -p /srv/bogcha && sudo chown $USER /srv/bogcha
cd /srv/bogcha
# kodni ko'chirish (git clone yoki scp)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt gunicorn
```

## 3. .env

```bash
cp .env.example .env
python3 -c "import secrets;print(secrets.token_urlsafe(50))"   # SECRET_KEY uchun
nano .env
```

`DJANGO_DEBUG=False`, `ALLOWED_HOSTS` ni aniq domenga va `DB_SSLMODE=require` ni
o'rnating. PostgreSQL rekvizitlarining barchasi majburiy.

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py createsuperuser   # yoki: manage.py seed (demo)
```

Birinchi kirishdan keyin Sozlamalar → moliyaviy siyosat, tariflar,
kalendar (bayramlar) va rollarni to'ldiring. Oshxona ishlatilsa, tegishli
rollarga `view_dailymenu`, `add_dailymenu`, `change_dailymenu` va
`add_stockmove` permissionlarini bering; masalliqlar, taom normalari va
boshlang'ich ombor kirimini taomnoma tasdiqlashdan oldin kiriting.

## 4. Gunicorn

`/etc/systemd/system/bogcha.service`:

```ini
[Unit]
Description=Bogcha
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/srv/bogcha
ExecStart=/srv/bogcha/.venv/bin/gunicorn config.wsgi:application \
  --workers 3 --bind 127.0.0.1:8001 --timeout 60
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo chown -R www-data:www-data /srv/bogcha
sudo systemctl enable --now bogcha
```

### Celery worker va beat

`/etc/systemd/system/bogcha-celery.service`:

```ini
[Unit]
Description=Bogcha Celery Worker
After=network.target redis-server.service postgresql.service
[Service]
User=www-data
Group=www-data
WorkingDirectory=/srv/bogcha
EnvironmentFile=/srv/bogcha/.env
ExecStart=/srv/bogcha/.venv/bin/celery -A config worker --loglevel=INFO
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/bogcha-celery-beat.service`:

```ini
[Unit]
Description=Bogcha Celery Beat
After=network.target redis-server.service postgresql.service
[Service]
User=www-data
Group=www-data
WorkingDirectory=/srv/bogcha
EnvironmentFile=/srv/bogcha/.env
ExecStart=/srv/bogcha/.venv/bin/celery -A config beat --loglevel=INFO
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bogcha-celery bogcha-celery-beat
```

`https://DOMEN/health/` manzilini UptimeRobot yoki boshqa tashqi monitoringga
5 daqiqalik interval bilan ulang. HTTP 503 database, Redis yoki Celery heartbeat
nosozligini bildiradi. Tashqi monitor Telegram ogohlantirishini yuborishi kerak;
Celery o'zi to'xtaganida o'zining xatosi haqida xabar bera olmaydi.

Sentry ishlatish uchun `.env`dagi `SENTRY_DSN`ni to'ldiring. Maxfiy shaxsiy
ma'lumotlar yuborilmasligi uchun `send_default_pii=False` o'rnatilgan.

## 5. Nginx va SSL

`/etc/nginx/sites-available/bogcha`:

```nginx
server {
    listen 80;
    server_name bogcha.uz www.bogcha.uz;
    client_max_body_size 10M;

    location /static/ { alias /srv/bogcha/staticfiles/; expires 30d; }

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/bogcha /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d bogcha.uz -d www.bogcha.uz
```

## 6. Zaxira nusxa (majburiy)

`/srv/bogcha/backup.sh`:

```bash
#!/bin/bash
set -e
D=/srv/backups && mkdir -p $D
export PGPASSWORD='KUCHLI_PAROL'
pg_dump -h 127.0.0.1 -U bogcha bogcha | gzip > $D/bogcha-$(date +%F-%H%M).sql.gz
find $D -name "bogcha-*.sql.gz" -mtime +30 -delete
# Boshqa serverga ko'chirish (ixtiyoriy, lekin juda tavsiya etiladi):
# rsync -a $D/ backup@boshqa-server:/backups/bogcha/
```

```bash
chmod +x /srv/bogcha/backup.sh
sudo crontab -e
```

```cron
30 2 * * * /srv/bogcha/backup.sh >> /var/log/bogcha-backup.log 2>&1
0 6 * * * cd /srv/bogcha && .venv/bin/python manage.py run_billing >> /var/log/bogcha-billing.log 2>&1
```

Ikkinchi qator — avtomatik invoys generatsiyasi. Har kuni ishga tushadi,
lekin faqat siyosatdagi `invoice_generation_day` kelganda invoys chiqaradi.

**Zaxiradan tiklashni bir marta sinab ko'ring:**

```bash
gunzip -c /srv/backups/bogcha-XXXX.sql.gz | psql -h 127.0.0.1 -U bogcha bogcha_test
```

Sinamagan zaxira — zaxira emas.

## 7. Chiqarishdan oldingi tekshiruv

```bash
.venv/bin/python manage.py check --deploy
.venv/bin/python -m pytest
```

- [ ] `DJANGO_DEBUG=False`
- [ ] `SECRET_KEY` tasodifiy va faqat `.env` da
- [ ] `ALLOWED_HOSTS` aniq domen (`*` emas)
- [ ] HTTPS ishlaydi, HTTP redirect qiladi
- [ ] Zaxira nusxa cron'da va tiklash sinalgan
- [ ] `seed` bilan yaratilgan demo hisoblar o'chirilgan
- [ ] Barcha rollar uchun ruxsatlar tekshirilgan
- [ ] Kalendarga bayramlar kiritilgan
- [ ] Tariflar va chegirmalar to'g'ri
- [ ] Oshxona permissionlari, masalliq normalari va boshlang'ich qoldiq to'g'ri

## 8. Birinchi oy

Bir guruh bilan parallel ishlating: buxgalter o'z usulida ham hisoblasin,
oy oxirida ikkala raqamni solishtiring. Farq chiqsa — sabab topilmaguncha
qolgan guruhlarga tarqatmang.
