"""Auth router - mock LDAP-style authentication for the CMA Workbench."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from models.schemas import LoginRequest, LoginResponse, UserInfo

router = APIRouter()

# In-memory token store: token -> {username, role, department}
_token_store: dict[str, dict] = {}

MOCK_PASSWORD = "capital1"

# The single permitted user for this build. Username + password are required;
# any other combination is rejected. Profile is what the UI badge shows.
MOCK_USERNAME = "pqr557"
_DEFAULT_PROFILES = {
    "pqr557": {
        "role": "Quantitative Analyst",
        "department": "Capital Markets & Analytics",
        # `groups` controls which domain packs the user can see / use.
        # The wildcard "*" grants access to every pack. When you onboard
        # additional users, list specific group names (e.g.
        # ["portfolio_managers", "treasury_desk"]) and have each pack
        # declare matching `user_groups` in its `pack.py:register`.
        "groups": ["*"],
    },
}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    if not token or token not in _token_store:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return _token_store[token]["username"]


def get_user_record(token: str = Depends(oauth2_scheme)) -> dict:
    if not token or token not in _token_store:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return _token_store[token]


def get_current_user_groups(token: str = Depends(oauth2_scheme)) -> list[str]:
    """Return the calling user's group memberships. Used to filter pack-scoped
    artifacts; an empty list (or "*") means "all groups"."""
    if not token or token not in _token_store:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return list(_token_store[token].get("groups", []))


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    if not request.username:
        raise HTTPException(status_code=400, detail="Username required")
    if request.username.lower() != MOCK_USERNAME or request.password != MOCK_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    profile = _DEFAULT_PROFILES[MOCK_USERNAME]
    token = str(uuid.uuid4())
    _token_store[token] = {
        "username": MOCK_USERNAME,
        "role": profile["role"],
        "department": profile["department"],
        "groups": list(profile.get("groups", [])),
    }
    return LoginResponse(
        token=token,
        username=MOCK_USERNAME,
        role=profile["role"],
        department=profile["department"],
        groups=list(profile.get("groups", [])),
    )


@router.post("/logout")
async def logout(token: str = Depends(oauth2_scheme)):
    if token and token in _token_store:
        del _token_store[token]
    return {"message": "Logged out"}


@router.get("/me", response_model=UserInfo)
async def me(user: dict = Depends(get_user_record)):
    return UserInfo(**user)
