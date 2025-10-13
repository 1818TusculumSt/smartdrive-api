import os
import sys
import json
import logging
import re
from typing import List, Dict, Tuple
from mcp.server import Server
from mcp.types import Tool, TextContent
from pinecone import Pinecone
from embeddings import EmbeddingProvider
from config import settings
from document_storage import DocumentStorage
from sentence_transformers import CrossEncoder

# Configure logging to stderr ONLY (stdout is reserved for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # CRITICAL: MCP uses stdout for JSON-RPC, logs must go to stderr
)

# Silence noisy Azure SDK logging
logging.getLogger('azure').setLevel(logging.WARNING)
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)

# Initialize
app = Server("smartdrive-mcp")
pc = Pinecone(api_key=settings.PINECONE_API_KEY)
index = pc.Index(
    name=settings.PINECONE_INDEX_NAME,
    host=settings.PINECONE_HOST
)
embedding_provider = EmbeddingProvider()
document_storage = DocumentStorage()

# Initialize reranker model (lightweight, fast)
logging.info("Loading reranking model...")
reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
logging.info("Reranker loaded successfully")

# ============================================================================
# INTELLIGENT SEARCH ENHANCEMENTS
# ============================================================================

def preprocess_query(query: str) -> str:
    """
    Enhance queries with semantic expansion and cleanup.
    Mimics what Claude does naturally through conversation.
    """
    query_lower = query.lower()

    # Tax-related queries
    tax_keywords = ["tax", "1099", "w-2", "w2", "w-9", "1040", "irs", "fiscal"]
    if any(kw in query_lower for kw in tax_keywords):
        query = f"{query} tax document IRS form fiscal year"

    # Financial documents
    financial_keywords = ["invoice", "receipt", "bill", "payment", "budget", "expense"]
    if any(kw in query_lower for kw in financial_keywords):
        query = f"{query} financial accounting expense"

    # Meeting/notes
    meeting_keywords = ["meeting", "notes", "minutes", "agenda"]
    if any(kw in query_lower for kw in meeting_keywords):
        query = f"{query} meeting notes discussion agenda"

    # Project/proposal
    project_keywords = ["project", "proposal", "plan", "roadmap"]
    if any(kw in query_lower for kw in project_keywords):
        query = f"{query} project plan proposal strategy"

    # Reports
    report_keywords = ["report", "analysis", "summary", "quarterly"]
    if any(kw in query_lower for kw in report_keywords):
        query = f"{query} report analysis summary data"

    # Remove common filler words that don't help semantic search
    filler_words = ["find", "search", "show me", "give me", "get me", "look for"]
    for filler in filler_words:
        query = re.sub(r'\b' + re.escape(filler) + r'\b', '', query, flags=re.IGNORECASE)

    # Clean up extra whitespace
    query = ' '.join(query.split())

    return query


def generate_query_variations(query: str) -> List[str]:
    """
    Generate multiple query variations to cast a wider semantic net.
    Mimics Claude's multi-attempt search strategy.
    """
    variations = [query]  # Always include original

    query_lower = query.lower()

    # Add variations without filler words
    cleaned = re.sub(r'\b(find|search|show|give|get|look)\s+(me|for)?\s*', '', query, flags=re.IGNORECASE).strip()
    if cleaned and cleaned != query:
        variations.append(cleaned)

    # Add keyword-focused version (just the nouns/important terms)
    keywords = re.findall(r'\b[A-Za-z0-9]+\b', query)
    # Filter out common words
    stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'find', 'search', 'show', 'me', 'my'}
    important_keywords = [kw for kw in keywords if kw.lower() not in stopwords]
    if len(important_keywords) >= 2:
        variations.append(' '.join(important_keywords))

    # Deduplicate while preserving order
    seen = set()
    unique_variations = []
    for v in variations:
        v_clean = v.strip()
        if v_clean and v_clean not in seen:
            seen.add(v_clean)
            unique_variations.append(v_clean)

    logging.info(f"Generated {len(unique_variations)} query variations: {unique_variations}")
    return unique_variations


