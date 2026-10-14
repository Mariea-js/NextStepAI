import os
import logging
from functools import lru_cache
from time import perf_counter
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .embeddings import HashEmbeddingService
from .llm_client import GeminiClient
from .member_a_client import MemberAClient, MemberAError
from .models import StudentProfile
from .presentation import FrontendAnalysisResponse, format_analysis_response
from .service import AnalysisService
from .source_fetcher import SourceFetcher
from .source_registry import SourceRegistry
from .vector_store import ChromaVectorStore
# Resolve relative to this package, not the process working directory.
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / '.env')
app=FastAPI(title='NextStep AI - Evidence Layer')
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if origin.strip()],
    allow_methods=['*'],
    allow_headers=['*'],
)
logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.INFO)
@lru_cache(maxsize=1)
def get_service():
 timeout = float(os.getenv('GEMINI_TIMEOUT_SECONDS', '30'))
 retry_delay = float(os.getenv('GEMINI_RETRY_DELAY_SECONDS', '0.5'))
 return AnalysisService(MemberAClient(os.getenv('MEMBER_A_BASE_URL','http://127.0.0.1:8000')),SourceFetcher(),SourceRegistry(os.getenv('SOURCE_REGISTRY_PATH','./.source_registry.sqlite3')),ChromaVectorStore(os.getenv('CHROMA_PATH','./.chroma')),HashEmbeddingService(),GeminiClient(os.getenv('GEMINI_API_KEY',''),os.getenv('LLM_MODEL','gemini-2.0-flash'), timeout_seconds=timeout, retry_delay_seconds=retry_delay, max_retries=1))
@app.get('/')
def root(): return {'status':'NextStep AI evidence layer is running'}
@app.post('/analyze', response_model=FrontendAnalysisResponse)
async def analyze(profile:StudentProfile):
 started = perf_counter()
 logger.info('timing stage=request_received')
 try:
  service_started = perf_counter()
  service = get_service()
  logger.info('timing stage=service_initialization duration_ms=%.1f', (perf_counter() - service_started) * 1000)
  analysis = await service.analyze(profile)
  formatting_started = perf_counter()
  response = format_analysis_response(analysis)
  logger.info('timing stage=response_formatting duration_ms=%.1f', (perf_counter() - formatting_started) * 1000)
  logger.info('timing stage=request_total duration_ms=%.1f', (perf_counter() - started) * 1000)
  return response
 except MemberAError as exc: raise HTTPException(503,detail={'code':'member_a_unavailable','message':str(exc)}) from exc
