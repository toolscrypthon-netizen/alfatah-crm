# Deploying to the VPS

The CRM runs as two Docker containers (the app and its own PostgreSQL database) next to whatever
else is on the server. The app listens only on `127.0.0.1:8010`; the web server already on the VPS
forwards `office.alfatah-marketing.com` to it.

## 1. Point the subdomain at the VPS (Cloudflare)

In Cloudflare → your domain → **DNS** → **Add record**: type `A`, name `office`, IPv4 = the VPS's
public IP, proxy status **Proxied** (orange cloud).

Then **SSL/TLS → Overview** → set encryption mode to **Full (strict)**.

## 2. Install Docker (skip if already installed)

```bash
curl -fsSL https://get.docker.com | sudo sh
```

## 3. Get the code and configure it

```bash
sudo mkdir -p /opt/alfatah-crm && sudo chown $USER /opt/alfatah-crm
git clone <your repo URL> /opt/alfatah-crm
cd /opt/alfatah-crm
cp .env.example .env
nano .env
```

Fill in `.env`. Generate each secret with `openssl rand -hex 32` (letters and digits only, so the database URL stays valid). If port 8010 is already used
by your other app, change `CRM_PORT`.

## 4. Start it

```bash
docker compose up -d --build
docker compose exec web python manage.py seed_cities
docker compose exec web python manage.py createsuperuser
```

## 5. Forward the subdomain to it

**If the VPS uses Nginx**, create `/etc/nginx/sites-available/office.alfatah-marketing.com`:

```nginx
server {
    listen 80;
    listen 443 ssl;
    server_name office.alfatah-marketing.com;

    # Cloudflare Origin Certificate (Cloudflare → SSL/TLS → Origin Server → Create certificate)
    ssl_certificate     /etc/ssl/cloudflare/alfatah-origin.pem;
    ssl_certificate_key /etc/ssl/cloudflare/alfatah-origin.key;

    client_max_body_size 10m;

    location / {
        proxy_pass http://127.0.0.1:8010;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/office.alfatah-marketing.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

`nginx -t` checks the config before reloading, so a typo won't take your other app down.

**If the VPS uses a control panel** (CloudPanel, aaPanel, Plesk and similar), add the site as a
"reverse proxy" to `http://127.0.0.1:8010` instead.

## 6. Add your team

Log in at https://office.alfatah-marketing.com/admin/ → **Users** → **Add user**. Pick a role:
**Admin** or **Manager** see and assign all leads, **Agent** works their own and unassigned leads.
Give admins the "Staff status" tick so they can open Settings.

## Updating

```bash
cd /opt/alfatah-crm && git pull && docker compose up -d --build
```

## Backups

```bash
docker compose exec -T db pg_dump -U crm crm | gzip > ~/crm-backup-$(date +%F).sql.gz
```

Put that line in a daily cron job and copy the file off the server now and then.
