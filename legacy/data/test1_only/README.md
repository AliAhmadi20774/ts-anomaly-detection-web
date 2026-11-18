# One Present Test, One Missing Test

Select `data/test1_only/input` in the application with device `device1`.
Serial: `SC_TEST1_ONLY`.

- `test1`: present with 22,528 finite synthetic samples (small noise around zero).
- `test2`: completely absent from the file.

Use batch mode to exercise both cases. The loader skips an absent test during inference; the batch HTML report includes a Missing Test tab and marks the serial Incomplete unless the available test has an anomaly.
The synthetic signal does not guarantee a Normal or Anomaly prediction.
