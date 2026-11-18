# Scenario Dataset

These inputs are synthetic. Scenario names do not guarantee Normal or Anomaly model results.

Select the matching device and a scenario's `input` folder in the application, then run a single test or batch.
The loader does not search subfolders. Do not select the root dataset folder as input.

The `99_mixed/input` folder combines all files. Files contain all configured tests except cases that deliberately omit a test or signal.

Empty signals never enter a model and appear as No Data in HTML reports. No models run when no eligible samples exist. NaN and Infinity are currently accepted by the loader and may invalidate model results.

`manifest.json` records original and loaded lengths, expected loader acceptance and scenario descriptions.
`verification.json` records checks with the real loader. It does not verify model inference or predicted labels.

| Device | Scenario | Input folder | Description |
|---|---|---|---|
| device1 | baseline | `device1/01_baseline/input` | Small finite noise around zero; synthetic reference, not a guaranteed Normal. |
| device1 | sine | `device1/02_sine/input` | Sine wave with small noise, at the expected length. |
| device1 | all_zero | `device1/03_all_zero/input` | Every sample is exactly zero, at the expected length. |
| device1 | empty_signal | `device1/04_empty_signal/input` | signal1 exists but its data array is empty; retained for No Data reporting and never evaluated by a model. |
| device1 | single_sample | `device1/05_single_sample/input` | One nonzero sample; remaining samples are padded with zeros. |
| device1 | short_signal | `device1/06_short_signal/input` | Half the expected length; loader pads the missing tail with zeros. |
| device1 | one_sample_short | `device1/07_one_sample_short/input` | Expected length minus one, to exercise the length boundary. |
| device1 | one_sample_long | `device1/08_one_sample_long/input` | Expected length plus one; loader keeps the extra sample. |
| device1 | long_signal | `device1/09_long_signal/input` | Expected length plus 1000; loader does not truncate it. |
| device1 | short_all_zero | `device1/10_short_all_zero/input` | Half-length all-zero signal; both zero data and length mismatch. |
| device1 | constant_nonzero | `device1/11_constant_nonzero/input` | Constant positive signal without variation. |
| device1 | constant_negative | `device1/12_constant_negative/input` | Constant negative signal without variation. |
| device1 | near_zero | `device1/13_near_zero/input` | Tiny nonzero values; distinguishes near-zero from exactly all-zero. |
| device1 | single_spike | `device1/14_single_spike/input` | One large spike in the middle of the signal. |
| device1 | negative_spike | `device1/15_negative_spike/input` | One large negative spike in the middle of the signal. |
| device1 | spike_each_section | `device1/16_spike_each_section/input` | A large spike at the midpoint of every configured section. |
| device1 | zero_section | `device1/17_zero_section/input` | A complete configured section is zero inside a nonzero signal. |
| device1 | zero_tail | `device1/18_zero_tail/input` | Final quarter is zero while the stored length remains correct. |
| device1 | step_change | `device1/19_step_change/input` | A sudden level shift halfway through the signal. |
| device1 | drift | `device1/20_drift/input` | Gradually increasing offset across the whole signal. |
| device1 | high_noise | `device1/21_high_noise/input` | Large-amplitude random noise. |
| device1 | nan_value | `device1/22_nan_value/input` | One NaN sample; current loader accepts it without finite-value validation. |
| device1 | positive_infinity | `device1/23_positive_infinity/input` | One positive infinity; current loader accepts it. |
| device1 | negative_infinity | `device1/24_negative_infinity/input` | One negative infinity; current loader accepts it. |
| device1 | missing_tests | `device1/25_missing_tests/input` | Device exists but testResult is empty; loader skips the file. |
| device1 | unknown_test | `device1/26_unknown_test/input` | Only an unconfigured test exists; loader skips the file. |
| device1 | missing_signals | `device1/27_missing_signals/input` | Configured tests exist but have no signals; loader skips the file. |
| device1 | wrong_signal_name | `device1/28_wrong_signal_name/input` | Only signal2 exists; loader skips the file. |
| device1 | uppercase_signal | `device1/29_uppercase_signal/input` | Signal1 spelling is accepted by the current loader. |
| device1 | wrong_device | `device1/30_wrong_device/input` | Device series does not match the selected device; loader skips it. |
| device1 | empty_root | `device1/31_empty_root/input` | Valid compressed protobuf with no device items; loader skips it. |
| device1 | invalid_gzip | `device1/32_invalid_gzip/input` | File is not gzip; loader logs a decoding error and skips it. |
| device1 | invalid_protobuf | `device1/33_invalid_protobuf/input` | Gzip is valid but its contents are invalid protobuf; loader logs an error and skips it. |
| device1 | zero_byte_file | `device1/34_zero_byte_file/input` | File has zero bytes; loader skips it. |
| device1 | ignored_extension | `device1/35_ignored_extension/input` | Valid gzip/protobuf stored as .dat.gz; directory loader ignores it. |
| device1 | empty_folder | `device1/36_empty_folder/input` | No .dat files exist; no models run and the dashboard has no serial rows. |
| device1 | missing_test1 | `device1/37_missing_test1/input` | Only test1 is absent; other configured tests remain available. |
| device1 | missing_test2 | `device1/38_missing_test2/input` | Only test2 is absent; other configured tests remain available. |
| device1 | mixed | `device1/99_mixed/input` | All file-based cases together, including valid, missing, nonfinite and corrupt data. |
