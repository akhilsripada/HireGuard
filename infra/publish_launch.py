"""Upload a synthesized stack (template + code assets) for the Launch Stack button.

    python3 publish_launch.py <cdk.out dir> <stack name> <bucket> <region>

Reads <stack>.assets.json, zips directory assets the way CDK does, uploads every
file asset to the bucket named in the manifest (skipping keys already there, since
keys are content hashes), then copies the template to a fixed key,
hireguard.template.json, and prints the Launch Stack URL.
Uses the AWS CLI, so it runs with whatever profile you are signed in with.
"""
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import quote

TEMPLATE_KEY = "hireguard.template.json"
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def zip_dir(src: Path, dest: Path) -> None:
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(p for p in src.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(path.relative_to(src).as_posix(), FIXED_TIME)
            info.external_attr = (path.stat().st_mode & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, path.read_bytes())


def aws(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["aws", *args], check=check, capture_output=True, text=True)


def exists(bucket: str, key: str, region: str) -> bool:
    return aws("s3api", "head-object", "--bucket", bucket, "--key", key, "--region", region, check=False).returncode == 0


def upload(path: Path, bucket: str, key: str, region: str) -> None:
    aws("s3", "cp", str(path), f"s3://{bucket}/{key}", "--region", region, "--only-show-errors")


def launch_url(bucket: str, region: str) -> str:
    template_url = f"https://{bucket}.s3.{region}.amazonaws.com/{TEMPLATE_KEY}"
    return (f"https://console.aws.amazon.com/cloudformation/home?region={region}"
            f"#/stacks/create/review?templateURL={quote(template_url, safe='')}&stackName=HireGuard")


def main(out_dir: str, stack: str, bucket: str, region: str) -> None:
    out = Path(out_dir)
    manifest = json.loads((out / f"{stack}.assets.json").read_text())
    if manifest.get("dockerImages"):
        raise SystemExit("Docker image assets are not supported by the Launch Stack publisher.")

    template_key = None
    with tempfile.TemporaryDirectory() as tmp:
        for asset_id, asset in manifest.get("files", {}).items():
            src = out / asset["source"]["path"]
            packaging = asset["source"].get("packaging", "file")
            for dest in asset["destinations"].values():
                if dest["bucketName"] != bucket:
                    raise SystemExit(f"Asset {asset_id} points at bucket {dest['bucketName']}, expected {bucket}. "
                                     "Synthesize with -c launchBucket=" + bucket)
                key = dest["objectKey"]
                if src.name == f"{stack}.template.json":
                    template_key = key
                if exists(bucket, key, region):
                    print(f"  exists   {key}")
                    continue
                if packaging == "zip":
                    path = Path(tmp) / f"{asset_id}.zip"
                    zip_dir(src, path)
                else:
                    path = src
                upload(path, bucket, key, region)
                print(f"  uploaded {key}")

    # Fixed name so the button never changes; always overwritten with the latest template.
    upload(out / f"{stack}.template.json", bucket, TEMPLATE_KEY, region)
    print(f"  uploaded {TEMPLATE_KEY}" + (f" (same as {template_key})" if template_key else ""))
    print()
    print("Launch Stack URL:")
    print(launch_url(bucket, region))


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit(__doc__)
    os.environ.setdefault("AWS_PAGER", "")
    main(*sys.argv[1:])
