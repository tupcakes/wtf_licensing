from fastapi import Depends

from src.routers.api import api_router
from src.routers.route_tags import Tags
from src.services.license_data_service import LicenseDataService

router = api_router.initRouter()


# setup global services
ms_licensing = None


def get_ms_licensing_service() -> LicenseDataService:
    """Get the database service instance."""
    global ms_licensing
    if ms_licensing is None:
        ms_licensing = LicenseDataService()
    return ms_licensing


@router.get("/licenses/sku/{sku}", tags=[Tags.LICENSING], name="Get License by SKU")
async def get_license_by_sku(
    sku: str, ms_licensing: LicenseDataService = Depends(get_ms_licensing_service)
):
    """Get license information by SKU."""
    # Check if data is loaded
    if not ms_licensing.get_all_products():
        return {
            "error": "License data not loaded yet. Please wait for app startup to complete."
        }

    license_data = ms_licensing.get_product_by_string_id(sku)

    if not license_data:
        return {"error": f"License with SKU '{sku}' not found"}

    return license_data
