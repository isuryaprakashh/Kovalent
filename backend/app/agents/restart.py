from app.models import AgentFinding, PodMetric, Severity


class RestartAgent:
    name = "Restart Agent"

    def analyze(self, metrics: list[PodMetric]) -> list[AgentFinding]:
        findings: list[AgentFinding] = []
        for metric in metrics:
            # Check for sudden restarts
            if metric.restart_count > 0:
                findings.append(
                    AgentFinding(
                        agent=self.name,
                        status=Severity.WARNING if metric.restart_count < 5 else Severity.CRITICAL,
                        pod=metric.pod,
                        service=metric.service,
                        signal="pod_restarts",
                        message=f"{metric.pod} has restarted {metric.restart_count} times.",
                        value=float(metric.restart_count),
                        threshold=1.0,
                    )
                )
        return findings
