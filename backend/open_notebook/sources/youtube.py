"""
YouTube Source Processor

Extracts transcripts and metadata from YouTube videos for embedding and search.
Uses youtube-transcript-api for transcript extraction and HTML parsing for metadata.
"""

import re
import json
import asyncio
from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable
)
import httpx
from bs4 import BeautifulSoup


def extract_video_id(url: str) -> str:
    """
    Extract video ID from various YouTube URL formats.

    Supports:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://www.youtube.com/v/VIDEO_ID

    Args:
        url: YouTube URL

    Returns:
        Video ID (11 characters)

    Raises:
        ValueError: If URL is invalid or video ID cannot be extracted
    """
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]{11})'
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    raise ValueError(f"Could not extract video ID from URL: {url}")


async def get_transcript(video_id: str, language: str = 'en') -> Tuple[str, Dict[str, Any]]:
    """
    Get video transcript using youtube-transcript-api.

    Tries manual captions first, falls back to auto-generated.
    If requested language unavailable, tries English, then any available language.

    Args:
        video_id: YouTube video ID
        language: Preferred language code (default: 'en')

    Returns:
        Tuple of (transcript_text, metadata):
        - transcript_text: Full transcript as formatted string
        - metadata: Dict with language, auto_generated, duration info

    Raises:
        TranscriptsDisabled: Video has no transcripts
        NoTranscriptFound: Requested language not available
        VideoUnavailable: Video is private or doesn't exist
    """
    # Run blocking transcript fetch in executor
    loop = asyncio.get_event_loop()

    def _fetch_transcript():
        # Try to get transcript in requested language
        try:
            # Create API instance
            api = YouTubeTranscriptApi()
            transcript_list = api.list(video_id)

            # Try manual transcript first
            try:
                transcript = transcript_list.find_manually_created_transcript([language])
                return transcript.fetch(), False, transcript.language_code
            except:
                pass

            # Try auto-generated transcript
            try:
                transcript = transcript_list.find_generated_transcript([language])
                return transcript.fetch(), True, transcript.language_code
            except:
                pass

            # Fall back to English
            if language != 'en':
                try:
                    transcript = transcript_list.find_transcript(['en'])
                    return transcript.fetch(), transcript.is_generated, 'en'
                except:
                    pass

            # Fall back to any available language
            available_transcripts = list(transcript_list)
            if available_transcripts:
                transcript = available_transcripts[0]
                return transcript.fetch(), transcript.is_generated, transcript.language_code

            raise NoTranscriptFound(video_id, [language], {})

        except Exception as e:
            raise e

    # Fetch transcript in executor
    transcript_data, is_auto_generated, lang_code = await loop.run_in_executor(
        None, _fetch_transcript
    )

    # Format transcript as readable text
    transcript_parts = []
    total_duration = 0

    for entry in transcript_data:
        text = entry.text.strip()
        if text:
            # Clean up common transcript artifacts
            text = text.replace('\n', ' ')
            transcript_parts.append(text)
            total_duration = max(total_duration, entry.start + entry.duration)

    transcript_text = ' '.join(transcript_parts)

    metadata = {
        'transcript_language': lang_code,
        'transcript_auto_generated': is_auto_generated,
        'transcript_duration_seconds': int(total_duration),
        'transcript_entries_count': len(transcript_data)
    }

    return transcript_text, metadata


