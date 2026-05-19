import os

for root, dirs, files in os.walk("app"):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if "CaseStatus.COMPLETED" in line:
                        print(f"{path} Line {i+1}: {line.strip()}")
