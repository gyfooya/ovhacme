#!/usr/bin/env python3
"""
GYFOOYA : https://github.com/gyfooya/ovhacme
version 1.0
wildcard support + apex
Let's Encrypt DNS-01 ACME Challenge with OVH API
Automatically creates and cleans up DNS TXT records for certificate validation
"""

import ovh
import time
import datetime
import dns.resolver
from acme import client, messages, challenges
from acme import crypto_util
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
import josepy as jose

# Import configuration from separate file
from config import (
    OVH_ENDPOINT,
    OVH_APPLICATION_KEY,
    OVH_APPLICATION_SECRET,
    OVH_CONSUMER_KEY,
    ACME_DIRECTORY,
    DOMAINS,
    EMAIL,
    DNS_PROPAGATION_WAIT
)


class OVHDNSChallenge:
    def __init__(self, endpoint, app_key, app_secret, consumer_key):
        """Initialize OVH API client"""
        self.client = ovh.Client(
            endpoint=endpoint,
            application_key=app_key,
            application_secret=app_secret,
            consumer_key=consumer_key
        )
        self.record_ids = {}

    def cleanup_old_challenge_records(self, domain, subdomain):
        """Clean up any old _acme-challenge records before starting"""
        zone = self._get_zone(domain)
        record_name = f'_acme-challenge.{subdomain}' if subdomain else '_acme-challenge'

        try:
            existing_records = self.client.get(f'/domain/zone/{zone}/record',
                fieldType='TXT',
                subDomain=record_name
            )
            if existing_records:
                print(f"\nCleaning up {len(existing_records)} old _acme-challenge record(s)...")
                for record_id in existing_records:
                    print(f"  Deleting old record ID: {record_id}")
                    self.client.delete(f'/domain/zone/{zone}/record/{record_id}')
                self.client.post(f'/domain/zone/{zone}/refresh')
                print(f"  Old records cleaned up")
        except Exception as e:
            print(f"No old records to clean up (or error checking): {e}")

    def create_txt_record(self, domain, subdomain, value):
        """Create TXT record for ACME challenge"""
        zone = self._get_zone(domain)
        record_name = f'_acme-challenge.{subdomain}' if subdomain else '_acme-challenge'

        print(f"Creating TXT record: {record_name}.{zone} = {value}")

        try:
            result = self.client.post(f'/domain/zone/{zone}/record',
                fieldType='TXT',
                subDomain=record_name,
                target=value,
                ttl=60
            )
            record_id = result['id']

            # Store record_id with value to track multiple records with same name
            record_key = f"{record_name}:{value}"
            self.record_ids[record_key] = record_id

            # Refresh the zone
            self.client.post(f'/domain/zone/{zone}/refresh')
            print(f"TXT record created with ID: {record_id}")
            print(f"Zone refreshed successfully")
            return record_id
        except Exception as e:
            print(f"Error creating TXT record: {e}")
            raise

    def delete_txt_record(self, domain, subdomain, value=None):
        """Delete TXT record after validation"""
        zone = self._get_zone(domain)
        record_name = f'_acme-challenge.{subdomain}' if subdomain else '_acme-challenge'

        # If value is provided, use it to find the specific record
        if value:
            record_key = f"{record_name}:{value}"
            if record_key in self.record_ids:
                record_id = self.record_ids[record_key]
                print(f"Deleting TXT record: {record_name}.{zone} (ID: {record_id})")

                try:
                    self.client.delete(f'/domain/zone/{zone}/record/{record_id}')
                    self.client.post(f'/domain/zone/{zone}/refresh')
                    print(f"TXT record deleted")
                    del self.record_ids[record_key]
                except Exception as e:
                    print(f"Error deleting TXT record: {e}")
        else:
            # Legacy support - delete by name only (for backwards compatibility)
            if record_name in self.record_ids:
                record_id = self.record_ids[record_name]
                print(f"Deleting TXT record: {record_name}.{zone} (ID: {record_id})")

                try:
                    self.client.delete(f'/domain/zone/{zone}/record/{record_id}')
                    self.client.post(f'/domain/zone/{zone}/refresh')
                    print(f"TXT record deleted")
                    del self.record_ids[record_name]
                except Exception as e:
                    print(f"Error deleting TXT record: {e}")

    def _get_zone(self, domain):
        """Extract the zone name from domain"""
        parts = domain.split('.')
        if len(parts) >= 2:
            return '.'.join(parts[-2:])
        return domain


