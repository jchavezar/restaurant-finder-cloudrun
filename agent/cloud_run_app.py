# Copyright 2026 Google LLC
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

"""Serve the restaurant A2A agent and the built Lit client on one port."""

import logging
import os
from pathlib import Path

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from agent import RestaurantAgent
from agent_executor import RestaurantAgentExecutor
from starlette.staticfiles import StaticFiles


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app():
    """Create the combined A2A and frontend ASGI application."""
    if os.getenv("GOOGLE_GENAI_USE_VERTEXAI") != "TRUE" and not os.getenv(
        "GEMINI_API_KEY"
    ):
        raise RuntimeError(
            "Set GEMINI_API_KEY or configure GOOGLE_GENAI_USE_VERTEXAI=TRUE."
        )

    agent_url = os.environ["AGENT_URL"].rstrip("/")
    agent = RestaurantAgent(base_url=agent_url)
    request_handler = DefaultRequestHandler(
        agent_executor=RestaurantAgentExecutor(agent),
        task_store=InMemoryTaskStore(),
    )
    app = A2AStarletteApplication(
        agent_card=agent.agent_card,
        http_handler=request_handler,
    ).build()

    app.mount("/static", StaticFiles(directory="images"), name="agent-static")

    # Mount this last so the A2A routes registered above retain precedence.
    frontend_dir = Path(os.getenv("FRONTEND_DIR", "/app/frontend"))
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    logger.info("Starting combined A2UI demo on port %d", port)
    uvicorn.run(app, host="0.0.0.0", port=port)
