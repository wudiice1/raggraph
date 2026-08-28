"""v1 路由聚合。"""
from fastapi import APIRouter

from app.api.v1 import auth, documents, graph, ontology, search

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(documents.router, prefix="/documents", tags=["文档管理"])
api_router.include_router(graph.router, prefix="/graph", tags=["知识图谱"])
api_router.include_router(search.router, prefix="/search", tags=["知识检索"])
api_router.include_router(ontology.router, prefix="/ontology", tags=["本体管理"])
