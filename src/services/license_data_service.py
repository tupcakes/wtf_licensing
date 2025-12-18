"""
O365 License Data Service - Singleton

This service downloads the Microsoft licensing CSV, parses all product SKUs and
service plans, identifies supersedence relationships, and generates simplified
JSON data where each product includes arrays of licenses it supersedes and is
superseded by.

Usage:
    service = LicenseDataService()
    service.generate_license_data(use_local=False)
    service.export_to_json("output.json")
"""

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set
import aiohttp
import aiofiles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LicenseDataService:
    """Singleton service for managing O365 license data."""

    _instance = None
    _initialized = False

    # Configuration constants
    CSV_URL = "https://download.microsoft.com/download/e/3/e/e3e9faf2-f28b-490a-9ada-c6089a1fc5b0/Product%20names%20and%20service%20plan%20identifiers%20for%20licensing.csv"

    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super(LicenseDataService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the service (only runs once due to singleton)."""
        if not self._initialized:
            self.products: Dict[str, Dict[str, Any]] = {}
            self.metadata: Dict[str, Any] = {}
            self._expanded_cache: Dict[str, List[str]] = {}
            self._service_plan_name_to_product_guid: Dict[str, str] = {}
            self._initialized = True
            logger.info("LicenseDataService initialized")

    async def download_csv(self, url: str, output_path: Path) -> None:
        """
        Download the license CSV from Microsoft.

        Args:
            url: The URL to download from
            output_path: Path where the CSV should be saved
        """
        logger.info(f"Downloading CSV from {url}...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    content = await response.read()
                    async with aiofiles.open(output_path, "wb") as f:
                        await f.write(content)
            logger.info(f"Downloaded to {output_path}")
        except Exception as e:
            logger.error(f"Error downloading CSV: {e}")
            raise

    async def parse_csv(self, csv_path: Path) -> Dict[str, Dict[str, Any]]:
        """
        Parse the license CSV and build product structure.

        Args:
            csv_path: Path to the CSV file

        Returns:
            Dictionary of products keyed by GUID
        """
        products: Dict[str, Dict[str, Any]] = {}

        logger.info("Parsing CSV and building license structure...")
        logger.info("  (filtering out self-referencing service plans...)")

        async with aiofiles.open(csv_path, "r", encoding="utf-8-sig") as csvfile:
            content = await csvfile.read()
            reader = csv.DictReader(content.splitlines())

            for row in reader:
                product_name = row["Product_Display_Name"].strip()
                string_id = row["String_Id"].strip()
                guid = row["GUID"].strip()

                service_plan_name = row["Service_Plan_Name"].strip()
                service_plan_id = row["Service_Plan_Id"].strip()
                service_plan_friendly_name = row[
                    "Service_Plans_Included_Friendly_Names"
                ].strip()

                if guid not in products:
                    products[guid] = {
                        "guid": guid,
                        "product_display_name": product_name,
                        "string_id": string_id,
                        "included_service_plans": [],
                        "supersedes": [],
                        "superseded_by": [],
                    }

                # Filter out self-referencing service plans
                if service_plan_name != string_id:
                    service_plan_entry = {
                        "service_plan_name": service_plan_name,
                        "service_plan_id": service_plan_id,
                        "service_plan_friendly_name": service_plan_friendly_name,
                    }
                    products[guid]["included_service_plans"].append(service_plan_entry)

        return products

    def _get_expanded_service_plans(
        self,
        product_guid: str,
        products: Dict[str, Dict[str, Any]],
        service_plan_name_to_guid: Dict[str, str],
        expanded_cache: Dict[str, List[str]],
        visited_products: Set[str],
    ) -> List[str]:
        """
        Recursively expand service plans to include transitive relationships.

        Args:
            product_guid: GUID of the product to expand
            products: Dictionary of all products
            service_plan_name_to_guid: Mapping of service plan names to product GUIDs
            expanded_cache: Cache of already expanded products
            visited_products: Set of products already visited (to prevent cycles)

        Returns:
            List of all service plan IDs (direct and transitive)
        """
        if product_guid in expanded_cache:
            return expanded_cache[product_guid]

        if product_guid in visited_products:
            return []

        visited_products.add(product_guid)

        all_plans: Set[str] = set()
        product = products[product_guid]

        for service_plan in product["included_service_plans"]:
            plan_id = service_plan["service_plan_id"]
            plan_name = service_plan["service_plan_name"]

            all_plans.add(plan_id)

            # If this service plan name references another product, expand it
            if plan_name in service_plan_name_to_guid:
                referenced_product_guid = service_plan_name_to_guid[plan_name]

                if referenced_product_guid != product_guid:
                    expanded_plans = self._get_expanded_service_plans(
                        referenced_product_guid,
                        products,
                        service_plan_name_to_guid,
                        expanded_cache,
                        visited_products.copy(),
                    )
                    all_plans.update(expanded_plans)

        expanded_cache[product_guid] = list(all_plans)
        return list(all_plans)

    def add_supersedence_relationships(
        self, products: Dict[str, Dict[str, Any]]
    ) -> None:
        """
        Analyze and add supersedence relationships between products.

        A product supersedes another if it contains all of the other's service plans.

        Args:
            products: Dictionary of all products
        """
        logger.info("Analyzing supersedence relationships...")
        logger.info("  (expanding transitive service plan relationships...)")

        # Build mapping of service plan names to product GUIDs
        service_plan_name_to_product_guid = {}
        for guid, product in products.items():
            string_id = product["string_id"]
            service_plan_name_to_product_guid[string_id] = guid

        # Calculate expanded service plans for each product
        expanded_cache = {}
        product_service_plans = {}

        logger.info("  (calculating expanded service plans for each product...)")
        for guid in products.keys():
            visited = set()
            expanded_plans = self._get_expanded_service_plans(
                guid,
                products,
                service_plan_name_to_product_guid,
                expanded_cache,
                visited,
            )
            product_service_plans[guid] = set(expanded_plans)

        # Compare products to find supersedence relationships
        logger.info("  (comparing products to find supersedence...)")
        product_list = list(products.keys())
        total_comparisons = (len(product_list) * (len(product_list) - 1)) // 2
        comparisons_done = 0
        last_progress_update = 0

        for i in range(len(product_list)):
            guid1 = product_list[i]
            product1 = products[guid1]
            plans1 = product_service_plans[guid1]

            for j in range(i + 1, len(product_list)):
                guid2 = product_list[j]
                product2 = products[guid2]
                plans2 = product_service_plans[guid2]

                comparisons_done += 1
                percent_complete = int((comparisons_done / total_comparisons) * 100)
                if percent_complete >= last_progress_update + 10:
                    logger.info(f"    Progress: {percent_complete}% complete...")
                    last_progress_update = percent_complete

                # Check if product1 is a subset of product2
                if len(plans1) > 0 and plans1.issubset(plans2):
                    products[guid1]["superseded_by"].append(
                        {
                            "guid": guid2,
                            "string_id": product2["string_id"],
                            "name": product2["product_display_name"],
                        }
                    )
                    products[guid2]["supersedes"].append(
                        {
                            "guid": guid1,
                            "string_id": product1["string_id"],
                            "name": product1["product_display_name"],
                        }
                    )

                # Check if product2 is a subset of product1
                if len(plans2) > 0 and plans2.issubset(plans1):
                    products[guid2]["superseded_by"].append(
                        {
                            "guid": guid1,
                            "string_id": product1["string_id"],
                            "name": product1["product_display_name"],
                        }
                    )
                    products[guid1]["supersedes"].append(
                        {
                            "guid": guid2,
                            "string_id": product2["string_id"],
                            "name": product2["product_display_name"],
                        }
                    )

        # Apply known upgrade patterns (e.g., E3 -> E5)
        logger.info("  (applying known license upgrade patterns...)")
        self._apply_upgrade_patterns(products)

    def _apply_upgrade_patterns(self, products: Dict[str, Dict[str, Any]]) -> None:
        """
        Apply known upgrade patterns where higher-tier licenses supersede lower-tier ones.

        This handles cases where Microsoft uses different service plan IDs for the same
        feature at different license levels (e.g., STREAM_O365_E3 vs STREAM_O365_E5).

        Args:
            products: Dictionary of all products
        """
        # Define known upgrade patterns: (base_pattern, upgrade_pattern)
        upgrade_patterns = [
            # Microsoft 365 E3 -> E5
            ("SPE_E3", "SPE_E5"),
            # Office 365 E3 -> E5
            ("ENTERPRISEPACK", "ENTERPRISEPREMIUM"),
            # Microsoft 365 Business Basic -> Standard -> Premium
            ("O365_BUSINESS_ESSENTIALS", "O365_BUSINESS_PREMIUM"),
            ("SMB_BUSINESS", "O365_BUSINESS_PREMIUM"),
            ("SPB", "O365_BUSINESS_PREMIUM"),
            # Microsoft 365 A3 -> A5 (Education)
            ("M365EDU_A3_FACULTY", "M365EDU_A5_FACULTY"),
            ("M365EDU_A3_STUDENT", "M365EDU_A5_STUDENT"),
            # EMS E3 -> E5
            ("EMS", "EMSPREMIUM"),
            # Microsoft 365 F1 -> F3
            ("M365_F1", "SPE_F1"),
        ]

        # Build a reverse lookup: string_id -> guid
        string_id_to_guid = {prod["string_id"]: guid for guid, prod in products.items()}

        for base_string_id, upgrade_string_id in upgrade_patterns:
            if (
                base_string_id in string_id_to_guid
                and upgrade_string_id in string_id_to_guid
            ):
                base_guid = string_id_to_guid[base_string_id]
                upgrade_guid = string_id_to_guid[upgrade_string_id]

                base_product = products[base_guid]
                upgrade_product = products[upgrade_guid]

                # Check if this relationship doesn't already exist
                already_supersedes = any(
                    s["guid"] == base_guid for s in upgrade_product["supersedes"]
                )

                if not already_supersedes:
                    # Add the upgrade relationship
                    upgrade_product["supersedes"].append(
                        {
                            "guid": base_guid,
                            "string_id": base_product["string_id"],
                            "name": base_product["product_display_name"],
                        }
                    )
                    base_product["superseded_by"].append(
                        {
                            "guid": upgrade_guid,
                            "string_id": upgrade_product["string_id"],
                            "name": upgrade_product["product_display_name"],
                        }
                    )
                    logger.info(
                        f"    Applied upgrade pattern: {upgrade_product['product_display_name']} "
                        f"supersedes {base_product['product_display_name']}"
                    )

    async def generate_license_data(
        self,
        use_local: bool = False,
        local_csv_path: str | None = None,
        output_json_path: str | None = None,
    ) -> Dict[str, Any]:
        """
        Generate the complete license data structure.

        Args:
            use_local: Use local CSV file instead of downloading
            local_csv_path: Path to local CSV file (if use_local=True)
            output_json_path: Optional path to export JSON immediately

        Returns:
            Complete license data dictionary with products and metadata
        """
        logger.info("")
        logger.info("=" * 64)
        logger.info("  O365 License Data Generator - Simplified Structure")
        logger.info("=" * 64)
        logger.info("")

        # Determine CSV path
        if use_local:
            if local_csv_path is None:
                # Default to tests directory
                csv_path = (
                    Path(__file__).parent.parent.parent
                    / "tests"
                    / "Product names and service plan identifiers for licensing.csv"
                )
            else:
                csv_path = Path(local_csv_path)

            if not csv_path.exists():
                raise FileNotFoundError(f"Local CSV file not found at {csv_path}")

            logger.info(f"Using local CSV file: {csv_path}")
        else:
            csv_path = Path(__file__).parent.parent.parent / "o365_licenses_temp.csv"
            await self.download_csv(self.CSV_URL, csv_path)

        # Parse CSV and build product structure
        self.products = await self.parse_csv(csv_path)

        # Add supersedence relationships
        self.add_supersedence_relationships(self.products)

        # Calculate statistics
        total_supersedes = sum(
            len(product["supersedes"]) for product in self.products.values()
        )

        # Build metadata
        self.metadata = {
            "total_products": len(self.products),
            "total_supersedence_relationships": total_supersedes,
            "source_url": self.CSV_URL,
            "description": (
                "Simplified O365 license structure with embedded supersedence relationships. "
                "Each product includes arrays of licenses it supersedes and is superseded by."
            ),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        license_data = {"products": self.products, "metadata": self.metadata}

        # Clean up temporary CSV if downloaded
        if not use_local and csv_path.exists():
            csv_path.unlink()
            logger.info("Temporary CSV file cleaned up.")

        # Print summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Products: {len(self.products)}")
        logger.info(f"Total Supersedence Relationships: {total_supersedes}")
        logger.info("=" * 60)
        logger.info("")
        logger.info("[SUCCESS] Simplified license data generated successfully!")
        logger.info("")

        # Export to JSON if path provided
        if output_json_path:
            await self.export_to_json(output_json_path)

        return license_data

    async def load_license_data_from_file(self, json_path: str | Path) -> None:
        """
        Load license data from a JSON file.

        Args:
            json_path: Path to the JSON file to load
        """
        json_path = Path(json_path)

        if not json_path.exists():
            raise FileNotFoundError(f"JSON file not found at {json_path}")

        logger.info(f"Loading license data from {json_path}...")

        async with aiofiles.open(json_path, "r", encoding="utf-8") as f:
            content = await f.read()
            license_data = json.loads(content)

        self.products = license_data.get("products", {})
        self.metadata = license_data.get("metadata", {})

        logger.info(f"Loaded {len(self.products)} products from cache")

    async def export_to_json(self, output_path: str | Path) -> None:
        """
        Export the license data to a JSON file.

        Args:
            output_path: Path where JSON should be saved
        """
        if not self.products:
            await self.generate_license_data(
                local_csv_path=self.CSV_URL,
            )
            # raise RuntimeError(
            #     "No license data available. Call generate_license_data() first."
            # )

        output_path = Path(output_path)

        license_data = {"products": self.products, "metadata": self.metadata}

        logger.info(f"Writing simplified license data to {output_path}...")

        async with aiofiles.open(output_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(license_data, indent=2, ensure_ascii=False))

        file_size_mb = output_path.stat().st_size / (1024 * 1024)

        logger.info("")
        logger.info(f"Output file: {output_path}")
        logger.info(f"File size: {file_size_mb:.2f} MB")

    def get_product_by_guid(self, guid: str) -> Dict[str, Any] | None:
        """Get a product by its GUID."""
        return self.products.get(guid)

    async def get_product_by_string_id(self, string_id: str) -> Dict[str, Any] | None:
        """Get a product by its string ID."""
        for product in self.products.values():
            if product["string_id"] == string_id:
                return product
        return None

    async def get_all_products(self) -> Dict[str, Dict[str, Any]]:
        """Get all products."""
        return self.products

    async def get_metadata(self) -> Dict[str, Any]:
        """Get metadata about the license data."""
        return self.metadata
