"""
API Generator
Generates API endpoints and routers
"""

from ...generators.base_generator import BaseGenerator
from ...core.config import ProjectType, AuthType


class APIGenerator(BaseGenerator):
    """Generates API endpoints"""

    def generate(self):
        """Generate API files"""
        # Generate main endpoints
        endpoints_content = self._get_endpoints_template()
        self.write_file(
            f"{self.config.path}/app/api/v1/endpoints.py", endpoints_content
        )

        # Generate auth endpoints if authentication is enabled
        if self.config.auth_type != AuthType.NONE:
            auth_endpoints_content = self._get_auth_endpoints_template()
            self.write_file(
                f"{self.config.path}/app/api/v1/auth.py", auth_endpoints_content
            )

        # Generate __init__.py that exports the router
        init_content = self._get_init_template()
        self.write_file(f"{self.config.path}/app/api/v1/__init__.py", init_content)

    def _get_endpoints_template(self) -> str:
        """Get main endpoints template"""
        template = '''"""
Main API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
{auth_imports}
{database_imports}

router = APIRouter()

{auth_endpoints_include}

@router.get("/")
async def root():
    """Root endpoint"""
    return {{"message": "Welcome to {project_name} API", "version": "1.0.0"}}


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {{"status": "healthy", "service": "{project_name}"}}

{project_specific_endpoints}
'''

        # Customize based on configuration
        auth_imports = ""
        auth_endpoints_include = ""
        database_imports = ""
        project_specific_endpoints = ""

        if self.config.auth_type != AuthType.NONE:
            auth_imports = "from app.core.security import get_current_user"
            auth_endpoints_include = ""

        # Add database imports
        if self.config.is_async:
            database_imports = "from app.db.database import get_db\nfrom sqlalchemy.ext.asyncio import AsyncSession\nfrom app.models.auth import User"
        else:
            database_imports = "from app.db.database import get_db\nfrom sqlalchemy.orm import Session\nfrom app.models.auth import User"

        # Add project-specific endpoints
        if self.config.project_type == ProjectType.ML_API:
            project_specific_endpoints = self._get_ml_endpoints()
        elif self.config.project_type == ProjectType.MICROSERVICE:
            project_specific_endpoints = self._get_microservice_endpoints()

        return template.format(
            project_name=self.get_template_vars()["project_name"],
            auth_imports=auth_imports,
            auth_endpoints_include=auth_endpoints_include,
            database_imports=database_imports,
            project_specific_endpoints=project_specific_endpoints,
        )

    def _get_ml_endpoints(self) -> str:
        """Get ML API specific endpoints"""
        return '''
@router.post("/predict")
async def predict(
    input_data: dict,
    current_user: User = Depends(get_current_user) if {has_auth} else None
):
    """Make ML prediction"""
    from app.services.prediction_service import make_prediction
    try:
        result = await make_prediction(input_data)
        return {{"prediction": result, "status": "success"}}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/model/info")
async def get_model_info(
    current_user: User = Depends(get_current_user) if {has_auth} else None
):
    """Get ML model information"""
    return {{
        "model_name": "DefaultModel",
        "version": "1.0.0",
        "description": "Machine Learning model for predictions"
    }}
'''.format(
            has_auth=self.config.auth_type != AuthType.NONE
        )

    def _get_microservice_endpoints(self) -> str:
        """Get microservice specific endpoints"""
        return '''
@router.get("/status")
async def service_status():
    """Get service status"""
    return {{
        "service": "{project_name}",
        "status": "running",
        "version": "1.0.0"
    }}


@router.post("/process")
async def process_data(
    data: dict,
    current_user: User = Depends(get_current_user) if {has_auth} else None
):
    """Process data"""
    from app.services.processing_service import process_data
    try:
        result = await process_data(data)
        return {{"result": result, "status": "processed"}}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
'''.format(
            project_name=self.config.name,
            has_auth=self.config.auth_type != AuthType.NONE,
        )

    def _get_auth_endpoints_template(self) -> str:
        """Get authentication endpoints template"""
        if self.config.is_async:
            session_import = "from sqlalchemy.ext.asyncio import AsyncSession"
            session_type = "AsyncSession"
            await_keyword = "await "
        else:
            session_import = "from sqlalchemy.orm import Session"
            session_type = "Session"
            await_keyword = ""

        template = f'''"""
Authentication Endpoints
"""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
{session_import}
from app.core.config import settings
from app.db.database import get_db
from app.schemas.auth import Token, UserLogin, UserCreate, User as UserSchema
from app.core.security import authenticate_user, create_access_token, get_current_user, create_user

router = APIRouter()


@router.post("/token", response_model=Token)
async def login_for_access_token(
    user_credentials: UserLogin,
    db: {session_type} = Depends(get_db)
):
    """Login endpoint to get access token"""
    user = {await_keyword}authenticate_user(db, user_credentials.email, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={{"WWW-Authenticate": "Bearer"}},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={{"sub": user.email}}, expires_delta=access_token_expires
    )
    
    return {{"access_token": access_token, "token_type": "bearer"}}


@router.post("/register", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    db: {session_type} = Depends(get_db)
):
    """Register new user"""
    # Check if user already exists
    from app.core.security import get_user_by_email
    existing_user = {await_keyword}get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user = {await_keyword}create_user(db, user_data.email, user_data.password)
    return user


@router.get("/me", response_model=UserSchema)
async def read_users_me(current_user: UserSchema = Depends(get_current_user)):
    """Get current user information"""
    return current_user


@router.put("/me", response_model=UserSchema)
async def update_user_me(
    user_update: dict,
    current_user: UserSchema = Depends(get_current_user),
    db: {session_type} = Depends(get_db)
):    
    """Update current user information"""
    # Implementation for updating user profile
    # This is a placeholder - implement based on your needs
    return current_user
'''

        return template

    def _get_init_template(self) -> str:
        """Get __init__.py template that exports the router"""
        from ...core.config import AuthType

        if self.config.auth_type != AuthType.NONE:
            template = '''"""
API v1 Router
"""

from fastapi import APIRouter
from .endpoints import router as endpoints_router
from .auth import router as auth_router

router = APIRouter()
router.include_router(endpoints_router)
router.include_router(auth_router, prefix="/auth", tags=["authentication"])
'''
        else:
            template = '''"""
API v1 Router
"""

from .endpoints import router
'''

        return template
