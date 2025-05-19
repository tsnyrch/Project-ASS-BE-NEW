# Fast Api / Docker / Poetry 

## Contents
1. [Requirements](#requirements)
2. [Best Practices](#best-practices)
3. [File structure](#file-structure)
4. [Setup and Running](#setup-and-running)
5. [Quick Start](#quick-start)

## Requirements
 - docker
 - docker compose
 - poetry
 - Python 3.9 or higher
 - PostgreSQL (for local development without Docker)
 - `boto3` (for AWS S3 integration, add via `poetry add boto3`)
 - `Pillow` (for image processing, add via `poetry add Pillow`)

## Best Practices

1. Naming conventions
   1. Every file should have a unique name
   2. Add type to file name outside of models. I believe it helps with search-ability/readability 
      ```
      order_controller, order_service, order_repository
      ```
2. Set custom exception_handler in `main.py` to better format error responses
   ```
      application.add_exception_handler(HTTPException, exh.http_exception_handler)
   ```
3. Use `@cbv` decorator to initialize shared dependencies.
   ```
      @cbv(order_router)
      class OrderController:
          def __init__(self):
              self.order_service = OrderService()
   ```
4. Model files has ORM and pydantic classes for easier updates (Might not be the best solution for all)
   - Schema - request/response object. It uses `BaseSchema.to_orm` to convert to ORM
   - ORM - DB object
5. Here is the [commit](https://github.com/rannysweis/fast-api-docker-poetry/tree/3a075badcf27b7a0e42fb5cc971492fcb7c82d23) before switching to async 



## File structure
```
fast-api-docker-poetry 
├── app                                       --  main application code directory
│   ├── config                                --  app configs
│   │   ├── exception_handlers.py        
│   │   ├── settings.py                  
│   ├── controllers                           --  api routes by objects
│   │   ├── order_controller.py 
│   │   ├── camera_controller.py           --  handles Aravis camera interactions (test, capture)
│   └── models                                --  orm and pydantic models
│   │   ├── order.py
│   │   ├── address.py
│   │   ├── base.py
│   │   ├── pageable.py
│   └── repository                            --  database queries
│   │   ├── order_repository.py
│   └── services                              --  business logic / data transformation
│   │   ├── order_service.py
│   │   ├── cloud_uploader_service.py      --  handles uploading files to cloud storage (e.g., AWS S3)
│   └── utils
│   │   ├── db.py
│   └── main.py
├── migrations/                               --  alembic migrations
├── tests/
│   ├── integrations                          --  test api routes by using TestClient
├── .env
├── .gitignore
├── docker-compose.yml
├── Makefile
├── pyproject.toml
└── alembic.ini
```

## Setup and Running

### Prerequisites

1. Install required software:
   - Docker and Docker Compose for containerized deployment
   - Poetry for Python dependency management (for local development)
   - Python 3.9 or higher (for local development)

2. Clone the repository and navigate to the project directory:
   ```bash
   git clone <repository-url>
   cd ass-api
   ```

### Docker Configuration

The application is configured to run in Docker with the following features:

1. **Volume Mounting**: The entire project directory is mounted into the container, allowing for real-time code changes without rebuilding the image.

2. **Profiles**:
   - `default`: Runs the API and PostgreSQL
   - `tracing`: Adds Jaeger for observability

3. **Environment Variables**:
   - `SET_JUMBO_MTU`: Set to "true" to enable jumbo packet MTU (9000) for camera operations that require high bandwidth
   - `APP_RELOAD`: Set to "true" to enable auto-reload for development
   - `OTEL_SERVICE_NAME`: Service name for OpenTelemetry tracing

### Database Setup

1. **Using Docker (recommended)**:
   ```bash
   # Start PostgreSQL container
   docker-compose up fast-api-postgres -d
   ```

2. **Local PostgreSQL**:
   - Create a database named `fastapi_db`
   - Use default credentials: username `postgres`, password `postgres`

3. **Run Migrations**:
   ```bash
   # With Poetry
   poetry run alembic upgrade head
   ```

4. **Create Admin User**:
   To set up the default admin user for authentication, run:
   ```bash
   # With Poetry
   poetry run python create_admin.py
   ```
   This will create an admin user with the following credentials:
   - Username: `admin`
   - Password: `admin123`

### Starting the Application

#### Using Docker

1. **Full stack with Jaeger tracing**:
   ```bash
   docker-compose --profile tracing up
   # Or using make
   make startd
   ```

2. **Without tracing**:
   ```bash
   docker-compose up
   # Or using make
   make startslimd
   ```

#### Using Poetry (local development)

```bash
# Make sure greenlet is installed for SQLAlchemy async
pip install greenlet

# Start the FastAPI application
make startp
```

### Accessing the Application

- The API will be available at: `http://localhost:8009`
- API documentation (Swagger UI): `http://localhost:8009/docs`
- Jaeger UI (when using tracing): `http://localhost:16686`

### Authentication

The API uses OAuth2 password flow for authentication. To authenticate:

1. **Using Swagger UI**:
   - Go to `http://localhost:8009/docs`
   - Click the "Authorize" button
   - Enter the admin credentials (username: `admin`, password: `admin123`)

2. **Using cURL**:
   ```bash
   curl -X 'POST' \
     'http://localhost:8009/api/users/login' \
     -H 'Content-Type: application/x-www-form-urlencoded' \
     -d 'username=admin&password=admin123'
   ```

3. **Use the returned token** in subsequent requests:
   ```bash
   curl -X 'GET' \
     'http://localhost:8009/api/users' \
     -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
   ```

## Quick Start

1. Start with jaeger tracing using docker
    ```
    make startd
    ```
2. Start with no tracing using docker
    ```
    make startslimd
    ```
3. Test with docker
    ```
    make testd
    ```
4. Start with poetry
    ```
    make startp
    ```
5. Test with poetry
    ```
    make testp
    ```
6. Create admin user
    ```
    poetry run python create_admin.py
    ```
7. Run migrations
    ```
    poetry run alembic upgrade head
    ```

## Key Features

### Camera Control (Aravis Integration)

This application integrates with GenICam compatible cameras using the Aravis library for image acquisition.

- **List and Test Cameras:** 
  - Endpoint: `GET /camera/test`
  - Description: Scans for connected Aravis-compatible cameras and returns a list of found devices with their details (ID, model, vendor, serial). Useful for identifying the `device_id` needed for other operations.

- **Capture Image:**
  - Endpoint: `POST /camera/capture`
  - Description: Triggers an image capture from a specified (or the first available) Aravis camera.
  - Query Parameters:
    - `device_id` (optional, string): The ID of the camera to use (obtained from `/camera/test`). If not provided, the first detected camera is used. It is highly recommended to specify a `device_id` in multi-camera setups or for stable operation.
  - Response: Returns a JSON object containing:
    - `status`: \"success\" or \"error\".
    - `device_id_used`: The ID of the camera from which the image was captured.
    - `image_base64`: Base64 encoded string of the captured image in PNG format (if successful).
    - `image_format`: \"png\".
    - `message` / `error`: Additional information or error details.
  - Dependencies: Uses Aravis for camera communication and Pillow (PIL) for image processing (conversion to PNG).
  - Configuration: Camera parameters (pixel format, exposure, gain) are currently set to camera defaults within the controller but can be configured directly in `app/controllers/camera_controller.py` (see `TODO` comments).

### Cloud Uploader Service (AWS S3)

Provides functionality to upload files and entire folders to AWS S3.

- **Service Class:** `app.services.cloud_uploader_service.CloudUploaderService`
- **Methods:**
  - `upload_file_to_s3(local_file_path: str, bucket_name: str, s3_object_name: Optional[str] = None) -> bool`:
    Uploads a single file to the specified S3 bucket.
  - `upload_folder_to_s3(local_folder_path: str, bucket_name: str, s3_destination_folder: Optional[str] = None) -> dict`:
    Uploads all files from a local folder (recursively) to the S3 bucket, optionally under a specific destination path in S3.
- **Configuration & Dependencies:**
  - Requires the `boto3` library (`poetry add boto3`).
  - AWS Credentials: The service relies on `boto3` to find AWS credentials. Ensure your environment is configured with `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_DEFAULT_REGION` (e.g., via environment variables or a shared credentials file like `~/.aws/credentials`). **Do not hardcode credentials in the source code.**
  - S3 Bucket: You must have an existing S3 bucket.
- **Usage:** This service can be imported and used by other parts of the application (e.g., controllers or other services) to handle file uploads after they are generated or processed.

