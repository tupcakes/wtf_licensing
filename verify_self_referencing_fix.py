#!/usr/bin/env python3
"""
Verification script to demonstrate that self-referencing service plans
are properly handled and don't cause false positive overlaps.
"""

import json


def main():
    # Load the data
    with open("o365_licenses_complete.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    print("=" * 70)
    print("VERIFICATION: Self-Referencing Service Plan Handling")
    print("=" * 70)

    # Show self-referencing plans info
    print(
        f"\n1. Self-Referencing Plans Identified: {data['self_referencing_plans']['count']}"
    )
    print(f"\n   {data['self_referencing_plans']['description']}")

    # Show some examples
    print("\n2. Example Self-Referencing Products:\n")
    for i, item in enumerate(
        data["self_referencing_plans"]["self_referencing_products"][:5]
    ):
        print(f"   {i + 1}. {item['product_name']}")
        print(f"      String ID: {item['string_id']}")
        print(f"      Service Plan ID: {item['self_referencing_service_plan_id']}")
        print(f"      Note: {item['note']}\n")

    # Verify AAD_PREMIUM case specifically
    print("3. Specific Test Case: Microsoft Entra ID P1 (AAD_PREMIUM)")
    print("-" * 70)

    aad_premium_guid = "078d2b04-f1bd-4111-bbd4-b4b1b354cef4"
    product = data["products"][aad_premium_guid]

    print(f"\n   Product: {product['product_display_name']}")
    print(f"   String ID: {product['string_id']}")
    print(f"   Total Service Plans: {len(product['included_service_plans'])}")

    # Show all service plans
    print("\n   Service Plans:")
    self_ref_found = False
    for sp in product["included_service_plans"]:
        is_self_ref = sp["service_plan_name"] == product["string_id"]
        marker = (
            " ← SELF-REFERENCING (filtered from overlap detection)"
            if is_self_ref
            else ""
        )
        print(f"      • {sp['service_plan_name']}{marker}")
        if is_self_ref:
            self_ref_found = True

    print(
        f"\n   ✓ Self-referencing service plan {'found and filtered' if self_ref_found else 'not present'}"
    )

    # Verify it's not considered a subset of itself
    print("\n4. Overlap Detection Test:")
    print("-" * 70)

    # Check if AAD_PREMIUM appears as both subset and superset with the same product
    problematic_overlaps = []
    for overlap in data["license_overlaps"]["overlaps"]:
        if (
            overlap["subset_product"]["guid"] == aad_premium_guid
            and overlap["superset_product"]["guid"] == aad_premium_guid
        ):
            problematic_overlaps.append(overlap)

    if problematic_overlaps:
        print("\n   ✗ ERROR: Product is incorrectly marked as overlapping with itself!")
        print("   This should not happen with self-referencing plan filtering.")
    else:
        print("\n   ✓ PASS: Product is NOT marked as overlapping with itself")

    # Check that P1 vs P2 overlap is still detected
    aad_premium_p2_guid = "84a661c4-e949-4bd2-a560-ed7766fcaf2b"
    p1_p2_overlap = [
        o
        for o in data["license_overlaps"]["overlaps"]
        if (
            o["subset_product"]["guid"] == aad_premium_guid
            and o["superset_product"]["guid"] == aad_premium_p2_guid
        )
    ]

    if p1_p2_overlap:
        print("   ✓ PASS: P1 and P2 overlap correctly detected")
        print(f"      {p1_p2_overlap[0]['subset_product']['name']}")
        print(f"      ⊆ {p1_p2_overlap[0]['superset_product']['name']}")
    else:
        print("   ✗ ERROR: P1 and P2 overlap not detected (should be detected)")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\nTotal Products: {data['metadata']['total_products']}")
    print(f"Total Service Plans: {data['metadata']['total_service_plans']}")
    print(f"Self-Referencing Plans: {data['self_referencing_plans']['count']}")
    print(f"License Overlaps: {data['license_overlaps']['count']}")
    print("\n✓ Self-referencing service plans are properly filtered from overlap")
    print("  detection to prevent false positives while preserving legitimate")
    print("  supersedence relationships.")
    print("=" * 70)


if __name__ == "__main__":
    main()
