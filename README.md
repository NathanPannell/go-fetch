# go-fetch
A semantic search system designed with scalability first

## Getting Started

### Prerequisites
- Docker and Docker Compose

### Running the App
1. Clone the repository
2. Run `docker compose up --build`
3. The API will be available at `http://localhost:8080`

### API Endpoints
- `GET /items` - List all items
- `POST /items` - Create a new item
- `GET /items/<id>` - Get a specific item
- `PUT /items/<id>` - Update an item
- `DELETE /items/<id>` - Delete an item
