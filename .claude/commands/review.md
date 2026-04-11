# Review

Review changed RumbleOS code for correctness, signal-processing accuracy, and pipeline safety.

Checklist:
1. **Critical parameters** — are TARGET_SR, N_FFT, HOP_LENGTH, N_COMPONENTS, PROP_DECREASE,
   ELEPHANT_THRESHOLD unchanged?
2. **Stage contracts** — does every `process()` method pass through all existing `msg` keys?
   (use `{**msg, ...}` pattern — never drop keys silently)
3. **Error forwarding** — does `'error' in msg` short-circuit correctly without losing context?
4. **Queue safety** — no blocking puts in the hot path; SenseCAP uses `put_nowait`
5. **NumPy correctness** — shapes, axis arguments, float32 vs float64, no silent broadcasting bugs
6. **Frequency bin math** — verify `librosa.fft_frequencies(sr=4000, n_fft=2048)` gives
   expected resolution (~1.95 Hz/bin) wherever freqs are used
7. **ISTFT reconstruction** — `hop_length` and `win_length` match STFT parameters
8. **Security** — no shell injection (subprocess calls), no hardcoded secrets
9. **Tests** — does the synthetic 18 Hz smoke test still pass?

Summarize: what's correct, what needs fixing, and why.
