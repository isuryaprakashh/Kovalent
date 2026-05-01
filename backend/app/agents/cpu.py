from app.models import AgentFinding, PodMetric, Severity


class CpuAgent:
    name = "CPU Agent"

    def analyze(self, metrics: list[PodMetric]) -> list[AgentFinding]:
        findings: list[AgentFinding] = []
        for metric in metrics:
            if metric.cpu_ratio >= 0.8:
                findings.append(
                    AgentFinding(
                        agent=self.name,
                        status=Severity.WARNING if metric.cpu_ratio < 0.95 else Severity.CRITICAL,
                        pod=metric.pod,
                        service=metric.service,
                        signal="cpu_saturation",
                        message=f"{metric.pod} is using {metric.cpu_ratio:.0%} of its CPU limit.",
                        value=metric.cpu_ratio,
                        threshold=0.8,
                    )
                )
        return findings

