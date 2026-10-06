"""Book Gap Analyzer MCP Server (FastAPI + Remote MCP SSE + REST OpenAPI)"""

import asyncio
import base64
import json
import os
from typing import Any, Dict, List, Optional
import uuid
from book_analyzer import BookGapEngine
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse, FileResponse

GOOGLE_BOOKS_API_KEY = os.environ.get("GOOGLE_BOOKS_API_KEY", None)
engine = BookGapEngine(api_key=GOOGLE_BOOKS_API_KEY)
sse_sessions: Dict[str, asyncio.Queue] = {}

ICON_PATH = os.path.join(os.path.dirname(__file__), "icon.png")
ICON_DATA_URI = ""
if os.path.exists(ICON_PATH):
    try:
        with open(ICON_PATH, "rb") as _f:
            ICON_DATA_URI = f"data:image/png;base64,{base64.b64encode(_f.read()).decode('utf-8')}"
    except Exception:
        pass

ICON_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Cross-Origin-Resource-Policy": "cross-origin",
    "Cache-Control": "public, max-age=86400",
}


# Pydantic Schemas for REST API
class SearchBooksRequest(BaseModel):
    theme: str = Field(..., description="Tema buku yang diteliti")
    language: Optional[str] = Field("id", description="Filter bahasa")
    max_results: Optional[int] = Field(40, description="Maksimal hasil")
    published_after_year: Optional[int] = Field(None, description="Tahun terbit minimal")


class SearchAdvancedRequest(BaseModel):
    query: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    publisher: Optional[str] = None
    subject: Optional[str] = None
    isbn: Optional[str] = None
    language: Optional[str] = None
    start_index: Optional[int] = 0
    max_results: Optional[int] = 20


class VolumeDetailRequest(BaseModel):
    volume_id: str


class LandscapeRequest(BaseModel):
    theme: str
    books: Optional[List[Dict[str, Any]]] = None


class TopicMatrixRequest(BaseModel):
    theme: str
    books: Optional[List[Dict[str, Any]]] = None


class GapAnalysisRequest(BaseModel):
    theme: str
    books: Optional[List[Dict[str, Any]]] = None


class BookOpportunitiesRequest(BaseModel):
    theme: str
    gaps: Optional[List[Dict[str, Any]]] = None


# MCP Tools Specification
MCP_TOOLS = [
    {
        "name": "search_books",
        "description": "Pencarian buku multi-query terotomasi dan deduplikasi.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "theme": {"type": "string"},
                "language": {"type": "string", "default": "id"},
                "max_results": {"type": "integer", "default": 40},
                "published_after_year": {"type": "integer"},
            },
            "required": ["theme"],
        },
    },
    {
        "name": "search_books_advanced",
        "description": "Pencarian lanjutan dengan operator Google Books.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "title": {"type": "string"},
                "author": {"type": "string"},
                "publisher": {"type": "string"},
                "subject": {"type": "string"},
                "isbn": {"type": "string"},
                "language": {"type": "string"},
                "start_index": {"type": "integer", "default": 0},
                "max_results": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "get_book_detail",
        "description": "Detail bibliografi buku berdasarkan volume_id.",
        "inputSchema": {
            "type": "object",
            "properties": {"volume_id": {"type": "string"}},
            "required": ["volume_id"],
        },
    },
    {
        "name": "build_book_landscape",
        "description": "Peta lanskap pasar kompetisi buku dan klaster tema.",
        "inputSchema": {
            "type": "object",
            "properties": {"theme": {"type": "string"}, "books": {"type": "array"}},
            "required": ["theme"],
        },
    },
    {
        "name": "extract_topics",
        "description": "Ekstraksi topik bahasan utama dan Topic Matrix.",
        "inputSchema": {
            "type": "object",
            "properties": {"theme": {"type": "string"}, "books": {"type": "array"}},
            "required": ["theme"],
        },
    },
    {
        "name": "find_book_gaps",
        "description": "Deteksi celah pasar (Gap) kompetitor dan kalkulasi Gap Score.",
        "inputSchema": {
            "type": "object",
            "properties": {"theme": {"type": "string"}, "books": {"type": "array"}},
            "required": ["theme"],
        },
    },
    {
        "name": "generate_book_opportunities",
        "description": "Usulan konsep buku unik dan draft daftar isi berdasarkan gap.",
        "inputSchema": {
            "type": "object",
            "properties": {"theme": {"type": "string"}, "gaps": {"type": "array"}},
            "required": ["theme"],
        },
    },
]

