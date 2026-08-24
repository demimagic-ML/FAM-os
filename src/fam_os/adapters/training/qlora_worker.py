"""Network-isolated QLoRA worker for one already-approved local job."""

from __future__ import annotations

import argparse
import hashlib
from importlib import import_module
import json
import os
import random
import signal
import sys
import time
import traceback
from pathlib import Path
from types import FrameType, ModuleType
from typing import Mapping, cast


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    arguments = parser.parse_args(argv)
    config = _load_config(arguments.config)
    output = Path(_text(config, "output_directory"))
    output.mkdir(parents=True, exist_ok=True)
    started = time.time()
    _install_signal_handler()
    try:
        result = _train(config, output)
    except BaseException as error:
        failure = {
            "adapter_bytes": 0,
            "adapter_config_sha256": None,
            "adapter_sha256": None,
            "base_weights_frozen": False,
            "duration_seconds": time.time() - started,
            "error_type": type(error).__name__,
            "metrics_sha256": hashlib.sha256(b"{}").hexdigest(),
            "reason_code": "training.worker_failed",
            "status": "failed",
            "unexpected_trainable_parameters": [],
            **_safe_error(error),
        }
        _write_json(output / "worker-result.json", failure)
        print(f"training worker failed: {type(error).__name__}", file=sys.stderr)
        return 1
    result["duration_seconds"] = time.time() - started
    _write_json(output / "worker-result.json", result)
    return 0


def _train(config: Mapping[str, object], output: Path) -> dict[str, object]:
    torch = import_module("torch")
    Dataset = getattr(import_module("datasets"), "Dataset")
    peft_module = import_module("peft")
    LoraConfig = getattr(peft_module, "LoraConfig")
    prepare_model_for_kbit_training = getattr(
        peft_module, "prepare_model_for_kbit_training",
    )
    transformers = import_module("transformers")
    AutoModelForCausalLM = getattr(transformers, "AutoModelForCausalLM")
    AutoTokenizer = getattr(transformers, "AutoTokenizer")
    BitsAndBytesConfig = getattr(transformers, "BitsAndBytesConfig")
    trl = import_module("trl")
    SFTConfig = getattr(trl, "SFTConfig")
    SFTTrainer = getattr(trl, "SFTTrainer")

    _seed(_integer(config, "seed"), torch)
    train_path = Path(_text(config, "train_dataset"))
    validation_path = Path(_text(config, "validation_dataset"))
    if "held" in train_path.name.casefold() or "held" in validation_path.name.casefold():
        raise ValueError("held-out content cannot enter the training worker")
    _require_sha256(train_path, _text(config, "train_sha256"))
    _require_sha256(validation_path, _text(config, "validation_sha256"))
    model_path = Path(_text(config, "base_model_directory"))
    if _directory_manifest_sha256(model_path) != _text(config, "base_model_sha256"):
        raise ValueError("base model files do not match the approved manifest")
    train_records = _records(train_path)
    validation_records = _records(validation_path)
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=(
            torch.bfloat16 if config["compute_dtype"] == "bfloat16"
            else torch.float16
        ),
    )
    tokenizer = AutoTokenizer.from_pretrained(
        model_path, local_files_only=True, trust_remote_code=False,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        model_path, local_files_only=True, trust_remote_code=False,
        quantization_config=quantization, device_map={"": 0},
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=True,
    )
    targets = cast(list[str], config["target_modules"])
    target_modules = "all-linear" if targets == ["all-linear"] else targets
    peft = LoraConfig(
        r=_integer(config, "rank"), lora_alpha=_integer(config, "alpha"),
        lora_dropout=_number(config, "dropout"),
        target_modules=target_modules, bias="none", task_type="CAUSAL_LM",
    )
    training = SFTConfig(
        output_dir=str(output / "trainer"),
        eos_token=tokenizer.eos_token,
        max_length=_integer(config, "maximum_sequence_tokens"),
        num_train_epochs=_number(config, "epochs"),
        max_steps=_integer(config, "maximum_steps"),
        per_device_train_batch_size=_integer(config, "per_device_batch_size"),
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=_integer(
            config, "gradient_accumulation_steps",
        ),
        gradient_checkpointing=True,
        learning_rate=_number(config, "learning_rate"),
        bf16=config["compute_dtype"] == "bfloat16",
        fp16=config["compute_dtype"] == "float16",
        completion_only_loss=True,
        eval_strategy="steps", eval_steps=_integer(config, "maximum_steps"),
        save_strategy="no", logging_steps=1, report_to="none",
        seed=_integer(config, "seed"), data_seed=_integer(config, "seed"),
    )
    trainer = SFTTrainer(
        model=model, args=training,
        train_dataset=Dataset.from_list(train_records),
        eval_dataset=Dataset.from_list(validation_records),
        peft_config=peft, processing_class=tokenizer,
    )
    unexpected = tuple(sorted(
        name for name, parameter in trainer.model.named_parameters()
        if parameter.requires_grad and "lora_" not in name
    ))
    if unexpected:
        raise RuntimeError("unapproved model parameters are trainable")
    outcome = trainer.train()
    adapter = output / "adapter"
    trainer.model.save_pretrained(adapter, safe_serialization=True)
    tokenizer.save_pretrained(adapter)
    metrics = {
        "eval": trainer.evaluate(),
        "log_history": trainer.state.log_history,
        "train": outcome.metrics,
    }
    metrics_path = output / "metrics.json"
    _write_json(metrics_path, metrics)
    adapter_config = adapter / "adapter_config.json"
    manifest = _directory_manifest_sha256(adapter)
    return {
        "adapter_bytes": _directory_bytes(adapter),
        "adapter_config_sha256": _file_sha256(adapter_config),
        "adapter_sha256": manifest,
        "base_weights_frozen": True,
        "metrics_sha256": _file_sha256(metrics_path),
        "reason_code": "training.completed",
        "status": "completed",
        "unexpected_trainable_parameters": list(unexpected),
    }


