import asyncio

from app.collectors.kubernetes_collector import (
    KubernetesCollectorConfig,
    KubernetesCollectionError,
    KubernetesDiscoveryCollector,
    parse_events,
    parse_namespaces,
    parse_pods,
)


def test_parse_kubernetes_payload_discovers_pod_owner_pvc_node_and_restart_state() -> None:
    pods_payload = {
        "items": [
            {
                "metadata": {
                    "namespace": "payments",
                    "name": "checkout-api-7d9f4c8c6f-abcde",
                    "labels": {"app.kubernetes.io/name": "checkout-api"},
                    "ownerReferences": [
                        {
                            "kind": "ReplicaSet",
                            "name": "checkout-api-7d9f4c8c6f",
                            "controller": True,
                        }
                    ],
                },
                "spec": {
                    "nodeName": "minikube",
                    "volumes": [
                        {"name": "data", "persistentVolumeClaim": {"claimName": "checkout-data"}},
                        {"name": "tmp", "emptyDir": {}},
                    ],
                },
                "status": {
                    "phase": "Running",
                    "containerStatuses": [
                        {
                            "restartCount": 3,
                            "state": {"waiting": {"reason": "CrashLoopBackOff"}},
                            "lastState": {"terminated": {"reason": "OOMKilled"}},
                        }
                    ],
                },
            }
        ]
    }
    events_payload = {
        "items": [
            {
                "metadata": {"namespace": "payments", "name": "checkout-warning"},
                "involvedObject": {
                    "kind": "Pod",
                    "namespace": "payments",
                    "name": "checkout-api-7d9f4c8c6f-abcde",
                },
                "reason": "BackOff",
                "message": "Back-off restarting failed container",
                "type": "Warning",
                "count": 4,
            }
        ]
    }

    events = parse_events(events_payload)
    pods = parse_pods(pods_payload, events)
    pod = pods[("payments", "checkout-api-7d9f4c8c6f-abcde")]

    assert pod.service == "checkout-api"
    assert pod.owner_kind == "ReplicaSet"
    assert pod.owner_name == "checkout-api-7d9f4c8c6f"
    assert pod.workload_kind == "Deployment"
    assert pod.workload_name == "checkout-api"
    assert pod.node_name == "minikube"
    assert pod.pvc_mounts == ["checkout-data"]
    assert pod.restart_count == 3
    assert pod.waiting_reason == "CrashLoopBackOff"
    assert pod.last_termination_reason == "OOMKilled"
    assert pod.oom_killed is True
    assert pod.events[0].reason == "BackOff"


def test_parse_namespaces_returns_sorted_names() -> None:
    payload = {
        "items": [
            {"metadata": {"name": "kube-system"}},
            {"metadata": {"name": "default"}},
        ]
    }

    assert parse_namespaces(payload) == ["default", "kube-system"]


def test_kubernetes_collector_converts_failures_to_status() -> None:
    class BrokenCollector(KubernetesDiscoveryCollector):
        def _load_with_kubectl(self) -> dict:
            raise KubernetesCollectionError("api server unavailable")

    collector = BrokenCollector(KubernetesCollectorConfig())

    discovery = asyncio.run(collector.collect())

    assert discovery.pods == {}
    assert discovery.namespaces == []
    assert discovery.status["available"] is False
    assert "api server unavailable" in discovery.status["message"]
