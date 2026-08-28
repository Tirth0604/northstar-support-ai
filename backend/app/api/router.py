from fastapi import APIRouter

from app.api.routes import admin, agent, auth, config, conversations, customer, documents, health

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(conversations.router)
api_router.include_router(customer.router)
api_router.include_router(agent.router)
api_router.include_router(admin.router)
api_router.include_router(documents.router)
api_router.include_router(config.router)
