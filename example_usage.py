#!/usr/bin/env python3
"""
Example script demonstrating how to use the generated o365_licenses_complete.json
to detect duplicate/overlapping licenses assigned to users.
"""

import json
from typing import List, Dict, Set


def load_license_data(json_path: str = "o365_licenses_complete.json") -> dict:
    """Load the license data JSON."""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_user_license_overlaps(
    user_license_guids: List[str], license_data: dict
) -> List[Dict]:
    """
    Check if a user has overlapping licenses.

    Note: The license_overlaps data already excludes self-referencing service plans
    (where a service plan name matches the product's string_id). This prevents
    false positives where a product would be flagged as superseded by another
    product when it's actually the core license itself.

    Args:
        user_license_guids: List of license GUIDs assigned to the user
        license_data: The loaded license data from the JSON

    Returns:
        List of overlaps found in the user's licenses
    """
    overlaps_found = []

    for overlap in license_data["license_overlaps"]["overlaps"]:
        subset_guid = overlap["subset_product"]["guid"]
        superset_guid = overlap["superset_product"]["guid"]

        # Check if user has both the subset and superset license
        if subset_guid in user_license_guids and superset_guid in user_license_guids:
            overlaps_found.append(overlap)

    return overlaps_found


def get_service_plan_overlap(
    license_guid1: str, license_guid2: str, license_data: dict
) -> Dict:
    """
    Compare two licenses to see how their service plans overlap.

    Returns:
        Dictionary with overlap analysis
    """
    products = license_data["products"]

    if license_guid1 not in products or license_guid2 not in products:
        return {"error": "One or both license GUIDs not found"}

    product1 = products[license_guid1]
    product2 = products[license_guid2]

    # Get service plan IDs
    plans1 = set(sp["service_plan_id"] for sp in product1["included_service_plans"])
    plans2 = set(sp["service_plan_id"] for sp in product2["included_service_plans"])

    # Calculate overlaps
    common_plans = plans1 & plans2
    only_in_1 = plans1 - plans2
    only_in_2 = plans2 - plans1

    return {
        "license1": {
            "name": product1["product_display_name"],
            "string_id": product1["string_id"],
            "total_plans": len(plans1),
        },
        "license2": {
            "name": product2["product_display_name"],
            "string_id": product2["string_id"],
            "total_plans": len(plans2),
        },
        "common_plans": len(common_plans),
        "only_in_license1": len(only_in_1),
        "only_in_license2": len(only_in_2),
        "overlap_percentage_1": round(len(common_plans) / len(plans1) * 100, 1)
        if plans1
        else 0,
        "overlap_percentage_2": round(len(common_plans) / len(plans2) * 100, 1)
        if plans2
        else 0,
    }


def find_license_by_name(search_term: str, license_data: dict) -> List[Dict]:
    """Find licenses matching a search term."""
    matches = []
    for guid, product in license_data["products"].items():
        if (
            search_term.lower() in product["product_display_name"].lower()
            or search_term.lower() in product["string_id"].lower()
        ):
            matches.append(
                {
                    "guid": guid,
                    "name": product["product_display_name"],
                    "string_id": product["string_id"],
                    "service_plan_count": len(product["included_service_plans"]),
                }
            )
    return matches


# Example usage
if __name__ == "__main__":
    print("Loading license data...")
    data = load_license_data()

    print("\n" + "=" * 70)
    print("EXAMPLE 1: Check user's licenses for overlaps")
    print("=" * 70)

    # Example: User has both Microsoft Entra ID P1 and P2
    user_licenses = [
        "078d2b04-f1bd-4111-bbd4-b4b1b354cef4",  # Microsoft Entra ID P1
        "84a661c4-e949-4bd2-a560-ed7766fcaf2b",  # Microsoft Entra ID P2
    ]

    overlaps = check_user_license_overlaps(user_licenses, data)

    if overlaps:
        print(f"\n⚠️  Found {len(overlaps)} overlap(s) in user's licenses:\n")
        for overlap in overlaps:
            print(f"  • {overlap['subset_product']['name']}")
            print(f"    is fully contained in")
            print(f"    {overlap['superset_product']['name']}")
            print(
                f"    → Consider removing the subset license to avoid paying twice!\n"
            )
    else:
        print("✓ No overlapping licenses detected")

    print("\n" + "=" * 70)
    print("EXAMPLE 2: Compare two specific licenses")
    print("=" * 70)

    # Compare M365 E3 and E5
    comparison = get_service_plan_overlap(
        "05e9a617-0261-4cee-bb44-138d3ef5d965",  # M365 E3
        "06ebc4ee-1bb5-47dd-8120-11324bc54e06",  # M365 E5
        data,
    )

    print(f"\nComparing:")
    print(
        f"  {comparison['license1']['name']} ({comparison['license1']['total_plans']} plans)"
    )
    print(f"  vs")
    print(
        f"  {comparison['license2']['name']} ({comparison['license2']['total_plans']} plans)"
    )
    print(f"\nResults:")
    print(f"  Common plans: {comparison['common_plans']}")
    print(f"  Only in E3: {comparison['only_in_license1']}")
    print(f"  Only in E5: {comparison['only_in_license2']}")
    print(f"  Overlap: {comparison['overlap_percentage_1']}% of E3 plans are in E5")

    print("\n" + "=" * 70)
    print("EXAMPLE 3: Search for licenses")
    print("=" * 70)

    search_results = find_license_by_name("Entra ID P", data)
    print(f"\nFound {len(search_results)} licenses matching 'Entra ID P':\n")
    for result in search_results[:5]:
        print(f"  • {result['name']}")
        print(f"    String ID: {result['string_id']}")
        print(f"    GUID: {result['guid']}")
        print(f"    Service Plans: {result['service_plan_count']}\n")

    print("\n" + "=" * 70)
    print("STATISTICS")
    print("=" * 70)
    print(f"\nTotal Products: {data['metadata']['total_products']}")
    print(f"Total Service Plans: {data['metadata']['total_service_plans']}")
    print(f"Potential Overlaps: {data['license_overlaps']['count']}")
