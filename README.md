# OVH Let's Encrypt DNS-01 ACME Challenge

Automatic Let's Encrypt wildcard and apex domain certificate generation using OVH's DNS API.

## Features

✅ **Wildcard certificates** - Supports `*.example.com` and `example.com` in one certificate  
✅ **Automatic DNS management** - Creates and cleans up `_acme-challenge` TXT records via OVH API  
✅ **Multiple domains** - Request certificates for multiple domains at once  
✅ **Auto-renewal** - Systemd timer for automatic monthly certificate renewal  
✅ **Production ready** - Handles DNS propagation, verification, and error recovery  
✅ **OVH Europe** - Configured for OVH Europe API endpoint  

## Requirements

- Python 3.7+
- OVH domain with API access
- OVH API credentials (application key, secret, consumer key)

## Installation

### 1. Clone or download this repository

```bash
git clone https://github.com/gyfooya/ovhacme.git
cd ovhacme
```

### 2. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure OVH API credentials

#### Create OVH API credentials:

1. Go to https://eu.api.ovh.com/createToken/
2. Set the following rights:
   - `GET /domain/zone/*`
   - `POST /domain/zone/*`
   - `DELETE /domain/zone/*/record/*`
   - `POST /domain/zone/*/refresh`
3. Save your credentials

#### Edit configuration file:

```bash
nano config.py  # or vim, or any editor
```

Edit `config.py` with your details:

```python
# OVH API Configuration
OVH_ENDPOINT = 'ovh-eu'
OVH_APPLICATION_KEY = 'your_application_key_here'
OVH_APPLICATION_SECRET = 'your_application_secret_here'
OVH_CONSUMER_KEY = 'your_consumer_key_here'

# Let's Encrypt Configuration
ACME_DIRECTORY = 'https://acme-v02.api.letsencrypt.org/directory'  # Production
# ACME_DIRECTORY = 'https://acme-staging-v02.api.letsencrypt.org/directory'  # Staging

# Your domain configuration
DOMAINS = ['example.com', '*.example.com']
EMAIL = 'admin@example.com'

# DNS propagation wait time (seconds)
DNS_PROPAGATION_WAIT = 60
```

**Important:** Start with the staging URL for testing to avoid rate limits!

## Usage

### Generate Certificate

```bash
python ovhacme.py
```

This will:
1. Clean up old `_acme-challenge` records
2. Create new TXT records for DNS-01 challenge
3. Wait for DNS propagation
4. Validate with Let's Encrypt
5. Download and save certificate
6. Clean up DNS records

### Output Files

- `example.crt` - Full certificate chain (safe to share)
- `example.key` - Private key (**keep secret!**)

### Cleanup Old DNS Records

If you have leftover `_acme-challenge` records:

```bash
python cleanup_acme_records.py
```

## Automatic Renewal with Systemd

### Installation

1. **Edit service file** with your paths:
   ```bash
   nano ovh-letsencrypt.service
   ```
   Update these lines:
   ```ini
   WorkingDirectory=/home/noname/ovhacme
   ExecStart=/home/noname/ovhacme/venv/bin/python /home/noname/ovhacme/ovhacme.py
   ```

2. **Install the service:**
   ```bash
   chmod +x install-systemd-service.sh
   sudo ./install-systemd-service.sh
   ```

### Systemd Commands

```bash
# Check timer status
sudo systemctl status ovh-letsencrypt.timer

# See next scheduled renewal
sudo systemctl list-timers ovh-letsencrypt.timer

# Run renewal NOW (manual)
sudo systemctl start ovh-letsencrypt.service

# View logs
sudo journalctl -u ovh-letsencrypt -f

# Stop auto-renewal
sudo systemctl stop ovh-letsencrypt.timer
sudo systemctl disable ovh-letsencrypt.timer
```

### Renewal Schedule

Default: **Monthly** on the 1st at 3:00 AM (with random 0-1h delay)

To change the schedule, edit `ovh-letsencrypt.timer`:

```ini
# Monthly (default)
OnCalendar=monthly

# Every 2 months
OnCalendar=*-01,03,05,07,09,11-01 03:00:00

# Twice a month (1st and 15th)
OnCalendar=*-*-01,15 03:00:00
```

Then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart ovh-letsencrypt.timer
```

## Using Your Certificate

### Nginx

```nginx
server {
    listen 443 ssl;
    server_name example.com *.example.com;
    
    ssl_certificate /path/to/example.crt;
    ssl_certificate_key /path/to/example.key;
    
    # Additional SSL settings...
}
```

### Apache

```apache
<VirtualHost *:443>
    ServerName example.com
    ServerAlias *.example.com
    
    SSLEngine on
    SSLCertificateFile /path/to/example.crt
    SSLCertificateKeyFile /path/to/example.key
    
    # Additional SSL settings...
