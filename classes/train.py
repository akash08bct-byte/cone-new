
import os
import torch
import joblib
import numpy as np

from pathlib import Path
from torchvision import models, transforms
from torch.utils.data import Dataset, DataLoader
from sklearn.neighbors import NearestNeighbors
from tqdm import tqdm
from classes.training_images import load_thread_image, training_image_paths

# ================= EFFICIENTNET B7 =================

class EffB7_Feature(torch.nn.Module):

    def __init__(self):
        super().__init__()

        model = models.efficientnet_b7(
            weights=models.EfficientNet_B7_Weights.IMAGENET1K_V1
        )

        self.backbone = model.features
        self.pool = torch.nn.AdaptiveAvgPool2d((1, 1))

        self.eval()

        for parameter in self.parameters():
            parameter.requires_grad = False

    @torch.no_grad()
    def forward(self, x):

        x = self.backbone(x)
        x = self.pool(x)
        x = torch.flatten(x, 1)

        return x


# ================= DATASET =================

class GoodConeDataset(Dataset):

    def __init__(self, image_dir, img_size, *, image_paths=None):
        self.image_paths = training_image_paths(image_dir) if image_paths is None else image_paths

        self.transform = transforms.Compose([
            transforms.Resize((img_size, img_size)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, index):

        return self.transform(load_thread_image(self.image_paths[index]))


# ================= TRAINING =================

def train_knn(
    GOOD_IMAGE_DIR, OUTPUT_PATH, USE_CPU=False, IMG_SIZE=224,
    BATCH_SIZE=8, K_NEIGHBORS=5, *, dataset=None, on_progress=None, feature_model=None
):

    USE_CUDA = not USE_CPU and torch.cuda.is_available()
    DEVICE = torch.device("cuda" if USE_CUDA else "cpu")
    print("Loading GOOD cone dataset...")

    if dataset is None:
        dataset = GoodConeDataset(GOOD_IMAGE_DIR, IMG_SIZE)

    print("Total GOOD images:", len(dataset))

    loader = DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0,
        pin_memory=USE_CUDA
    )

    if feature_model is None:
        print("Loading EfficientNet-B7...")
        feature_model = EffB7_Feature()
    model = feature_model.to(DEVICE)

    if USE_CUDA:
        model = model.to(
            memory_format=torch.channels_last
        )

    model.eval()

    all_embeddings = []
    completed = 0

    print("Extracting features...")

    with torch.no_grad():

        for images in tqdm(loader):

            if USE_CUDA:
                images = images.to(
                    DEVICE,
                    non_blocking=True
                ).to(memory_format=torch.channels_last)

            embeddings = model(images)

            embeddings = embeddings.float().cpu().numpy()

            all_embeddings.append(embeddings)
            completed += len(embeddings)
            if on_progress is not None:
                on_progress(completed)

    embeddings = np.concatenate(
        all_embeddings,
        axis=0
    )

    print("Embedding shape:", embeddings.shape)

    # ================= NORMALIZATION =================

    embed_mean = embeddings.mean(axis=0)

    embed_std = embeddings.std(axis=0)

    # Prevent division by zero
    embed_std[embed_std < 1e-8] = 1.0

    embeddings_z = (
        embeddings - embed_mean
    ) / embed_std

    # ================= KNN =================

    n_neighbors = min(
        K_NEIGHBORS,
        len(embeddings_z)
    )

    print("Training kNN...")
    print("Neighbors:", n_neighbors)

    knn = NearestNeighbors(
        n_neighbors=n_neighbors,
        algorithm="auto",
        metric="euclidean",
        n_jobs=-1
    )

    knn.fit(embeddings_z)

    # ================= SAVE ARTIFACT =================

    artifact = {
        "img_size": IMG_SIZE,
        "knn": knn,
        "embed_mean": embed_mean.astype(np.float32),
        "embed_std": embed_std.astype(np.float32),
        "n_neighbors": n_neighbors,
        "feature_dim": embeddings.shape[1]
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    joblib.dump(
        artifact,
        OUTPUT_PATH,
        compress=3
    )

    print("\nTraining completed!")
    print("Artifact saved:", OUTPUT_PATH)
    print("Total training images:", len(embeddings))
    print("Feature dimension:", embeddings.shape[1])


if __name__ == "__main__":
    GOOD_IMAGE_DIR = Path("ConeI_Data/training_images/gg_hh_jj/top_uv")
    OUTPUT_PATH = Path("ConeI_Data/models/b7_knn_artifact.joblib")

    train_knn(GOOD_IMAGE_DIR,OUTPUT_PATH)
