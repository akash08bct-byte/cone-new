import json
import sys
from contextlib import redirect_stdout
from pathlib import Path


def run(job_dir, output_dir):
    job = Path(job_dir)
    output = Path(output_dir)
    total = None
    completed = 0

    def report(stage, message):
        print(json.dumps({
            "stage": stage,
            "message": message,
            "completed": completed,
            "total": total,
        }), file=sys.__stdout__, flush=True)

    try:
        with redirect_stdout(sys.stderr):
            report("running", "Checking training images")
            from classes.training_images import load_thread_image, training_image_paths

            models = [
                ("top_white", "Top White", training_image_paths(job / "top_white")),
                ("top_uv", "Top UV", training_image_paths(job / "top_uv")),
            ]
            total = sum(len(paths) for _, _, paths in models)
            for _, _, paths in models:
                load_thread_image(paths[0])

            report("running", "Loading PyTorch")
            from classes.train import EffB7_Feature, GoodConeDataset, train_knn

            report("running", "Loading EfficientNet-B7 weights (downloads on first use)")
            feature_model = EffB7_Feature()
            for folder, label, paths in models:
                dataset = GoodConeDataset(job / folder, 224, image_paths=paths)
                offset = completed
                report("running", f"Extracting {label} image features")

                def update_progress(count):
                    nonlocal completed
                    completed = offset + count
                    if count == len(dataset):
                        report("running", f"Saving {label} model")
                    else:
                        report("running", f"Training {label} model")

                train_knn(
                    job / folder,
                    output / f"{folder}.joblib",
                    dataset=dataset,
                    on_progress=update_progress,
                    feature_model=feature_model,
                )
    except Exception as exc:
        message = str(exc)
        if isinstance(exc, OSError) and getattr(exc, "winerror", None) in (126, 1114):
            message = (
                "PyTorch could not load. Install or repair the Microsoft Visual C++ "
                f"x64 Redistributable and try again. {exc}"
            )
        report("failed", message)
        return 1

    report("completed", "Both Top White and Top UV models trained successfully.")
    return 0
