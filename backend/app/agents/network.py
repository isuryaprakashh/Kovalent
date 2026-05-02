from app.models import AgentFinding, PodMetric, Severity


class NetworkAgent:
    name = "Network Agent"

    def analyze(self, metrics: list[PodMetric]) -> list[AgentFinding]:
        findings: list[AgentFinding] = []
        for metric in metrics:
            # Check for high network throughput (combined RX/TX > 10MB/s as warning)
            throughput = metric.network_rx_kbps + metric.network_tx_kbps
            if throughput >= 10000:
                findings.append(
                    AgentFinding(
                        agent=self.name,
                        status=Severity.WARNING if throughput < 50000 else Severity.CRITICAL,
                        pod=metric.pod,
                        service=metric.service,
                        signal="network_saturation",
                        message=f"{metric.pod} network throughput is high: {throughput/1024:.1f} MB/s.",
                        value=throughput,
                        threshold=10000,
                    )
                )
        return findings
