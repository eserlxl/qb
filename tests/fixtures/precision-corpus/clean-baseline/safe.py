import subprocess


def list_dir(path):
    return subprocess.run(["ls", "-la", path], shell=False, check=False)