async def get_metadata(video_id: str) -> Dict[str, Any]:
    """
    Fetch video metadata from YouTube page HTML.

    Extracts metadata from:
    - JSON-LD structured data in page HTML
    - Open Graph meta tags
    - YouTube-specific meta tags
    - Embedded JSON data in page source

    Args:
        video_id: YouTube video ID

    Returns:
        Dict with metadata fields:
        {
            'title': str,
            'description': str,
            'channel_id': str,
            'channel_name': str,
            'channel_handle': str (optional),
            'duration_seconds': int,
            'upload_date': str (ISO format),
            'view_count': int,
            'thumbnail_url': str,
            'keywords': List[str]
        }

    Raises:
        httpx.HTTPError: If page fetch fails
    """
    url = f"https://www.youtube.com/watch?v={video_id}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()

    soup = BeautifulSoup(response.content, 'html.parser')
    page_source = str(response.content)

    metadata = {
        'title': 'YouTube Video',
        'description': '',
        'channel_id': '',
        'channel_name': '',
        'channel_handle': '',
        'duration_seconds': 0,
        'upload_date': '',
        'view_count': 0,
        'thumbnail_url': '',
        'keywords': []
    }

    # Extract from JSON-LD structured data
    scripts = soup.find_all('script', {'type': 'application/ld+json'})
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                # Video metadata
                if '@type' in data and data['@type'] == 'VideoObject':
                    metadata['title'] = data.get('name', metadata['title'])
                    metadata['upload_date'] = data.get('uploadDate', '')
                    metadata['thumbnail_url'] = data.get('thumbnailUrl', '')

                    # Parse duration (ISO 8601 format: PT1H23M45S)
                    duration_str = data.get('duration', '')
                    if duration_str:
                        metadata['duration_seconds'] = parse_iso_duration(duration_str)
        except:
            continue

    # Extract from Open Graph meta tags (fallback)
    if not metadata['title'] or metadata['title'] == 'YouTube Video':
        og_title = soup.find('meta', {'property': 'og:title'})
        if og_title:
            metadata['title'] = og_title.get('content', metadata['title'])

    if not metadata['description']:
        og_desc = soup.find('meta', {'property': 'og:description'})
        if og_desc:
            metadata['description'] = og_desc.get('content', '')

    if not metadata['thumbnail_url']:
        og_image = soup.find('meta', {'property': 'og:image'})
        if og_image:
            metadata['thumbnail_url'] = og_image.get('content', '')

    # Extract keywords
    keywords_meta = soup.find('meta', {'name': 'keywords'})
    if keywords_meta:
        keywords_str = keywords_meta.get('content', '')
        metadata['keywords'] = [k.strip() for k in keywords_str.split(',') if k.strip()]

    # Extract from page source JSON (most reliable for channel/view data)
    try:
        # Channel ID
        channel_id_match = re.search(r'"channelId":"([^"]+)"', page_source)
        if channel_id_match:
            metadata['channel_id'] = channel_id_match.group(1)

        # Channel name
        author_match = re.search(r'"author":"([^"]+)"', page_source)
        if author_match:
            metadata['channel_name'] = author_match.group(1)

        # View count
        view_match = re.search(r'"viewCount":"(\d+)"', page_source)
        if view_match:
            metadata['view_count'] = int(view_match.group(1))

        # Channel handle (from ownerChannelName or canonicalBaseUrl)
        handle_match = re.search(r'"ownerChannelName":"([^"]+)"', page_source)
        if handle_match:
            metadata['channel_handle'] = handle_match.group(1)
        else:
            # Try canonicalBaseUrl
            canonical_match = re.search(r'"canonicalBaseUrl":"/@([^"]+)"', page_source)
            if canonical_match:
                metadata['channel_handle'] = f"@{canonical_match.group(1)}"
    except Exception as e:
        print(f"⚠️ Error parsing page source metadata: {e}")

    return metadata


def parse_iso_duration(duration_str: str) -> int:
    """
    Parse ISO 8601 duration string to seconds.

    Examples:
    - PT1H23M45S → 5025 seconds
    - PT5M30S → 330 seconds
    - PT45S → 45 seconds

    Args:
        duration_str: ISO 8601 duration (e.g., PT1H23M45S)

    Returns:
        Total seconds as integer
    """
    if not duration_str or not duration_str.startswith('PT'):
        return 0

    # Remove PT prefix
    duration_str = duration_str[2:]

    hours = 0
    minutes = 0
    seconds = 0

    # Extract hours
    if 'H' in duration_str:
        hours_match = re.search(r'(\d+)H', duration_str)
        if hours_match:
            hours = int(hours_match.group(1))

    # Extract minutes
    if 'M' in duration_str:
        minutes_match = re.search(r'(\d+)M', duration_str)
        if minutes_match:
            minutes = int(minutes_match.group(1))

    # Extract seconds
    if 'S' in duration_str:
        seconds_match = re.search(r'(\d+)S', duration_str)
        if seconds_match:
            seconds = int(seconds_match.group(1))

    return hours * 3600 + minutes * 60 + seconds


