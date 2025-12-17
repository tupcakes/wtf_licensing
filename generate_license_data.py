#!/usr/bin/env python3
"""
Script to generate a comprehensive JSON file of all O365 licenses and their relationships.
This includes all product SKUs and the service plans they supersede/include.
"""

import csv
import json
import sys
import urllib.request
from pathlib import Path
from typing import Dict, List, Any


# URL for the Microsoft licensing CSV
CSV_URL = "https://download.microsoft.com/download/e/3/e/e3e9faf2-f28b-490a-9ada-c6089a1fc5b0/Product%20names%20and%20service%20plan%20identifiers%20for%20licensing.csv"

# For testing, use local file
LOCAL_CSV_PATH = "tests/Product names and service plan identifiers for licensing.csv"


def download_csv(url: str, output_path: Path) -> None:
    """Download the CSV file from Microsoft."""
    print(f"Downloading CSV from {url}...")
    try:
        with urllib.request.urlopen(url) as response:
            data = response.read()
            output_path.write_bytes(data)
        print(f"Downloaded to {output_path}")
    except Exception as e:
        print(f"Error downloading CSV: {e}", file=sys.stderr)
        raise


def parse_csv_to_license_structure(csv_path: Path) -> Dict[str, Any]:
    """
    Parse the CSV and create a comprehensive license structure.

    Returns a dictionary with:
    - products: dict of all product SKUs with their included service plans
    - service_plans: dict of all unique service plans
    - supersedence_map: mapping to help identify license overlaps
    """
    products = {}
    service_plans = {}

    with csv_path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Extract product information
            product_name = row["Product_Display_Name"].strip()
            string_id = row["String_Id"].strip()
            guid = row["GUID"].strip()

            # Extract service plan information
            service_plan_name = row["Service_Plan_Name"].strip()
            service_plan_id = row["Service_Plan_Id"].strip()
            service_plan_friendly_name = row[
                "Service_Plans_Included_Friendly_Names"
            ].strip()

            # Create unique product key (using GUID as it's unique)
            product_key = guid

            # Initialize product entry if not exists
            if product_key not in products:
                products[product_key] = {
                    "product_display_name": product_name,
                    "string_id": string_id,
                    "guid": guid,
                    "included_service_plans": [],
                }

            # Add service plan to product
            service_plan_entry = {
                "service_plan_name": service_plan_name,
                "service_plan_id": service_plan_id,
                "service_plan_friendly_name": service_plan_friendly_name,
            }
            products[product_key]["included_service_plans"].append(service_plan_entry)

            # Track all unique service plans
            if service_plan_id not in service_plans:
                service_plans[service_plan_id] = {
                    "service_plan_id": service_plan_id,
                    "service_plan_name": service_plan_name,
                    "service_plan_friendly_name": service_plan_friendly_name,
                    "included_in_products": [],
                }

            # Add this product to the service plan's list of products
            if (
                product_key
                not in service_plans[service_plan_id]["included_in_products"]
            ):
                service_plans[service_plan_id]["included_in_products"].append(
                    product_key
                )

    return {
        "products": products,
        "service_plans": service_plans,
        "metadata": {
            "total_products": len(products),
            "total_service_plans": len(service_plans),
            "source_url": CSV_URL,
            "description": "Complete O365 license structure showing all products and their included service plans",
        },
    }