class ACMEClient:
    def __init__(self, directory_url, email):
        """Initialize ACME client"""
        self.directory_url = directory_url
        self.email = email
        self.account_key = self._generate_account_key()
        self.client = None
        self.account = None

    def _generate_account_key(self):
        """Generate RSA key for ACME account"""
        print("Generating account key...")
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        return jose.JWKRSA(key=private_key)

    def _generate_domain_key(self):
        """Generate RSA key for domain certificate"""
        self.domain_private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        pem = self.domain_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )
        return pem

    def register(self):
        """Register with ACME server"""
        print(f"Connecting to ACME server: {self.directory_url}")
        net = client.ClientNetwork(self.account_key)
        directory = messages.Directory.from_json(net.get(self.directory_url).json())
        self.client = client.ClientV2(directory, net=net)

        print(f"Registering account with email: {self.email}")
        self.account = self.client.new_account(
            messages.NewRegistration.from_data(
                email=self.email,
                terms_of_service_agreed=True
            )
        )
        print("Account registered successfully")

    def request_certificate(self, domains, dns_handler):
        """Request certificate using DNS-01 challenge for multiple domains"""
        print(f"\nRequesting certificate for: {', '.join(domains)}")

        # Create CSR for multiple domains
        csr_pem = crypto_util.make_csr(
            private_key_pem=self._generate_domain_key(),
            domains=domains
        )

        # Create order for multiple domains
        order = self.client.new_order(csr_pem)
        print(f"Order created: {order.uri}")

        # Group challenges by the DNS record name they'll use
        # This handles the case where *.example.com and example.com both use _acme-challenge.example.com
        challenges_by_record = {}

        # Step 1: Collect and group all challenges
        print("\n=== Collecting challenges ===")
        for authz in order.authorizations:
            domain_name = authz.body.identifier.value
            print(f"Processing authorization for: {domain_name}")

            # Find DNS-01 challenge
            dns_challenge = None
            for challenge in authz.body.challenges:
                if isinstance(challenge.chall, challenges.DNS01):
                    dns_challenge = challenge
                    break

            if not dns_challenge:
                raise Exception("No DNS-01 challenge found")

            # Get validation value
            validation = dns_challenge.chall.validation(self.account_key)
            print(f"  Challenge validation: {validation}")

            # For wildcard domains, remove the asterisk
            clean_domain = domain_name.replace('*.', '')

            # Extract subdomain and base domain
            base_domain = self._get_base_domain(clean_domain)
            subdomain = clean_domain.replace(f".{base_domain}", "")
            if subdomain == clean_domain:
                subdomain = ""

            # Create a key based on the DNS record that will be created
            record_key = (base_domain, subdomain)

            # Group challenges by DNS record location
            if record_key not in challenges_by_record:
                challenges_by_record[record_key] = {
                    'base_domain': base_domain,
                    'subdomain': subdomain,
                    'validations': [],
                    'challenges': []
                }

            challenges_by_record[record_key]['validations'].append(validation)
            challenges_by_record[record_key]['challenges'].append({
                'challenge': dns_challenge,
                'authz': authz,
                'domain_name': domain_name
            })

        # Step 2: Create DNS records (one per unique record location)
        print("\n=== Creating DNS records ===")
        dns_records_created = []

        # First, cleanup old records for each unique DNS location
        cleaned_locations = set()
        for record_key, record_info in challenges_by_record.items():
            base_domain = record_info['base_domain']
            subdomain = record_info['subdomain']
            location_key = (base_domain, subdomain)

            if location_key not in cleaned_locations:
                dns_handler.cleanup_old_challenge_records(base_domain, subdomain)
                cleaned_locations.add(location_key)

        # Now create the new records
        for record_key, record_info in challenges_by_record.items():
            base_domain = record_info['base_domain']
            subdomain = record_info['subdomain']
            validations = record_info['validations']

            zone = dns_handler._get_zone(base_domain)
            record_name = f'_acme-challenge.{subdomain}' if subdomain else '_acme-challenge'

            print(f"\nDNS record: {record_name}.{zone}")
            print(f"  Domains using this record: {[c['domain_name'] for c in record_info['challenges']]}")
            print(f"  Number of validations: {len(validations)}")

            # Create a TXT record for each validation value
            for validation in validations:
                dns_handler.create_txt_record(base_domain, subdomain, validation)
                dns_records_created.append((base_domain, subdomain, validation))

        # Verify records in OVH
        print("\n=== Verifying records in OVH DNS zone ===")
        all_records_present = True

        for record_key, record_info in challenges_by_record.items():
            base_domain = record_info['base_domain']
            subdomain = record_info['subdomain']
            validations = record_info['validations']

            zone = dns_handler._get_zone(base_domain)
            record_name = f'_acme-challenge.{subdomain}' if subdomain else '_acme-challenge'

            try:
                existing_records = dns_handler.client.get(f'/domain/zone/{zone}/record',
                    fieldType='TXT',
                    subDomain=record_name
                )
                print(f"\nChecking {record_name}.{zone}:")
                print(f"  Found {len(existing_records)} TXT record(s) in OVH")
                print(f"  Expected {len(validations)} record(s)")

                # Check if our validation values exist
                found_values = []
                for record_id in existing_records:
                    record_details = dns_handler.client.get(f'/domain/zone/{zone}/record/{record_id}')
                    target_value = record_details.get('target', '')
                    # Remove quotes if present
                    clean_target = target_value.strip('"')
                    print(f"  - ID {record_id}: {clean_target[:50]}...")
                    if clean_target in validations:
                        found_values.append(clean_target)
                        print(f"    ✓ Validation value found!")

                if len(found_values) != len(validations):
                    print(f"  ⚠ WARNING: Expected {len(validations)} values but found {len(found_values)}")
                    all_records_present = False

            except Exception as e:
                print(f"  Error checking records: {e}")
                all_records_present = False

        if not all_records_present:
            print("\n⚠ WARNING: Not all expected records found in OVH!")
        else:
            print("\n✓ All validation records confirmed in OVH DNS zone")

        # Step 3: Wait for DNS propagation
        print(f"\n=== Waiting {DNS_PROPAGATION_WAIT} seconds for DNS propagation ===")
        time.sleep(DNS_PROPAGATION_WAIT)

        # Step 4: Verify DNS records are publicly visible
        print("\n=== Verifying DNS records are publicly visible ===")
        for record_key, record_info in challenges_by_record.items():
            for challenge_info in record_info['challenges']:
                domain_name = challenge_info['domain_name']

                print(f"Checking public DNS for {domain_name}...")
                try:
                    txt_record = f'_acme-challenge.{domain_name}'
                    answers = dns.resolver.resolve(txt_record, 'TXT')
                    print(f"  Found {len(answers)} TXT record(s)")
                    for rdata in answers:
                        txt_value = rdata.to_text().strip('"')
                        print(f"    - {txt_value[:50]}...")
                except Exception as e:
                    print(f"  ⚠ Warning: Could not verify DNS record: {e}")

        # Step 5: Answer all challenges
        print("\n=== Answering all challenges ===")
        for record_key, record_info in challenges_by_record.items():
            for challenge_info in record_info['challenges']:
                dns_challenge = challenge_info['challenge']
                domain_name = challenge_info['domain_name']
                print(f"Answering challenge for {domain_name}...")
                self.client.answer_challenge(dns_challenge, dns_challenge.chall.response(self.account_key))
                print(f"  ✓ Challenge answered")

        # Step 6: Poll for validation of all challenges
        print("\n=== Waiting for validation ===")
        try:
            from acme import errors as acme_errors

            for record_key, record_info in challenges_by_record.items():
                for challenge_info in record_info['challenges']:
                    authz = challenge_info['authz']
                    domain_name = challenge_info['domain_name']

                    print(f"Polling validation for {domain_name}...")

                    challenge_deadline = time.time() + 90
                    while time.time() < challenge_deadline:
                        authz_response = self.client.poll(authz)
                        # poll() returns a tuple (response, authz_uri)
                        if isinstance(authz_response, tuple):
                            authz_response = authz_response[0]

                        if authz_response.body.status == messages.STATUS_VALID:
                            print(f"  ✓ Challenge validated for {domain_name}")
                            break
                        elif authz_response.body.status == messages.STATUS_INVALID:
                            print(f"  ✗ Challenge validation failed for {domain_name}!")
                            if authz_response.body.challenges:
                                for chall in authz_response.body.challenges:
                                    if chall.error:
                                        print(f"  Error: {chall.error}")
                            raise Exception(f"Challenge validation failed for {domain_name}")
                        else:
                            print(f"  Status: {authz_response.body.status}, waiting...")
                            time.sleep(5)

                    if authz_response.body.status != messages.STATUS_VALID:
                        raise acme_errors.TimeoutError(f"Challenge validation timed out for {domain_name}")

        except Exception as e:
            print(f"\nError during validation: {e}")
            # Clean up all DNS records before raising
            print("\n=== Cleaning up DNS records ===")
            for base_domain, subdomain, validation in dns_records_created:
                dns_handler.delete_txt_record(base_domain, subdomain, validation)
            raise

        # Step 7: Clean up all DNS records
        print("\n=== Cleaning up DNS records ===")
        for base_domain, subdomain, validation in dns_records_created:
            dns_handler.delete_txt_record(base_domain, subdomain, validation)

        # Step 8: Finalize order after all authorizations are valid
        print("\n=== Finalizing order ===")
        deadline = datetime.datetime.now() + datetime.timedelta(seconds=90)
        order = self.client.poll_and_finalize(order, deadline)

        print("\n✓ Certificate issued successfully!")
        return order

    def _get_base_domain(self, domain):
        """Extract base domain"""
        parts = domain.split('.')
        if len(parts) >= 2:
            return '.'.join(parts[-2:])
        return domain


