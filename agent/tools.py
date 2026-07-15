# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging
import os
import re
from pathlib import Path
from dotenv import load_dotenv

# Load and override local .env settings for correct project ID and Vertex AI configuration
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=True)

from google import genai
from google.genai import types
from google.adk.tools.tool_context import ToolContext

logger = logging.getLogger(__name__)


def get_restaurants(
    cuisine: str, location: str, tool_context: ToolContext, count: int = 5
) -> str:
    """Call this tool to get a list of restaurants based on a cuisine and location.
    'count' is the number of restaurants to return.
    """
    logger.info(f"--- TOOL CALLED: get_restaurants (count: {count}) ---")
    logger.info(f"  - Cuisine: {cuisine}")
    logger.info(f"  - Location: {location}")

    # Step 1: Attempt to do a real live Google Search Grounding with Gemini
    items = []
    try:
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "vtxdemos")
        location_gcp = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        logger.info(f"Connecting to live Vertex AI using project={project}, location={location_gcp}...")
        
        client = genai.Client(
            vertexai=True,
            project=project,
            location=location_gcp
        )
        
        prompt = f"""
        Find the top {count} {cuisine} restaurants in {location}.
        For each restaurant, provide:
        1. name: Name of the restaurant
        2. detail: A brief 1-2 sentence description of why it's famous
        3. imageUrl: A high-quality relevant image URL (Unsplash or actual restaurant static photo)
        4. rating: Star characters rating based on reviews (e.g. ★★★★☆ or ★★★★★)
        5. infoLink: Markdown link [More Info](official_website_url)
        6. address: Street address
        
        Format your response EXACTLY as a JSON list of objects. Wrap the JSON in a markdown code block like this:
        ```json
        [
          ...
        ]
        ```
        Do not add any conversational text before or after the code block.
        """
        
        model_name = os.getenv("MODEL_NAME", "gemini-3.1-flash-lite")
        logger.info(f"Generating content using model={model_name} with Google Maps grounding...")
        
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_maps=types.GoogleMaps())],
                temperature=0.2
            )
        )
        
        # Extract and parse JSON block
        match = re.search(r"```json\s*(.*?)\s*```", response.text, re.DOTALL)
        json_str = match.group(1) if match else response.text
        items_live = json.loads(json_str)
        
        if items_live and isinstance(items_live, list):
            logger.info(f"  - Success: Retrieved {len(items_live)} real-time restaurants using Google Search Grounding!")
            items = items_live[:count]
            
    except Exception as e:
        logger.warning(f"  - Live Search Grounding failed ({e}). Falling back to local database mock...")

    # Step 2: Fall back to local mock data if live search fails or returned nothing
    if not items:
        if "new york" in location.lower() or "ny" in location.lower():
            try:
                script_dir = os.path.dirname(__file__)
                file_path = os.path.join(script_dir, "restaurant_data.json")
                with open(file_path) as f:
                    restaurant_data_str = f.read()
                    if base_url := tool_context.state.get("base_url"):
                        restaurant_data_str = restaurant_data_str.replace(
                            "http://localhost:10002", base_url
                        )
                        logger.info(f"Updated base URL from tool context: {base_url}")
                    all_items = json.loads(restaurant_data_str)

                # Filter by cuisine if a specific one is requested
                if cuisine and cuisine.strip():
                    clean_cuisine = cuisine.strip().lower()
                    filtered_items = [
                        item for item in all_items 
                        if item.get("cuisine", "").lower() == clean_cuisine
                    ]
                    # If we couldn't find exact match, search in details or default back
                    if not filtered_items:
                        filtered_items = [
                            item for item in all_items 
                            if clean_cuisine in item.get("detail", "").lower() or clean_cuisine in item.get("name", "").lower()
                        ]
                    
                    items = filtered_items[:count]
                else:
                    items = all_items[:count]

                logger.info(
                    f"  - Success (Fallback): Found {len(items)} matching restaurants out of {len(all_items)} total."
                )

            except FileNotFoundError:
                logger.error(f"  - Error: restaurant_data.json not found at {file_path}")
            except json.JSONDecodeError:
                logger.error(f"  - Error: Failed to decode JSON from {file_path}")

    # Step 3: Sanitization & Enrichment post-processing for all returned items
    UNSPLASH_FOOD_IMAGES = {
        "mexican": "https://images.unsplash.com/photo-1565299585323-38d6b0865b47?w=500&auto=format&fit=crop&q=80",
        "italian": "https://images.unsplash.com/photo-1513104890138-7c749659a591?w=500&auto=format&fit=crop&q=80",
        "chinese": "https://images.unsplash.com/photo-1563245372-f21724e3856d?w=500&auto=format&fit=crop&q=80",
        "japanese": "https://images.unsplash.com/photo-1579871494447-9811cf80d66c?w=500&auto=format&fit=crop&q=80",
        "sushi": "https://images.unsplash.com/photo-1579871494447-9811cf80d66c?w=500&auto=format&fit=crop&q=80",
        "french": "https://images.unsplash.com/photo-1550966871-3ed3cdb5ed0c?w=500&auto=format&fit=crop&q=80",
        "indian": "https://images.unsplash.com/photo-1585938338392-50a59970d8ee?w=500&auto=format&fit=crop&q=80",
        "thai": "https://images.unsplash.com/photo-1559314809-0d155014e29e?w=500&auto=format&fit=crop&q=80",
        "spanish": "https://images.unsplash.com/photo-1534080391025-a13093b3410e?w=500&auto=format&fit=crop&q=80",
        "greek": "https://images.unsplash.com/photo-1534080391025-a13093b3410e?w=500&auto=format&fit=crop&q=80"
    }
    
    clean_cuisine = cuisine.strip().lower() if cuisine else "general"
    default_unsplash = UNSPLASH_FOOD_IMAGES.get(
        clean_cuisine, 
        "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=500&auto=format&fit=crop&q=80"
    )

    for item in items:
        name_lower = item.get("name", "").lower()
        
        # 1. Map to high-resolution local assets if available
        if "cosme" in name_lower:
            item["imageUrl"] = "/static/cosme.png"
        elif "casa enrique" in name_lower:
            item["imageUrl"] = "/static/casaenrique.png"
        elif "empellon" in name_lower or "empellón" in name_lower:
            item["imageUrl"] = "/static/empellon.png"
        elif "la esquina" in name_lower:
            item["imageUrl"] = "/static/laesquina.png"
        elif "los tacos" in name_lower:
            item["imageUrl"] = "/static/lostacos.png"
        else:
            # 2. For any other restaurant, always use the premium, cuisine-aligned fallback (e.g. delicious street tacos for Mexican)
            item["imageUrl"] = default_unsplash

        # 3. Standardize and ensure the infoLink is valid markdown
        link = item.get("infoLink", "")
        if link and not link.startswith("["):
            item["infoLink"] = f"[More Info]({link})"
        elif not link:
            item["infoLink"] = "[More Info](https://www.google.com/search?q=" + item.get("name", "").replace(" ", "+") + ")"

    return json.dumps(items)
