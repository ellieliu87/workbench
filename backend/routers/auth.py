"""Auth router - mock LDAP-style authentication for the CMA Workbench."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from models.schemas import LoginRequest, LoginResponse, UserInfo

router = APIRouter()

# In-memory token store: token -> {username, role, department}
_token_store: dict[str, dict] = {}

MOCK_PASSWORD = "capital1"

# Username -> default role/department mapping for demo
_DEFAULT_PROFILES = {
    "alice":  {"role": "Capital Markets Analyst",   "department": "Capital Markets"},
    "bob":    {"role": "Treasury Analyst",          "department": "Finance"},
    "carol":  {"role": "Senior Quant",              "department": "Capital Markets"},
    "david":  {"role": "Risk Analyst",              "department": "Finance"},
    "demo":   {"role": "Capital Markets Analyst",   "department": "Capital Markets"},
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


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    if not request.username:
        raise HTTPException(status_code=400, detail="Username required")
    if request.password != MOCK_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials (hint: capital1)")

    profile = _DEFAULT_PROFILES.get(request.username.lower(), {
        "role": "Analyst",
        "department": "Capital Markets",
    })
    token = str(uuid.uuid4())
    _token_store[token] = {
        "username": request.username,
        "role": profile["role"],
        "department": profile["department"],
    }
    return LoginResponse(
        token=token,
        username=request.username,
        role=profile["role"],
        department=profile["department"],
    )


@router.post("/logout")
async def logout(token: str = Depends(oauth2_scheme)):
    if token and token in _token_store:
        del _token_store[token]
    return {"message": "Logged out"}


@router.get("/me", response_model=UserInfo)
async def me(user: dict = Depends(get_user_record)):
    return UserInfo(**user)
