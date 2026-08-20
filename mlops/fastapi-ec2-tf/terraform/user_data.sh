#!/bin/bash
set -e

apt-get update -y
apt-get install -y python3-pip nginx

pip3 install fastapi uvicorn

mkdir -p /home/ubuntu/app

cat > /home/ubuntu/app/main.py << 'PYEOF'
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    text: str


items = []


@app.get("/")
def root():
    return {"Hello": "World"}


@app.post("/items")
def create_item(item: Item):
    items.append(item)
    return items


@app.get("/items")
def list_items(limit: int = 10):
    return items[0:limit]


@app.get("/items/{item_id}")
def get_item(item_id: int):
    if 0 <= item_id < len(items):
        return items[item_id]
    raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
PYEOF

chown -R ubuntu:ubuntu /home/ubuntu/app

# Uruchom jako systemd service (restart po crashu)
cat > /etc/systemd/system/fastapi.service << 'SVCEOF'
[Unit]
Description=FastAPI App
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/app
ExecStart=/usr/local/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable fastapi
systemctl start fastapi

# ── NGINX reverse proxy ────────────────────────────────────
cat > /etc/nginx/sites-enabled/fastapi_nginx << 'NGINXEOF'
server {
    listen 80;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
NGINXEOF

rm -f /etc/nginx/sites-enabled/default
systemctl restart nginx