def main():
    """Main execution"""
    print("=" * 60)
    print("Let's Encrypt DNS-01 ACME Challenge with OVH API")
    print("=" * 60)

    # Initialize DNS handler
    dns_handler = OVHDNSChallenge(
        OVH_ENDPOINT,
        OVH_APPLICATION_KEY,
        OVH_APPLICATION_SECRET,
        OVH_CONSUMER_KEY
    )

    # Initialize ACME client
    acme_client = ACMEClient(ACME_DIRECTORY, EMAIL)
    acme_client.register()

    # Request certificate
    try:
        order = acme_client.request_certificate(DOMAINS, dns_handler)

        # Download certificate
        cert = order.fullchain_pem
        print("\nCertificate chain:")
        print(cert[:200] + "...")

        # Save certificate with sanitized filename
        filename = DOMAINS[0].replace('*.', 'wildcard-').replace('/', '-')

        # Save certificate
        with open(f'{filename}.crt', 'w') as f:
            f.write(cert)
        print(f"\n✓ Certificate saved to: {filename}.crt")

        # Save private key
        private_key_pem = acme_client.domain_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )
        with open(f'{filename}.key', 'wb') as f:
            f.write(private_key_pem)
        print(f"✓ Private key saved to: {filename}.key")

        print(f"\n✓ Certificate covers: {', '.join(DOMAINS)}")
        print(f"\n⚠ IMPORTANT: Keep {filename}.key secure and private!")
        print(f"   Never share or commit this file to version control!")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


if __name__ == '__main__':
    main()
