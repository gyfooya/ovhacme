"""
Configuration file for Let's Encrypt DNS ACME Challenge with OVH API
"""

# OVH API Configuration
OVH_ENDPOINT = 'ovh-eu'  # Europe endpoint
OVH_APPLICATION_KEY = 'your_application_key'
OVH_APPLICATION_SECRET = 'your_application_secret'
OVH_CONSUMER_KEY = 'your_consumer_key'

# Let's Encrypt Configuration
ACME_DIRECTORY = 'https://acme-v02.api.letsencrypt.org/directory'  # Production
# ACME_DIRECTORY = 'https://acme-staging-v02.api.letsencrypt.org/directory'  # Staging/testing

# Your domain configuration
DOMAINS = ['yourDomainApex.xxx', '*.yourDomainWildcard.xxx']  # Can include multiple domains and wildcards
EMAIL = 'hostmaster@yourdomain.xxx'

# DNS propagation wait time (seconds)
DNS_PROPAGATION_WAIT = 60
