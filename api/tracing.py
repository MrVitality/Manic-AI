"""OpenTelemetry tracing configuration.

Enables distributed tracing across the API, outbound HTTP calls (Ollama, Qdrant),
and database queries. Traces are exported to an OTLP-compatible collector
(Jaeger, Tempo, etc.) when OTEL_EXPORTER_OTLP_ENDPOINT is set.

Set OTEL_ENABLED=true in .env to enable tracing.
"""

import logging
from api.config import settings

logger = logging.getLogger(__name__)


def setup_tracing(app):
    """Configure OpenTelemetry tracing for the FastAPI app."""
    otel_enabled = getattr(settings, 'OTEL_ENABLED', False)
    if not otel_enabled:
        logger.info("OpenTelemetry tracing disabled (set OTEL_ENABLED=true to enable)")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        resource = Resource.create({
            "service.name": "manic-ai-api",
            "service.version": "2.0.0",
            "deployment.environment": "production",
        })

        provider = TracerProvider(resource=resource)

        # Export to OTLP collector if configured
        endpoint = getattr(settings, 'OTEL_EXPORTER_OTLP_ENDPOINT', '')
        if endpoint:
            exporter = OTLPSpanExporter(endpoint=endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("OTLP exporter configured: %s", endpoint)

        trace.set_tracer_provider(provider)

        # Instrument FastAPI
        FastAPIInstrumentor.instrument_app(app)

        # Instrument outbound HTTP (Ollama, Qdrant, SearXNG calls)
        HTTPXClientInstrumentor().instrument()

        # Instrument asyncpg (database queries)
        try:
            from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
            AsyncPGInstrumentor().instrument()
        except Exception:
            logger.debug("asyncpg instrumentation not available")

        logger.info("OpenTelemetry tracing enabled")
    except ImportError as e:
        logger.warning("OpenTelemetry packages not installed: %s", e)
    except Exception as e:
        logger.warning("Failed to setup tracing: %s", e)
