"""Tests for OpenTelemetry tracing setup."""

import sys
from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI


@pytest.fixture()
def bare_app() -> FastAPI:
    """A minimal FastAPI app not wired to the full create_app() factory."""
    return FastAPI()


def test_setup_tracing_disabled_by_default(bare_app):
    """Tracing should not crash and should return early when OTEL_ENABLED=False."""
    with patch("api.tracing.settings") as mock_settings:
        mock_settings.OTEL_ENABLED = False

        from api.tracing import setup_tracing

        # Should complete without error and return None
        result = setup_tracing(bare_app)
        assert result is None


def test_setup_tracing_handles_missing_packages(bare_app):
    """Should handle ImportError gracefully and log a warning instead of crashing."""
    with patch("api.tracing.settings") as mock_settings:
        mock_settings.OTEL_ENABLED = True
        mock_settings.OTEL_EXPORTER_OTLP_ENDPOINT = ""

        # Force opentelemetry imports to fail
        with patch.dict(sys.modules, {
            "opentelemetry": None,
            "opentelemetry.trace": None,
            "opentelemetry.sdk": None,
            "opentelemetry.sdk.trace": None,
            "opentelemetry.sdk.trace.export": None,
            "opentelemetry.sdk.resources": None,
            "opentelemetry.exporter": None,
            "opentelemetry.exporter.otlp": None,
            "opentelemetry.exporter.otlp.proto": None,
            "opentelemetry.exporter.otlp.proto.grpc": None,
            "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": None,
            "opentelemetry.instrumentation": None,
            "opentelemetry.instrumentation.fastapi": None,
            "opentelemetry.instrumentation.httpx": None,
            "opentelemetry.instrumentation.asyncpg": None,
        }):
            # Re-import to pick up the patched sys.modules inside the function
            import importlib
            import api.tracing as tracing_module
            importlib.reload(tracing_module)

            # Should not raise — ImportError caught internally
            tracing_module.setup_tracing(bare_app)


def test_setup_tracing_enabled_no_endpoint(bare_app):
    """When OTEL_ENABLED=True but no endpoint set, provider is set without an exporter."""
    mock_provider = MagicMock()
    mock_trace = MagicMock()
    mock_resource_cls = MagicMock(return_value=MagicMock())
    mock_tracer_provider_cls = MagicMock(return_value=mock_provider)
    mock_instrumentor = MagicMock()
    mock_httpx_instrumentor = MagicMock(return_value=mock_instrumentor)

    otel_mocks = {
        "opentelemetry": MagicMock(),
        "opentelemetry.trace": mock_trace,
        "opentelemetry.sdk": MagicMock(),
        "opentelemetry.sdk.trace": MagicMock(TracerProvider=mock_tracer_provider_cls),
        "opentelemetry.sdk.trace.export": MagicMock(),
        "opentelemetry.sdk.resources": MagicMock(Resource=mock_resource_cls),
        "opentelemetry.exporter": MagicMock(),
        "opentelemetry.exporter.otlp": MagicMock(),
        "opentelemetry.exporter.otlp.proto": MagicMock(),
        "opentelemetry.exporter.otlp.proto.grpc": MagicMock(),
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": MagicMock(),
        "opentelemetry.instrumentation": MagicMock(),
        "opentelemetry.instrumentation.fastapi": MagicMock(),
        "opentelemetry.instrumentation.httpx": MagicMock(
            HTTPXClientInstrumentor=mock_httpx_instrumentor
        ),
        "opentelemetry.instrumentation.asyncpg": MagicMock(),
    }

    with patch("api.tracing.settings") as mock_settings:
        mock_settings.OTEL_ENABLED = True
        mock_settings.OTEL_EXPORTER_OTLP_ENDPOINT = ""

        with patch.dict(sys.modules, otel_mocks):
            import importlib
            import api.tracing as tracing_module
            importlib.reload(tracing_module)

            tracing_module.setup_tracing(bare_app)

        # No exporter span processor should have been added
        mock_provider.add_span_processor.assert_not_called()
