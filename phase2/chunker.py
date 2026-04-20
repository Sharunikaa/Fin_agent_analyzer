"""
Hierarchical Chunking: Create chunks with parent-child relationships
"""

import re
from typing import Dict, List, Optional
from config import CHUNKING_CONFIG, HIERARCHY_LEVELS


def estimate_tokens(text: str) -> int:
    """
    Estimate token count (rough approximation: 1 token ≈ 4 characters).
    
    Args:
        text: Input text
        
    Returns:
        token_count: Estimated tokens
    """
    return len(text) // 4


def split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences.
    
    Args:
        text: Input text
        
    Returns:
        sentences: List of sentences
    """
    # Simple sentence splitter (can be enhanced with NLTK)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def split_into_paragraphs(text: str) -> List[str]:
    """
    Split text into paragraphs.
    
    Args:
        text: Input text
        
    Returns:
        paragraphs: List of paragraphs
    """
    paragraphs = text.split('\n\n')
    return [p.strip() for p in paragraphs if p.strip()]


def create_chunks(
    text: str,
    chunk_size: int = None,
    overlap: int = None,
    preserve_sentences: bool = True,
    preserve_paragraphs: bool = True,
) -> List[str]:
    """
    Create chunks from text with overlap.
    
    Args:
        text: Input text
        chunk_size: Target chunk size in tokens
        overlap: Overlap size in tokens
        preserve_sentences: Don't break mid-sentence
        preserve_paragraphs: Prefer paragraph boundaries
        
    Returns:
        chunks: List of text chunks
    """
    chunk_size = chunk_size or CHUNKING_CONFIG['chunk_size']
    overlap = overlap or CHUNKING_CONFIG['overlap']
    
    # If text is small, return as single chunk
    if estimate_tokens(text) <= chunk_size:
        return [text]
    
    chunks = []
    
    # Try paragraph-based chunking first
    if preserve_paragraphs:
        paragraphs = split_into_paragraphs(text)
        current_chunk = []
        current_tokens = 0
        
        for para in paragraphs:
            para_tokens = estimate_tokens(para)
            
            # If paragraph alone exceeds chunk size, split it
            if para_tokens > chunk_size:
                # Save current chunk if exists
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_tokens = 0
                
                # Split large paragraph by sentences
                sentences = split_into_sentences(para)
                sent_chunk = []
                sent_tokens = 0
                
                for sent in sentences:
                    sent_tokens_count = estimate_tokens(sent)
                    
                    if sent_tokens + sent_tokens_count > chunk_size and sent_chunk:
                        chunks.append(' '.join(sent_chunk))
                        # Keep overlap
                        overlap_sents = []
                        overlap_tokens = 0
                        for s in reversed(sent_chunk):
                            s_tokens = estimate_tokens(s)
                            if overlap_tokens + s_tokens <= overlap:
                                overlap_sents.insert(0, s)
                                overlap_tokens += s_tokens
                            else:
                                break
                        sent_chunk = overlap_sents
                        sent_tokens = overlap_tokens
                    
                    sent_chunk.append(sent)
                    sent_tokens += sent_tokens_count
                
                if sent_chunk:
                    chunks.append(' '.join(sent_chunk))
            
            # If adding paragraph doesn't exceed chunk size, add it
            elif current_tokens + para_tokens <= chunk_size:
                current_chunk.append(para)
                current_tokens += para_tokens
            
            # Otherwise, save current chunk and start new one
            else:
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                
                # Keep overlap (last paragraph)
                if overlap > 0 and current_chunk:
                    overlap_para = current_chunk[-1]
                    overlap_tokens = estimate_tokens(overlap_para)
                    if overlap_tokens <= overlap:
                        current_chunk = [overlap_para, para]
                        current_tokens = overlap_tokens + para_tokens
                    else:
                        current_chunk = [para]
                        current_tokens = para_tokens
                else:
                    current_chunk = [para]
                    current_tokens = para_tokens
        
        # Add last chunk
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
    
    else:
        # Simple token-based chunking
        tokens = text.split()
        for i in range(0, len(tokens), chunk_size - overlap):
            chunk_tokens = tokens[i:i + chunk_size]
            chunks.append(' '.join(chunk_tokens))
    
    return chunks


def create_hierarchical_chunks(
    section: Dict,
    parent_id: Optional[str] = None,
    doc_id: str = None,
) -> List[Dict]:
    """
    Create hierarchical chunks from a section.
    
    Args:
        section: Section dict with 'text', 'section_id', 'section_type'
        parent_id: Optional parent section ID
        doc_id: Document ID
        
    Returns:
        chunks: List of chunk dicts with hierarchy
    """
    text = section.get('text', '')
    section_id = section.get('section_id', 'unknown')
    section_type = section.get('section_type', 'other')
    
    # Create text chunks
    text_chunks = create_chunks(text)
    
    # Create chunk dicts with metadata
    chunks = []
    for i, chunk_text in enumerate(text_chunks):
        chunk = {
            'chunk_id': f"{section_id}_chunk_{i:04d}",
            'doc_id': doc_id,
            'section_id': section_id,
            'parent_id': parent_id,
            'section_type': section_type,
            'chunk_index': i,
            'total_chunks': len(text_chunks),
            'text': chunk_text,
            'token_count': estimate_tokens(chunk_text),
            'char_count': len(chunk_text),
        }
        chunks.append(chunk)
    
    return chunks


def create_all_chunks(
    sections: List[Dict],
    doc_id: str,
    doc_metadata: Dict = None,
) -> List[Dict]:
    """
    Create chunks for all sections in a document.
    
    Args:
        sections: List of sections with 'section_type' field
        doc_id: Document ID
        doc_metadata: Optional document metadata
        
    Returns:
        all_chunks: List of all chunks with hierarchy
    """
    all_chunks = []
    
    for section in sections:
        section_chunks = create_hierarchical_chunks(
            section=section,
            parent_id=section.get('parent_id'),
            doc_id=doc_id,
        )
        all_chunks.extend(section_chunks)
    
    return all_chunks


def get_chunk_statistics(chunks: List[Dict]) -> Dict:
    """
    Get statistics on chunks.
    
    Args:
        chunks: List of chunk dicts
        
    Returns:
        stats: Dict with counts and averages
    """
    from collections import Counter
    
    section_types = [c['section_type'] for c in chunks]
    type_counts = Counter(section_types)
    
    token_counts = [c['token_count'] for c in chunks]
    
    stats = {
        'total_chunks': len(chunks),
        'by_section_type': dict(type_counts),
        'avg_tokens_per_chunk': sum(token_counts) / len(token_counts) if token_counts else 0,
        'min_tokens': min(token_counts) if token_counts else 0,
        'max_tokens': max(token_counts) if token_counts else 0,
    }
    
    return stats


if __name__ == "__main__":
    # Test chunking
    test_text = """
    Our company operates in three primary segments: Data Center, Client, and Gaming.
    
    The Data Center segment includes server processors and GPUs for cloud computing and AI workloads. Revenue in this segment increased 123% year-over-year to $6.5 billion.
    
    The Client segment includes desktop and laptop processors. Revenue grew 31% to $9.0 billion.
    
    The Gaming segment includes graphics cards for gaming PCs and consoles. Revenue increased 42% to $5.5 billion.
    
    We face significant competition from Intel and NVIDIA in all segments.
    """
    
    chunks = create_chunks(test_text, chunk_size=100, overlap=20)
    
    print(f"Created {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        tokens = estimate_tokens(chunk)
        print(f"\nChunk {i+1} ({tokens} tokens):")
        print(f"  {chunk[:100]}...")