async def extract_youtube_data(url: str, language: str = 'en') -> Dict[str, Any]:
    """
    Main function: Extract transcript + metadata from YouTube URL.

    Combines transcript extraction and metadata fetching.
    Handles errors gracefully with partial data fallback.

    Args:
        url: YouTube video URL
        language: Preferred transcript language (default: 'en')

    Returns:
        Dict with complete YouTube data:
        {
            'video_id': str,
            'title': str,
            'transcript': str,  # Full transcript text
            'description': str,
            'channel_id': str,
            'channel_name': str,
            'channel_handle': str,
            'duration': int,  # seconds
            'upload_date': str,  # ISO format
            'view_count': int,
            'thumbnail_url': str,
            'transcript_language': str,
            'auto_generated': bool,
            'keywords': List[str],
            'transcript_available': bool,
            'error': str or None
        }

    Raises:
        ValueError: If video ID extraction fails
    """
    # Extract video ID
    video_id = extract_video_id(url)

    result = {
        'video_id': video_id,
        'title': 'YouTube Video',
        'transcript': '',
        'description': '',
        'channel_id': '',
        'channel_name': '',
        'channel_handle': '',
        'duration': 0,
        'upload_date': '',
        'view_count': 0,
        'thumbnail_url': '',
        'transcript_language': language,
        'auto_generated': False,
        'keywords': [],
        'transcript_available': False,
        'error': None
    }

    # Fetch metadata and transcript in parallel
    metadata_task = asyncio.create_task(get_metadata(video_id))

    transcript_text = None
    transcript_meta = None
    transcript_error = None

    try:
        transcript_text, transcript_meta = await get_transcript(video_id, language)
        result['transcript_available'] = True
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as e:
        transcript_error = str(e)
        print(f"⚠️ Transcript unavailable for {video_id}: {e}")
    except Exception as e:
        transcript_error = str(e)
        print(f"❌ Error fetching transcript for {video_id}: {e}")

    # Get metadata
    try:
        metadata = await metadata_task
        result.update({
            'title': metadata['title'],
            'description': metadata['description'],
            'channel_id': metadata['channel_id'],
            'channel_name': metadata['channel_name'],
            'channel_handle': metadata['channel_handle'],
            'duration': metadata['duration_seconds'],
            'upload_date': metadata['upload_date'],
            'view_count': metadata['view_count'],
            'thumbnail_url': metadata['thumbnail_url'],
            'keywords': metadata['keywords']
        })
    except Exception as e:
        print(f"❌ Error fetching metadata for {video_id}: {e}")
        result['error'] = f"Metadata extraction failed: {str(e)}"

    # Handle transcript data
    if transcript_text:
        result['transcript'] = transcript_text
        if transcript_meta:
            result['transcript_language'] = transcript_meta['transcript_language']
            result['auto_generated'] = transcript_meta['transcript_auto_generated']
            # Use transcript duration if metadata duration not available
            if not result['duration']:
                result['duration'] = transcript_meta['transcript_duration_seconds']
    else:
        # Fallback: use description + title as content
        fallback_content = f"Title: {result['title']}\n\n"
        if result['description']:
            fallback_content += f"Description: {result['description']}\n\n"
        fallback_content += f"Note: Video transcript is not available.\n"
        if transcript_error:
            fallback_content += f"Reason: {transcript_error}"

        result['transcript'] = fallback_content
        result['error'] = transcript_error

    return result
