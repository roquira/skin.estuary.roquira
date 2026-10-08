#!/usr/bin/env bash
#
# Build the installable add-on zip from HEAD into OUTPUT_DIRECTORY and print
# its path. With a tag argument, require the tag to match the add-on version.

set -euo pipefail

if (( $# < 1 || $# > 2 )); then
  echo "Usage: $0 OUTPUT_DIRECTORY [TAG]" >&2
  exit 2
fi

output_dir=$1
tag=${2:-}
repo_root=$(git rev-parse --show-toplevel)

read -r addon_id version < <(
  python3 -c 'import sys, xml.etree.ElementTree as ET
addon = ET.parse(sys.argv[1]).getroot()
print(addon.get("id"), addon.get("version"))' "$repo_root/addon.xml"
)

if [[ -n "$tag" && "$tag" != "$version" ]]; then
  echo "Tag $tag does not match add-on version $version." >&2
  exit 1
fi

mkdir -p "$output_dir"
zip="$output_dir/$addon_id-$version.zip"
git -C "$repo_root" archive --format=zip --prefix="$addon_id/" -o "$(realpath "$zip")" HEAD
echo "$zip"
