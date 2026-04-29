#!/usr/bin/env python3
"""
Voice Agent Backend: LiveKit Cloud + Cartesia TTS + Cerebras LLM + FastAPI
Single-file implementation for easy deployment & testing.

Usage:
  python voice_agent_backend.py api          # Run FastAPI server (port 8000)
  python voice_agent_backend.py agent        # Run LiveKit Agent worker
  python voice_agent_backend.py agent --dev  # Run agent in dev mode
  python voice_agent_backend.py --help       # Show help

Environment Variables (.env):
  LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_URL
  CEREBRAS_API_KEY, CEREBRAS_MODEL, CEREBRAS_BASE_URL
  CARTESIA_API_KEY (optional, if not using LiveKit Inference)
  LOG_LEVEL, ENVIRONMENT, CORS_ORIGINS
"""

import os
import sys
import time
import logging
import argparse
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load environment variables early
load_dotenv(".env")

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("voice-agent")

# ============================================================================
# FASTAPI SECTION - Token Generation & API Endpoints
# ============================================================================

try:
    from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    from pydantic import field_validator
    from livekit import api as livekit_api
    from livekit.api import RoomAgentDispatch
    import uvicorn

    FASTAPI_AVAILABLE = True
except Exception:
    FASTAPI_AVAILABLE = False
    logger.warning("FastAPI dependencies not installed. API server mode disabled.")


