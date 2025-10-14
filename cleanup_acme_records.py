#!/usr/bin/env python3
"""
Cleanup old _acme-challenge TXT records from OVH DNS
"""

import ovh
from config import (
    OVH_ENDPOINT,
    OVH_APPLICATION_KEY,
    OVH_APPLICATION_SECRET,
    OVH_CONSUMER_KEY,
    DOMAINS
)


def cleanup_acme_records():
    """Remove all _acme-challenge records for configured domains"""

    # Initialize OVH client
    client = ovh.Client(
        endpoint=OVH_ENDPOINT,
        application_key=OVH_APPLICATION_KEY,
        application_secret=OVH_APPLICATION_SECRET,
        consumer_key=OVH_CONSUMER_KEY
    )

    # Get base domain from first domain in list
    first_domain = DOMAINS[0].replace('*.', '')
    parts = first_domain.split('.')
    zone = '.'.join(parts[-2:]) if len(parts) >= 2 else first_domain

    print(f"Checking DNS zone: {zone}")
    print(f"Looking for _acme-challenge records...\n")

    try:
        # Get all _acme-challenge TXT records
        record_ids = client.get(f'/domain/zone/{zone}/record',
            fieldType='TXT',
            subDomain='_acme-challenge'
        )

        if not record_ids:
            print("✓ No _acme-challenge records found. DNS zone is clean!")
            return

        print(f"Found {len(record_ids)} _acme-challenge record(s):\n")

        # Show details and delete
        for record_id in record_ids:
            record = client.get(f'/domain/zone/{zone}/record/{record_id}')
            target = record.get('target', 'N/A')
            print(f"  ID {record_id}: {target}")

            # Delete the record
            client.delete(f'/domain/zone/{zone}/record/{record_id}')
            print(f"  ✓ Deleted\n")

        # Refresh the zone
        print("Refreshing DNS zone...")
        client.post(f'/domain/zone/{zone}/refresh')
        print(f"\n✓ Successfully cleaned up {len(record_ids)} record(s)")
        print("✓ DNS zone refreshed")

    except Exception as e:
        print(f"✗ Error: {e}")
        raise


if __name__ == '__main__':
    print("=" * 60)
    print("OVH DNS Cleanup - Remove _acme-challenge records")
    print("=" * 60)
    print()

    cleanup_acme_records()
