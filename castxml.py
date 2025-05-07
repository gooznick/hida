import argparse
import os
import subprocess
import tempfile
from pathlib import Path

def run_castxml_on_headers(input_dir: Path, output_dir: Path, castxml_path: str = "castxml"):
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    for header_file in input_dir.rglob("*.h"):
        output_file = output_dir / (header_file.stem + ".xml")
        print(f"Processing: {header_file} -> {output_file}")

        with tempfile.NamedTemporaryFile(suffix=".cpp", mode="w", delete=False) as tmp_cpp:
            tmp_cpp.write(f"#include \"{header_file}\"\n")
            tmp_cpp_path = tmp_cpp.name

        cmd = [
            castxml_path,
            "--castxml-output=1",
            "--std=c++17",
            "-o", str(output_file),
            tmp_cpp_path
        ]

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error processing {header_file}: {e}")
        finally:
            os.unlink(tmp_cpp_path)

def main():
    parser = argparse.ArgumentParser(description="Run castxml on all .h files in a directory.")
    parser.add_argument("input_dir", type=Path, nargs='?', default=Path("."), help="Directory containing .h files (default: current directory)")
    parser.add_argument("output_dir", type=Path, nargs='?', default=Path("castxml"), help="Directory to write .xml files (default: ./castxml)")
    parser.add_argument("--castxml", type=str, default="castxml", help="Path to castxml binary")

    args = parser.parse_args()
    run_castxml_on_headers(args.input_dir, args.output_dir, args.castxml)

if __name__ == "__main__":
    main()
