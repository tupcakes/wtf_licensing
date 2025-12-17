# O365 License Data Generator

This script generates a comprehensive JSON file containing all Office 365 licenses, their SKUs, identifiers, and supersedence relationships.

## Purpose

The generated JSON file is designed to help identify when users are "doubled up" on licenses by:
- Capturing ALL O365 product SKUs with their GUIDs and String IDs
- Mapping all service plans included in each product
- Identifying supersedence relationships (which licenses contain others)
- Finding overlapping licenses where one product contains all service plans of another

## Usage

### Run with downloaded data (recommended for production)
```bash
python3 generate_license_data.py
```

This will:
1. Download the latest CSV from Microsoft
2. Parse all license data
3. Generate `o365_licenses_complete.json`

### Run with local test data
```bash
python3 generate_license_data.py --local
```

This uses the pre-downloaded CSV file in `tests/` directory for testing.

## Output Structure

The generated `o365_licenses_complete.json` contains:

### 1. `products` (610 products)
Each product is keyed by its GUID and contains:
- `product_display_name`: Human-readable name
- `string_id`: Product SKU string identifier
- `guid`: Product SKU GUID
- `included_service_plans`: Array of all service plans included in this product
  - `service_plan_name`: Technical name
  - `service_plan_id`: GUID identifier
  - `service_plan_friendly_name`: Human-readable name

**Note:** Some products include a service plan with the same name as the product's `string_id`. This represents the "core" license itself and is filtered from overlap detection (see section on Self-Referencing Plans).

**Example:**
```json
{
  "84a661c4-e949-4bd2-a560-ed7766fcaf2b": {
    "product_display_name": "Microsoft Entra ID P2",
    "string_id": "AAD_PREMIUM_P2",
    "guid": "84a661c4-e949-4bd2-a560-ed7766fcaf2b",
    "included_service_plans": [
      {
        "service_plan_name": "AAD_PREMIUM",
        "service_plan_id": "41781fb2-bc02-4b7c-bd55-b576c07bb09d",
        "service_plan_friendly_name": "Microsoft Entra ID P1"
      },
      ...
    ]
  }
}
```

### 2. `service_plans` (769 unique service plans)
Each service plan is keyed by its ID and contains:
- `service_plan_id`: GUID identifier
- `service_plan_name`: Technical name
- `service_plan_friendly_name`: Human-readable name
- `included_in_products`: Array of product GUIDs that include this service plan

**Example:**
```json
{
  "41781fb2-bc02-4b7c-bd55-b576c07bb09d": {
    "service_plan_id": "41781fb2-bc02-4b7c-bd55-b576c07bb09d",
    "service_plan_name": "AAD_PREMIUM",
    "service_plan_friendly_name": "Microsoft Entra ID P1",
    "included_in_products": [
      "078d2b04-f1bd-4111-bbd4-b4b1b354cef4",
      "84a661c4-e949-4bd2-a560-ed7766fcaf2b",
      ...
    ]
  }
}
```

### 3. `supersedence_map`
Quick lookup for comparing products. Each entry contains:
- `product_name`: Display name
- `string_id`: SKU identifier
- `service_plan_ids`: Sorted array of all service plan IDs
- `service_plan_count`: Total count

**Use case:** Quickly compare two products to see which service plans they have in common.

### 4. `self_referencing_plans` (150 products affected)
Identifies products where a service plan name matches the product's `string_id`. These represent the "core" license itself.

**Structure:**
- `count`: Number of products with self-referencing plans
- `description`: Explanation of what these are
- `self_referencing_products`: Array of products with self-referencing plans

**Important:** These self-referencing service plans are **excluded from overlap detection** to prevent false positives. Without this filtering, a product like "Microsoft Entra ID P1" (AAD_PREMIUM) could be incorrectly flagged as superseded by another product when you're actually checking the core license itself.

**Example:**
```json
{
  "count": 150,
  "description": "Products where a service plan name matches the product's string_id...",
  "self_referencing_products": [
    {
      "product_guid": "078d2b04-f1bd-4111-bbd4-b4b1b354cef4",
      "product_name": "Microsoft Entra ID P1",
      "string_id": "AAD_PREMIUM",
      "self_referencing_service_plan_id": "41781fb2-bc02-4b7c-bd55-b576c07bb09d",
      "note": "This service plan represents the core product license itself"
    }
  ]
}
```

