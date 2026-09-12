import os
import glob

def clean():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    targets = [
        os.path.join(base, "images", "sprites", "*.svg"),
        os.path.join(base, "front-end", "public", "images", "sprites", "*.svg"),
    ]
    for pattern in targets:
        for f in glob.glob(pattern):
            try:
                os.remove(f)
                print(f"Removed: {f}")
            except Exception as e:
                print(f"Failed removing {f}: {e}")

clean()

if __name__ == "__main__":
    clean()
