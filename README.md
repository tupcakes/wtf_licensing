# O365 License Data Service

Python singleton service for managing Microsoft O365 license data with supersedence relationships.

## Features

- **Singleton Pattern**: Ensures only one instance of the service exists
- **Data Caching**: Generated license data is cached in the singleton instance
- **Supersedence Analysis**: Automatically identifies which licenses supersede others based on service plan inclusion
- **Flexible Data Source**: Download from Microsoft or use local CSV file
- **JSON Export**: Export processed data to JSON format

## Installation

This project uses Python 3.14+. No external dependencies required (uses only standard library).

```bash
# Clone the repository
git clone <repository-url>
cd wtf_licensing

# Run directly
python main.py
```

## Usage

### Command Line

```bash
# Download latest data from Microsoft and generate JSON
python main.py

# Use local CSV file
python main.py --use-local

# Specify local CSV path and output location
python main.py --use-local --local-csv path/to/file.csv --output custom_output.json

# See all options
python main.py --help
```

### As a Python Service

```python
from src.services import LicenseDataService

# Get singleton instance
service = LicenseDataService()

# Generate license data (downloads from Microsoft by default)
license_data = service.generate_license_data()

# Or use local CSV file
license_data = service.generate_license_data(
    use_local=True,
    local_csv_path="tests/Product names and service plan identifiers for licensing.csv"
)

# Export to JSON
service.export_to_json("output.json")

# Query the data
metadata = service.get_metadata()
print(f"Total products: {metadata['total_products']}")

# Get specific product by GUID
product = service.get_product_by_guid("some-guid-here")

# Get product by string ID
product = service.get_product_by_string_id("ENTERPRISEPACK")

# Get all products
all_products = service.get_all_products()

# Access the singleton again (returns same instance with cached data)
service2 = LicenseDataService()
assert service is service2  # True - same instance
```

## Service Methods

### Core Methods

- `generate_license_data(use_local=False, local_csv_path=None, output_json_path=None)` - Generate complete license data structure
- `export_to_json(output_path)` - Export license data to JSON file

### Query Methods

- `get_product_by_guid(guid)` - Get a product by its GUID
- `get_product_by_string_id(string_id)` - Get a product by its string ID
- `get_all_products()` - Get all products
- `get_metadata()` - Get metadata about the license data

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

## Original PowerShell Script

The original PowerShell script is preserved in `original/Generate-LicenseData-Simple.ps1` for reference.

## License

See LICENSE file for details.
