# Plan

Produce a concrete implementation plan for the requested RumbleOS change.

1. **Understand the goal** — what stage(s) of the pipeline are affected?
2. **Identify files** — which agents / helpers need to change?
3. **Check critical parameters** — do any of the locked constants need to stay fixed?
   (TARGET_SR, N_FFT, HOP_LENGTH, N_COMPONENTS, PROP_DECREASE, ELEPHANT_THRESHOLD)
4. **Outline steps** — numbered, in the order they should be implemented
5. **Note risks** — signal-processing correctness, queue back-pressure, RPi memory limits
6. **Propose a smoke test** — synthetic signal or small CSV subset to verify the change

Keep the plan short and actionable. One decision per step.
