# O365 License Data Service

Python API for querying MS O365 licensing relationships

## API Endpoints Availble

- /api/license/metadata
  - Returns data source, last refresh time, etc...
- /api/license/superseded/{sku}
  - Returns the supersedence relationships for a particular license sku
- /api/license/all
  - Returns all license data.

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd wtf_licensing

# Run directly
uv run fastapi dev main.py
```

## Data Structure

Each product in the generated data includes:

```json
{
  "guid": "product-guid",
  "product_display_name": "Office 365 E3",
  "string_id": "ENTERPRISEPACK",
  "included_service_plans": [
    {
      "service_plan_name": "EXCHANGE_S_ENTERPRISE",
      "service_plan_id": "plan-guid",
      "service_plan_friendly_name": "Exchange Online (Plan 2)"
    }
  ],
  "supersedes": [
    {
      "guid": "other-product-guid",
      "string_id": "STANDARDPACK",
      "name": "Office 365 E1"
    }
  ],
  "superseded_by": []
}
```

## How Supersedence Works

A product **supersedes** another product if it contains all of that product's service plans (including transitive service plans). For example:

- Office 365 E5 supersedes Office 365 E3 (because E5 includes all E3 plans plus more)
- Office 365 E3 supersedes Office 365 E1 (because E3 includes all E1 plans plus more)

The service automatically:

1. Expands all service plan references recursively
2. Compares all products pairwise
3. Identifies subset relationships
4. Builds bidirectional supersedence arrays
