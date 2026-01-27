# O365 License Data Service

Python API for querying MS O365 licensing relationships.

## About

I discovered that MS provides their O365 license relationships in a csv located [here](https://learn.microsoft.com/en-us/entra/identity/users/licensing-service-plan-reference). Something that I'm sure everyone who has had to use O365 is figuring out what license supersedes/includes other products, so I created an api to return the relationships between related MS O365 products.

I did use AI to create the logic for parsing the Microsoft licensing CSV file in license_data_service.py, because lets be honest...even MS' licensing people usually can't make heads or tails out of their own licensing, and I didn't want to have to become a O365 licensing expert. So the use of AI is something to be aware of.

The MS csv data also doesn't explicitly state ALL relationships. For example SPE_E5 should supersede SPE_E3, since it has all the same service plans and more (or at least upgraded versions of the service plans included in SPE_E3). However the CSV file doesn't show that relationship. So I had to setup some special logic with the naming pattens of the skus that infer supersedence in cases like I just described. So YMMV. If you find something not right with the supersedence in the returned data, let me know.

In theory this api can be used in concert with Get-MgUserLicenseDetails and Set-MgUserLicenseDetails to automate cleaning up over licensed users.

## API Endpoints Availble

- /api/license/metadata
  - Returns data source, last refresh time, etc...
- /api/license/sku/{sku}
  - Returns the supersedence relationships for a particular license sku
- /api/license/all
  - Returns all license data.

~~Try it out here (render.com free plan takes about 30 seconds to spin up if idle): <https://wtf-licensing.onrender.com/docs>~~ Currently down.

## Installation

```bash
# Clone the repository
git clone https://github.com/tupcakes/wtf_licensing.git
cd wtf_licensing

# Run directly
uv run fastapi dev main.py
```

## Data Structure

Each product in the generated data includes:

```json
{
  "guid": "6fd2c87f-b296-42f0-b197-1e91e994b900",
  "product_display_name": "Office 365 E3",
  "string_id": "ENTERPRISEPACK",
  "included_service_plans": [
    {
      "service_plan_name": "MESH_AVATARS_FOR_TEAMS",
      "service_plan_id": "dcf9d2f4-772e-4434-b757-77a453cfbc02",
      "service_plan_friendly_name": "Avatars for Teams"
    },
    {
      "service_plan_name": "MESH_AVATARS_ADDITIONAL_FOR_TEAMS",
      "service_plan_id": "3efbd4ed-8958-4824-8389-1321f8730af8",
      "service_plan_friendly_name": "Avatars for Teams (additional)"
    },
    ...and more
  ],
  "supersedes": [
    {
      "guid": "d2dea78b-507c-4e56-b400-39447f4738f8",
      "string_id": "CDSAICAPACITY",
      "name": "AI Builder Capacity add-on"
    },
    {
      "guid": "631d5fb1-a668-4c2a-9427-8830665a742e",
      "string_id": "CDS_FILE_CAPACITY",
      "name": "Common Data Service for Apps File Capacity"
    },
    ...and more
  ]
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

## Building for dev

### Local

Clone the repo.

`uv sync`

`uv run fastapi dev main.py`

### Docker

`sh build.sh`

## Running in prod

### Local

`uv sync`

`uv run fastapi run main.py'

### Docker

`docker compose up -d`
