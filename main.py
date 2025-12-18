import os
from fastapi import FastAPI
from contextlib import asynccontextmanager

from src.routers.api import licensing_api


from src.services.license_data_service import LicenseDataService

# Initialize global services
ms_licensing = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    global ms_licensing

    print("App Startup - Initializing services...")
    print("-" * 60)

    # Initialize Services
    ms_licensing = LicenseDataService()

    # Load or generate license data
    # TODO - force refresh at startup
    # TODO - implement scheduler
    cache_file = "/tmp/o365_licenses.json"
    if os.path.exists(cache_file):
        print(f"Using cached license data: {cache_file}")
        await ms_licensing.load_license_data_from_file(cache_file)
    else:
        print("Downloading fresh license data...")
        await ms_licensing.export_to_json(cache_file)

    print("-" * 60)
    print("App startup complete\n")

    yield
    print("App Shutdown - Cleaning up services...")
    # Perform any necessary cleanup here

    print("App shutdown complete\n")


# initialize FastAPI app
app = FastAPI(
    title="WTF Licensing API",
    summary="",
    description="""
    fill this out later
    """,
    lifespan=lifespan,
)

# Include API routers
app.include_router(licensing_api.router)
