# Views

Views allow you to create different representations of the same data model. This is useful for:

- Creating DTOs (Data Transfer Objects)
- Serializing different versions of the same data
- Hiding sensitive fields in certain contexts

## Basic Usage

```python
from cwtch import dataclass, view

@dataclass
class User:
    name: str
    email: str
    password: str

# Use exclude to hide sensitive fields
@view(User, exclude={"password"})
class PublicUser:
    """Public view without sensitive data"""
    pass

# Create a user
user = User(name="John", email="john@example.com", password="secret")

# Create a view (call as function!)
public_user = user.PublicUser()
print(public_user)
# Output: PublicUser(name='John', email='john@example.com')
```

## Including Specific Fields

Use `include` to specify which fields to include:

```python
from cwtch import dataclass, view

@dataclass
class User:
    name: str
    email: str
    password: str
    created_at: str

@view(User, include={"name", "email"})
class PublicUser:
    pass

user = User(
    name="John",
    email="john@example.com",
    password="secret",
    created_at="2024-01-01"
)
print(user.PublicUser())
# Output: PublicUser(name='John', email='john@example.com')
```

## Excluding Specific Fields

Use `exclude` to remove specific fields:

```python
from cwtch import dataclass, view

@dataclass
class User:
    name: str
    email: str
    password: str

@view(User, exclude={"password"})
class SafeUser:
    pass

user = User(name="John", email="john@example.com", password="secret")
print(user.SafeUser())
# Output: SafeUser(name='John', email='john@example.com')
```

## Named Views

You can give views custom names:

```python
from cwtch import dataclass, view

@dataclass
class User:
    name: str
    email: str
    password: str

@view(User, "PublicProfile")
class PublicProfile:
    """Public profile view"""
    pass

user = User(name="John", email="john@example.com", password="secret")
print(user.PublicProfile().name)  # "John"
```

## Attaching Views to Models

By default, views are attached to the model class. You can disable this:

```python
from cwtch import dataclass, view

@dataclass
class User:
    name: str
    email: str
    password: str = "secret"

@view(User, attach=False)
class PublicUser:
    pass

# Access directly, not via the model
public_user = PublicUser(name="John", email="john@example.com")
```

## View Options

Views inherit options from the base model by default, but you can override them:

```python
from cwtch import dataclass, view

@dataclass
class User:
    name: str
    email: str
    password: str

@view(User, validate=False)
class PublicUser:
    """View that doesn't validate"""
    pass

# Can create with invalid data
user = User(name="John", email="not-an-email", password="secret")
public = user.PublicUser()  # No validation error
```

## Recursive Views

Use `recursive=True` to automatically convert nested models to their views:

```python
from cwtch import dataclass, view

@dataclass
class Address:
    street: str
    city: str
    zip_code: str

@dataclass
class User:
    name: str
    address: Address | None

@view(User, "PublicUser", recursive=True)
class PublicUser:
    pass

# address will be converted to PublicAddress automatically
user = User(name="John", address=Address(street="123 Main St", city="Boston", zip_code="02101"))
print(user.PublicUser().address.street)  # "123 Main St"
```

## Multiple Views

You can create multiple views for the same model:

```python
from cwtch import dataclass, view

@dataclass
class User:
    name: str
    email: str
    password: str
    api_key: str

@view(User, include={"name", "email"})
class PublicUser:
    """Public profile"""
    pass

@view(User, exclude={"password", "api_key"})
class AdminView:
    """Admin view without secrets"""
    pass

user = User(
    name="John",
    email="john@example.com",
    password="secret",
    api_key="key123"
)

print(user.PublicUser())
# Output: PublicUser(name='John', email='john@example.com')
print(user.AdminView())
# Output: AdminView(name='John', email='john@example.com')
```

## Cloning Models

Use `clone` to create a modified copy of a model with different fields or options:

```python
from cwtch import dataclass, clone

@dataclass
class User:
    name: str
    email: str
    password: str
    api_key: str

# Create a clone without certain fields
@clone(User, exclude={"password", "api_key"})
class UserPublic:
    pass

# Create instances using the cloned class
public = UserPublic(name="John", email="john@example.com")
print(public.name)   # "John"
print(public.email)  # "john@example.com"
```

### Clone Options

Clone supports many options to customize the new model:

```python
from cwtch import dataclass, clone

@dataclass
class User:
    name: str
    email: str
    password: str

# Clone with validation disabled
@clone(User, validate=False)
class UserNoValidation:
    pass

# Clone with only specific fields
@clone(User, include={"name"})
class UserNameOnly:
    pass

# Clone with all fields as keyword-only
@clone(User, kw_only=True)
class UserKwOnly:
    pass
```
