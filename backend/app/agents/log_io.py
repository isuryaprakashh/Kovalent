from app.models import AgentFinding, PodMetric, Severity


class LogIoAgent:
    name = "Log/IO Agent"

    def analyze(self, metrics: list[PodMetric]) -> list[AgentFinding]:
        findings: list[AgentFinding] = []
        for metric in metrics:
            if metric.error_rate_per_minute >= 10:
                findings.append(
                    AgentFinding(
                        agent=self.name,
                        status=Severity.WARNING if metric.error_rate_per_minute < 30 else Severity.CRITICAL,
                        pod=metric.pod,
                        service=metric.service,
                        signal="application_errors",
                        message=f"{metric.service} is emitting {metric.error_rate_per_minute:.0f} errors per minute.",
                        value=metric.error_rate_per_minute,
                        threshold=10,
                    )
                )
        return findings

