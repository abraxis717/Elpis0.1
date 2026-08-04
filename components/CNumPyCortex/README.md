# C.NumPyCortex

A telemetry-first stream processor for Elpis Canon.

## Data path

1. Linux sysfs, psutil, NVIDIA telemetry and llama-server health
   are sampled directly.

2. A fixed NumPy ring buffer carries the rolling context without
   text tokenization.

3. Nine selected channels across nine recent samples become a
   semantic 9x9 telemetry lattice.

4. Values are robustly normalized and quantized to tokens 0..9.
   Zero means missing data.

5. Four binary bit planes preserve a lossless binary representation
   of the token lattice.

6. Chronos-2 runs asynchronously at a slower cadence and produces
   a forecast-anomaly channel.

7. The latest Grid81 packet is written atomically for
   TRMFractalSpine.

## Important semantic rule

The 9x9 structure is not treated as Sudoku.

No row, column or 3x3 uniqueness constraint is imposed. The existing
Sudoku geometry is reused only as a fixed 81-cell transport and
recursion topology.

The recursive signature summarizes:

- all 81 normalized cells;
- mean, standard deviation and range of each 3x3 region;
- nine temporal means;
- nine channel means.

## Run

```bash
cnumpy-cortex --config config/cortex.toml
```
