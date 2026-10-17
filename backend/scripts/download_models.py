"""Explicit one-time model provisioning. Never runs during API startup."""
from huggingface_hub import snapshot_download
MODELS = {
    'PekingU/rtdetr_v2_r50vd': '282494075698cab9faa1096ae26856890030c817',
    'google/owlv2-base-patch16-ensemble': 'cfd3195ba4ea9592eec887ded089f4c08eff231d',
    'facebook/dinov2-base': 'f9e44c814b77203eaa57a6bdbbd535f21ede1415',
    'Qwen/Qwen3-VL-4B-Instruct': 'ebb281ec70b05090aa6165b016eac8ec08e71b17',
}
if __name__ == '__main__':
    from pathlib import Path
    for repo, revision in MODELS.items():
        snapshot = Path(snapshot_download(repo_id=repo, revision=revision))
        # Runtime uses default main; freeze that local cache ref to this release.
        refs = snapshot.parent.parent / 'refs'
        refs.mkdir(exist_ok=True)
        (refs / 'main').write_text(revision)
        print(repo, revision)