if FASTAPI_AVAILABLE:
    class TokenRequest(BaseModel):
        room_name: Optional[str] = Field(
            None, description="Optional room name (auto-generated if not provided)"
        )
        participant_identity: Optional[str] = Field(None, description="Unique user identity")
        participant_name: str = Field("User", description="Display name for participant")
        participant_metadata: Optional[str] = Field(None, description="JSON string metadata")
        participant_attributes: Optional[Dict[str, str]] = Field(default_factory=dict)
        agent_name: str = Field("voice-agent", description="Name of agent to dispatch")
        room_config: Optional[Dict[str, Any]] = Field(
            None, description="Additional room configuration"
        )

        @field_validator("participant_name")
        @classmethod
        def validate_name(cls, v: str) -> str:
            if len(v.strip()) == 0:
                raise ValueError("Participant name cannot be empty")
            return v.strip()


    class TokenResponse(BaseModel):
        server_url: str
        participant_token: str
        room_name: str
        agent_name: str
        expires_at: Optional[int] = None


    class HealthResponse(BaseModel):
        status: str
        service: str
        version: str = "1.0.0"
        timestamp: int = Field(default_factory=lambda: int(time.time()))


    async def verify_auth(authorization: str = Header(...)) -> Dict[str, Any]:
        """
        Verify authorization token.
        Replace this with your actual JWT/OAuth validation logic.
        """
        try:
            if not authorization or not authorization.startswith("Bearer "):
                raise HTTPException(401, "Missing or invalid authorization header")

            return {
                "user_id": "demo_user",
                "permissions": ["voice_agent", "room_create"],
                "token_valid": True,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Auth error: {e}")
            raise HTTPException(401, "Authentication failed")


    def create_fastapi_app() -> FastAPI:
        """Create and configure FastAPI application."""

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            logger.info("Starting Voice Agent Backend API...")

            required_vars = ["LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "LIVEKIT_URL", "CEREBRAS_API_KEY"]
            missing = [var for var in required_vars if not os.getenv(var)]
            if missing:
                logger.warning(f"Missing environment variables: {missing}")
                logger.warning("API may not function correctly without these values")

            yield

            logger.info("Shutting down Voice Agent Backend API...")

        app = FastAPI(
            title="Voice Agent Backend",
            description="FastAPI backend for LiveKit voice agent with Cartesia TTS + Cerebras LLM",
            version="1.0.0",
            lifespan=lifespan,
            docs_url="/docs",
            redoc_url="/redoc",
            openapi_url="/openapi.json",
        )

        app.add_middleware(
            CORSMiddleware,
            allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )

        @app.get("/health", response_model=HealthResponse, tags=["health"])
        async def health_check():
            return HealthResponse(status="healthy", service="voice-agent-backend")

        @app.get("/", tags=["info"])
        async def root():
            return {
                "message": "Voice Agent Backend API",
                "documentation": "/docs",
                "health": "/health",
                "endpoints": {"POST /api/token": "Generate LiveKit access token for client connection"},
                "version": "1.0.0",
            }

        async def log_token_event(user_id: str, room_name: str, agent_name: str):
            try:
                logger.info(
                    f"Event: token_generated | user={user_id} | room={room_name} | agent={agent_name}"
                )
            except Exception as e:
                logger.error(f"Failed to log token event: {e}")

        @app.post(
            "/api/token",
            response_model=TokenResponse,
            status_code=201,
            tags=["authentication"],
        )
        async def generate_token(
            request: TokenRequest,
            background_tasks: BackgroundTasks,
            auth: Dict[str, Any] = Depends(verify_auth),
        ):
            try:
                api_key = os.getenv("LIVEKIT_API_KEY")
                api_secret = os.getenv("LIVEKIT_API_SECRET")
                server_url = os.getenv("LIVEKIT_URL")

                if not all([api_key, api_secret, server_url]):
                    logger.error("Missing LiveKit configuration")
                    raise HTTPException(500, "Server configuration error: Missing LiveKit credentials")

                room_name = request.room_name or f"room-{int(time.time())}-{os.urandom(4).hex()}"
                participant_identity = request.participant_identity or (
                    f"user-{auth['user_id']}-{int(time.time())}-{os.urandom(3).hex()}"
                )

                logger.info(f"Generating token for room={room_name}, user={participant_identity}")

                token_builder = (
                    livekit_api.AccessToken(api_key, api_secret)
                    .with_identity(participant_identity)
                    .with_name(request.participant_name)
                    .with_grants(
                        livekit_api.VideoGrants(
                            room_join=True,
                            room=room_name,
                            can_publish=True,
                            can_subscribe=True,
                            can_publish_data=True,
                            can_update_own_metadata=True,
                        )
                    )
                )

                if request.participant_metadata:
                    token_builder = token_builder.with_metadata(request.participant_metadata)

                if request.participant_attributes:
                    token_builder = token_builder.with_attributes(request.participant_attributes)

                if request.agent_name:
                    from livekit.protocol.room import RoomConfiguration
                    room_cfg = RoomConfiguration(
                        agents=[RoomAgentDispatch(agent_name=request.agent_name)]
                    )
                    token_builder = token_builder.with_room_config(room_cfg)

                jwt_token = token_builder.to_jwt()
                expires_at = int(time.time()) + (24 * 60 * 60)

                background_tasks.add_task(
                    log_token_event,
                    user_id=auth["user_id"],
                    room_name=room_name,
                    agent_name=request.agent_name,
                )

                return TokenResponse(
                    server_url=server_url,
                    participant_token=jwt_token,
                    room_name=room_name,
                    agent_name=request.agent_name,
                    expires_at=expires_at,
                )

            except HTTPException:
                raise
            except Exception as e:
                logger.exception(f"Token generation failed: {e}")
                raise HTTPException(500, f"Failed to generate token: {str(e)}")

        return app


# ============================================================================
# LIVEKIT AGENT SECTION - Voice Pipeline with Cerebras + Cartesia
# ============================================================================

try:
    from livekit.agents import (
        AgentServer,
        AgentSession,
        Agent,
        room_io,
        TurnHandlingOptions,
        JobContext,
        cli,
    )
    from livekit.plugins import deepgram, silero  # noqa: F401
    try:
        from livekit.plugins import ai_coustics  # type: ignore
        HAVE_AI_COUSTICS = True
    except Exception:
        ai_coustics = None  # type: ignore
        HAVE_AI_COUSTICS = False
    from livekit.plugins.openai import LLM as OpenAILLM
    LIVEKIT_AVAILABLE = True
except Exception:
    LIVEKIT_AVAILABLE = False
    logger.warning("LiveKit Agents dependencies not installed. Agent mode disabled.")


if LIVEKIT_AVAILABLE:
    def _create_cerebras_llm() -> OpenAILLM:
        model = os.getenv("CEREBRAS_MODEL", "llama3.1-8b")
        temperature = float(os.getenv("CEREBRAS_TEMPERATURE", "0.7"))
        logger.info(f"Cerebras LLM initialized: model={model}")
        return OpenAILLM.with_cerebras(
            model=model,
            api_key=os.getenv("CEREBRAS_API_KEY"),
            temperature=temperature,
        )


    class VoiceAssistant(Agent):
        DEFAULT_SYSTEM_PROMPT = """
You are a helpful, friendly, and concise voice assistant.

Guidelines:
- Keep responses natural and conversational (1-3 sentences preferred)
- Avoid markdown, emojis, lists, or complex formatting
- Speak in a warm, professional tone
- Ask clarifying questions when user intent is unclear
- If you don't know something, say so honestly and offer to help with what you can
- Never make up facts or pretend to have capabilities you don't have
- End responses with a question or prompt to keep conversation flowing when appropriate

You are integrated with a voice interface, so:
- Use natural speech patterns (contractions, pauses implied by punctuation)
- Avoid reading out URLs, code, or complex data unless specifically asked
- If providing numbers/dates, speak them naturally
""".strip()

        def __init__(self, system_prompt: Optional[str] = None):
            super().__init__(instructions=system_prompt or self.DEFAULT_SYSTEM_PROMPT)
            logger.info("VoiceAssistant initialized")

        async def on_enter(self):
            logger.info("Agent entered room, sending greeting")
            await self.session.generate_reply(
                instructions="Greet the user warmly in 1 short sentence and ask how you can help today."
            )

        async def on_user_turn_completed(self, turn_ctx, new_message):
            if new_message.text_content.lower().strip().startswith("/help"):
                await self.session.generate_reply(
                    instructions="Briefly explain 3 things you can help with in a friendly voice."
                )
                return
            await super().on_user_turn_completed(turn_ctx, new_message)


    async def voice_agent_session(ctx: JobContext):
        """Module-level entrypoint so multiprocessing can pickle it on Windows."""
        logger.info(f"New agent session: room={ctx.room.name}, job={ctx.job.id}")

        vad = silero.VAD.load(
            min_speech_duration=0.25,
            min_silence_duration=0.5,
            prefix_padding_duration=0.1,
            max_buffered_speech=3.0,
        )

        llm = _create_cerebras_llm()

        turn_handling = _build_turn_handling()
        session_kwargs: Dict[str, Any] = {
            "stt": "deepgram/nova-3:multi",
            "llm": llm,
            "tts": "cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
            "vad": vad,
            "use_tts_aligned_transcript": True,
        }
        if turn_handling is not None:
            session_kwargs["turn_handling"] = turn_handling

        session = AgentSession(**session_kwargs)

        await session.start(
            room=ctx.room,
            agent=VoiceAssistant(),
            room_options=room_io.RoomOptions(
                audio_input=room_io.AudioInputOptions(
                    noise_cancellation=(
                        ai_coustics.audio_enhancement(model=ai_coustics.EnhancerModel.QUAIL_VF_L)
                        if HAVE_AI_COUSTICS
                        else None
                    ),
                ),
                audio_output=room_io.AudioOutputOptions(sample_rate=24000),
            ),
        )

        logger.info(f"Agent session started successfully: {ctx.room.name}")


    def create_agent_server() -> AgentServer:
        if not LIVEKIT_AVAILABLE:
            raise RuntimeError("LiveKit Agents not available. Install requirements first.")

        worker_host = os.getenv("AGENT_HTTP_HOST", "").strip()
        worker_port = int(os.getenv("AGENT_HTTP_PORT", "8081"))
        server = AgentServer(host=worker_host, port=worker_port)

        server.rtc_session(voice_agent_session, agent_name="voice-agent")

        logger.info("AgentServer configured with 'voice-agent' endpoint")
        return server


    def _build_turn_handling() -> Optional[TurnHandlingOptions]:
        """
        Turn detection is optional because some turn-detector models require
        downloading extra files before first run.
        """
        use_turn = os.getenv("USE_TURN_DETECTOR", "0").strip().lower() in {"1", "true", "yes", "on"}
        if not use_turn:
            return None

        try:
            from livekit.plugins.turn_detector.multilingual import MultilingualModel

            return TurnHandlingOptions(
                turn_detection=MultilingualModel(),
                min_turn_duration_ms=800,
                max_turn_duration_ms=8000,
            )
        except Exception as e:
            logger.warning(f"Turn detector unavailable, continuing without it: {type(e).__name__}: {e}")
            return None


# ============================================================================
# CLI & ENTRY POINT - Unified Runner for API or Agent Mode
# ============================================================================


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Voice Agent Backend: LiveKit + Cartesia + Cerebras + FastAPI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="mode", help="Operation mode", required=True)

    api_parser = subparsers.add_parser("api", help="Run FastAPI backend server")
    api_parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    api_parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    api_parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev only)")

    agent_parser = subparsers.add_parser("agent", help="Run LiveKit Agent worker")
    agent_parser.add_argument("--dev", action="store_true", help="Run in development mode")
    agent_parser.add_argument("--console", action="store_true", help="Run in console mode (local testing)")
    agent_parser.add_argument(
        "--download-files", action="store_true", help="Download model files and exit"
    )
    agent_parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=os.getenv("LOG_LEVEL", "INFO"),
        help="Logging level",
    )

    return parser.parse_args()


