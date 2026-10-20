# EVT3 boundary fix under validation

The same 432,230,512-byte RAW payload decoded to different CD counts depending
on the read path and chunk size. Sequential reads with 1,048,576-byte chunks
decoded 174,832,271 events with three partial-vector and three invalid-base
warnings. Changing to 1,048,578-byte chunks decoded 174,832,287 events without
protocol warnings. Both runs consumed every payload byte and had no backwards
timestamps or out-of-bounds decoded events. This establishes chunk-dependent
decoding. It does not prove lossless camera acquisition.

Inspection of the OpenEB decoder found that its pending-event completion path
ignores the return value from decoding the temporary buffer and clears it.
An OTHERS marker with no continuation payload can need less than its maximum
lookahead. That lookahead may contain the start of another multiword item.
Clearing the temporary buffer then discards the unfinished item's raw words.

The guarded patch preserves that unfinished suffix and continues assembling it.
It retains robust validation and changes no recorded RAW bytes. A backup of the
original header is created alongside it. Keep the patch recipe in this project
for reproducibility and future container builds.

Run from iteration_3 with the Python 3.12 environment active:

```bash
# Optional baseline: the 8-byte fixture case is expected to fail before patching.
bash scripts/validate_raw.sh

python scripts/patch_openeb_evt3_boundary.py "$HOME/src/openeb-5.2.0"
bash scripts/build_openeb_python.sh

bash scripts/validate_raw.sh --recording \
    "data/recordings/buffer-test-20261020T012235.400912Z-41835d81/events.raw"
```

The last command must pass the synthetic cases, consume the real payload, report
zero protocol violations, and produce identical decoded-event SHA-256 values
for both real-file chunk sizes. It hashes a canonical little-endian x/y/p/t
representation, independent of callback boundaries and structure padding.

The validation launcher selects the plugin from the project build and resolves
its dependencies from the same build. The older installed C++ viewer and
metavision_file_info under ~/opt/openeb-5.2.0 remain unpatched until separately
rebuilt. Do not use their old warning counts to judge the new decoder.

This patch has not been native-tested in the assistant's environment, which has
no OpenEB libraries or camera. The on-device regression is required. If the patch
script reports an unrecognized layout, it leaves the source unchanged.

Source examined: https://github.com/prophesee-ai/openeb/blob/main/hal/cpp/include/metavision/hal/decoders/evt3/evt3_decoder.h
