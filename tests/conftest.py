import pytest
from pathlib import Path


@pytest.fixture
def tmp_ts_repo(tmp_path):
    """Creates a minimal TypeScript repo for testing."""
    (tmp_path / "package.json").write_text(
        '{"name": "test-api", "dependencies": {"express": "^4"}}'
    )
    types_dir = tmp_path / "src" / "types"
    types_dir.mkdir(parents=True)
    (types_dir / "user.ts").write_text("""
export interface User {
  id: string;
  email: string;
  name: string;
  createdAt: string;
}

export type AuthToken = {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
}

export interface ApiResponse<T> {
  data: T | null;
  error: string | null;
}
""")
    routes_dir = tmp_path / "src" / "routes"
    routes_dir.mkdir(parents=True)
    (routes_dir / "users.ts").write_text("""
import { Router } from 'express';
const router = Router();

router.get('/api/users', async (req, res) => {
  res.json({ data: [], error: null });
});

router.post('/api/users', async (req, res) => {
  const user: User = req.body;
  res.json({ data: user, error: null });
});

router.get('/api/users/:id', async (req, res) => {
  res.json({ data: null, error: null });
});
""")
    return tmp_path


@pytest.fixture
def tmp_python_repo(tmp_path):
    """Creates a minimal Python/FastAPI repo for testing."""
    (tmp_path / "requirements.txt").write_text(
        "fastapi\npydantic\nsqlalchemy\n"
    )
    (tmp_path / "main.py").write_text("""
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

class User(BaseModel):
    id: str
    email: str
    name: str
    created_at: str

class CreateUserRequest(BaseModel):
    email: str
    name: str

@app.get("/api/users/{user_id}")
async def get_user(user_id: str) -> User:
    pass

@app.post("/api/users")
async def create_user(body: CreateUserRequest) -> User:
    pass
""")
    return tmp_path


@pytest.fixture
def tmp_openapi_repo(tmp_path):
    """Creates a repo with an OpenAPI spec."""
    (tmp_path / "package.json").write_text('{"name": "test-api"}')
    (tmp_path / "openapi.yaml").write_text("""
openapi: "3.0.0"
info:
  title: Test API
  version: "1.0"
paths:
  /api/users:
    get:
      summary: List users
      responses:
        "200":
          description: Success
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/UserList"
    post:
      summary: Create user
      requestBody:
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/CreateUserRequest"
      responses:
        "201":
          description: Created
components:
  schemas:
    User:
      type: object
      properties:
        id:
          type: string
        email:
          type: string
        name:
          type: string
    UserList:
      type: array
      items:
        $ref: "#/components/schemas/User"
    CreateUserRequest:
      type: object
      required: [email, name]
      properties:
        email:
          type: string
        name:
          type: string
""")
    return tmp_path


@pytest.fixture
def graph_store(tmp_path):
    """Creates an isolated GraphStore for testing."""
    from upstreamiq.graph.store import GraphStore
    store = GraphStore(db_path=tmp_path / "test.db")
    yield store
    store.close()