### 5. `license_overlaps` (11,203 overlaps found)
Identifies all cases where one product completely contains another product's service plans.

**Example:**
**Example:**
```json
{
  "count": 11203,
  "overlaps": [
    {
      "subset_product": {
        "guid": "078d2b04-f1bd-4111-bbd4-b4b1b354cef4",
        "string_id": "AAD_PREMIUM",
        "name": "Microsoft Entra ID P1"
      },
      "superset_product": {
        "guid": "84a661c4-e949-4bd2-a560-ed7766fcaf2b",
        "string_id": "AAD_PREMIUM_P2",
        "name": "Microsoft Entra ID P2"
      },
      "note": "All service plans in subset_product are included in superset_product"
    }
  ]
}
```

**Use case:** If a user has both "subset_product" and "superset_product" assigned, they're paying for overlapping features.

**Note:** Overlap detection automatically excludes self-referencing service plans to avoid false positives.

### 6. `metadata`
Contains statistics and source information.

## Data Source

All data comes from Microsoft's official licensing reference:
```
https://download.microsoft.com/download/e/3/e/e3e9faf2-f28b-490a-9ada-c6089a1fc5b0/Product%20names%20and%20service%20plan%20identifiers%20for%20licensing.csv
```

## Output File

- **File**: `o365_licenses_complete.json`
- **Size**: ~7.9 MB
- **Format**: JSON with 2-space indentation
- **Encoding**: UTF-8

## Important: Self-Referencing Service Plan Filtering

The script automatically identifies and filters **150 products** that have "self-referencing" service plans - where a service plan name matches the product's `string_id`. This is critical for accurate overlap detection.

### Why This Matters

Many O365 products include a service plan that represents the core product license itself. For example:
- **Microsoft Entra ID P1** (string_id: `AAD_PREMIUM`) includes a service plan named `AAD_PREMIUM`
- **Microsoft 365 Audio Conferencing** (string_id: `MCOMEETADV`) includes a service plan named `MCOMEETADV`

Without filtering these self-referencing plans, the overlap detection could incorrectly flag a product as superseded by another product when you're actually checking the core license itself. This would lead to **false positives** where you might accidentally remove the very license you're trying to check.

### How It's Handled

1. All self-referencing service plans are identified and documented in the `self_referencing_plans` section
2. These plans are **excluded** from overlap detection calculations
3. Legitimate supersedence relationships (like P1 ⊆ P2) are still correctly detected
4. The original product data retains all service plans for reference

## License Comparison Example

To check if a user has duplicate licenses:

```python
import json

# Load the data
with open('o365_licenses_complete.json') as f:
    data = json.load(f)

# Get user's assigned licenses (GUIDs)
user_licenses = [
    "078d2b04-f1bd-4111-bbd4-b4b1b354cef4",  # Entra ID P1
    "84a661c4-e949-4bd2-a560-ed7766fcaf2b"   # Entra ID P2
]

# Check for overlaps
for overlap in data['license_overlaps']['overlaps']:
    subset_guid = overlap['subset_product']['guid']
    superset_guid = overlap['superset_product']['guid']
    
    if subset_guid in user_licenses and superset_guid in user_licenses:
        print(f"DUPLICATE: User has both:")
        print(f"  - {overlap['subset_product']['name']}")
        print(f"  - {overlap['superset_product']['name']}")
        print(f"  The second license includes all features of the first!")
```

## Statistics

- **Total Products**: 610
- **Total Service Plans**: 769
- **Self-Referencing Plans**: 150 (automatically filtered from overlap detection)
- **License Overlaps**: 11,203 supersedence relationships identified

## Verification

To verify the self-referencing plan handling is working correctly:

```bash
python3 verify_self_referencing_fix.py
```

This will show:
- Which products have self-referencing service plans
- That these plans are properly filtered from overlap detection
- That legitimate supersedence relationships are still detected

## Requirements

- Python 3.6+
- Standard library only (no external dependencies)
