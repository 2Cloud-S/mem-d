# Semantic-label trie inspection — 2026-11-15

This is a read-only inspection of the Phase 3B mechanism and cached pinned
tokenizers, not a new model experiment or a correction of historical scores.
The actual historical assistant boundary ends with
`<|im_start|>assistant\n` in all three native templates. Concatenating each label
to that rendered prompt preserves the original prompt IDs and gives the same
suffix IDs used by `harness.forced_choice.label_trie`.

| Attempted checkpoint / revision | Label | Token IDs | Decoded pieces |
| --- | --- | --- | --- |
| Qwen2.5-0.5B / `7ae557604adf67be50417f59c2c2f167def9a775` | proceed | 776, 4635 | pro · ceed |
| same | do_not_proceed | 2982, 7913, 2540, 4635 | do · _not · _pro · ceed |
| same | insufficient_evidence | 1330, 26683, 2204, 27480 | ins · ufficient · _e · vidence |
| SmolLM2-360M / `a10cc1512eabd3dde888204e902eca88bddb4951` | proceed | 1228, 3196 | pro · ceed |
| same | do_not_proceed | 4326, 79, 1766, 79, 1228, 3196 | do · _ · not · _ · pro · ceed |
| same | insufficient_evidence | 927, 101, 3574, 79, 42477 | ins · u · fficient · _ · evidence |
| Qwen2.5-1.5B / `989aa7980e4cf806f80c7fef2b1adb7bc71aa306` | proceed | 776, 4635 | pro · ceed |
| same | do_not_proceed | 2982, 7913, 2540, 4635 | do · _not · _pro · ceed |
| same | insufficient_evidence | 1330, 26683, 2204, 27480 | ins · ufficient · _e · vidence |

Every pair of labels has a zero-length common token prefix in each tokenizer:
the **first generated token is the only three-way branch**. After that choice,
only one label remains reachable and each continuation token is forced, including
EOS (Qwen ID 151645; SmolLM2 ID 2). This is greedy next-token selection among
`pro`/`do`/`ins`, rather than a comparison of complete semantic-label sequence
probabilities. No beam search or full-sequence likelihood comparison was used.

Reachability proves that no label was structurally forbidden. It does not show
that different token strings have equal prior probability, that their first
pieces fairly represent complete answers, or that the model correctly binds
evidence to labels. Longer suffix probabilities cannot reverse an initial
choice in this trie. Neither this mechanism nor the observed label distributions
prove that token bias caused the calibration failures: capability, prompt
sensitivity, label semantics and greedy decoding remain competing explanations.

The available Qwen1.5B tokenizer encodes neutral codes A/B/C as IDs 32/33/34;
Qwen0.5B uses the same IDs and SmolLM2 uses 49/50/51. They are single tokens at
the inspected historical boundary. The new diagnostic additionally verifies
**every actual new rendered prompt**: encoding `prompt + code` must equal
`encode(prompt) + [code_id]` for all three codes, and decoding must round-trip.
All three code IDs are equally permitted at the decision step, then only EOS.
Equal token length does not itself remove code priors or mapping-binding errors.
All six code/label mappings therefore need evaluation, without selecting the best.

Machine-readable token IDs, boundary hashes, unique-prefix lengths and revision
provenance accompany this inspection in the new diagnostic artifact directory.
