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
├── app
│   ├── config                                --  app configs
│   │   ├── exception_handlers.py        
│   │   ├── settings.py                  
│   ├── controllers                           --  api routes by objects
│   │   ├── order_controller.py 
│   └── models                                --  orm and pydantic models
│   │   ├── order.py
│   │   ├── address.py
│   │   ├── base.py
│   │   ├── pageable.py
│   └── repository                            --  database queries
│   │   ├── order_repository.py
│   └── services                              --  business logic / data transformation
│   │   ├── order_service.py
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
   - Poetry for Python dependency management
   - Python 3.9 or higher

2. Clone the repository and navigate to the project directory:
   ```bash
   git clone <repository-url>
   cd ass-api
   ```

### Database Setup

1. **Using Docker (recommended)**:
   ```bash
   # Start PostgreSQL container
   docker-compose -f docker-compose.local.yml up fast-api-postgres -d
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
   make startd
   ```

2. **Without tracing**:
   ```bash
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