def create_supersedence_analysis(license_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a supersedence analysis to help identify overlapping licenses.
    This maps each product to all service plans it includes, enabling comparison.
    """
    products = license_data["products"]

    supersedence_map = {}

    for product_guid, product_info in products.items():
        # Get all service plan IDs for this product
        service_plan_ids = {
            sp["service_plan_id"] for sp in product_info["included_service_plans"]
        }

        supersedence_map[product_guid] = {
            "product_name": product_info["product_display_name"],
            "string_id": product_info["string_id"],
            "service_plan_ids": sorted(list(service_plan_ids)),
            "service_plan_count": len(service_plan_ids),
        }

    return supersedence_map


def identify_self_referencing_plans(license_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Identify products that have service plans with the same name as the product's string_id.
    These are typically the "core" service plan that represents the product itself.

    Returns information about self-referencing service plans for transparency.
    """
    products = license_data["products"]
    self_referencing = []

    for guid, product_info in products.items():
        string_id = product_info["string_id"]
        for sp in product_info["included_service_plans"]:
            if sp["service_plan_name"] == string_id:
                self_referencing.append(
                    {
                        "product_guid": guid,
                        "product_name": product_info["product_display_name"],
                        "string_id": string_id,
                        "self_referencing_service_plan_id": sp["service_plan_id"],
                        "note": "This service plan represents the core product license itself",
                    }
                )
                break  # Only one self-referencing plan per product

    return {
        "count": len(self_referencing),
        "description": "Products where a service plan name matches the product's string_id. These are filtered from overlap detection to prevent incorrectly identifying a product as superseded when it's the core license itself.",
        "self_referencing_products": self_referencing,
    }


def find_overlapping_licenses(license_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Find all pairs of licenses where one completely contains the other's service plans.
    This helps identify when users might be doubled up on licenses.

    Note: Excludes self-referencing service plans (where the service plan name
    matches the product's string_id) to avoid incorrectly flagging a product
    as superseded by another when the "core" service plan is the product itself.
    """
    products = license_data["products"]
    overlaps = []

    # Create a map of product GUID to set of service plan IDs
    # Exclude self-referencing service plans to avoid false positives
    product_service_plans = {}
    for guid, product_info in products.items():
        string_id = product_info["string_id"]
        # Filter out service plans that have the same name as the product's string_id
        product_service_plans[guid] = set(
            sp["service_plan_id"]
            for sp in product_info["included_service_plans"]
            if sp["service_plan_name"] != string_id
        )

    # Compare each product pair
    product_list = list(products.items())
    for i, (guid1, product1) in enumerate(product_list):
        plans1 = product_service_plans[guid1]

        for guid2, product2 in product_list[i + 1 :]:
            plans2 = product_service_plans[guid2]

            # Check if one is a subset of the other
            if plans1.issubset(plans2) and plans1:
                overlaps.append(
                    {
                        "subset_product": {
                            "guid": guid1,
                            "string_id": product1["string_id"],
                            "name": product1["product_display_name"],
                        },
                        "superset_product": {
                            "guid": guid2,
                            "string_id": product2["string_id"],
                            "name": product2["product_display_name"],
                        },
                        "note": "All service plans in subset_product are included in superset_product",
                    }
                )
            elif plans2.issubset(plans1) and plans2:
                overlaps.append(
                    {
                        "subset_product": {
                            "guid": guid2,
                            "string_id": product2["string_id"],
                            "name": product2["product_display_name"],
                        },
                        "superset_product": {
                            "guid": guid1,
                            "string_id": product1["string_id"],
                            "name": product1["product_display_name"],
                        },
                        "note": "All service plans in subset_product are included in superset_product",
                    }
                )

    return overlaps


def main():
    """Main execution function."""
    # Determine which CSV to use
    use_local = "--local" in sys.argv

    if use_local:
        csv_path = Path(LOCAL_CSV_PATH)
        if not csv_path.exists():
            print(f"Error: Local CSV file not found at {csv_path}", file=sys.stderr)
            sys.exit(1)
        print(f"Using local CSV file: {csv_path}")
    else:
        # Download the CSV
        csv_path = Path("o365_licenses_temp.csv")
        try:
            download_csv(CSV_URL, csv_path)
        except Exception as e:
            print(
                f"Failed to download CSV. Use --local flag to use local file.",
                file=sys.stderr,
            )
            sys.exit(1)

    # Parse the CSV
    print("Parsing CSV and building license structure...")
    license_data = parse_csv_to_license_structure(csv_path)

    # Identify self-referencing service plans
    print("Identifying self-referencing service plans...")
    self_referencing_info = identify_self_referencing_plans(license_data)
    license_data["self_referencing_plans"] = self_referencing_info

    # Create supersedence analysis
    print("Creating supersedence analysis...")
    supersedence_map = create_supersedence_analysis(license_data)
    license_data["supersedence_map"] = supersedence_map

    # Find overlapping licenses
    print("Finding overlapping licenses (excluding self-referencing plans)...")
    overlaps = find_overlapping_licenses(license_data)
    license_data["license_overlaps"] = {"count": len(overlaps), "overlaps": overlaps}

    # Write the JSON output
    output_path = Path("o365_licenses_complete.json")
    print(f"Writing complete license data to {output_path}...")
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(license_data, f, indent=2, ensure_ascii=False)

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total Products: {license_data['metadata']['total_products']}")
    print(f"Total Service Plans: {license_data['metadata']['total_service_plans']}")
    print(f"Self-Referencing Plans: {license_data['self_referencing_plans']['count']}")
    print(f"License Overlaps Found: {license_data['license_overlaps']['count']}")
    print(f"\nOutput file: {output_path}")
    print(f"File size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
    print("=" * 60)

    # Clean up temp file if we downloaded it
    if not use_local and csv_path.exists():
        csv_path.unlink()
        print("Temporary CSV file cleaned up.")


if __name__ == "__main__":
    main()
