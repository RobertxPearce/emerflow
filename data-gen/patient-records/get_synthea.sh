#!/usr/bin/env bash
# Downloads Synthea (~180 MB, from its official GitHub releases) and generates patients.
# Needs Java 17+. Output: patient-records/synthea/output/fhir/*.json
#
#   ./get_synthea.sh            # 50 patients, seed 42
#   ./get_synthea.sh 200 7      # 200 patients, seed 7
#
# Then build facility copies + answer key from them:
#   python3 generate.py --from-synthea synthea/output/fhir
set -euo pipefail
cd "$(dirname "$0")"

PATIENTS="${1:-50}"
SEED="${2:-42}"
JAR="synthea/synthea-with-dependencies.jar"
URL="https://github.com/synthetichealth/synthea/releases/download/master-branch-latest/synthea-with-dependencies.jar"

command -v java >/dev/null || { echo "Java 17+ is required (java not found)." >&2; exit 1; }
mkdir -p synthea
if [ ! -f "$JAR" ]; then
  echo "Downloading Synthea from $URL"
  curl -fL -o "$JAR" "$URL"
fi

cd synthea
rm -rf output/fhir
# Only patient bundles are needed, not the hospital/practitioner directories.
java -jar synthea-with-dependencies.jar -p "$PATIENTS" -s "$SEED" \
  --exporter.fhir.export true \
  --exporter.hospital.fhir.export false \
  --exporter.practitioner.fhir.export false \
  Maryland Baltimore
echo "Synthea patients written to $(pwd)/output/fhir"
