import asyncio
from app.agents.network import NetworkAgent
from app.agents.restart import RestartAgent
from app.agents.baseline import BaselineAgent
from app.models import PodMetric, Severity
from datetime import datetime, timezone

def test_network_agent() -> None:
    agent = NetworkAgent()
    metrics = [
        PodMetric(
            namespace="default", pod="heavy-net", service="heavy-svc",
            cpu_millicores=100, cpu_limit_millicores=1000,
            memory_mb=100, memory_limit_mb=1000,
            network_rx_kbps=6000, network_tx_kbps=5000, # 11MB/s total
            observed_at=datetime.now(timezone.utc)
        )
    ]
    findings = agent.analyze(metrics)
    assert len(findings) == 1
    assert findings[0].signal == "network_saturation"
    assert findings[0].status == Severity.WARNING

def test_restart_agent() -> None:
    agent = RestartAgent()
    metrics = [
        PodMetric(
            namespace="default", pod="crasher", service="crash-svc",
            cpu_millicores=100, cpu_limit_millicores=1000,
            memory_mb=100, memory_limit_mb=1000,
            network_rx_kbps=0, network_tx_kbps=0,
            restart_count=10,
            observed_at=datetime.now(timezone.utc)
        )
    ]
    findings = agent.analyze(metrics)
    assert len(findings) == 1
    assert findings[0].signal == "pod_restarts"
    assert findings[0].status == Severity.CRITICAL

def test_baseline_agent() -> None:
    agent = BaselineAgent()
    now = datetime.now(timezone.utc)
    def m(pod, cpu):
        return PodMetric(
            namespace="d", pod=pod, service="s", 
            cpu_millicores=cpu, cpu_limit_millicores=100, 
            memory_mb=100, memory_limit_mb=1000,
            network_rx_kbps=0, network_tx_kbps=0,
            observed_at=now
        )
    
    # Provide more baseline points to reduce the stdev and make the anomaly stand out
    metrics = [m(f"p{i}", 10) for i in range(10)]
    metrics.append(m("anomaly", 90))
    
    findings = agent.analyze(metrics)
    # The anomaly pod should be flagged
    assert any(f.pod == "anomaly" for f in findings)
    assert any(f.signal == "baseline_deviation_cpu" for f in findings)
