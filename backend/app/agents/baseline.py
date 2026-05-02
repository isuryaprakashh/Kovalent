import statistics
from app.models import AgentFinding, PodMetric, Severity


class BaselineAgent:
    name = "Baseline Agent"

    def analyze(self, metrics: list[PodMetric]) -> list[AgentFinding]:
        findings: list[AgentFinding] = []
        
        # Group metrics by service
        service_metrics: dict[str, list[PodMetric]] = {}
        for m in metrics:
            service_metrics.setdefault(m.service, []).append(m)
            
        for service, pods in service_metrics.items():
            if len(pods) < 3:
                continue # Need at least 3 pods for meaningful baseline comparison
                
            # Compare CPU ratio baseline
            cpu_values = [p.cpu_ratio for p in pods]
            avg_cpu = statistics.mean(cpu_values)
            stdev_cpu = statistics.stdev(cpu_values) if len(pods) > 1 else 0
            
            for p in pods:
                if stdev_cpu > 0.05 and abs(p.cpu_ratio - avg_cpu) > (2 * stdev_cpu):
                    findings.append(
                        AgentFinding(
                            agent=self.name,
                            status=Severity.INFO,
                            pod=p.pod,
                            service=p.service,
                            signal="baseline_deviation_cpu",
                            message=f"{p.pod} CPU is significantly different from service average ({p.cpu_ratio:.2f} vs {avg_cpu:.2f}).",
                            value=p.cpu_ratio,
                            threshold=avg_cpu,
                        )
                    )
        return findings
