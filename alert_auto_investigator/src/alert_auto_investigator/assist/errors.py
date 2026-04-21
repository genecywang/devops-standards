from __future__ import annotations


class AnalysisError(Exception):
    pass


class AnalysisTimeoutError(AnalysisError):
    pass


class AnalysisRateLimitError(AnalysisError):
    pass


class AnalysisProviderError(AnalysisError):
    pass


class AnalysisSchemaError(AnalysisError):
    pass


class AnalysisRedactionBlockedError(AnalysisError):
    pass