def rerank_results(query: str, doc_results: Dict[str, Dict]) -> List[Tuple[str, Dict]]:
    """
    Rerank search results using a cross-encoder model for better relevance.
    This is more accurate than vector similarity alone.
    """
    if not doc_results:
        return []

    # Prepare pairs for reranking: [query, document_text]
    doc_ids = list(doc_results.keys())
    pairs = []
    for doc_id in doc_ids:
        doc_info = doc_results[doc_id]
        # Use first 1000 chars for reranking (balance between context and speed)
        text_snippet = doc_info['full_text'][:1000]
        pairs.append([query, text_snippet])

    # Get reranking scores
    logging.info(f"Reranking {len(pairs)} documents...")
    rerank_scores = reranker.predict(pairs)

    # Combine original scores with rerank scores
    reranked = []
    for doc_id, rerank_score in zip(doc_ids, rerank_scores):
        doc_info = doc_results[doc_id]
        # Blend original Pinecone score (0-1) with rerank score (-10 to 10)
        # Normalize rerank score to 0-1 range and blend 50/50
        normalized_rerank = (rerank_score + 10) / 20  # Map [-10, 10] to [0, 1]
        blended_score = (doc_info['score'] + normalized_rerank) / 2

        doc_info['original_score'] = doc_info['score']
        doc_info['rerank_score'] = float(rerank_score)
        doc_info['blended_score'] = float(blended_score)

        reranked.append((doc_id, doc_info))

    # Sort by blended score (descending)
    reranked.sort(key=lambda x: x[1]['blended_score'], reverse=True)

    logging.info(f"Reranking complete. Top result score: {reranked[0][1]['blended_score']:.3f}")
    return reranked

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name="search_onedrive",
            description="""
            🔍 INTELLIGENT HYBRID SEARCH across OneDrive documents.

            COMBINES:
            - Semantic search (understands meaning, not just keywords)
            - Keyword/BM25 search (exact term matching)
            - Multi-query expansion (searches multiple variations)
            - AI reranking (reorders results for maximum relevance)

            HOW TO USE:
            - Use natural language queries (e.g., "tax documents from 2024")
            - Combine specific terms with context (e.g., "project proposal Q4 budget")
            - Include file types if relevant (e.g., "Excel budget spreadsheet")
            - Time periods work great (e.g., "meeting notes March 2024")

            EXAMPLE QUERIES THAT WORK GREAT:
            ✓ "1099 tax forms" → finds W-2s, 1099s, tax documents, IRS forms
            ✓ "meeting notes about the budget" → finds meeting notes discussing budgets
            ✓ "quarterly report Q4 2024" → finds Q4 2024 reports
            ✓ "project proposal client presentation" → finds proposals and presentations
            ✓ "invoice from Acme Corp" → finds invoices from that company

            RETURNS:
            Top matching documents with:
            - File names, paths, and modification dates
            - Relevance scores (higher = better match)
            - Content previews (first 2000 chars)
            - Document IDs (use with read_document for full text)

            TIPS FOR BEST RESULTS:
            - Be specific: "2024 tax forms" > "taxes"
            - Include context: "Q4 budget meeting notes" > "notes"
            - Use multiple keywords: "invoice payment receipt" > "invoice"
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query - use natural language, be specific, include context"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5, max: 20)",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="read_document",
            description="""
            📄 RETRIEVE FULL DOCUMENT TEXT from Azure Blob Storage.

            Use this when you need the complete content of a document found in search results.
            Every search result includes a Document ID - pass that ID here to get the full text.

            WHEN TO USE:
            - After finding a document with search_onedrive
            - When you need more than the 2000-char preview
            - To analyze complete document contents
            - To extract specific information from the full text

            EXAMPLE:
            1. search_onedrive("2024 tax forms")
               → Returns: doc_abc123 (W-2 form, 15,234 chars)
            2. read_document(doc_id="doc_abc123")
               → Returns: Full 15,234 character document text
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": "Document ID (e.g., 'doc_abc123def456') from search_onedrive results"
                    }
                },
                "required": ["doc_id"]
            }
        ),
        Tool(
            name="suggest_queries",
            description="""
            💡 GENERATE BETTER SEARCH QUERIES for improved results.

            Takes your original query and generates multiple optimized variations:
            - Removes filler words ("find", "show me", etc.)
            - Adds semantic context (e.g., "tax" → "tax document IRS form")
            - Creates keyword-focused versions
            - Suggests alternative phrasings

            USE THIS WHEN:
            - Your initial search returns poor results
            - You want to explore different search angles
            - You're unsure how to phrase your query

            RETURNS:
            - List of 2-5 optimized query suggestions
            - Try each suggestion with search_onedrive to compare results
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Your original search query that needs improvement"
                    }
                },
                "required": ["query"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""
    if name == "search_onedrive":
        original_query = arguments["query"]
        top_k = arguments.get("top_k", 5)

        logging.info(f"🔍 Search request: '{original_query}' (top_k={top_k})")

        # ENHANCEMENT 1: Preprocess query (add semantic context)
        enhanced_query = preprocess_query(original_query)
        logging.info(f"📝 Enhanced query: '{enhanced_query}'")

        # ENHANCEMENT 2: Generate query variations
        query_variations = generate_query_variations(enhanced_query)

        # Collect results from all query variations
        all_doc_results = {}
        queries_attempted = 0

        # Search with enhanced query + variations (max 3 variations to avoid slowdown)
        for query_variant in query_variations[:3]:
            queries_attempted += 1
            logging.info(f"🔎 Searching with variant {queries_attempted}: '{query_variant}'")

            # Generate dense query embedding (semantic)
            query_embedding = await embedding_provider.get_embedding(query_variant)

            if query_embedding is None:
                logging.warning(f"⚠️ Failed to generate embedding for variant: '{query_variant}'")
                continue

            query_embedding = query_embedding.tolist()

            # Generate sparse query embedding (keyword/BM25) for hybrid search
            sparse_query_embedding = await embedding_provider.get_sparse_embedding(query_variant)

            # Search Pinecone with hybrid search (dense + sparse)
            # Fetch more results than requested for reranking (top_k * 4)
            fetch_count = min(top_k * 4, 20)  # Max 20 for reranking
            query_params = {
                "vector": query_embedding,
                "top_k": fetch_count,
                "namespace": "smartdrive",
                "include_metadata": True
            }

            # Add sparse vector if generated successfully
            if sparse_query_embedding:
                query_params["sparse_vector"] = sparse_query_embedding

            results = index.query(**query_params)

            # Collect documents from this query variant
            for match in results.matches:
                meta = match.metadata
                doc_id = meta.get('doc_id')

                if doc_id and doc_id not in all_doc_results:
                    # First time seeing this document - retrieve full text from Azure Blob
                    full_text = document_storage.retrieve_document(doc_id)

                    if full_text:
                        all_doc_results[doc_id] = {
                            "file_name": meta.get('file_name', 'Unknown'),
                            "file_path": meta.get('file_path', 'Unknown'),
                            "modified": meta.get('modified', 'Unknown'),
                            "score": match.score,
                            "full_text": full_text,
                            "source_query": query_variant
                        }

        # Check if we found anything
        if not all_doc_results:
            return [TextContent(
                type="text",
                text=f"❌ No matching documents found for: '{original_query}'\n\n"
                     f"💡 Try:\n"
                     f"- Using different keywords\n"
                     f"- Being more specific\n"
                     f"- Using the 'suggest_queries' tool for better query ideas"
            )]

        logging.info(f"📊 Found {len(all_doc_results)} unique documents across {queries_attempted} query variations")

        # ENHANCEMENT 3: Rerank results using CrossEncoder
        reranked_results = rerank_results(original_query, all_doc_results)

        # Take only top_k after reranking
        reranked_results = reranked_results[:top_k]

        # Format output
        output = f"🔍 Found {len(reranked_results)} results for: '{original_query}'\n"
        output += f"🧠 Searched {queries_attempted} query variations, reranked with AI\n\n"

        # Format output with document summaries (prevent 1MB limit issues)
        MAX_PREVIEW_CHARS = 2000  # Show first 2000 chars per document
        MAX_TOTAL_SIZE = 900_000  # Keep total response under 900KB (well below 1MB limit)

        current_size = len(output)

        for i, (doc_id, doc_info) in enumerate(reranked_results, 1):
            full_text = doc_info['full_text']
            text_length = len(full_text)

            # Truncate if needed
            if text_length > MAX_PREVIEW_CHARS:
                preview_text = full_text[:MAX_PREVIEW_CHARS] + f"\n\n... [Truncated: {text_length - MAX_PREVIEW_CHARS:,} more characters. Use read_document('{doc_id}') for full text]"
            else:
                preview_text = full_text

            # Show blended score (more meaningful after reranking)
            score_display = f"{doc_info['blended_score']:.3f}"
            score_details = f"(Vector: {doc_info['original_score']:.3f}, Rerank: {doc_info['rerank_score']:.2f})"

            result_block = (
                f"**Result {i}** - Relevance Score: {score_display} {score_details}\n"
                f"📄 **File:** {doc_info['file_name']}\n"
                f"📁 **Path:** {doc_info['file_path']}\n"
                f"📅 **Modified:** {doc_info['modified']}\n"
                f"📊 **Size:** {text_length:,} characters\n"
                f"🔑 **Document ID:** `{doc_id}`\n"
                f"📝 **Preview:**\n{preview_text}\n\n"
                f"---\n\n"
            )

            # Check if adding this result would exceed total size limit
            if current_size + len(result_block) > MAX_TOTAL_SIZE:
                output += f"\n⚠️ **Remaining results omitted** (response size limit reached)\n"
                break

            output += result_block
            current_size += len(result_block)

        return [TextContent(type="text", text=output)]

    elif name == "read_document":
        doc_id = arguments["doc_id"]

        logging.info(f"📖 Reading document: {doc_id}")

        # Retrieve full document text from Azure Blob Storage
        full_text = document_storage.retrieve_document(doc_id)

        if full_text is None:
            return [TextContent(
                type="text",
                text=f"❌ Document not found: {doc_id}\n\nThe document may have been deleted or the doc_id may be incorrect."
            )]

        # Return full document with metadata
        output = (
            f"📄 **Document ID:** {doc_id}\n"
            f"📊 **Size:** {len(full_text):,} characters\n\n"
            f"**Full Text:**\n{full_text}"
        )

        logging.info(f"✅ Retrieved document {doc_id} ({len(full_text):,} chars)")
        return [TextContent(type="text", text=output)]

    elif name == "suggest_queries":
        original_query = arguments["query"]

        logging.info(f"💡 Generating query suggestions for: '{original_query}'")

        # Generate enhanced query and variations
        enhanced = preprocess_query(original_query)
        variations = generate_query_variations(enhanced)

        # Format output
        output = f"💡 **Query Suggestions for:** '{original_query}'\n\n"
        output += "Here are optimized versions of your query that may yield better results:\n\n"

        for i, suggestion in enumerate(variations, 1):
            output += f"**{i}.** `{suggestion}`\n"
            if suggestion != original_query:
                # Explain what changed
                if len(suggestion.split()) < len(original_query.split()):
                    output += "   _(removed filler words for cleaner search)_\n"
                elif len(suggestion.split()) > len(original_query.split()):
                    output += "   _(added semantic context for better matching)_\n"
                else:
                    output += "   _(keyword-focused version)_\n"
            else:
                output += "   _(your original query)_\n"
            output += "\n"

        output += "\n**💡 Tips:**\n"
        output += "- Try each suggestion with `search_onedrive`\n"
        output += "- Combine keywords from multiple suggestions\n"
        output += "- Add specific dates, names, or file types if known\n"

        return [TextContent(type="text", text=output)]

    raise ValueError(f"Unknown tool: {name}")

if __name__ == "__main__":
    import asyncio
    import mcp.server.stdio
    
    async def main():
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )
    
    asyncio.run(main())