app = FastAPI(
    title="Book Research & Gap Analyzer MCP",
    description="Remote MCP Server & API untuk analisa GAP penulisan buku berbasis Google Books.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def handle_tool_call(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if name == "search_books":
        return engine.search_books(
            theme=args.get("theme", ""),
            language=args.get("language", "id"),
            max_results=int(args.get("max_results", 40)),
            published_after_year=args.get("published_after_year"),
        )
    elif name == "search_books_advanced":
        return engine.search_books_advanced(
            query=args.get("query"),
            title=args.get("title"),
            author=args.get("author"),
            publisher=args.get("publisher"),
            subject=args.get("subject"),
            isbn=args.get("isbn"),
            language=args.get("language"),
            start_index=int(args.get("start_index", 0)),
            max_results=int(args.get("max_results", 20)),
        )
    elif name == "get_book_detail":
        return engine.get_book_detail(volume_id=args.get("volume_id", ""))
    elif name == "build_book_landscape":
        return engine.build_book_landscape(
            theme=args.get("theme", ""), books=args.get("books")
        )
    elif name == "extract_topics":
        return engine.extract_topics(
            theme=args.get("theme", ""), books=args.get("books")
        )
    elif name == "find_book_gaps":
        return engine.find_book_gaps(
            theme=args.get("theme", ""), books=args.get("books")
        )
    elif name == "generate_book_opportunities":
        return engine.generate_book_opportunities(
            theme=args.get("theme", ""), gaps=args.get("gaps")
        )
    raise ValueError(f"Unknown tool: {name}")


def process_mcp_message(msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method = msg.get("method")
    msg_id = msg.get("id")

    if method == "initialize":
        params = msg.get("params", {})
        client_version = params.get("protocolVersion", "2024-11-05")
        
        icons_list = [
            {
                "src": "https://book-gab-mcp.onrender.com/icon.png",
                "mimeType": "image/png",
                "sizes": ["256x256"],
            }
        ]
        if ICON_DATA_URI:
            icons_list.append({
                "src": ICON_DATA_URI,
                "mimeType": "image/png",
                "sizes": ["256x256"],
            })

        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": client_version if client_version.startswith("202") else "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": "book-gap-analyzer-mcp",
                    "title": "Book Gap Analyzer Mcp",
                    "version": "1.0.0",
                    "icon": "https://book-gab-mcp.onrender.com/icon.png",
                    "iconUrl": "https://book-gab-mcp.onrender.com/icon.png",
                    "icons": icons_list,
                },
            },
        }
    elif method == "notifications/initialized":
        return None
    elif method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    elif method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": MCP_TOOLS}}
    elif method == "tools/call":
        params = msg.get("params", {})
        try:
            res_data = handle_tool_call(
                params.get("name"), params.get("arguments", {})
            )
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(res_data, indent=2, ensure_ascii=False),
                    }],
                    "isError": False,
                },
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32603, "message": str(e)},
            }
    return None


# 1. MCP Endpoints (Streamable HTTP & SSE)
@app.post("/mcp")
async def mcp_direct_post(request: Request):
    body = await request.json()
    res = process_mcp_message(body)
    return JSONResponse(content=res) if res else Response(status_code=204)


@app.get("/sse")
async def sse_endpoint(request: Request):
    session_id = str(uuid.uuid4())
    queue = asyncio.Queue()
    sse_sessions[session_id] = queue

    async def generator():
        yield f"event: endpoint\ndata: /messages?session_id={session_id}\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=20.0)
                    yield f"event: message\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield "event: ping\ndata: {}\n\n"
        finally:
            sse_sessions.pop(session_id, None)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/messages")
async def messages_endpoint(
    session_id: str = Query(...), request: Request = None
):
    if session_id not in sse_sessions:
        raise HTTPException(status_code=404, detail="Session expired")
    body = await request.json()
    res = process_mcp_message(body)
    if res:
        await sse_sessions[session_id].put(res)
    return Response(status_code=202)


# 2. REST Endpoints (for ChatGPT Actions)
@app.post("/api/v1/search-books")
def api_search_books(req: SearchBooksRequest):
    return engine.search_books(
        theme=req.theme,
        language=req.language,
        max_results=req.max_results or 40,
        published_after_year=req.published_after_year,
    )


@app.post("/api/v1/search-books-advanced")
def api_search_books_advanced(req: SearchAdvancedRequest):
    return engine.search_books_advanced(
        query=req.query,
        title=req.title,
        author=req.author,
        publisher=req.publisher,
        subject=req.subject,
        isbn=req.isbn,
        language=req.language,
        start_index=req.start_index or 0,
        max_results=req.max_results or 20,
    )


@app.post("/api/v1/get-book-detail")
def api_get_book_detail(req: VolumeDetailRequest):
    return engine.get_book_detail(volume_id=req.volume_id)


