import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPLOYMENT_DIR = ROOT / "deployment"
DOCKERFILE = ROOT / "Dockerfile"

REQUIRED_FIELDS = {
    "environment",
    "base_model",
    "adapter_uri",
    "dataset_version",
    "rag_index_dir",
}

ADAPTER_PATTERN = re.compile(r"^stefanind/qwen-stefan-lora-(v\d{3})$")
VERSION_PATTERN = re.compile(r"^v\d{3}$")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def read_docker_env(name: str) -> str:
    prefix = f"ENV {name}="

    for line in DOCKERFILE.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()

    raise ValueError(f"Missing {prefix} in Dockerfile")


def validate_manifest(path: Path, expected_environment: str) -> dict:
    manifest = load_json(path)
    missing = sorted(REQUIRED_FIELDS - manifest.keys())

    if missing:
        raise ValueError(f"{path}: missing required fields: {', '.join(missing)}")

    environment = manifest["environment"]
    if environment != expected_environment:
        raise ValueError(
            f"{path}: expected environment {expected_environment!r}, got {environment!r}"
        )

    adapter_uri = manifest["adapter_uri"]
    adapter_match = ADAPTER_PATTERN.fullmatch(adapter_uri)
    if not adapter_match:
        raise ValueError(
            f"{path}: adapter_uri must look like stefanind/qwen-stefan-lora-v001"
        )

    adapter_version = adapter_match.group(1)
    dataset_version = manifest["dataset_version"]
    if not VERSION_PATTERN.fullmatch(dataset_version):
        raise ValueError(f"{path}: dataset_version must look like v001")

    if adapter_version != dataset_version:
        raise ValueError(
            f"{path}: adapter version {adapter_version} must match dataset_version {dataset_version}"
        )

    dataset_manifest = ROOT / "data" / dataset_version / "dataset_manifest.json"
    if not dataset_manifest.exists():
        raise ValueError(f"{path}: missing dataset manifest {dataset_manifest}")

    rag_index_dir = ROOT / manifest["rag_index_dir"]
    if not rag_index_dir.is_dir():
        raise ValueError(f"{path}: rag_index_dir does not exist: {rag_index_dir}")

    rag_manifest = rag_index_dir / "manifest.json"
    if not rag_manifest.exists():
        raise ValueError(f"{path}: missing RAG manifest {rag_manifest}")

    return manifest


def main() -> None:
    production = validate_manifest(
        DEPLOYMENT_DIR / "production_model.json",
        "production",
    )

    validate_manifest(
        DEPLOYMENT_DIR / "staging_model.json",
        "staging",
    )

    docker_model = read_docker_env("MODEL_NAME")
    docker_adapter = read_docker_env("ADAPTER_DIR")

    if docker_model != production["base_model"]:
        raise ValueError(
            "Dockerfile MODEL_NAME must match production_model.json base_model "
            f"({docker_model!r} != {production['base_model']!r})"
        )

    if docker_adapter != production["adapter_uri"]:
        raise ValueError(
            "Dockerfile ADAPTER_DIR must match production_model.json adapter_uri "
            f"({docker_adapter!r} != {production['adapter_uri']!r})"
        )

    print("Deployment manifests valid OK")


if __name__ == "__main__":
    main()