</VirtualHost>
```

### Caddy

Caddy can use external certificates with the `tls` directive:

```caddy
example.com, *.example.com {
    tls /path/to/example.crt /path/to/example.key
    
    # Your site configuration
    reverse_proxy localhost:8080
}
```

Or using a Caddyfile with automatic reloading:

```caddy
example.com, *.example.com {
    tls /path/to/example.crt /path/to/example.key {
        # Optional: protocols and ciphers
    }
    
    # Your configuration
    root * /var/www/html
    file_server
}
```

**Reload Caddy after certificate renewal:**

Add this to your systemd service file to reload Caddy automatically:

Edit `ovh-letsencrypt.service`:
```ini
[Service]
Type=oneshot
User=root
WorkingDirectory=/home/noname/ovhacme
ExecStart=/home/noname/ovhacme/venv/bin/python /home/noname/ovhacme/ovhacme.py
# Reload Caddy after successful renewal
ExecStartPost=/usr/bin/systemctl reload caddy
```

Or create a separate reload service that runs after renewal:

**caddy-reload.service:**
```ini
[Unit]
Description=Reload Caddy after certificate renewal
After=ovh-letsencrypt.service

[Service]
Type=oneshot
ExecStart=/usr/bin/systemctl reload caddy
```

Then add to `ovh-letsencrypt.service`:
```ini
[Service]
Type=oneshot
User=root
WorkingDirectory=/home/noname/ovhacme
ExecStart=/home/noname/ovhacme/venv/bin/python /home/noname/ovhacme/ovhacme.py
ExecStartPost=/usr/bin/systemctl start caddy-reload.service
```

## Project Structure

```
OVHACME/
├── ovhacme.py                    # Main certificate generation script
├── config.py                     # Your configuration (not in git)
├── config.example.py             # Configuration template
├── cleanup_acme_records.py       # Cleanup utility
├── requirements.txt              # Python dependencies
├── ovh-letsencrypt.service       # Systemd service file
├── ovh-letsencrypt.timer         # Systemd timer file
├── install-systemd-service.sh    # Systemd installer
├── .gitignore                    # Git ignore rules
└── README.md                     # This file
```

## Troubleshooting

### DNS propagation issues

If validation fails due to DNS propagation:

1. Increase wait time in `config.py`:
   ```python
   DNS_PROPAGATION_WAIT = 120  # 2 minutes
   ```

2. Verify DNS manually:
   ```bash
   dig _acme-challenge.example.com TXT +short
   ```

### Rate limits

Let's Encrypt has rate limits:
- **50 certificates per domain per week**
- **5 failed validations per hour**

**Solution:** Use staging URL for testing:
```python
ACME_DIRECTORY = 'https://acme-staging-v02.api.letsencrypt.org/directory'
```

### OVH API errors

Common issues:
- **Invalid credentials** - Check your API keys in `config.py`
- **Insufficient rights** - Ensure API token has all required permissions
- **Domain not found** - Verify domain is managed by OVH

### Certificate not renewing

Check systemd logs:
```bash
sudo journalctl -u ovh-letsencrypt -n 50
```

Test manual renewal:
```bash
sudo systemctl start ovh-letsencrypt.service
```

## Security Notes

⚠️ **Keep your private key secure!**
- Never commit `*.key` files to git
- Set proper file permissions: `chmod 600 example.key`
- Store backups securely

⚠️ **Protect your configuration:**
- `config.py` contains API credentials - never commit it
- Use `.gitignore` to prevent accidental commits

## How It Works

1. **Collect challenges** - Gets DNS-01 challenges from Let's Encrypt for each domain
2. **Group by DNS record** - Both `example.com` and `*.example.com` use the same `_acme-challenge.example.com` record
3. **Create TXT records** - Adds validation values to OVH DNS via API
4. **Wait for propagation** - Allows DNS changes to propagate (configurable)
5. **Verify DNS** - Checks that records are publicly visible
6. **Answer challenges** - Tells Let's Encrypt validation is ready
7. **Poll for validation** - Waits for Let's Encrypt to verify
8. **Download certificate** - Gets the signed certificate
9. **Cleanup** - Removes temporary DNS records

## Certificate Validity

- Let's Encrypt certificates are valid for **90 days**
- Recommended renewal: **Every 60 days**
- Systemd timer renews **monthly** by default

## Advanced Configuration

### Multiple domains from different zones

```python
DOMAINS = [
    'example.com', '*.example.com',
    'example.net', '*.example.net'
]
```

**Note:** All domains must be in OVH DNS zones accessible by your API credentials.

## Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.

## Acknowledgments

- Built with [acme](https://github.com/certbot/certbot) library
- Uses [OVH API](https://github.com/ovh/python-ovh)
- Inspired by [Certbot](https://certbot.eff.org/)

## Support

For issues with:
- **This script:** Open an issue on GitHub
- **Let's Encrypt:** https://community.letsencrypt.org/
- **OVH API:** https://help.ovhcloud.com/

---

**Happy encrypting! 🔒**
