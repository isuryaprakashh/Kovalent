from app.collectors.prometheus_collector import CollectorConfig, PrometheusTelemetryCollector


class FakeLiveCollector(PrometheusTelemetryCollector):
    def _get_json(self, url: str, params: dict[str, str]) -> dict:
        query = params["query"]
        if "container_cpu_usage_seconds_total" in query:
            return self._vector("checkout-api-7d9f", 820)
        if "resource=\"cpu\"" in query:
            return self._vector("checkout-api-7d9f", 1000)
        if "container_memory_working_set_bytes" in query:
            return self._vector("checkout-api-7d9f", 512)
        if "resource=\"memory\"" in query:
            return self._vector("checkout-api-7d9f", 1024)
        if "container_network_receive_bytes_total" in query:
            return self._vector("checkout-api-7d9f", 120)
        if "container_network_transmit_bytes_total" in query:
            return self._vector("checkout-api-7d9f", 140)
        if "kube_pod_container_status_restarts_total" in query:
            return self._vector("checkout-api-7d9f", 2)
        if "kube_pod_labels" in query:
            return {
                "status": "success",
                "data": {
                    "result": [
                        {
                            "metric": {
                                "namespace": "payments",
                                "pod": "checkout-api-7d9f",
                                "label_app_kubernetes_io_name": "checkout-api",
                            },
                            "value": [0, "1"],
                        }
                    ]
                },
            }
        if "kube_pod_spec_volumes_persistentvolumeclaims_info" in query:
            return {
                "status": "success",
                "data": {
                    "result": [
                        {
                            "metric": {
                                "namespace": "payments",
                                "pod": "checkout-api-7d9f",
                                "persistentvolumeclaim": "checkout-data",
                            },
                            "value": [0, "1"],
                        }
                    ]
                },
            }
        if "container_fs_io_time_seconds_total" in query:
            return self._vector("checkout-api-7d9f", 130)
        if "container_fs_reads_total" in query:
            return self._vector("checkout-api-7d9f", 60)
        if "loki" in url:
            return self._vector("checkout-api-7d9f", 12)
        return {"status": "success", "data": {"result": []}}

    def _vector(self, pod: str, value: float) -> dict:
        return {
            "status": "success",
            "data": {
                "result": [
                    {
                        "metric": {"namespace": "payments", "pod": pod},
                        "value": [0, str(value)],
                    }
                ]
            },
        }


def test_live_collector_maps_prometheus_and_loki_payloads() -> None:
    collector = FakeLiveCollector(
        CollectorConfig(
            prometheus_url="http://prometheus.test",
            loki_url="http://loki.test",
        )
    )

    metrics = collector.collect()

    assert len(metrics) == 1
    metric = metrics[0]
    assert metric.namespace == "payments"
    assert metric.pod == "checkout-api-7d9f"
    assert metric.service == "checkout-api"
    assert metric.cpu_millicores == 820
    assert metric.memory_limit_mb == 1024
    assert metric.pvc_name == "checkout-data"
    assert metric.pvc_latency_ms == 130
    assert metric.error_rate_per_minute == 12
    assert metric.restart_count == 2