@app.post("/api/v1/build-book-landscape")
def api_build_book_landscape(req: LandscapeRequest):
    return engine.build_book_landscape(theme=req.theme, books=req.books)


@app.post("/api/v1/extract-topics")
def api_extract_topics(req: TopicMatrixRequest):
    return engine.extract_topics(theme=req.theme, books=req.books)


@app.post("/api/v1/find-book-gaps")
def api_find_book_gaps(req: GapAnalysisRequest):
    return engine.find_book_gaps(theme=req.theme, books=req.books)


@app.post("/api/v1/generate-book-opportunities")
def api_generate_book_opportunities(req: BookOpportunitiesRequest):
    return engine.generate_book_opportunities(theme=req.theme, gaps=req.gaps)


# 3. MCP Discovery Endpoints
@app.get("/.well-known/mcp.json", include_in_schema=False)
@app.get("/.well-known/mcp/server-card.json", include_in_schema=False)
def mcp_server_card():
    return {
        "name": "book-gap-analyzer-mcp",
        "title": "Book Gap Analyzer Mcp",
        "description": "Remote MCP Server & API untuk analisa GAP penulisan buku berbasis Google Books.",
        "version": "1.0.0",
        "iconUrl": "https://book-gab-mcp.onrender.com/icon.png",
        "icon": "https://book-gab-mcp.onrender.com/icon.png",
        "icons": [
            {
                "src": "https://book-gab-mcp.onrender.com/icon.png",
                "mimeType": "image/png",
                "sizes": ["256x256"],
            }
        ],
        "transport": {
            "type": "http",
            "url": "https://book-gab-mcp.onrender.com/mcp",
        },
    }


# 4. Icon & Favicon Handlers (with CORS & Cross-Origin-Resource-Policy)
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    if os.path.exists("favicon.ico"):
        return FileResponse("favicon.ico", media_type="image/x-icon", headers=ICON_HEADERS)
    if os.path.exists("icon.png"):
        return FileResponse("icon.png", media_type="image/png", headers=ICON_HEADERS)
    return Response(status_code=404)


@app.get("/icon.png", include_in_schema=False)
@app.get("/favicon.png", include_in_schema=False)
@app.get("/apple-touch-icon.png", include_in_schema=False)
@app.get("/apple-touch-icon-precomposed.png", include_in_schema=False)
async def icon_png():
    if os.path.exists("icon.png"):
        return FileResponse("icon.png", media_type="image/png", headers=ICON_HEADERS)
    return Response(status_code=404)


# 5. Root & Health Endpoints
@app.get("/", include_in_schema=False)
def root(request: Request):
    accept = request.headers.get("accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return {
            "status": "ok",
            "service": "Book Gap Analyzer MCP",
            "docs": "/docs",
            "mcp_sse": "/sse",
            "icon": "/icon.png",
        }
    html_content = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Book Gap Analyzer MCP</title>
    <link rel="icon" type="image/x-icon" href="/favicon.ico">
    <link rel="icon" type="image/png" sizes="256x256" href="/icon.png">
    <link rel="shortcut icon" href="/favicon.ico">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">
    <meta property="og:title" content="Book Gap Analyzer MCP">
    <meta property="og:description" content="Remote MCP Server & API untuk analisa GAP penulisan buku berbasis Google Books.">
    <meta property="og:image" content="https://book-gab-mcp.onrender.com/icon.png">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #0f172a; color: #f8fafc; }
        .card { text-align: center; padding: 2.5rem; background: #1e293b; border-radius: 1rem; border: 1px solid #334155; max-width: 420px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); }
        .card img { width: 96px; height: 96px; border-radius: 1rem; margin-bottom: 1rem; }
        h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
        p { color: #94a3b8; font-size: 0.95rem; line-height: 1.5; margin-bottom: 1.5rem; }
        .badge { display: inline-block; padding: 0.45rem 1rem; background: #0284c7; color: #fff; font-size: 0.85rem; font-weight: 600; border-radius: 9999px; text-decoration: none; }
        .badge:hover { background: #0369a1; }
    </style>
</head>
<body>
    <div class="card">
        <img src="/icon.png" alt="Book Gap Analyzer MCP Logo">
        <h1>Book Gap Analyzer MCP</h1>
        <p>Remote MCP Server & API untuk analisa GAP penulisan buku berbasis Google Books.</p>
        <a class="badge" href="/docs">Buka Dokumentasi API</a>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html_content, status_code=200)


@app.get("/health")
def health():
    return {"status": "ok", "service": "Book Gap Analyzer MCP"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=False,
    )
