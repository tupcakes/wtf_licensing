"""
Example usage of the LicenseDataService.

This script demonstrates how to use the singleton service to generate
O365 license data with supersedence relationships.
"""

import argparse
from pathlib import Path
from src.services import LicenseDataService


def main():
    parser = argparse.ArgumentParser(
        description="Generate O365 license data with supersedence relationships"
    )
    parser.add_argument(
        "--use-local",
        action="store_true",
        help="Use local CSV file instead of downloading from Microsoft",
    )
    parser.add_argument(
        "--local-csv", type=str, help="Path to local CSV file (used with --use-local)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="o365_licenses_simple.json",
        help="Output JSON file path (default: o365_licenses_simple.json)",
    )

    args = parser.parse_args()

    # Get the singleton service instance
    service = LicenseDataService()

    # Generate license data
    try:
        service.generate_license_data(
            use_local=args.use_local,
            local_csv_path=args.local_csv,
            output_json_path=args.output,
        )

        # Example: Access specific product data
        print("\nExample queries:")
        print("-" * 60)

        # Get metadata
        metadata = service.get_metadata()
        print(f"Total products loaded: {metadata['total_products']}")

        # Get all products and show first one as example
        all_products = service.get_all_products()
        if all_products:
            first_guid = next(iter(all_products.keys()))
            first_product = all_products[first_guid]
            print(f"\nExample product:")
            print(f"  Name: {first_product['product_display_name']}")
            print(f"  String ID: {first_product['string_id']}")
            print(f"  GUID: {first_product['guid']}")
            print(f"  Service plans: {len(first_product['included_service_plans'])}")
            print(f"  Supersedes: {len(first_product['supersedes'])} products")
            print(f"  Superseded by: {len(first_product['superseded_by'])} products")

        print("\n✓ Service can be accessed again via: service = LicenseDataService()")
        print("  (returns the same singleton instance with cached data)")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
