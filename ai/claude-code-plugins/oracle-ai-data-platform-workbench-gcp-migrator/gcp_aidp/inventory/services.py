"""Cloud Storage, and the services migrated after 0.1 (inventoried so the plan
never understates the estate): Dataproc, Composer, Dataform, Dataflow, Vertex AI.

Metadata GETs only. A service whose API is not enabled cannot hold resources,
so it is recorded as `api_disabled` with nothing found, not as an error. A
call that is refused for any other reason is recorded under `not_scanned`.
"""
from __future__ import annotations

from typing import Callable

from gcp_aidp.gcp_client import GcpClient, GcpError

GCS = "https://storage.googleapis.com/storage/v1"


def _scan(collections: dict[str, Callable[[], list[dict]]], depends: dict[str, str] | None = None) -> dict:
    """Run each collection's fetch. A collection listed in `depends` is only as
    scanned as its parent: Composer DAGs are found through the environments."""
    items: dict[str, list[dict]] = {}
    not_scanned: dict[str, str] = {}
    disabled = False
    for name, fetch in collections.items():
        parent = (depends or {}).get(name)
        if parent in not_scanned:
            items[name] = []
            not_scanned[name] = f"{parent} were not scanned"
            continue
        try:
            items[name] = fetch()
        except GcpError as exc:
            items[name] = []
            if exc.api_disabled:
                disabled = True
            else:
                not_scanned[name] = str(exc)
    summary: dict = {k: len(v) for k, v in items.items() if k not in not_scanned}
    if disabled:
        summary["api_disabled"] = True
    if not_scanned:
        summary["not_scanned"] = not_scanned
    return {"summary": summary, "items": items}


def _per_region(regions, fetch) -> list[dict]:
    out: list[dict] = []
    for region in regions:
        out += fetch(region)
    return out


def scan_gcs(client: GcpClient, **_) -> dict:
    def buckets():
        return [{"name": b["name"], "location": b.get("location"), "storage_class": b.get("storageClass")}
                for b in client.pages(f"{GCS}/b", "items", {"project": client.project})]
    return _scan({"buckets": buckets})


def scan_dataproc(client: GcpClient, *, regions=("us-central1",), **_) -> dict:
    base = f"https://dataproc.googleapis.com/v1/projects/{client.project}/regions"

    def clusters():
        return _per_region(regions, lambda r: [
            {"name": c["clusterName"], "region": r,
             "image_version": c.get("config", {}).get("softwareConfig", {}).get("imageVersion"),
             "worker_count": c.get("config", {}).get("workerConfig", {}).get("numInstances")}
            for c in client.pages(f"{base}/{r}/clusters", "clusters")])

    def jobs():
        return _per_region(regions, lambda r: [
            {"id": j["reference"]["jobId"], "region": r, "cluster": j.get("placement", {}).get("clusterName"),
             "job_type": next((k.removesuffix("Job") for k in j if k.endswith("Job")), "unknown")}
            for j in client.pages(f"{base}/{r}/jobs", "jobs")])

    return _scan({"clusters": clusters, "jobs": jobs})


def scan_composer(client: GcpClient, *, regions=("us-central1",), **_) -> dict:
    envs: list[dict] = []

    def environments():
        for r in regions:
            for e in client.pages(f"https://composer.googleapis.com/v1/projects/{client.project}"
                                  f"/locations/{r}/environments", "environments"):
                envs.append({"name": e["name"].rsplit("/", 1)[-1], "region": r,
                             "image_version": e.get("config", {}).get("softwareConfig", {}).get("imageVersion"),
                             "dag_prefix": e.get("config", {}).get("dagGcsPrefix")})
        return envs

    def dags():
        # DAG files listed from the environment's bucket (object metadata only).
        # ponytail: one DAG per .py file is assumed; a file defining several DAGs is counted once.
        out = []
        for e in envs:
            prefix = e.get("dag_prefix") or ""
            if not prefix.startswith("gs://"):
                continue
            bucket, _, path = prefix[5:].partition("/")
            for o in client.pages(f"{GCS}/b/{bucket}/o", "items", {"prefix": path.rstrip("/") + "/"}):
                if o["name"].endswith(".py"):
                    out.append({"environment": e["name"], "dag_id": o["name"].rsplit("/", 1)[-1][:-3],
                                "file": f"gs://{bucket}/{o['name']}"})
        return out

    return _scan({"environments": environments, "dags": dags}, depends={"dags": "environments"})


def scan_dataform(client: GcpClient, *, regions=("us-central1",), **_) -> dict:
    def repositories():
        return _per_region(regions, lambda r: [
            {"name": x["name"].rsplit("/", 1)[-1], "region": r}
            for x in client.pages(f"https://dataform.googleapis.com/v1beta1/projects/{client.project}"
                                  f"/locations/{r}/repositories", "repositories")])
    return _scan({"repositories": repositories})


def scan_dataflow(client: GcpClient, **_) -> dict:
    def jobs():
        return [{"id": j["id"], "name": j.get("name", j["id"]), "job_type": j.get("type"),
                 "region": j.get("location"), "state": j.get("currentState")}
                for j in client.pages(f"https://dataflow.googleapis.com/v1b3/projects/{client.project}"
                                      "/jobs:aggregated", "jobs")]
    return _scan({"jobs": jobs})


def scan_vertex(client: GcpClient, *, regions=("us-central1",), **_) -> dict:
    def collection(path: str, key: str):
        def fetch():
            return _per_region(regions, lambda r: [
                {"id": x["name"].rsplit("/", 1)[-1], "name": x.get("displayName") or x["name"], "region": r}
                for x in client.pages(f"https://{r}-aiplatform.googleapis.com/v1/projects/{client.project}"
                                      f"/locations/{r}/{path}", key)])
        return fetch
    return _scan({"models": collection("models", "models"),
                  "endpoints": collection("endpoints", "endpoints"),
                  "pipelines": collection("pipelineJobs", "pipelineJobs")})