def run_api_server(host: str, port: int, reload: bool):
    if not FASTAPI_AVAILABLE:
        logger.error("FastAPI not available. Install Backend/requirements.txt first.")
        sys.exit(1)

    logger.info(f"Starting FastAPI server on {host}:{port} (reload={reload})")

    uvicorn.run(
        "voice_agent_backend:create_fastapi_app",
        host=host,
        port=port,
        reload=reload,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
        factory=True,
    )


def run_agent_worker(dev: bool = False, console: bool = False, download_files: bool = False):
    if not LIVEKIT_AVAILABLE:
        logger.error("LiveKit Agents not available. Install Backend/requirements.txt first.")
        sys.exit(1)

    required = ["LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "LIVEKIT_URL", "CEREBRAS_API_KEY"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        logger.error(f"Agent mode requires environment variables: {missing}")
        sys.exit(1)

    logger.info(f"Starting Agent Worker (dev={dev}, console={console})")
    server = create_agent_server()

    logger.info("Running agent worker")
    # livekit.agents.cli.run_app() is a Typer-based CLI that parses sys.argv.
    # Since we're already in our own argparse subcommand ("agent"), translate
    # our flags into LiveKit CLI subcommands.
    if download_files:
        lk_cmd = "download-files"
    elif console:
        lk_cmd = "console"
    elif dev:
        lk_cmd = "dev"
    else:
        lk_cmd = "start"

    sys.argv = [sys.argv[0], lk_cmd]
    cli.run_app(server)


def main():
    args = parse_arguments()

    if hasattr(args, "log_level"):
        logging.getLogger().setLevel(getattr(logging, args.log_level, logging.INFO))

    logger.info(f"Voice Agent Backend starting in '{args.mode}' mode")

    try:
        if args.mode == "api":
            run_api_server(host=args.host, port=args.port, reload=args.reload)
        elif args.mode == "agent":
            run_agent_worker(dev=args.dev, console=args.console, download_files=args.download_files)
        else:
            logger.error(f"Unknown mode: {args.mode}")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