def _load_config(path: Path) -> dict[str, object]:
    document = json.loads(path.read_text("utf-8"))
    required = {
        "alpha", "base_model_directory", "base_model_sha256", "compute_dtype",
        "dropout", "epochs", "gradient_accumulation_steps", "learning_rate",
        "maximum_sequence_tokens", "maximum_steps", "output_directory",
        "per_device_batch_size", "rank", "record_format", "seed", "target_modules",
        "train_dataset", "train_sha256", "validation_dataset", "validation_sha256",
    }
    if not isinstance(document, dict) or set(document) != required:
        raise ValueError("training worker config fields are invalid")
    if document["compute_dtype"] not in {"bfloat16", "float16"}:
        raise ValueError("training compute dtype is invalid")
    if document["record_format"] != "qwen_chat_prompt_completion_v1":
        raise ValueError("training record format is invalid")
    targets = document["target_modules"]
    if not isinstance(targets, list) or not targets or any(
        not isinstance(item, str) or not item for item in targets
    ):
        raise ValueError("training target modules are invalid")
    return cast(dict[str, object], document)


def _records(path: Path) -> list[dict[str, object]]:
    values: list[dict[str, object]] = []
    for line in path.read_text("utf-8").splitlines():
        document = json.loads(line)
        if not isinstance(document, dict) or not isinstance(
            document.get("input"), str,
        ) or not isinstance(document.get("completion"), str):
            raise ValueError("training dataset record is invalid")
        values.append({
            "prompt": [{"role": "user", "content": document["input"]}],
            "completion": [
                {"role": "assistant", "content": document["completion"]},
            ],
            "chat_template_kwargs": {"enable_thinking": False},
        })
    if not values:
        raise ValueError("training dataset partition is empty")
    return values


def _seed(seed: int, torch: ModuleType) -> None:
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def _install_signal_handler() -> None:
    def stop(_signum: int, _frame: FrameType | None) -> None:
        raise InterruptedError("training worker was stopped")

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)


def _directory_manifest_sha256(path: Path) -> str:
    if not path.is_dir() or path.is_symlink():
        raise ValueError("training artifact directory is invalid")
    records: list[tuple[str, str]] = []
    for item in sorted(path.rglob("*")):
        if item.is_symlink():
            raise ValueError("training artifact directories cannot contain symlinks")
        if item.is_file():
            records.append((item.relative_to(path).as_posix(), _file_sha256(item)))
    if not records:
        raise ValueError("training artifact directory is empty")
    return hashlib.sha256(json.dumps(
        records, separators=(",", ":"),
    ).encode()).hexdigest()


def _directory_bytes(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _require_sha256(path: Path, expected: str) -> None:
    if _file_sha256(path) != expected:
        raise ValueError("training input digest does not match")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, document: Mapping[str, object]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(document, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _safe_error(error: BaseException) -> dict[str, object]:
    frames: list[dict[str, object]] = []
    for frame in traceback.extract_tb(error.__traceback__)[-12:]:
        frames.append({
            "file": _safe_path(frame.filename),
            "function": frame.name[:128],
            "line": frame.lineno,
        })
    document: dict[str, object] = {
        "error_frames": frames,
        "error_type": type(error).__name__,
    }
    if isinstance(error, OSError):
        document["error_errno"] = error.errno
        if error.filename is not None:
            document["error_filename"] = _safe_path(str(error.filename))
    return document


def _safe_path(value: str) -> str:
    path = Path(value)
    allowed = ("/environment", "/input", "/model", "/output", "/tmp", "/usr")
    normalized = str(path)
    if any(normalized == root or normalized.startswith(root + "/") for root in allowed):
        return normalized[:512]
    return path.name[:128]


def _text(document: Mapping[str, object], name: str) -> str:
    value = document.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be text")
    return value


def _integer(document: Mapping[str, object], name: str) -> int:
    value = document.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    return value


def _number(document: Mapping[str, object], name: str) -> float:
    value = document.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    return float(value)


if __name__ == "__main__":
    raise SystemExit(main())
