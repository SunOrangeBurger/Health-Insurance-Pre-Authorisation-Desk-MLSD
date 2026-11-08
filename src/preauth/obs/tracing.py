from contextlib import contextmanager
from typing import Any, Iterator

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


_configured = False


def configure_tracing(service_name: str, endpoint: str, enabled: bool = True) -> None:
    global _configured
    if _configured or not enabled:
        return
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    )
    trace.set_tracer_provider(provider)
    _configured = True


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Any]:
    tracer = trace.get_tracer("preauth-desk")
    clean = {key: value for key, value in attributes.items() if value is not None}
    with tracer.start_as_current_span(name, attributes=clean) as active:
        yield active

