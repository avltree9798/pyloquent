"""FastAPI integration example for Pyloquent."""

from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import EmailStr

from pyloquent import ConnectionManager, Model

app = FastAPI(title="Pyloquent FastAPI Example")
manager = ConnectionManager()


class User(Model):
    """User model."""

    __table__ = "users"
    __fillable__ = ["name", "email", "is_active"]

    id: Optional[int] = None
    name: str
    email: EmailStr
    is_active: bool = True


class UserCreate(BaseModel):
    """User creation schema."""

    name: str
    email: EmailStr
    is_active: bool = True


class UserUpdate(BaseModel):
    """User update schema."""

    name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


class Post(Model):
    """Post model."""

    __table__ = "posts"
    __fillable__ = ["user_id", "title", "content", "is_published"]

    id: Optional[int] = None
    user_id: int
    title: str
    content: Optional[str] = None
    is_published: bool = False

    def author(self):
        return self.belongs_to(User)


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    # Configure database connection
    manager.add_connection(
        "default",
        {
            "driver": "sqlite",
            "database": "example.db",
        },
        default=True,
    )

    await manager.connect()

    # Create tables if they don't exist
    conn = manager.connection()
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            is_published BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )


@app.on_event("shutdown")
async def shutdown():
    """Close database connection on shutdown."""
    await manager.disconnect()


# User endpoints
@app.get("/users", response_model=List[User])
async def list_users(skip: int = 0, limit: int = 100):
    """List all users."""
    users = await User.offset(skip).limit(limit).get()
    return users


@app.get("/users/{user_id}", response_model=User)
async def get_user(user_id: int):
    """Get a specific user by ID."""
    try:
        user = await User.find_or_fail(user_id)
        return user
    except Exception:
        raise HTTPException(status_code=404, detail="User not found")


@app.post("/users", response_model=User)
async def create_user(user: UserCreate):
    """Create a new user."""
    try:
        new_user = await User.create(user.model_dump())
        return new_user
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/users/{user_id}", response_model=User)
async def update_user(user_id: int, user_update: UserUpdate):
    """Update a user."""
    try:
        user = await User.find_or_fail(user_id)

        # Update only provided fields
        update_data = user_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(user, key, value)

        await user.save()
        return user
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/users/{user_id}")
async def delete_user(user_id: int):
    """Delete a user."""
    try:
        user = await User.find_or_fail(user_id)
        await user.delete()
        return {"message": "User deleted successfully"}
    except Exception:
        raise HTTPException(status_code=404, detail="User not found")


# Post endpoints
@app.get("/posts", response_model=List[Post])
async def list_posts(user_id: Optional[int] = None, published_only: bool = False):
    """List posts with optional filtering."""
    query = Post.query()

    if user_id:
        query = query.where("user_id", user_id)

    if published_only:
        query = query.where("is_published", True)

    posts = await query.order_by("created_at", "desc").get()
    return posts


@app.get("/posts/{post_id}", response_model=Post)
async def get_post(post_id: int):
    """Get a specific post."""
    try:
        post = await Post.find_or_fail(post_id)
        return post
    except Exception:
        raise HTTPException(status_code=404, detail="Post not found")


@app.post("/posts", response_model=Post)
async def create_post(user_id: int, title: str, content: str = ""):
    """Create a new post."""
    try:
        # Verify user exists
        await User.find_or_fail(user_id)

        post = await Post.create(
            {"user_id": user_id, "title": title, "content": content}
        )
        return post
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Relationship endpoints
@app.get("/users/{user_id}/posts")
async def get_user_posts(user_id: int):
    """Get all posts for a user."""
    try:
        user = await User.find_or_fail(user_id)
        posts = await user.posts().get()
        return posts
    except Exception:
        raise HTTPException(status_code=404, detail="User not found")


@app.get("/posts/{post_id}/author")
async def get_post_author(post_id: int):
    """Get the author of a post."""
    try:
        post = await Post.find_or_fail(post_id)
        author = await post.author().get()
        return author
    except Exception:
        raise HTTPException(status_code=404, detail="Post or author not found")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
